"""Telegram bot for remote agent control.

Allows users to:
- Send text prompts to the Listen job server
- Check job status
- Send images/files that get saved and referenced in prompts
- Take screenshots of the agent's desktop
- Run steer/drive commands directly
"""

import logging
import os
import subprocess
import shutil
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

LISTEN_URL = os.environ.get("LISTEN_URL", "http://localhost:7600")
REPO_ROOT = Path(__file__).parent.parent.parent
UPLOADS_DIR = Path(tempfile.gettempdir()) / "telegram-uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

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
        "/status <id> - Check job status\n"
        "/stop <id> - Stop a running job\n"
        "/screenshot - Take a screenshot\n"
        "/steer <cmd> - Run a steer command\n"
        "/drive <cmd> - Run a drive command\n"
        "/shell <cmd> - Run a shell command\n"
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

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LISTEN_URL}/job",
                json={"prompt": prompt},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                job_id = data.get("id", "unknown")
                await update.message.reply_text(f"Job submitted: {job_id}")
            else:
                await update.message.reply_text(f"Error: {resp.status_code} — {resp.text}")
    except Exception as e:
        await update.message.reply_text(f"Failed to submit job: {e}")


async def handle_jobs(update, context):
    """List all jobs."""
    if not is_authorized(update.effective_user.id):
        return
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{LISTEN_URL}/jobs", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if not data:
                    await update.message.reply_text("No jobs.")
                    return
                lines = []
                for job in data[:10]:  # Show latest 10
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
    """Check status of a specific job."""
    if not is_authorized(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /status <job_id>")
        return
    job_id = context.args[0]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{LISTEN_URL}/job/{job_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                lines = [
                    f"Job: {data.get('id', '?')}",
                    f"Status: {data.get('status', '?')}",
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
        await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")

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
        await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")
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
        await update.message.reply_text(f"```\n{output}\n```", parse_mode="Markdown")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("Command timed out (30s)")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def handle_photo(update, context):
    """Handle received photos — save and confirm."""
    if not is_authorized(update.effective_user.id):
        return
    photo = update.message.photo[-1]  # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    filename = f"photo_{photo.file_unique_id}.jpg"
    save_path = UPLOADS_DIR / filename
    await file.download_to_drive(str(save_path))
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
    filename = doc.file_name or f"file_{doc.file_unique_id}"
    save_path = UPLOADS_DIR / filename
    await file.download_to_drive(str(save_path))
    await update.message.reply_text(
        f"File saved: {save_path}\n"
        f"Reference it in a job prompt with: /job Use the file at {save_path} to ..."
    )


async def handle_text(update, context):
    """Handle plain text messages — treat as job prompts."""
    if not is_authorized(update.effective_user.id):
        return
    text = update.message.text
    if not text:
        return

    # Treat plain text as a job submission
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LISTEN_URL}/job",
                json={"prompt": text},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                job_id = data.get("id", "unknown")
                await update.message.reply_text(f"Job submitted: {job_id}\nUse /status {job_id} to check progress.")
            else:
                await update.message.reply_text(f"Error: {resp.status_code} — {resp.text}")
    except Exception as e:
        await update.message.reply_text(f"Failed to submit job: {e}")
