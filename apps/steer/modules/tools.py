"""Tool availability checks for Linux dependencies."""

import shutil

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


def check_display() -> str:
    """Return the DISPLAY environment variable, raising if unset."""
    import os
    display = os.environ.get("DISPLAY")
    if not display:
        raise SteerError("DISPLAY environment variable not set. An X11 session is required.")
    return display
