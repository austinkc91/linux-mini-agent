"""Element store for persisting UI element snapshots."""

import json
import os
import tempfile
from pathlib import Path


_cache: dict[str, list[dict]] = {}
STORE_DIR = os.path.join(tempfile.gettempdir(), "steer")


def save(snap_id: str, elements: list[dict]) -> None:
    """Save elements to cache and disk."""
    _cache[snap_id] = elements
    os.makedirs(STORE_DIR, exist_ok=True)
    path = os.path.join(STORE_DIR, f"{snap_id}.json")
    with open(path, "w") as f:
        json.dump(elements, f, indent=2)


def load(snap_id: str) -> list[dict] | None:
    """Load elements from cache or disk."""
    if snap_id in _cache:
        return _cache[snap_id]
    path = os.path.join(STORE_DIR, f"{snap_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        els = json.load(f)
    _cache[snap_id] = els
    return els


def latest() -> tuple[str, list[dict]] | None:
    """Get the most recent snapshot."""
    # Check in-memory cache first
    if _cache:
        snap_id = max(_cache.keys())
        return (snap_id, _cache[snap_id])
    # Fall back to disk
    if not os.path.exists(STORE_DIR):
        return None
    json_files = [
        f for f in os.listdir(STORE_DIR) if f.endswith(".json")
    ]
    if not json_files:
        return None
    # Sort by modification time, newest first
    json_files.sort(
        key=lambda f: os.path.getmtime(os.path.join(STORE_DIR, f)),
        reverse=True,
    )
    snap_id = json_files[0].removesuffix(".json")
    with open(os.path.join(STORE_DIR, json_files[0])) as f:
        els = json.load(f)
    _cache[snap_id] = els
    return (snap_id, els)


def resolve(query: str, snap: str | None = None) -> dict:
    """Resolve an element by ID or label.

    Raises KeyError if not found.
    """
    from modules.errors import ElementNotFound, NoSnapshot

    if snap:
        els = load(snap)
        if els is None:
            raise NoSnapshot()
    else:
        result = latest()
        if result is None:
            raise NoSnapshot()
        els = result[1]

    lq = query.lower()

    # Exact ID match
    for el in els:
        if el.get("id", "").lower() == lq:
            return el
    # Exact label match
    for el in els:
        if el.get("label", "").lower() == lq:
            return el
    # Partial label match
    for el in els:
        if lq in el.get("label", "").lower():
            return el

    raise ElementNotFound(query)


def center_of(el: dict) -> tuple[int, int]:
    """Get center coordinates of an element."""
    return (el["x"] + el["width"] // 2, el["y"] + el["height"] // 2)
