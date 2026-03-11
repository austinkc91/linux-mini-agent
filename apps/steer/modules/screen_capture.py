"""Screen capture using scrot/import on Linux (X11)."""

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass

from modules.errors import CaptureFailure, ScreenNotFound
from modules.tools import require


@dataclass
class ScreenInfo:
    index: int
    name: str
    width: int
    height: int
    origin_x: int
    origin_y: int
    is_main: bool
    scale_factor: float

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "originX": self.origin_x,
            "originY": self.origin_y,
            "isMain": self.is_main,
            "scaleFactor": self.scale_factor,
        }


@dataclass
class WindowBounds:
    window_x: int
    window_y: int
    window_width: int
    window_height: int
    window_title: str | None
    window_id: int

    def to_dict(self) -> dict:
        return {
            "windowX": self.window_x,
            "windowY": self.window_y,
            "windowWidth": self.window_width,
            "windowHeight": self.window_height,
            "windowTitle": self.window_title,
            "windowID": self.window_id,
        }


def list_screens() -> list[ScreenInfo]:
    """List connected displays using xrandr."""
    require("xrandr")
    result = subprocess.run(
        ["xrandr", "--query"], capture_output=True, text=True
    )
    screens = []
    # Parse xrandr output for connected displays
    pattern = re.compile(
        r"^(\S+)\s+connected\s+(?:primary\s+)?(\d+)x(\d+)\+(\d+)\+(\d+)",
        re.MULTILINE,
    )
    for i, m in enumerate(pattern.finditer(result.stdout)):
        name, w, h, ox, oy = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        is_main = "primary" in result.stdout.split(name)[1].split("\n")[0]
        screens.append(ScreenInfo(
            index=i, name=name,
            width=w, height=h,
            origin_x=ox, origin_y=oy,
            is_main=is_main,
            scale_factor=1.0,
        ))
    return screens


def screen_info(index: int) -> ScreenInfo | None:
    """Get info for a specific screen by index."""
    screens = list_screens()
    if 0 <= index < len(screens):
        return screens[index]
    return None


def capture_display(output_path: str | None = None) -> str:
    """Capture the entire display. Returns path to PNG."""
    require("scrot")
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".png", dir=_steer_dir())
    subprocess.run(
        ["scrot", "--overwrite", output_path],
        capture_output=True, text=True, check=True,
    )
    if not os.path.exists(output_path):
        raise CaptureFailure("scrot did not produce output file")
    return output_path


def capture_screen(index: int, output_path: str | None = None) -> str:
    """Capture a specific screen by index. Returns path to PNG."""
    screens = list_screens()
    if index < 0 or index >= len(screens):
        raise ScreenNotFound(index, len(screens))
    screen = screens[index]
    require("scrot")
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".png", dir=_steer_dir())
    # Use scrot with area selection for specific monitor
    area = f"{screen.width}x{screen.height}+{screen.origin_x}+{screen.origin_y}"
    subprocess.run(
        ["scrot", "--overwrite", "-a", area, output_path],
        capture_output=True, text=True,
    )
    # If -a not supported, fall back to full capture and crop
    if not os.path.exists(output_path):
        full_path = capture_display()
        _crop_image(full_path, output_path, screen.origin_x, screen.origin_y, screen.width, screen.height)
        os.unlink(full_path)
    return output_path


def capture_window(window_id: int, output_path: str | None = None) -> str:
    """Capture a specific window by ID. Returns path to PNG."""
    require("import")
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".png", dir=_steer_dir())
    result = subprocess.run(
        ["import", "-window", str(window_id), output_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not os.path.exists(output_path):
        # Fall back to scrot with window focus
        return capture_display(output_path)
    return output_path


def capture_app(app_name: str, output_path: str | None = None) -> str:
    """Capture windows belonging to an app. Returns path to PNG."""
    from modules.app_control import find_app_windows
    windows = find_app_windows(app_name)
    if windows:
        return capture_window(windows[0]["id"], output_path)
    return capture_display(output_path)


def window_bounds(app_name: str) -> list[WindowBounds]:
    """Get window bounds for an app."""
    from modules.app_control import find_app_windows
    windows = find_app_windows(app_name)
    bounds = []
    for w in windows:
        if w["width"] > 1 and w["height"] > 1:
            bounds.append(WindowBounds(
                window_x=w["x"], window_y=w["y"],
                window_width=w["width"], window_height=w["height"],
                window_title=w.get("title"),
                window_id=w["id"],
            ))
    return bounds


def _steer_dir() -> str:
    """Ensure and return the steer temp directory."""
    d = os.path.join(tempfile.gettempdir(), "steer")
    os.makedirs(d, exist_ok=True)
    return d


def _crop_image(src: str, dst: str, x: int, y: int, w: int, h: int) -> None:
    """Crop an image using PIL."""
    from PIL import Image
    img = Image.open(src)
    cropped = img.crop((x, y, x + w, y + h))
    cropped.save(dst)
