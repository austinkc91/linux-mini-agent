"""Job worker — runs a Claude Code agent in a visible terminal window.

Creates a headed tmux session, sends the claude command with sentinel
markers, polls for completion, then updates the job in SQLite.
"""

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import db

SENTINEL_PREFIX = "__JOBDONE_"
POLL_INTERVAL = 2.0
MAX_JOB_DURATION = 4 * 3600  # 4 hours max per job

# Global state for signal handler
_job_id: str = ""
_start_time: float = 0.0
_session_name: str = ""
_shutdown_requested: bool = False


def _handle_sigterm(signum, frame):
    """Signal handler: set flag for main thread to handle cleanup."""
    global _shutdown_requested
    _shutdown_requested = True


def _do_shutdown_cleanup():
    """Perform actual shutdown cleanup (called from main thread, not signal handler)."""
    if _job_id:
        try:
            job = db.sync_get_job(_job_id)
            if job and job.get("status") == "running":
                duration = round(time.time() - _start_time)
                now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                db.sync_update_job(
                    _job_id,
                    status="stopped",
                    exit_code=143,
                    duration_seconds=duration,
                    completed_at=now,
                )
        except Exception:
            pass  # Best-effort — don't block shutdown

    # Clean up tmux session
    if _session_name and _session_exists(_session_name):
        _tmux("kill-session", "-t", _session_name, check=False)

    sys.exit(143)


def _tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a tmux command."""
    return subprocess.run(["tmux", *args], capture_output=True, text=True, check=check)


def _session_exists(name: str) -> bool:
    result = _tmux("has-session", "-t", name, check=False)
    return result.returncode == 0


def _open_terminal(session_name: str, cwd: str) -> None:
    """Create a detached tmux session, then open a terminal window attached to it."""
    result = subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, "-c", cwd],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create tmux session '{session_name}': {result.stderr.strip()}"
        )

    attach_cmd = f"tmux attach-session -t {session_name}"
    terminals = [
        ("xterm", ["-e", f"bash -c '{attach_cmd}'"]),
        ("gnome-terminal", ["--", "bash", "-c", attach_cmd]),
        ("konsole", ["-e", "bash", "-c", attach_cmd]),
        ("xfce4-terminal", ["-e", f"bash -c '{attach_cmd}'"]),
    ]

    for term, args in terminals:
        path = shutil.which(term)
        if path:
            subprocess.Popen(
                [path] + args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            break


def _send_keys(session: str, keys: str) -> None:
    """Send keys to tmux session then press Enter."""
    _tmux("send-keys", "-t", f"{session}:", keys)
    _tmux("send-keys", "-t", f"{session}:", "Enter")


def _capture_pane(session: str) -> str | None:
    """Capture tmux pane content. Returns None if session no longer exists."""
    result = _tmux("capture-pane", "-p", "-t", f"{session}:", "-S", "-500", check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def _check_sentinel_file(job_id: str, token: str) -> int | None:
    """Check if sentinel was written to fallback file. Returns exit code or None."""
    sentinel_file = Path(f"/tmp/sentinel-{job_id}.txt")
    if not sentinel_file.exists():
        return None
    pattern = re.compile(
        rf"^{re.escape(SENTINEL_PREFIX)}{token}:(\d+)\s*$", re.MULTILINE
    )
    match = pattern.search(sentinel_file.read_text())
    return int(match.group(1)) if match else None


def _wait_for_sentinel(session: str, token: str, job_id: str = "", timeout: float = MAX_JOB_DURATION) -> int:
    """Poll until sentinel appears or timeout/shutdown."""
    pattern = re.compile(
        rf"^{re.escape(SENTINEL_PREFIX)}{token}:(\d+)\s*$", re.MULTILINE
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _shutdown_requested:
            _do_shutdown_cleanup()
        time.sleep(POLL_INTERVAL)
        captured = _capture_pane(session)
        if captured is None:
            if not _session_exists(session):
                if job_id:
                    file_exit = _check_sentinel_file(job_id, token)
                    if file_exit is not None:
                        return file_exit
                raise RuntimeError(
                    f"Tmux session '{session}' died before job completed. "
                    "The Claude agent may have crashed, been OOM-killed, or the session was killed externally."
                )
            continue
        match = pattern.search(captured)
        if match:
            return int(match.group(1))
    raise TimeoutError(f"Job timed out after {timeout}s")


def main():
    global _job_id, _start_time, _session_name

    if len(sys.argv) < 3:
        print("Usage: worker.py <job_id> <prompt>")
        sys.exit(1)

    job_id = sys.argv[1]
    prompt = sys.argv[2]
    _job_id = job_id

    # Verify job exists in DB
    job_data = db.sync_get_job(job_id)
    if not job_data:
        print(f"Job not found in database: {job_id}")
        sys.exit(1)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_sigterm)

    repo_root = Path(__file__).parent.parent.parent
    sys_prompt_file = (
        repo_root / ".claude" / "agents" / "listen-drive-and-steer-system-prompt.md"
    )
    sys_prompt = sys_prompt_file.read_text().replace("{{JOB_ID}}", job_id)

    # Inject user identity into system prompt if available
    submitted_by = job_data.get("submitted_by")
    submitted_by_email = job_data.get("submitted_by_email")
    if submitted_by:
        user_context = f"\n\n# Submitted By\n\nThis job was submitted by **{submitted_by}**."
        if submitted_by_email:
            user_context += f"\nTheir email address is: {submitted_by_email}"
        user_context += (
            "\n\nPersonalize your response for this user. "
            "If they ask for reminders or emails, send to their email address. "
            "Address them by name in your summary."
        )
        sys_prompt += user_context

    # Write system prompt and user prompt to temp files
    sys_prompt_fd, sys_prompt_tmp = tempfile.mkstemp(
        prefix=f"sysprompt-{job_id}-", suffix=".txt"
    )
    prompt_fd, prompt_tmp = tempfile.mkstemp(
        prefix=f"prompt-{job_id}-", suffix=".txt"
    )
    os.fchmod(sys_prompt_fd, 0o600)
    os.fchmod(prompt_fd, 0o600)

    sys_prompt_path = Path(sys_prompt_tmp)
    prompt_path = Path(prompt_tmp)

    try:
        with os.fdopen(sys_prompt_fd, "w") as f:
            f.write(sys_prompt)
        with os.fdopen(prompt_fd, "w") as f:
            f.write(f"/listen-drive-and-steer-user-prompt {prompt}")

        session_name = f"job-{job_id}"
        _session_name = session_name
        token = uuid.uuid4().hex[:8]

        stderr_file = f"/tmp/claude-stderr-{job_id}.txt"
        max_attempts = 2  # Retry once on failure

        claude_cmd = (
            f"claude --dangerously-skip-permissions -p"
            f" --append-system-prompt \"$(cat '{sys_prompt_tmp}')\""
            f" \"$(cat '{prompt_tmp}')\""
            f" 2>{stderr_file}"
        )

        sentinel_file = f"/tmp/sentinel-{job_id}.txt"
        wrapped = (
            f'{claude_cmd} ; _exit=$?'
            f' ; echo "{SENTINEL_PREFIX}{token}:$_exit"'
            f' ; echo "{SENTINEL_PREFIX}{token}:$_exit" > {sentinel_file}'
        )

        start_time = time.time()
        _start_time = start_time

        env_clean = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        exit_code = None
        error_msg = None

        for attempt in range(1, max_attempts + 1):
            # Reset sentinel file between attempts
            Path(sentinel_file).unlink(missing_ok=True)
            Path(stderr_file).unlink(missing_ok=True)

            try:
                if attempt == 1:
                    _open_terminal(session_name, str(repo_root))
                else:
                    # Retry: re-create session if it died
                    if not _session_exists(session_name):
                        _open_terminal(session_name, str(repo_root))
                    db.sync_update_job(job_id, summary=None)  # Clear stale summary

                _send_keys(session_name, wrapped)

                # Update job with session info
                db.sync_update_job(job_id, session=session_name)

                exit_code = _wait_for_sentinel(session_name, token, job_id=job_id)

            except TimeoutError:
                exit_code = 124
                error_msg = f"Job timed out after {MAX_JOB_DURATION}s"
                print(f"Job {job_id}: {error_msg}", file=sys.stderr)
                break  # Don't retry timeouts
            except Exception as e:
                exit_code = 1
                error_msg = str(e)
                print(f"Worker error: {e}", file=sys.stderr)

            # Read stderr for context on failures
            stderr_content = ""
            try:
                stderr_path = Path(stderr_file)
                if stderr_path.exists():
                    stderr_content = stderr_path.read_text().strip()[-500:]
            except Exception:
                pass

            if exit_code == 0:
                error_msg = None
                break  # Success

            # On failure, check if retryable (short duration = likely API/startup error)
            elapsed = time.time() - start_time
            if attempt < max_attempts and elapsed < 120:
                print(f"Job {job_id}: attempt {attempt} failed (exit {exit_code}), retrying...", file=sys.stderr)
                if stderr_content:
                    print(f"  stderr: {stderr_content[:200]}", file=sys.stderr)
                # Brief pause before retry
                time.sleep(3)
                # Generate new token for retry
                token = uuid.uuid4().hex[:8]
                wrapped = (
                    f'{claude_cmd} ; _exit=$?'
                    f' ; echo "{SENTINEL_PREFIX}{token}:$_exit"'
                    f' ; echo "{SENTINEL_PREFIX}{token}:$_exit" > {sentinel_file}'
                )
                continue
            else:
                # Include stderr in error message
                if stderr_content and not error_msg:
                    error_msg = stderr_content
                elif stderr_content:
                    error_msg = f"{error_msg} | stderr: {stderr_content}"
                break

        duration = round(time.time() - start_time)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Read current state (agent may have written summary/updates via HTTP)
        current = db.sync_get_job(job_id) or {}

        status = "completed" if exit_code == 0 else "failed"
        update_fields = {
            "status": status,
            "exit_code": exit_code,
            "duration_seconds": duration,
            "completed_at": now,
        }

        # Set a fallback summary if the agent didn't write one
        if exit_code != 0 and not current.get("summary"):
            update_fields["summary"] = (
                f"Job failed (exit code {exit_code}). "
                f"{error_msg or 'The agent process exited unexpectedly.'}"
            )

        db.sync_update_job(job_id, **update_fields)

        # Clean up tmux session
        if _session_exists(session_name):
            _tmux("kill-session", "-t", session_name, check=False)

    finally:
        sys_prompt_path.unlink(missing_ok=True)
        prompt_path.unlink(missing_ok=True)
        Path(f"/tmp/sentinel-{job_id}.txt").unlink(missing_ok=True)
        Path(f"/tmp/claude-stderr-{job_id}.txt").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
