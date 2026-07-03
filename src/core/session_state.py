"""
Session state — remembers which project was open when the app last closed,
so launching CaatMaster resumes it automatically (like reopening a Word
document), unless the user explicitly closed the project first.

Deliberately separate from recent_projects.py: the recent list is ordered
for a "Recent" picker (pinned entries can sit at the top regardless of what
was last active), which isn't the same question as "what should auto-open
next launch."
"""
import json
from pathlib import Path
from typing import Optional


def _state_path() -> Path:
    d = Path.home() / ".caatmaster"
    d.mkdir(parents=True, exist_ok=True)
    return d / "session_state.json"


def set_active_project(path: Optional[str]):
    """Record which project is currently open. Pass None when the user
    explicitly closes a project, so the next launch starts empty instead of
    resuming it."""
    try:
        _state_path().write_text(json.dumps({"active_project_path": path}, indent=2))
    except Exception:
        pass  # Session resume is a convenience, never worth crashing over


def get_active_project() -> Optional[str]:
    path = _state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("active_project_path")
    except Exception:
        return None
