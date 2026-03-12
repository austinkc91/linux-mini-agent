"""Job worker — runs a Claude Code agent in a visible terminal window.

Creates a headed tmux session, sends the claude command with sentinel
markers, polls for completion, then updates the job YAML.
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

import yaml

SENTINEL_PREFIX = "__JOBDONE_"
POLL_INTERVAL = 2.0
MAX_JOB_DURATION = 4 * 3600  # 4 hours max per job

# Global state for signal handler
_job_file: Path | None = None
_start_time: float = 0.0
_session_name: str = ""
_shutdown_requested: bool = False


def _handle_sigterm(signum, frame):
    """Signal handler: set flag for main thread to handle cleanup."""
    global _shutdown_requested
    _shutdown_requested = True


def _do_shutdown_cleanup():
    """Perform actual shutdown cleanup (called from main thread, not signal handler)."""
    if _job_file and _job_file.exists():
        try:
            with open(_job_file) as f:
                data = yaml.safe_load(f)
            if data.get("status") == "running":
                duration = round(time.time() - _start_time)
                now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                data["status"] = "stopped"
                data["exit_code"] = 143
                data["duration_seconds"] = duration
                data["completed_at"] = now
                _atomic_yaml_write(_job_file, data)
        except Exception:
            pass  # Best-effort — don't block shutdown

    # Clean up tmux session
    if _session_name and _session_exists(_session_name):
        _tmux("kill-session", "-t", _session_name, check=False)

    sys.exit(143)


def _atomic_yaml_write(path: Path, data: dict):
    """Write YAML atomically: write to temp file then rename."""
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, suffix=".tmp", prefix=path.stem
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a tmux command."""
    return subprocess.run(["tmux", *args], capture_output=True, text=True, check=check)


def _session_exists(name: str) -> bool:
    result = _tmux("has-session", "-t", name, check=False)
    return result.returncode == 0


def _open_terminal(session_name: str, cwd: str) -> None:
    """Create a detached tmux session, then open a terminal window attached to it.

    The tmux session is created first (instant, reliable) so the worker never
    blocks on a terminal emulator launching. The terminal window is best-effort
    — if it fails to open, the session still exists headlessly.
    """
    # Step 1: Create detached tmux session (always works)
    result = subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, "-c", cwd],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create tmux session '{session_name}': {result.stderr.strip()}"
        )

    # Step 2: Try to open a terminal window attached to the session (best-effort)
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


def _capture_pane(session: str) -> str:
    result = _tmux("capture-pane", "-p", "-t", f"{session}:", "-S", "-500")
    return result.stdout


def _wait_for_sentinel(session: str, token: str, timeout: float = MAX_JOB_DURATION) -> int:
    """Poll until sentinel appears or timeout/shutdown.

    Args:
        timeout: Max seconds to wait. Default MAX_JOB_DURATION (4 hours).

    Returns:
        Exit code from the sentinel marker.

    Raises:
        TimeoutError: If sentinel not detected within timeout.
    """
    pattern = re.compile(
        rf"^{re.escape(SENTINEL_PREFIX)}{token}:(\d+)\s*$", re.MULTILINE
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _shutdown_requested:
            _do_shutdown_cleanup()
        time.sleep(POLL_INTERVAL)
        captured = _capture_pane(session)
        match = pattern.search(captured)
        if match:
            return int(match.group(1))
    raise TimeoutError(f"Job timed out after {timeout}s")


def main():
    global _job_file, _start_time, _session_name

    if len(sys.argv) < 3:
        print("Usage: worker.py <job_id> <prompt>")
        sys.exit(1)

    job_id = sys.argv[1]
    prompt = sys.argv[2]

    jobs_dir = Path(__file__).parent / "jobs"
    job_file = jobs_dir / f"{job_id}.yaml"
    _job_file = job_file

    if not job_file.exists():
        print(f"Job file not found: {job_file}")
        sys.exit(1)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_sigterm)

    repo_root = Path(__file__).parent.parent.parent
    sys_prompt_file = (
        repo_root / ".claude" / "agents" / "listen-drive-and-steer-system-prompt.md"
    )
    sys_prompt = sys_prompt_file.read_text().replace("{{JOB_ID}}", job_id)

    # Write system prompt and user prompt to temp files with restrictive permissions
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

        # Build the claude command — use cat with proper quoting to avoid injection.
        # The temp file paths are generated by us (not user-controlled).
        claude_cmd = (
            f"claude --dangerously-skip-permissions -p"
            f" --append-system-prompt \"$(cat '{sys_prompt_tmp}')\""
            f" \"$(cat '{prompt_tmp}')\""
        )

        # Wrap with sentinel: <cmd> ; echo "__JOBDONE_<token>:$?"
        wrapped = f'{claude_cmd} ; echo "{SENTINEL_PREFIX}{token}:$?"'

        start_time = time.time()
        _start_time = start_time

        # Strip CLAUDECODE from env — pass clean env to subprocess, don't mutate global
        env_clean = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        try:
            # Open headed terminal window with tmux session
            _open_terminal(session_name, str(repo_root))

            # Send the wrapped command
            _send_keys(session_name, wrapped)

            # Update job with session info using atomic write
            with open(job_file) as f:
                data = yaml.safe_load(f)
            data["session"] = session_name
            _atomic_yaml_write(job_file, data)

            # Wait for completion with timeout
            exit_code = _wait_for_sentinel(session_name, token)

        except TimeoutError:
            exit_code = 124  # Standard timeout exit code
            print(f"Job {job_id} timed out after {MAX_JOB_DURATION}s", file=sys.stderr)
        except Exception as e:
            exit_code = 1
            print(f"Worker error: {e}", file=sys.stderr)

        duration = round(time.time() - start_time)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with open(job_file) as f:
            data = yaml.safe_load(f)

        data["status"] = "completed" if exit_code == 0 else "failed"
        data["exit_code"] = exit_code
        data["duration_seconds"] = duration
        data["completed_at"] = now

        _atomic_yaml_write(job_file, data)

        # Clean up tmux session
        if _session_exists(session_name):
            _tmux("kill-session", "-t", session_name, check=False)

    finally:
        # Always clean up temp files
        sys_prompt_path.unlink(missing_ok=True)
        prompt_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
