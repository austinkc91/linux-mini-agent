"""Keyboard control using xdotool on Linux."""

import subprocess

from modules.tools import require

_SUBPROCESS_TIMEOUT = 10

# Map macOS-style modifier names to xdotool key names
MODIFIER_MAP = {
    "cmd": "super",
    "command": "super",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "shift": "shift",
    "fn": "fn",
    "super": "super",
    "meta": "super",
}

# Map key names to xdotool key names
KEY_MAP = {
    "return": "Return",
    "enter": "Return",
    "tab": "Tab",
    "space": "space",
    "delete": "BackSpace",
    "backspace": "BackSpace",
    "escape": "Escape",
    "esc": "Escape",
    "left": "Left",
    "right": "Right",
    "down": "Down",
    "up": "Up",
    "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4",
    "f5": "F5", "f6": "F6", "f7": "F7", "f8": "F8",
    "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",
    "home": "Home",
    "end": "End",
    "pageup": "Prior",
    "pagedown": "Next",
    "forwarddelete": "Delete",
}


def type_text(text: str) -> None:
    """Type a string of text."""
    require("xdotool")
    subprocess.run(
        ["xdotool", "type", "--clearmodifiers", "--delay", "8", text],
        capture_output=True, timeout=_SUBPROCESS_TIMEOUT,
    )


def hotkey(combo: str) -> None:
    """Execute a hotkey combo like 'ctrl+s', 'alt+tab', 'return'.

    Maps macOS-style combos (cmd+s) to Linux equivalents (super+s).
    """
    require("xdotool")
    parts = combo.lower().split("+")
    xdo_keys = []
    for part in parts:
        part = part.strip()
        if part in MODIFIER_MAP:
            xdo_keys.append(MODIFIER_MAP[part])
        elif part in KEY_MAP:
            xdo_keys.append(KEY_MAP[part])
        elif len(part) == 1:
            xdo_keys.append(part)
        else:
            xdo_keys.append(part)

    key_combo = "+".join(xdo_keys)
    subprocess.run(
        ["xdotool", "key", "--clearmodifiers", key_combo],
        capture_output=True, timeout=_SUBPROCESS_TIMEOUT,
    )


def parse_modifiers(combo: str) -> list[str]:
    """Parse modifier string into list of xdotool modifier names."""
    mods = []
    for part in combo.lower().split("+"):
        part = part.strip()
        if part in MODIFIER_MAP:
            mods.append(MODIFIER_MAP[part])
    return mods
