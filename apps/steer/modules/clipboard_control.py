"""Clipboard control using xclip on Linux."""

import os
import subprocess
import tempfile

from modules.errors import ClipboardEmpty
from modules.tools import require


def read_text() -> str | None:
    """Read text from the clipboard."""
    require("xclip")
    result = subprocess.run(
        ["xclip", "-selection", "clipboard", "-o"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def write_text(text: str) -> None:
    """Write text to the clipboard."""
    require("xclip")
    proc = subprocess.Popen(
        ["xclip", "-selection", "clipboard"],
        stdin=subprocess.PIPE,
    )
    proc.communicate(input=text.encode())


def read_image(save_to: str | None = None) -> str:
    """Read an image from the clipboard and save to file. Returns path."""
    require("xclip")
    result = subprocess.run(
        ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        raise ClipboardEmpty("image")

    if save_to is None:
        steer_dir = os.path.join(tempfile.gettempdir(), "steer")
        os.makedirs(steer_dir, exist_ok=True)
        import uuid
        save_to = os.path.join(steer_dir, f"clipboard-{uuid.uuid4().hex[:8]}.png")

    with open(save_to, "wb") as f:
        f.write(result.stdout)
    return save_to


def write_image(from_path: str) -> None:
    """Write an image file to the clipboard."""
    require("xclip")
    if not os.path.exists(from_path):
        raise ClipboardEmpty(f"image at {from_path}")
    subprocess.run(
        ["xclip", "-selection", "clipboard", "-t", "image/png", "-i", from_path],
        capture_output=True,
    )
