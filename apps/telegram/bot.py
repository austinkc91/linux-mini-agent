"""Telegram bot for remote agent control.

Allows users to:
- Send text prompts to the Listen job server
- Check job status
- Send images/files that get saved and referenced in prompts
- Take screenshots of the agent's desktop
- Run steer/drive commands directly
"""

import asyncio
import json
import logging
import os
import subprocess
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

logger = logging.getLogger(__name__)

# --- Chat history for conversational context ---
CHAT_HISTORY_FILE = Path(__file__).parent.parent / "listen" / "jobs" / "chat_history.jsonl"
CHAT_HISTORY_CONTEXT_LINES = 20  # How many recent messages to inject as context
CHAT_HISTORY_MAX_LINES = 50  # Max lines kept on disk (rotated on write)


def _log_chat(role: str, text: str):
    """Append a message to the chat history log, rotating if over max."""
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,  # "user" or "bot"
            "text": text[:2000],  # Cap stored length
        }
        new_line = json.dumps(entry)

        # Read existing, append, and rotate if needed
        lines = []
        if CHAT_HISTORY_FILE.exists():
            lines = CHAT_HISTORY_FILE.read_text().strip().splitlines()
        lines.append(new_line)

        # Keep only the last N lines
        if len(lines) > CHAT_HISTORY_MAX_LINES:
            lines = lines[-CHAT_HISTORY_MAX_LINES:]

        # Atomic write via temp file
        tmp = CHAT_HISTORY_FILE.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n")
        tmp.rename(CHAT_HISTORY_FILE)
    except Exception as e:
        logger.error(f"Failed to log chat: {e}")


def _get_recent_chat(n: int = CHAT_HISTORY_CONTEXT_LINES) -> str:
    """Return the last N chat messages formatted as context."""
    if not CHAT_HISTORY_FILE.exists():
        return ""
    try:
        lines = CHAT_HISTORY_FILE.read_text().strip().splitlines()
        recent = lines[-n:] if len(lines) > n else lines
        formatted = []
        for line in recent:
            entry = json.loads(line)
            who = "User" if entry["role"] == "user" else "Bot"
            formatted.append(f"[{who}]: {entry['text']}")
        return "\n".join(formatted)
    except Exception as e:
        logger.error(f"Failed to read chat history: {e}")
        return ""


def _build_prompt_with_context(prompt: str) -> str:
    """Wrap the user's prompt with recent chat history for conversational context."""
    history = _get_recent_chat()
    if not history:
        return prompt
    return (
        f"Recent Telegram chat history (for context — the user may reference earlier messages):\n"
        f"---\n{history}\n---\n\n"
        f"Current request: {prompt}"
    )

MAX_TG_MSG = 4000  # Conservative limit (Telegram allows 4096)


def _split_message(text: str, limit: int = MAX_TG_MSG) -> list[str]:
    """Split a long message into chunks that fit Telegram's character limit.
    Splits on double-newlines first, then single newlines, then hard-cuts."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split at a double newline
        cut = text.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip("\n")
    return chunks

LISTEN_URL = os.environ.get("LISTEN_URL", "http://localhost:7600")
REPO_ROOT = Path(__file__).parent.parent.parent
JOBS_DIR = REPO_ROOT / "apps" / "listen" / "jobs"
DELIVERED_FILE = JOBS_DIR / ".delivered"
UPLOADS_DIR = Path(tempfile.gettempdir()) / "telegram-uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


def _load_delivered() -> set[str]:
    """Load set of job IDs that have already been delivered to Telegram."""
    if DELIVERED_FILE.exists():
        return set(DELIVERED_FILE.read_text().strip().splitlines())
    return set()


def _mark_delivered(job_id: str):
    """Mark a job as delivered so it won't be re-sent on restart."""
    with open(DELIVERED_FILE, "a") as f:
        f.write(job_id + "\n")


def _save_chat_id(chat_id: int):
    """Persist the chat ID so recovery works after restart."""
    chat_id_file = JOBS_DIR / ".chat_id"
    chat_id_file.write_text(str(chat_id))

# Authorized user IDs (set via TELEGRAM_ALLOWED_USERS env var, comma-separated)
ALLOWED_USERS: set[int] = set()
_allowed = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
if _allowed:
    ALLOWED_USERS = {int(uid.strip()) for uid in _allowed.split(",") if uid.strip()}


def is_authorized(user_id: int) -> bool:
    """Check if a user is authorized. If no users configured, allow all."""
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


async def _poll_and_reply(chat_id, job_id, context):
    """Poll the listen server until the job completes, then send the result."""
    try:
        async with httpx.AsyncClient() as client:
            poll_count = 0
            while poll_count < 7200:  # ~4 hours max
                poll_count += 1
                # Adaptive polling: 2s for first 5 min (150 polls), then 10s
                interval = 2 if poll_count <= 150 else 10
                await asyncio.sleep(interval)
                try:
                    resp = await client.get(f"{LISTEN_URL}/job/{job_id}", timeout=10)
                    if resp.status_code != 200:
                        continue
                    data = yaml.safe_load(resp.text)
                    if data.get("status") in ("completed", "failed", "stopped"):
                        await _send_job_result(context.bot, chat_id, data, job_id)
                        return
                except Exception:
                    continue
            await context.bot.send_message(chat_id=chat_id, text=f"Sorry, that took too long. Use /status {job_id} to check.")
            _mark_delivered(job_id)
    except Exception as e:
        logger.error(f"Poll error for job {job_id}: {e}", exc_info=True)


async def _send_job_result(bot, chat_id, data, job_id):
    """Send a job's result (summary + attachments) to Telegram."""
    msg = data.get("summary", "") or f"Job {job_id} {data.get('status', 'done')}."
    _log_chat("bot", msg)
    # Split long messages into chunks to avoid Telegram's 4096 char limit
    for chunk in _split_message(msg):
        await bot.send_message(chat_id=chat_id, text=chunk)

    for attachment in data.get("attachments", []):
        try:
            file_path = str(attachment)
            if not os.path.exists(file_path):
                continue
            ext = os.path.splitext(file_path)[1].lower()
            with open(file_path, "rb") as f:
                if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
                    await bot.send_photo(chat_id=chat_id, photo=f, caption=os.path.basename(file_path))
                elif ext in (".ogg", ".opus", ".oga"):
                    await bot.send_voice(chat_id=chat_id, voice=f)
                else:
                    await bot.send_document(chat_id=chat_id, document=f, filename=os.path.basename(file_path))
        except Exception as e:
            logger.error(f"Failed to send attachment {attachment}: {e}")

    _mark_delivered(job_id)
    logger.info(f"Sent result for job {job_id} to chat {chat_id}")


async def recover_undelivered(bot, chat_id):
    """Scan for completed jobs that were never delivered (e.g., after a restart or cron-triggered)."""
    delivered = _load_delivered()
    recovered = 0
    for job_file in sorted(JOBS_DIR.glob("*.yaml")):
        job_id = job_file.stem
        if job_id in delivered:
            continue
        try:
            with open(job_file) as f:
                data = yaml.safe_load(f)
            if data.get("status") in ("completed", "failed", "stopped"):
                await _send_job_result(bot, chat_id, data, job_id)
                recovered += 1
        except Exception as e:
            logger.error(f"Recovery failed for {job_id}: {e}")
    if recovered:
        logger.info(f"Recovered {recovered} undelivered job(s)")


async def periodic_delivery_check(bot):
    """Periodically check for undelivered jobs (catches cron-triggered jobs)."""
    chat_id_file = JOBS_DIR / ".chat_id"
    while True:
        await asyncio.sleep(30)  # Check every 30 seconds
        try:
            if not chat_id_file.exists():
                continue
            chat_id = int(chat_id_file.read_text().strip())
            await recover_undelivered(bot, chat_id)
        except Exception as e:
            logger.error(f"Periodic delivery check error: {e}")


async def handle_start(update, context):
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Unauthorized. Your user ID: " + str(update.effective_user.id))
        return
    await update.message.reply_text(
        "Linux Agent Bot\n\n"
        "Commands:\n"
        "/job <prompt> - Submit a job to the agent\n"
        "/jobs - List all jobs\n"
        "/status [id] - Check job status (latest if no ID)\n"
        "/stop <id> - Stop a running job\n"
        "/screenshot - Take a screenshot\n"
        "/steer <cmd> - Run a steer command\n"
        "/drive <cmd> - Run a drive command\n"
        "/shell <cmd> - Run a shell command\n"
        "/cron - Manage scheduled cron jobs (add/list/edit/del/toggle/trigger)\n"
        "/reset - Soft reset (stop jobs, kill processes, restart services)\n"
        "/reset hard - Full reboot of the Pi\n"
        "\nYou can also send images and files — they'll be saved and "
        "you can reference them in subsequent job prompts."
    )


async def handle_job(update, context):
    """Submit a job to the Listen server."""
    if not is_authorized(update.effective_user.id):
        return
    prompt = " ".join(context.args) if context.args else None
    if not prompt:
        await update.message.reply_text("Usage: /job <prompt>")
        return

    _log_chat("user", f"/job {prompt}")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LISTEN_URL}/job",
                json={"prompt": prompt},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                job_id = data.get("job_id", data.get("id", "unknown"))
                asyncio.create_task(_poll_and_reply(update.effective_chat.id, job_id, context))
            else:
                await update.message.reply_text(f"Something went wrong, try again.")
    except Exception as e:
        await update.message.reply_text(f"Sorry, I couldn't process that: {e}")


async def handle_jobs(update, context):
    """List all jobs."""
    if not is_authorized(update.effective_user.id):
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{LISTEN_URL}/jobs", timeout=10)
            if resp.status_code == 200:
                data = yaml.safe_load(resp.text)
                jobs = data.get("jobs", []) if data else []
                if not jobs:
                    await update.message.reply_text("No jobs.")
                    return
                lines = []
                for job in jobs[:10]:  # Show latest 10
                    status = job.get("status", "?")
                    jid = job.get("id", "?")
                    prompt = (job.get("prompt", "")[:50] + "...") if len(job.get("prompt", "")) > 50 else job.get("prompt", "")
                    lines.append(f"[{status}] {jid}: {prompt}")
                await update.message.reply_text("\n".join(lines))
            else:
                await update.message.reply_text(f"Error: {resp.status_code}")
    except Exception as e:
        await update.message.reply_text(f"Failed to list jobs: {e}")


async def handle_status(update, context):
    """Check status of a specific job, or show latest job if no ID given."""
    if not is_authorized(update.effective_user.id):
        return

    job_id = context.args[0] if context.args else None

    try:
        async with httpx.AsyncClient() as client:
            # If no job_id, find the latest running job (or most recent job)
            if not job_id:
                resp = await client.get(f"{LISTEN_URL}/jobs", timeout=10)
                if resp.status_code != 200:
                    await update.message.reply_text("Could not fetch jobs.")
                    return
                data = yaml.safe_load(resp.text)
                jobs = data.get("jobs", []) if data else []
                if not jobs:
                    await update.message.reply_text("No jobs found.")
                    return
                # Prefer running jobs, otherwise most recent
                running = [j for j in jobs if j.get("status") == "running"]
                target = running[-1] if running else jobs[-1]
                job_id = target.get("id")

            resp = await client.get(f"{LISTEN_URL}/job/{job_id}", timeout=10)
            if resp.status_code == 200:
                data = yaml.safe_load(resp.text)
                lines = [
                    f"Job: {data.get('id', '?')}",
                    f"Status: {data.get('status', '?')}",
                    f"Prompt: {(data.get('prompt', '')[:80] + '...') if len(data.get('prompt', '')) > 80 else data.get('prompt', '')}",
                ]
                if data.get("summary"):
                    lines.append(f"Summary: {data['summary']}")
                if data.get("duration_seconds"):
                    lines.append(f"Duration: {data['duration_seconds']}s")
                if data.get("updates"):
                    lines.append("Updates:")
                    for u in data["updates"][-5:]:  # Last 5 updates
                        lines.append(f"  - {u}")
                await update.message.reply_text("\n".join(lines))
            else:
                await update.message.reply_text(f"Job not found: {resp.status_code}")
    except Exception as e:
        await update.message.reply_text(f"Failed to get status: {e}")


async def handle_stop(update, context):
    """Stop a running job."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /stop <job_id>")
        return
    job_id = context.args[0]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(f"{LISTEN_URL}/job/{job_id}", timeout=10)
            await update.message.reply_text(f"Stop result: {resp.status_code} — {resp.text}")
    except Exception as e:
        await update.message.reply_text(f"Failed to stop job: {e}")


async def handle_screenshot(update, context):
    """Take a screenshot and send it back."""
    if not is_authorized(update.effective_user.id):
        return
    try:
        screenshot_path = os.path.join(tempfile.gettempdir(), "telegram-screenshot.png")
        # Try steer first, fall back to scrot
        steer_path = REPO_ROOT / "apps" / "steer"
        result = subprocess.run(
            ["uv", "run", "python", "main.py", "see", "--json"],
            capture_output=True, text=True,
            cwd=str(steer_path), timeout=15,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            ss_path = data.get("screenshot", "")
            if ss_path and os.path.exists(ss_path):
                with open(ss_path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Desktop screenshot")
                return

        # Fallback: scrot
        scrot = shutil.which("scrot")
        if scrot:
            subprocess.run([scrot, "--overwrite", screenshot_path], capture_output=True, timeout=10)
            if os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="Desktop screenshot")
                return

        await update.message.reply_text("Failed to capture screenshot.")
    except Exception as e:
        await update.message.reply_text(f"Screenshot error: {e}")


async def handle_steer(update, context):
    """Run a steer command."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /steer <command> [args...]")
        return
    cmd_args = list(context.args)
    steer_path = REPO_ROOT / "apps" / "steer"
    try:
        result = subprocess.run(
            ["uv", "run", "python", "main.py"] + cmd_args + ["--json"],
            capture_output=True, text=True,
            cwd=str(steer_path), timeout=30,
        )
        output = result.stdout or result.stderr or "(no output)"
        # Truncate for Telegram's message limit
        if len(output) > 4000:
            output = output[:4000] + "\n...(truncated)"
        await update.message.reply_text(output)

        # If the command was 'see' or 'ocr', try to send the screenshot too
        if cmd_args and cmd_args[0] in ("see", "ocr") and result.returncode == 0:
            try:
                import json
                data = json.loads(result.stdout)
                ss_path = data.get("screenshot", "")
                if ss_path and os.path.exists(ss_path):
                    with open(ss_path, "rb") as f:
                        await update.message.reply_photo(photo=f)
            except Exception:
                pass

    except subprocess.TimeoutExpired:
        await update.message.reply_text("Command timed out (30s)")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def handle_drive(update, context):
    """Run a drive command."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /drive <command> [args...]")
        return
    cmd_args = list(context.args)
    drive_path = REPO_ROOT / "apps" / "drive"
    try:
        result = subprocess.run(
            ["uv", "run", "python", "main.py"] + cmd_args + ["--json"],
            capture_output=True, text=True,
            cwd=str(drive_path), timeout=30,
        )
        output = result.stdout or result.stderr or "(no output)"
        if len(output) > 4000:
            output = output[:4000] + "\n...(truncated)"
        await update.message.reply_text(output)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Command timed out (30s)")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def handle_shell(update, context):
    """Run an arbitrary shell command."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /shell <command>")
        return
    cmd = " ".join(context.args)
    try:
        result = subprocess.run(
            cmd, shell=True,
            capture_output=True, text=True,
            timeout=30, cwd=str(REPO_ROOT),
        )
        output = result.stdout or result.stderr or "(no output)"
        if len(output) > 4000:
            output = output[:4000] + "\n...(truncated)"
        await update.message.reply_text(output)
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Command timed out (30s)")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def handle_photo(update, context):
    """Handle received photos — save and auto-submit as job if caption present."""
    if not is_authorized(update.effective_user.id):
        return
    photo = update.message.photo[-1]  # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    filename = f"photo_{photo.file_unique_id}.jpg"
    save_path = UPLOADS_DIR / filename
    await file.download_to_drive(str(save_path))

    caption = update.message.caption
    if caption:
        # Auto-submit as job with photo reference
        _save_chat_id(update.effective_chat.id)
        _log_chat("user", f"[photo] {caption}")
        prompt = f"{caption}\n\nImage attached at: {save_path}"
        prompt_with_context = _build_prompt_with_context(prompt)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{LISTEN_URL}/job",
                    json={"prompt": prompt_with_context},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    job_id = data.get("job_id", data.get("id", "unknown"))
                    asyncio.create_task(_poll_and_reply(update.effective_chat.id, job_id, context))
                else:
                    await update.message.reply_text(f"Something went wrong, try again.")
        except Exception as e:
            await update.message.reply_text(f"Sorry, I couldn't process that: {e}")
    else:
        await update.message.reply_text(
            f"Photo saved: {save_path}\n"
            f"Reference it in a job prompt with: /job Use the image at {save_path} to ..."
        )


async def handle_document(update, context):
    """Handle received documents/files — save and confirm."""
    if not is_authorized(update.effective_user.id):
        return
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    # Sanitize filename to prevent path traversal (e.g. ../../../etc/passwd)
    raw_name = doc.file_name or f"file_{doc.file_unique_id}"
    filename = os.path.basename(raw_name)  # Strip any directory components
    if not filename:
        filename = f"file_{doc.file_unique_id}"
    save_path = UPLOADS_DIR / filename
    # Verify the resolved path is still inside UPLOADS_DIR
    if not save_path.resolve().is_relative_to(UPLOADS_DIR.resolve()):
        await update.message.reply_text("Invalid filename.")
        return
    await file.download_to_drive(str(save_path))

    # Validate the downloaded file isn't corrupted (all null bytes)
    file_bytes = save_path.read_bytes()
    if len(file_bytes) > 0 and all(b == 0 for b in file_bytes[:1024]):
        logger.warning(f"Downloaded file {filename} appears corrupted (null bytes)")
        await update.message.reply_text(
            f"The file {filename} downloaded as corrupted data (all null bytes). "
            f"This usually happens when the file hasn't fully synced from cloud storage "
            f"(iCloud, Google Drive, etc.) on your device. Try opening the file on your "
            f"phone first to make sure it's fully downloaded, then re-send it."
        )
        return

    caption = update.message.caption
    if caption:
        # Auto-submit as job with file reference
        _save_chat_id(update.effective_chat.id)
        _log_chat("user", f"[file: {filename}] {caption}")
        prompt = f"{caption}\n\nFile attached at: {save_path}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{LISTEN_URL}/job",
                    json={"prompt": prompt},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    job_id = data.get("job_id", data.get("id", "unknown"))
                    asyncio.create_task(_poll_and_reply(update.effective_chat.id, job_id, context))
                else:
                    await update.message.reply_text(f"Something went wrong, try again.")
        except Exception as e:
            await update.message.reply_text(f"Sorry, I couldn't process that: {e}")
    else:
        await update.message.reply_text(
            f"File saved: {save_path}\n"
            f"Reference it in a job prompt with: /job Use the file at {save_path} to ..."
        )


async def handle_cron(update, context):
    """Manage cron jobs. Usage:
    /cron list — show all crons
    /cron add <schedule> | <name> | <prompt> — create a cron
    /cron del <id> — delete a cron
    /cron toggle <id> — enable/disable a cron
    /cron edit <id> schedule <new_schedule> — edit schedule
    /cron edit <id> name <new_name> — edit name
    /cron edit <id> prompt <new_prompt> — edit prompt
    /cron trigger <id> — fire a cron right now
    """
    if not is_authorized(update.effective_user.id):
        return

    args = context.args if context.args else []
    if not args:
        await update.message.reply_text(
            "Cron Commands:\n\n"
            "/cron list — show all crons\n"
            "/cron add <crontab> | <name> | <prompt>\n"
            "  e.g. /cron add 3 7 * * * | Morning Briefing | Get weather and news\n"
            "/cron del <id> — delete a cron\n"
            "/cron toggle <id> — enable/disable\n"
            "/cron edit <id> schedule|name|prompt <value>\n"
            "/cron trigger <id> — fire now (for testing)\n"
            "\nCrontab format: min hour day month weekday\n"
            "Examples: '0 9 * * *' = 9am daily, '0 9 * * 1-5' = 9am weekdays"
        )
        return

    subcommand = args[0].lower()

    if subcommand == "list":
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{LISTEN_URL}/crons", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    crons = data.get("crons", [])
                    if not crons:
                        await update.message.reply_text("No crons set up yet. Use /cron add to create one.")
                        return
                    lines = []
                    for c in crons:
                        status = "ON" if c.get("enabled", True) else "OFF"
                        lines.append(
                            f"[{status}] {c['id']}: {c.get('name', '?')}\n"
                            f"  Schedule: {c.get('schedule', '?')} ({c.get('timezone', 'US/Central')})\n"
                            f"  Prompt: {c.get('prompt', '?')[:80]}{'...' if len(c.get('prompt', '')) > 80 else ''}"
                        )
                    await update.message.reply_text("\n\n".join(lines))
                else:
                    await update.message.reply_text(f"Error: {resp.status_code}")
        except Exception as e:
            await update.message.reply_text(f"Failed: {e}")

    elif subcommand == "add":
        # Parse: everything after "add" joined, split by |
        raw = " ".join(args[1:])
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 3:
            await update.message.reply_text(
                "Usage: /cron add <crontab> | <name> | <prompt>\n"
                "Example: /cron add 3 7 * * * | Morning Briefing | Get weather and news for Austin TX"
            )
            return

        schedule = parts[0]
        name = parts[1]
        prompt = parts[2]

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{LISTEN_URL}/cron",
                    json={"name": name, "schedule": schedule, "prompt": prompt},
                    timeout=10,
                )
                if resp.status_code == 200:
                    cron = resp.json()
                    await update.message.reply_text(
                        f"Cron created!\n"
                        f"ID: {cron['id']}\n"
                        f"Name: {cron['name']}\n"
                        f"Schedule: {cron['schedule']}\n"
                        f"Prompt: {cron['prompt'][:100]}"
                    )
                else:
                    error = resp.json().get("detail", resp.text)
                    await update.message.reply_text(f"Failed to create cron: {error}")
        except Exception as e:
            await update.message.reply_text(f"Error creating cron: {e}")

    elif subcommand == "del":
        if len(args) < 2:
            await update.message.reply_text("Usage: /cron del <id>")
            return
        cron_id = args[1]
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.delete(f"{LISTEN_URL}/cron/{cron_id}", timeout=10)
                if resp.status_code == 200:
                    await update.message.reply_text(f"Cron {cron_id} deleted.")
                else:
                    await update.message.reply_text(f"Cron not found: {cron_id}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    elif subcommand == "toggle":
        if len(args) < 2:
            await update.message.reply_text("Usage: /cron toggle <id>")
            return
        cron_id = args[1]
        try:
            async with httpx.AsyncClient() as client:
                # Get current state
                resp = await client.get(f"{LISTEN_URL}/cron/{cron_id}", timeout=10)
                if resp.status_code != 200:
                    await update.message.reply_text(f"Cron not found: {cron_id}")
                    return
                cron = resp.json()
                new_state = not cron.get("enabled", True)
                # Update
                resp = await client.put(
                    f"{LISTEN_URL}/cron/{cron_id}",
                    json={"enabled": new_state},
                    timeout=10,
                )
                if resp.status_code == 200:
                    state_str = "ON" if new_state else "OFF"
                    await update.message.reply_text(f"Cron {cron_id} ({cron.get('name', '?')}) is now {state_str}")
                else:
                    await update.message.reply_text(f"Failed to toggle: {resp.text}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    elif subcommand == "edit":
        if len(args) < 4:
            await update.message.reply_text(
                "Usage: /cron edit <id> <field> <value>\n"
                "Fields: schedule, name, prompt"
            )
            return
        cron_id = args[1]
        field = args[2].lower()
        value = " ".join(args[3:])
        if field not in ("schedule", "name", "prompt", "timezone"):
            await update.message.reply_text(f"Unknown field: {field}. Use: schedule, name, prompt, timezone")
            return
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.put(
                    f"{LISTEN_URL}/cron/{cron_id}",
                    json={field: value},
                    timeout=10,
                )
                if resp.status_code == 200:
                    cron = resp.json()
                    await update.message.reply_text(f"Updated {field} for cron {cron_id} ({cron.get('name', '?')})")
                else:
                    await update.message.reply_text(f"Failed: {resp.text}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    elif subcommand == "trigger":
        if len(args) < 2:
            await update.message.reply_text("Usage: /cron trigger <id>")
            return
        cron_id = args[1]
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{LISTEN_URL}/cron/{cron_id}/trigger", timeout=10)
                if resp.status_code == 200:
                    await update.message.reply_text(f"Cron {cron_id} triggered! A job has been submitted.")
                    # Poll for the result
                    # We don't know the job ID here, but the cron will have fired it
                else:
                    await update.message.reply_text(f"Failed: {resp.text}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    else:
        await update.message.reply_text(f"Unknown subcommand: {subcommand}. Try /cron for help.")


async def handle_reset(update, context):
    """Reset the Pi — stop all jobs, kill stale processes, and optionally reboot."""
    if not is_authorized(update.effective_user.id):
        return

    args = context.args if context.args else []
    mode = args[0].lower() if args else "soft"

    if mode == "hard":
        await update.message.reply_text("Rebooting the Pi now... I'll be back in a minute or two.")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{LISTEN_URL}/reset/{mode}", timeout=30)
            data = resp.json()
    except Exception as e:
        await update.message.reply_text(f"Reset failed: {e}")
        return

    if mode == "hard":
        return  # Already sent the reboot message

    lines = []
    lines.append(f"Stopped {data.get('jobs_stopped', 0)} running job(s)")
    lines.append(f"Killed {data.get('processes_killed', 0)} stale claude process(es)")
    lines.append(f"Killed {data.get('sessions_killed', 0)} orphan tmux session(s)")
    lines.append(f"Service restart: {data.get('service_restart', 'unknown')}")

    await update.message.reply_text("Reset complete!\n\n" + "\n".join(lines))


async def handle_text(update, context):
    """Handle plain text messages — treat as job prompts."""
    if not is_authorized(update.effective_user.id):
        return
    text = update.message.text
    if not text:
        return
    _save_chat_id(update.effective_chat.id)
    _log_chat("user", text)

    # Treat plain text as a job submission, with chat history context
    prompt_with_context = _build_prompt_with_context(text)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LISTEN_URL}/job",
                json={"prompt": prompt_with_context},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                job_id = data.get("job_id", data.get("id", "unknown"))
                asyncio.create_task(_poll_and_reply(update.effective_chat.id, job_id, context))
            else:
                await update.message.reply_text(f"Something went wrong, try again.")
    except Exception as e:
        await update.message.reply_text(f"Sorry, I couldn't process that: {e}")
