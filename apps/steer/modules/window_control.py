"""Window management using wmctrl and xdotool on Linux."""

import subprocess
from dataclasses import dataclass

from modules.app_control import find_app_windows, activate
from modules.errors import AppNotFound, WindowNotFound, WindowActionFailed
from modules.tools import require


@dataclass
class WinInfo:
    app: str
    title: str
    x: int
    y: int
    width: int
    height: int
    is_minimized: bool
    is_fullscreen: bool

    def to_dict(self) -> dict:
        return {
            "app": self.app,
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "isMinimized": self.is_minimized,
            "isFullscreen": self.is_fullscreen,
        }


def list_windows(app_name: str) -> list[WinInfo]:
    """List all windows for an app."""
    windows = find_app_windows(app_name)
    if not windows:
        return []
    results = []
    for w in windows:
        # Check window state via xprop
        is_min = _is_minimized(w["id"])
        is_full = _is_fullscreen(w["id"])
        results.append(WinInfo(
            app=app_name,
            title=w.get("title", ""),
            x=w["x"], y=w["y"],
            width=w["width"], height=w["height"],
            is_minimized=is_min,
            is_fullscreen=is_full,
        ))
    return results


def move(app_name: str, x: float, y: float) -> None:
    """Move the focused window of an app."""
    require("wmctrl")
    windows = find_app_windows(app_name)
    if not windows:
        raise WindowNotFound(app_name)
    wid_hex = f"0x{windows[0]['id']:08x}"
    result = subprocess.run(
        ["wmctrl", "-i", "-r", wid_hex, "-e", f"0,{int(x)},{int(y)},-1,-1"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise WindowActionFailed("move", app_name)


def resize(app_name: str, width: float, height: float) -> None:
    """Resize the focused window of an app."""
    require("wmctrl")
    windows = find_app_windows(app_name)
    if not windows:
        raise WindowNotFound(app_name)
    wid_hex = f"0x{windows[0]['id']:08x}"
    result = subprocess.run(
        ["wmctrl", "-i", "-r", wid_hex, "-e", f"0,-1,-1,{int(width)},{int(height)}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise WindowActionFailed("resize", app_name)


def minimize(app_name: str, flag: bool = True) -> None:
    """Minimize or restore a window."""
    require("xdotool")
    windows = find_app_windows(app_name)
    if not windows:
        raise WindowNotFound(app_name)
    wid = str(windows[0]["id"])
    if flag:
        subprocess.run(
            ["xdotool", "windowminimize", wid],
            capture_output=True, text=True,
        )
    else:
        subprocess.run(
            ["xdotool", "windowactivate", wid],
            capture_output=True, text=True,
        )


def fullscreen(app_name: str) -> None:
    """Toggle fullscreen for a window."""
    require("wmctrl")
    windows = find_app_windows(app_name)
    if not windows:
        raise WindowNotFound(app_name)
    wid_hex = f"0x{windows[0]['id']:08x}"
    subprocess.run(
        ["wmctrl", "-i", "-r", wid_hex, "-b", "toggle,fullscreen"],
        capture_output=True, text=True,
    )


def close(app_name: str) -> None:
    """Close a window."""
    require("wmctrl")
    windows = find_app_windows(app_name)
    if not windows:
        raise WindowNotFound(app_name)
    wid_hex = f"0x{windows[0]['id']:08x}"
    subprocess.run(
        ["wmctrl", "-i", "-c", wid_hex],
        capture_output=True, text=True,
    )


def _is_minimized(wid: int) -> bool:
    """Check if a window is minimized using xprop."""
    try:
        result = subprocess.run(
            ["xprop", "-id", str(wid), "_NET_WM_STATE"],
            capture_output=True, text=True,
        )
        return "_NET_WM_STATE_HIDDEN" in result.stdout
    except Exception:
        return False


def _is_fullscreen(wid: int) -> bool:
    """Check if a window is fullscreen using xprop."""
    try:
        result = subprocess.run(
            ["xprop", "-id", str(wid), "_NET_WM_STATE"],
            capture_output=True, text=True,
        )
        return "_NET_WM_STATE_FULLSCREEN" in result.stdout
    except Exception:
        return False
