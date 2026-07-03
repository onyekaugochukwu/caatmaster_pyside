"""
Audit Programs — reusable, named sequences of transformation steps.

A firm typically reruns the same audit procedures (three-way match, Benford's
Law on a GL extract, duplicate-payment detection, ...) on a new client's
data every engagement. An Audit Program captures a dataset's current
Applied Steps as a named, reusable template that can be applied to any other
dataset later — a genuine differentiator over stock Power Query, which has
no equivalent concept.

Stored as plain JSON files (one per program) under
~/Documents/CaatMaster/AuditPrograms/ — consistent with the rest of the
app's "inspectable, no database required" file philosophy.
"""
import json
from pathlib import Path
from typing import Any, Dict, List


def _programs_dir() -> Path:
    d = Path.home() / "Documents" / "CaatMaster" / "AuditPrograms"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name).strip() or "Untitled"


def list_programs() -> List[Dict[str, Any]]:
    """Return [{name, description, step_count}] for every saved program."""
    programs = []
    for f in sorted(_programs_dir().glob("*.json")):
        try:
            data = json.loads(f.read_text())
            programs.append({
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "step_count": len(data.get("steps", [])),
                "file_path": str(f),
            })
        except Exception:
            continue
    return programs


def save_program(name: str, description: str, steps: List[Dict[str, Any]]) -> str:
    """Save a named program. `steps` is a list of {operation_id, params}."""
    if not name or not name.strip():
        raise ValueError("Program name is required.")

    data = {
        "name": name.strip(),
        "description": description or "",
        "steps": [{"operation_id": s["operation_id"], "params": s["params"]} for s in steps],
    }
    path = _programs_dir() / f"{_safe_filename(name)}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    return str(path)


def load_program(file_path: str) -> Dict[str, Any]:
    """Load a program by its file path (as returned in list_programs())."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audit program not found: {file_path}")
    return json.loads(path.read_text())


def delete_program(file_path: str):
    path = Path(file_path)
    if path.exists():
        path.unlink()
