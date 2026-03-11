"""Mouse control using xdotool on Linux."""

import subprocess
import time

from modules.tools import require


def click(
    x: float,
    y: float,
    button: int = 1,
    count: int = 1,
    modifiers: list[str] | None = None,
) -> None:
    """Click at coordinates.

    button: 1=left, 2=middle, 3=right
    """
    require("xdotool")
    args = ["xdotool"]
    if modifiers:
        args.extend(["key", "--clearmodifiers"])

    # Move mouse first
    subprocess.run(
        ["xdotool", "mousemove", "--sync", str(int(x)), str(int(y))],
        capture_output=True,
    )
    time.sleep(0.02)

    # Build click command
    cmd = ["xdotool", "click"]
    if modifiers:
        for mod in modifiers:
            cmd.extend(["--clearmodifiers"])
            break
    cmd.extend(["--repeat", str(count)])
    cmd.append(str(button))
    subprocess.run(cmd, capture_output=True)


def drag(
    from_x: float,
    from_y: float,
    to_x: float,
    to_y: float,
    steps: int = 20,
    modifiers: list[str] | None = None,
) -> None:
    """Drag from one point to another."""
    require("xdotool")
    # Move to start
    subprocess.run(
        ["xdotool", "mousemove", "--sync", str(int(from_x)), str(int(from_y))],
        capture_output=True,
    )
    time.sleep(0.05)
    # mousedown
    subprocess.run(["xdotool", "mousedown", "1"], capture_output=True)
    time.sleep(0.1)
    # Interpolate drag
    for i in range(1, steps + 1):
        t = i / steps
        cx = from_x + (to_x - from_x) * t
        cy = from_y + (to_y - from_y) * t
        subprocess.run(
            ["xdotool", "mousemove", "--sync", str(int(cx)), str(int(cy))],
            capture_output=True,
        )
        time.sleep(0.01)
    time.sleep(0.05)
    # mouseup
    subprocess.run(["xdotool", "mouseup", "1"], capture_output=True)


def move_to(x: float, y: float) -> None:
    """Move mouse cursor to coordinates."""
    require("xdotool")
    subprocess.run(
        ["xdotool", "mousemove", "--sync", str(int(x)), str(int(y))],
        capture_output=True,
    )


def scroll(direction: str, lines: int = 3) -> None:
    """Scroll in a direction by N lines.

    xdotool uses button 4=up, 5=down, 6=left, 7=right
    """
    require("xdotool")
    button_map = {"up": "4", "down": "5", "left": "6", "right": "7"}
    btn = button_map.get(direction.lower())
    if btn is None:
        raise ValueError(f"Direction must be: up, down, left, right")
    for _ in range(lines):
        subprocess.run(["xdotool", "click", btn], capture_output=True)
        time.sleep(0.02)
