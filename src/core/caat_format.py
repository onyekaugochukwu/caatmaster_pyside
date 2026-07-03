"""
.caat portable project file format.

A .caat file is a zip container — the same trick most modern document
formats already use — holding everything needed to reopen and continue an
audit engagement on another machine: for every dataset, the untouched
source snapshot plus the ordered list of transformation steps applied to
it, and project-level metadata. Storing source + steps (not just the
transformed result) is what makes "Refresh" possible — re-read the source
and replay the steps — and it's what keeps the file small and the steps
themselves diffable in plain text.

Layout:
    manifest.json           format_version, app_version, project id, author
    project.json            name, client, engagement type, risk score, tags
    datasets/<id>/source.parquet   the original imported snapshot, untouched
    datasets/<id>/steps.json       ordered transformation steps + metadata
    relationships.json       join/append lineage between datasets (seed for
                              a future dataset-dependency view)
    ui_state.json             last active dataset, for resuming on reopen

JSON/JSONL is used deliberately instead of a binary blob: an auditor's
review file should be inspectable without CaatMaster installed, and two
versions of a project should be meaningfully diffable.
"""
import json
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import polars as pl

from .project_manager import Project, Dataset

CAAT_FORMAT_VERSION = 1
APP_VERSION = "1.0.0"
CAAT_EXTENSION = ".caat"


class CaatFormatError(ValueError):
    """Raised for invalid or unsupported .caat files."""


def save_caat(project: Project, file_path: str, author: Optional[str] = None,
              active_dataset_id: Optional[str] = None) -> str:
    """Save a Project as a .caat file — the app's native save format.

    Each dataset's *original* (pre-transformation) data is written to
    Parquet, and its transformation steps (including disabled ones) are
    written alongside as JSON — never the transformed result — so the file
    can always be refreshed and replayed.

    Saves to `file_path` exactly as given (including e.g. an
    "x.caat.autosave" recovery path) — callers that need to enforce the
    ".caat" extension for a user-facing Save dialog should do so themselves
    before calling this.
    """
    path = Path(file_path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        manifest = {
            "format_version": CAAT_FORMAT_VERSION,
            "app_version": APP_VERSION,
            "project_id": project.id,
            "author": author,
            "saved_at": datetime.now().isoformat(),
        }
        (tmp_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        project_meta = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "client_name": project.client_name,
            "phase": project.phase,
            "engagement_type": project.engagement_type,
            "risk_score": project.risk_score,
            "objectives": project.objectives,
            "metadata": project.metadata,
            "parameters": project.parameters,
        }
        (tmp_dir / "project.json").write_text(json.dumps(project_meta, indent=2, default=str))

        datasets_dir = tmp_dir / "datasets"
        datasets_dir.mkdir()

        for dataset in project.list_datasets():
            ds_dir = datasets_dir / dataset.id
            ds_dir.mkdir()

            pipeline = dataset.transformation_pipeline
            source_df = pipeline.original_df if pipeline is not None else dataset.original_dataframe
            if source_df is None:
                source_df = pl.DataFrame()
            source_df.write_parquet(ds_dir / "source.parquet")

            dataset_meta = dataset.to_dict()
            (ds_dir / "steps.json").write_text(json.dumps(dataset_meta, indent=2, default=str))

        # Seeds for future features (dataset lineage view) plus the actual
        # last-active-dataset state, so reopening a project resumes on the
        # same dataset instead of always defaulting to the first one.
        (tmp_dir / "relationships.json").write_text(json.dumps({"joins": [], "appends": []}, indent=2))
        (tmp_dir / "ui_state.json").write_text(json.dumps({"last_active_dataset_id": active_dataset_id}, indent=2))

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in tmp_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(tmp_dir))

    return str(path)


def load_caat(file_path: str) -> Project:
    """Load a Project from a .caat file, replaying each dataset's steps
    against its stored source snapshot."""
    path = Path(file_path)
    if not path.exists():
        raise CaatFormatError(f"File not found: {path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        try:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(tmp_dir)
        except zipfile.BadZipFile:
            raise CaatFormatError(f"'{path.name}' is not a valid .caat file.")

        manifest_path = tmp_dir / "manifest.json"
        if not manifest_path.exists():
            raise CaatFormatError(f"'{path.name}' is not a valid .caat file: missing manifest.json")
        manifest = json.loads(manifest_path.read_text())

        format_version = manifest.get("format_version", 1)
        if format_version > CAAT_FORMAT_VERSION:
            raise CaatFormatError(
                f"'{path.name}' was saved with a newer version of CaatMaster "
                f"(.caat format v{format_version}); this version supports up to "
                f"v{CAAT_FORMAT_VERSION}. Please update CaatMaster to open it."
            )

        project_meta_path = tmp_dir / "project.json"
        if not project_meta_path.exists():
            raise CaatFormatError(f"'{path.name}' is not a valid .caat file: missing project.json")
        project_meta = json.loads(project_meta_path.read_text())
        project = Project.from_dict(project_meta)

        datasets_dir = tmp_dir / "datasets"
        if datasets_dir.exists():
            for ds_dir in sorted(datasets_dir.iterdir()):
                if not ds_dir.is_dir():
                    continue
                source_path = ds_dir / "source.parquet"
                steps_path = ds_dir / "steps.json"
                if not source_path.exists() or not steps_path.exists():
                    continue

                source_df = pl.read_parquet(source_path)
                dataset_meta = json.loads(steps_path.read_text())
                dataset = Dataset.from_dict(dataset_meta, source_df)
                project.add_dataset(dataset)

        # Not part of Project's own data model (it's UI resume-state, not
        # project data) — stashed as a plain attribute so callers can restore
        # which dataset was active without every Project needing this field.
        project.last_active_dataset_id = None
        ui_state_path = tmp_dir / "ui_state.json"
        if ui_state_path.exists():
            try:
                ui_state = json.loads(ui_state_path.read_text())
                project.last_active_dataset_id = ui_state.get("last_active_dataset_id")
            except Exception:
                pass

    return project


def peek_caat_metadata(file_path: str) -> dict:
    """Read just manifest.json + project.json (and count dataset folders)
    from a .caat file without extracting any parquet data — cheap enough to
    call for every file in a projects list without loading each one fully.
    """
    path = Path(file_path)
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("manifest.json")) if "manifest.json" in names else {}
        project_meta = json.loads(zf.read("project.json")) if "project.json" in names else {}
        dataset_ids = {n.split("/")[1] for n in names if n.startswith("datasets/") and "/" in n[len("datasets/"):]}

    return {
        "name": project_meta.get("name", path.stem),
        "client_name": project_meta.get("client_name"),
        "engagement_type": project_meta.get("engagement_type"),
        "phase": project_meta.get("phase"),
        "risk_score": project_meta.get("risk_score"),
        "description": project_meta.get("description"),
        "objectives": project_meta.get("objectives"),
        "dataset_count": len(dataset_ids),
        "saved_at": manifest.get("saved_at"),
        "author": manifest.get("author"),
        "path": str(path),
    }


def is_caat_file(file_path: str) -> bool:
    return Path(file_path).suffix == CAAT_EXTENSION
