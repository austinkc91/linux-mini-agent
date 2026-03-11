"""Accessibility tree walking using AT-SPI on Linux.

Falls back gracefully if python-atspi is not available.
"""

import subprocess
from modules.tools import require


def is_available() -> bool:
    """Check if AT-SPI accessibility is available."""
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
        return True
    except (ImportError, ValueError):
        return False


def walk(app_name: str, max_depth: int = 10) -> list[dict]:
    """Walk the accessibility tree for an app.

    Returns list of UIElement-compatible dicts.
    """
    if not is_available():
        return []

    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        desktop = Atspi.get_desktop(0)
        target = None

        # Find the app
        for i in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(i)
            if app and app_name.lower() in (app.get_name() or "").lower():
                target = app
                break

        if target is None:
            return []

        elements = []
        _walk_element(target, 0, max_depth, elements)

        # Filter to interactive elements and assign IDs
        visible = [e for e in elements if e["width"] > 1 and e["height"] > 1 and _is_interactive(e["role"])]
        return _assign_ids(visible)

    except Exception:
        return []


def focused_element(app_name: str | None = None) -> dict | None:
    """Get the currently focused UI element."""
    if not is_available():
        return None

    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        desktop = Atspi.get_desktop(0)

        # Search apps for focused element
        for i in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(i)
            if app is None:
                continue
            if app_name and app_name.lower() not in (app.get_name() or "").lower():
                continue

            focused = _find_focused(app)
            if focused:
                return focused

        return None

    except Exception:
        return None


def _walk_element(el, depth: int, max_depth: int, out: list[dict]) -> None:
    """Recursively walk an AT-SPI element tree."""
    if depth >= max_depth:
        return

    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        role = el.get_role_name() or "unknown"
        name = el.get_name() or ""
        description = el.get_description() or ""

        # Get position and size
        try:
            component = el.get_component_iface()
            if component:
                rect = component.get_extents(Atspi.CoordType.SCREEN)
                x, y, w, h = rect.x, rect.y, rect.width, rect.height
            else:
                x, y, w, h = 0, 0, 0, 0
        except Exception:
            x, y, w, h = 0, 0, 0, 0

        # Get value if available
        value = None
        try:
            text_iface = el.get_text_iface()
            if text_iface:
                value = text_iface.get_text(0, text_iface.get_character_count())
        except Exception:
            pass

        label = name or description
        out.append({
            "role": role,
            "label": label,
            "value": value,
            "x": x, "y": y,
            "width": w, "height": h,
            "isEnabled": True,
            "depth": depth,
        })

        # Walk children
        for i in range(el.get_child_count()):
            child = el.get_child_at_index(i)
            if child:
                _walk_element(child, depth + 1, max_depth, out)

    except Exception:
        pass


def _find_focused(el) -> dict | None:
    """Find the focused element in a tree."""
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        state_set = el.get_state_set()
        if state_set and state_set.contains(Atspi.StateType.FOCUSED):
            role = el.get_role_name() or "unknown"
            name = el.get_name() or ""

            try:
                component = el.get_component_iface()
                if component:
                    rect = component.get_extents(Atspi.CoordType.SCREEN)
                    x, y, w, h = rect.x, rect.y, rect.width, rect.height
                else:
                    x, y, w, h = 0, 0, 0, 0
            except Exception:
                x, y, w, h = 0, 0, 0, 0

            value = None
            try:
                text_iface = el.get_text_iface()
                if text_iface:
                    value = text_iface.get_text(0, text_iface.get_character_count())
            except Exception:
                pass

            return {
                "id": "F0",
                "role": role,
                "label": name,
                "value": value,
                "x": x, "y": y,
                "width": w, "height": h,
                "isEnabled": True,
                "depth": 0,
            }

        for i in range(el.get_child_count()):
            child = el.get_child_at_index(i)
            if child:
                result = _find_focused(child)
                if result:
                    return result

    except Exception:
        pass
    return None


def _is_interactive(role: str) -> bool:
    """Check if a role is considered interactive."""
    interactive_roles = {
        "push button", "toggle button", "radio button", "check box",
        "text", "password text", "entry", "combo box",
        "menu item", "menu", "menu bar",
        "link", "slider", "spin button",
        "tab", "tool bar", "label", "image",
        "list item", "tree item", "cell",
    }
    return role.lower() in interactive_roles


def _assign_ids(elements: list[dict]) -> list[dict]:
    """Assign role-based IDs to elements."""
    prefix_map = {
        "push button": "B", "toggle button": "B",
        "text": "T", "entry": "T", "password text": "T", "combo box": "T",
        "label": "S",
        "image": "I",
        "check box": "C",
        "radio button": "R",
        "combo box": "P",
        "slider": "SL", "spin button": "SL",
        "link": "L",
        "menu item": "M", "menu bar": "M", "menu": "M",
        "tab": "TB",
        "list item": "E", "tree item": "E", "cell": "E",
    }

    counts: dict[str, int] = {}
    result = []
    for el in elements:
        prefix = prefix_map.get(el["role"].lower(), "E")
        counts[prefix] = counts.get(prefix, 0) + 1
        el["id"] = f"{prefix}{counts[prefix]}"
        result.append(el)
    return result
