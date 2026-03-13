"""Subprocess wrappers for tmux CLI.

All tmux interaction flows through this module.
Command files import from here; they never call subprocess directly.
"""
import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass

from modules.errors import (
    SessionExistsError,
    SessionNotFoundError,
    TmuxCommandError,
    TmuxNotFoundError,
)


def require_tmux() -> str:
    """Return path to tmux binary or raise TmuxNotFoundError."""
    path = shutil.which("tmux")
    if path is None:
        raise TmuxNotFoundError()
    return path


def _run(
    args: list[str], *, check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a tmux command. All subprocess calls are centralized here."""
    tmux = require_tmux()
    cmd = [tmux] + args
    try:
        result = subprocess.run(
            cmd, capture_output=capture, text=True, timeout=10
        )
        if check and result.returncode != 0:
            raise TmuxCommandError(cmd=args, stderr=result.stderr.strip())
        return result
    except subprocess.TimeoutExpired:
        raise TmuxCommandError(cmd=args, stderr="tmux command timed out after 10s")
    except FileNotFoundError:
        raise TmuxNotFoundError()


# --- Session operations ---


def session_exists(name: str) -> bool:
    """Check if a tmux session exists."""
    result = _run(["has-session", "-t", name], check=False)
    return result.returncode == 0


def require_session(name: str) -> None:
    """Raise SessionNotFoundError if session does not exist."""
    if not session_exists(name):
        raise SessionNotFoundError(name)


@dataclass
class SessionInfo:
    name: str
    windows: int
    created: str
    attached: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "windows": self.windows,
            "created": self.created,
            "attached": self.attached,
        }


def _sanitize_session_name(name: str) -> str:
    """Validate and sanitize a tmux session name.

    Tmux session names must not contain periods or colons.
    """
    # Strip dangerous characters, keep alphanumeric, hyphens, underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    if not sanitized:
        sanitized = "session"
    return sanitized[:64]  # Reasonable length limit


def open_terminal_window(command: str) -> None:
    """Open a new terminal window and run a command in it.

    On Linux, tries xterm, gnome-terminal, konsole, or xfce4-terminal.
    The new window inherits the current working directory.
    """
    cwd = os.getcwd()
    # Use shlex.quote to properly escape cwd for shell execution
    shell_command = f"cd {shlex.quote(cwd)} && {command}"

    # Try available terminal emulators in order of preference
    # All use list-based args to avoid shell injection
    terminals = [
        ("xterm", ["-e", "bash", "-c", shell_command]),
        ("gnome-terminal", ["--", "bash", "-c", shell_command]),
        ("konsole", ["-e", "bash", "-c", shell_command]),
        ("xfce4-terminal", ["-e", "bash -c " + shlex.quote(shell_command)]),
    ]

    for term, args in terminals:
        path = shutil.which(term)
        if path:
            subprocess.Popen(
                [path] + args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return

    # Fallback: create detached tmux session directly (no visible window)
    tmux = require_tmux()
    parts = command.split()
    session_name = _sanitize_session_name(parts[-1] if parts else "fallback")
    subprocess.run(
        [tmux, "new-session", "-d", "-s", session_name],
        capture_output=True,
        text=True,
    )


def create_session(
    name: str,
    *,
    window_name: str | None = None,
    start_directory: str | None = None,
    detach: bool = False,
) -> None:
    """Create a tmux session.

    By default opens a new terminal window attached to the session
    so the user can watch live. Use detach=True for headless sessions.
    """
    # Validate session name
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise TmuxCommandError(
            cmd=["new-session", "-s", name],
            stderr=f"Invalid session name '{name}': only alphanumeric, hyphens, and underscores allowed",
        )

    if session_exists(name):
        raise SessionExistsError(name)

    if detach:
        args = ["new-session", "-d", "-s", name]
        if window_name:
            args.extend(["-n", window_name])
        if start_directory:
            args.extend(["-c", start_directory])
        _run(args)
    else:
        # Open a new terminal window with tmux session attached.
        # -A: attach if exists, create if not.
        tmux_cmd = f"tmux new-session -A -s {shlex.quote(name)}"
        if window_name:
            tmux_cmd += f" -n {shlex.quote(window_name)}"
        if start_directory:
            tmux_cmd += f" -c {shlex.quote(start_directory)}"
        open_terminal_window(tmux_cmd)
        # Wait for the session to appear (Terminal + tmux startup time)
        _wait_for_session(name, timeout=5.0)


def _wait_for_session(name: str, timeout: float = 5.0) -> None:
    """Poll until a tmux session exists or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if session_exists(name):
            return
        time.sleep(0.2)
    raise TmuxCommandError(
        cmd=["new-session", "-s", name],
        stderr=f"Session '{name}' did not appear within {timeout}s",
    )


def list_sessions() -> list[SessionInfo]:
    """List all tmux sessions. Empty list if no server running."""
    result = _run(
        [
            "list-sessions",
            "-F",
            "#{session_name}\t#{session_windows}\t#{session_created_string}\t#{session_attached}",
        ],
        check=False,
    )
    if result.returncode != 0:
        return []
    sessions = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            sessions.append(
                SessionInfo(
                    name=parts[0],
                    windows=int(parts[1]),
                    created=parts[2],
                    attached=parts[3] != "0",
                )
            )
    return sessions


def kill_session(name: str) -> None:
    """Kill a tmux session."""
    require_session(name)
    _run(["kill-session", "-t", name])


# --- Pane operations ---


def resolve_target(session: str, pane: str | None = None) -> str:
    """Build a tmux target string."""
    if pane is not None:
        if not str(pane).isdigit():
            raise TmuxCommandError(
                cmd=["target", str(pane)],
                stderr=f"Invalid pane '{pane}': must be a numeric index",
            )
        return f"{session}:.{pane}"
    return f"{session}:"


def send_keys(
    session: str,
    keys: str,
    *,
    pane: str | None = None,
    enter: bool = True,
    literal: bool = False,
) -> None:
    """Send keystrokes to a tmux pane."""
    require_session(session)
    target = resolve_target(session, pane)
    args = ["send-keys", "-t", target]
    if literal:
        args.append("-l")
    args.append(keys)
    _run(args)
    # When literal mode is on, "Enter" would be sent as text.
    # Send Enter as a separate non-literal key press.
    if enter:
        _run(["send-keys", "-t", target, "Enter"])


def capture_pane(
    session: str,
    *,
    pane: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Capture pane content (and optionally scrollback)."""
    require_session(session)
    target = resolve_target(session, pane)
    args = ["capture-pane", "-p", "-t", target]
    if start_line is not None:
        args.extend(["-S", str(start_line)])
    if end_line is not None:
        args.extend(["-E", str(end_line)])
    result = _run(args)
    return result.stdout.rstrip("\n")
