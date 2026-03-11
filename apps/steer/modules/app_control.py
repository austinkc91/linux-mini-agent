"""Application control on Linux using wmctrl and xdotool."""

import os
import re
import subprocess

from modules.tools import require


def list_apps() -> list[dict]:
    """List running GUI applications with windows."""
    require("wmctrl")
    result = subprocess.run(
        ["wmctrl", "-l", "-p"],
        capture_output=True, text=True,
    )
    apps = {}
    active_wid = _get_active_window_id()

    for line in result.stdout.strip().splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        wid = parts[0]
        pid = int(parts[2]) if parts[2] != "0" else 0
        title = parts[4] if len(parts) > 4 else ""
        # Get process name from PID
        name = _pid_to_name(pid) if pid else title.split(" - ")[-1] if title else "unknown"
        if name not in apps:
            apps[name] = {
                "name": name,
                "pid": pid,
                "bundleId": None,
                "isActive": wid == active_wid,
            }
        elif wid == active_wid:
            apps[name]["isActive"] = True
    return list(apps.values())


def find_app(name: str) -> dict | None:
    """Find a running app by name (case-insensitive)."""
    apps = list_apps()
    name_lower = name.lower()
    for app in apps:
        if app["name"].lower() == name_lower:
            return app
    # Partial match
    for app in apps:
        if name_lower in app["name"].lower():
            return app
    return None


def find_app_windows(name: str) -> list[dict]:
    """Find all windows belonging to an app."""
    require("wmctrl")
    result = subprocess.run(
        ["wmctrl", "-l", "-p", "-G"],
        capture_output=True, text=True,
    )
    windows = []
    name_lower = name.lower()

    for line in result.stdout.strip().splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        wid_str = parts[0]
        pid = int(parts[2]) if parts[2] != "0" else 0
        x, y, w, h = int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6])
        title = parts[8] if len(parts) > 8 else ""

        proc_name = _pid_to_name(pid) if pid else ""
        if (name_lower in proc_name.lower() or
            name_lower in title.lower()):
            wid = int(wid_str, 16) if wid_str.startswith("0x") else int(wid_str)
            windows.append({
                "id": wid,
                "x": x, "y": y,
                "width": w, "height": h,
                "title": title,
                "pid": pid,
            })
    return windows


def activate(name: str) -> None:
    """Activate (bring to front) an app by name."""
    require("wmctrl")
    windows = find_app_windows(name)
    if not windows:
        # Try wmctrl -a which does fuzzy title match
        result = subprocess.run(
            ["wmctrl", "-a", name],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            from modules.errors import AppNotFound
            raise AppNotFound(name)
        return
    # Activate first window
    wid_hex = f"0x{windows[0]['id']:08x}"
    subprocess.run(
        ["wmctrl", "-i", "-a", wid_hex],
        capture_output=True, text=True,
    )


def launch(name: str) -> None:
    """Launch an application by name."""
    # Try common launch methods
    result = subprocess.run(
        ["which", name.lower().replace(" ", "-")],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        subprocess.Popen(
            [result.stdout.strip()],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    # Try xdg-open for desktop entries
    result = subprocess.run(
        ["gtk-launch", f"{name.lower().replace(' ', '-')}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return

    # Try direct command
    subprocess.Popen(
        [name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True,
    )


def frontmost() -> dict | None:
    """Get the frontmost (active) application."""
    wid = _get_active_window_id()
    if not wid:
        return None
    pid = _wid_to_pid(wid)
    name = _pid_to_name(pid) if pid else "unknown"
    return {"name": name, "pid": pid, "bundleId": None, "isActive": True}


def _get_active_window_id() -> str | None:
    """Get the active window ID as hex string."""
    try:
        require("xdotool")
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            wid = int(result.stdout.strip())
            return f"0x{wid:08x}"
    except Exception:
        pass
    return None


def _wid_to_pid(wid_hex: str) -> int:
    """Get PID from window ID."""
    try:
        require("xdotool")
        wid = int(wid_hex, 16) if wid_hex.startswith("0x") else int(wid_hex)
        result = subprocess.run(
            ["xdotool", "getwindowpid", str(wid)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0


def _pid_to_name(pid: int) -> str:
    """Get process name from PID."""
    try:
        comm_path = f"/proc/{pid}/comm"
        if os.path.exists(comm_path):
            with open(comm_path) as f:
                return f.read().strip()
    except Exception:
        pass
    return "unknown"
