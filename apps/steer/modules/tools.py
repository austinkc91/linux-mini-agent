"""Tool availability checks for Linux dependencies."""

import os
import re
import shutil
import subprocess

from modules.errors import SteerError, ToolNotFound


def require(tool: str) -> str:
    """Return path to a required tool binary, or raise ToolNotFound."""
    path = shutil.which(tool)
    if path is None:
        hints = {
            "xdotool": "sudo apt install xdotool",
            "scrot": "sudo apt install scrot",
            "tesseract": "sudo apt install tesseract-ocr",
            "xclip": "sudo apt install xclip",
            "wmctrl": "sudo apt install wmctrl",
            "xprop": "sudo apt install x11-utils",
            "xwininfo": "sudo apt install x11-utils",
            "xrandr": "sudo apt install x11-xserver-utils",
            "import": "sudo apt install imagemagick",
        }
        raise ToolNotFound(tool, hints.get(tool, f"sudo apt install {tool}"))
    return path


def _detect_display() -> str | None:
    """Auto-detect a working X11 display by checking common displays and Xvfb."""
    for display in (":99", ":0", ":1"):
        try:
            result = subprocess.run(
                ["xdpyinfo"],
                capture_output=True, text=True, timeout=3,
                env={**os.environ, "DISPLAY": display},
            )
            if result.returncode == 0:
                return display
        except Exception:
            continue

    # Parse Xvfb process for display number
    try:
        result = subprocess.run(
            ["pgrep", "-a", "Xvfb"], capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            match = re.search(r":(\d+)", result.stdout)
            if match:
                return f":{match.group(1)}"
    except Exception:
        pass
    return None


def ensure_display() -> str:
    """Ensure DISPLAY is set to a working X11 display. Auto-detects if needed."""
    display = os.environ.get("DISPLAY")

    # If DISPLAY is set, verify it works
    if display:
        try:
            result = subprocess.run(
                ["xdpyinfo"], capture_output=True, text=True, timeout=3,
                env={**os.environ, "DISPLAY": display},
            )
            if result.returncode == 0:
                return display
        except Exception:
            pass

    # DISPLAY not set or not working — auto-detect
    detected = _detect_display()
    if detected:
        os.environ["DISPLAY"] = detected
        return detected

    raise SteerError(
        "No working X11 display found. Set DISPLAY or start Xvfb."
    )


def check_display() -> str:
    """Return the DISPLAY environment variable, raising if unset."""
    return ensure_display()
