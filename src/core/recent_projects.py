"""
Recent projects index — a small local JSON file (not a database) tracking
which .caat files were opened/saved recently, with pinning, for a
Power-BI-Desktop-style "Recent" list on the app's start screen.

This is exactly the kind of local index the plan calls for once .caat files
became the source of truth for project data: cheap metadata about files on
disk, not analytical data itself.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

MAX_ENTRIES = 15


def _index_path() -> Path:
    d = Path.home() / ".caatmaster"
    d.mkdir(parents=True, exist_ok=True)
    return d / "recent_projects.json"


def _load() -> List[Dict[str, Any]]:
    path = _index_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data.get("recent", [])
    except Exception:
        return []


def _save(entries: List[Dict[str, Any]]):
    _index_path().write_text(json.dumps({"recent": entries}, indent=2))


def add_recent(path: str, name: str):
    """Record that `path` was just opened or saved. Moves it to the top."""
    entries = _load()
    entries = [e for e in entries if e.get("path") != path]
    entries.insert(0, {
        "path": path,
        "name": name,
        "last_opened": datetime.now().isoformat(),
        "pinned": False,
    })
    _prune_and_save(entries)


def toggle_pin(path: str):
    entries = _load()
    for e in entries:
        if e.get("path") == path:
            e["pinned"] = not e.get("pinned", False)
    _prune_and_save(entries)


def remove_recent(path: str):
    entries = [e for e in _load() if e.get("path") != path]
    _save(entries)


def list_recent(limit: int = MAX_ENTRIES) -> List[Dict[str, Any]]:
    """Pinned entries first (by last_opened desc), then unpinned (by last_opened desc).
    Entries whose file no longer exists are silently dropped."""
    entries = [e for e in _load() if Path(e.get("path", "")).exists()]
    pinned = sorted([e for e in entries if e.get("pinned")], key=lambda e: e.get("last_opened", ""), reverse=True)
    unpinned = sorted([e for e in entries if not e.get("pinned")], key=lambda e: e.get("last_opened", ""), reverse=True)
    return (pinned + unpinned)[:limit]


def _prune_and_save(entries: List[Dict[str, Any]]):
    """Keep all pinned entries plus enough unpinned ones to reach MAX_ENTRIES —
    pinning should protect an entry from ever being aged out."""
    pinned = [e for e in entries if e.get("pinned")]
    unpinned = sorted(
        [e for e in entries if not e.get("pinned")],
        key=lambda e: e.get("last_opened", ""), reverse=True
    )
    keep_unpinned = max(0, MAX_ENTRIES - len(pinned))
    _save(pinned + unpinned[:keep_unpinned])
