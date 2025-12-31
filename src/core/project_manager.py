"""
Project Manager
Handles project creation, serialization, and dataset management with embedded pipeline metadata.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import polars as pl
import zipfile
import io


class Dataset:
    """Represents a dataset with transformation pipeline metadata."""

    def __init__(self, id: str = None, name: str = "", dataframe: pl.DataFrame = None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.original_dataframe: pl.DataFrame = dataframe
        self.transformation_pipeline = None
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "row_count": len(dataframe) if dataframe is not None else 0,
            "column_count": len(dataframe.columns) if dataframe is not None else 0,
            "columns": list(dataframe.columns) if dataframe is not None else []
        }

    def set_pipeline(self, pipeline):
        """Set the transformation pipeline for this dataset."""
        self.transformation_pipeline = pipeline

    def get_current_dataframe(self) -> pl.DataFrame:
        """Get the current state of the dataframe after all transformations."""
        if self.transformation_pipeline:
            return self.transformation_pipeline.apply()
        return self.original_dataframe

    def to_dict(self) -> Dict[str, Any]:
        """Serialize dataset to dictionary."""
        # Get current dataframe state
        current_df = self.get_current_dataframe()

        # Serialize pipeline steps
        pipeline_data = None
        if self.transformation_pipeline:
            pipeline_data = {
                "steps": [
                    {
                        "operation_id": step.operation_id,
                        "params": step.params,
                        "step_number": step.step_number,
                        "created_columns": step.created_columns,
                        "timestamp": step.timestamp.isoformat()
                    }
                    for step in self.transformation_pipeline.get_steps()
                ],
                "column_tracking": self.transformation_pipeline._column_tracking
            }

        return {
            "id": self.id,
            "name": self.name,
            "metadata": self.metadata,
            "pipeline": pipeline_data,
            # Note: Dataframe is stored separately in the export format
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], dataframe: pl.DataFrame = None) -> 'Dataset':
        """Deserialize dataset from dictionary."""
        dataset = cls(
            id=data["id"],
            name=data["name"],
            dataframe=dataframe
        )
        dataset.metadata = data.get("metadata", {})

        # Restore pipeline if present
        pipeline_data = data.get("pipeline")
        if pipeline_data and dataframe is not None:
            from .data_processor import TransformationPipeline, TransformationStep

            pipeline = TransformationPipeline(dataframe)
            for step_data in pipeline_data["steps"]:
                step = TransformationStep(
                    operation_id=step_data["operation_id"],
                    params=step_data["params"],
                    step_number=step_data["step_number"]
                )
                step.created_columns = step_data.get("created_columns", [])
                step.timestamp = datetime.fromisoformat(step_data["timestamp"])
                pipeline.steps.append(step)

            # Restore column tracking
            pipeline._column_tracking = pipeline_data.get("column_tracking", {})
            dataset.set_pipeline(pipeline)

        return dataset


class Project:
    """Represents a CaatMaster project with multiple datasets and metadata."""

    def __init__(self, id: str = None, name: str = "", description: str = "",
                 client_name: str = None, phase: str = "planning",
                 engagement_type: str = "financial audit", risk_score: int = 5,
                 objectives: str = None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.client_name = client_name
        self.phase = phase
        self.engagement_type = engagement_type
        self.risk_score = risk_score
        self.objectives = objectives
        self.datasets: Dict[str, Dataset] = {}
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "last_modified": datetime.now().isoformat(),
            "author": "",
            "tags": []
        }

    def add_dataset(self, dataset: Dataset):
        """Add a dataset to the project."""
        self.datasets[dataset.id] = dataset
        self._update_last_modified()

    def remove_dataset(self, dataset_id: str):
        """Remove a dataset from the project."""
        if dataset_id in self.datasets:
            del self.datasets[dataset_id]
            self._update_last_modified()

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get a dataset by ID."""
        return self.datasets.get(dataset_id)

    def list_datasets(self) -> List[Dataset]:
        """Get all datasets in the project."""
        return list(self.datasets.values())

    def _update_last_modified(self):
        """Update the last modified timestamp."""
        self.metadata["last_modified"] = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize project to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "client_name": self.client_name,
            "phase": self.phase,
            "engagement_type": self.engagement_type,
            "risk_score": self.risk_score,
            "objectives": self.objectives,
            "metadata": self.metadata,
            "datasets": {ds_id: ds.to_dict() for ds_id, ds in self.datasets.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Deserialize project from dictionary."""
        project = cls(
            id=data.get("id"),
            name=data["name"],
            description=data.get("description", ""),
            client_name=data.get("client_name"),
            phase=data.get("phase", "planning"),
            engagement_type=data.get("engagement_type", "financial audit"),
            risk_score=data.get("risk_score", 5),
            objectives=data.get("objectives"),
        )
        project.metadata = data.get("metadata", {})

        # Note: Datasets are loaded separately during import
        return project


class ProjectExporter:
    """Handles project and dataset export/import operations."""

    @staticmethod
    def export_project(project: Project, export_path: str, format: str = "excel+metadata") -> str:
        """
        Export a project with all its datasets and transformation pipelines.

        Args:
            project: The project to export
            export_path: Path where to save the export
            format: Export format ("excel+metadata", "parquet", "json")

        Returns:
            Path to the exported file
        """
        export_path = Path(export_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "excel+metadata":
            return ProjectExporter._export_excel_metadata(project, export_path, timestamp)
        elif format == "parquet":
            return ProjectExporter._export_parquet(project, export_path, timestamp)
        elif format == "json":
            return ProjectExporter._export_json(project, export_path, timestamp)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    @staticmethod
    def _export_excel_metadata(project: Project, export_path: Path, timestamp: str) -> str:
        """Export project as Excel files with embedded metadata."""
        project_dir = export_path / f"{project.name}_{timestamp}"
        project_dir.mkdir(exist_ok=True)

        # Export project metadata
        project_data = project.to_dict()
        with open(project_dir / "project.json", 'w') as f:
            json.dump(project_data, f, indent=2, default=str)

        # Export each dataset
        for dataset in project.list_datasets():
            dataset_name = dataset.name.replace(" ", "_")
            file_path = project_dir / f"{dataset_name}.xlsx"

            # Get current dataframe state
            current_df = dataset.get_current_dataframe()

            # Export to Excel
            current_df.write_excel(str(file_path))

            # Create metadata file for this dataset
            dataset_metadata = dataset.to_dict()
            metadata_path = project_dir / f"{dataset_name}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(dataset_metadata, f, indent=2, default=str)

        # Create a zip archive
        zip_path = export_path / f"{project.name}_{timestamp}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in project_dir.rglob('*'):
                if file_path.is_file():
                    zipf.write(file_path, file_path.relative_to(project_dir))

        # Clean up temporary directory
        import shutil
        shutil.rmtree(project_dir)

        return str(zip_path)

    @staticmethod
    def _export_parquet(project: Project, export_path: Path, timestamp: str) -> str:
        """Export project as Parquet files with embedded metadata."""
        project_dir = export_path / f"{project.name}_{timestamp}"
        project_dir.mkdir(exist_ok=True)

        # Export project metadata
        project_data = project.to_dict()
        with open(project_dir / "project.json", 'w') as f:
            json.dump(project_data, f, indent=2, default=str)

        # Export each dataset
        for dataset in project.list_datasets():
            dataset_name = dataset.name.replace(" ", "_")

            # Get current dataframe state
            current_df = dataset.get_current_dataframe()

            # Export to Parquet
            file_path = project_dir / f"{dataset_name}.parquet"
            current_df.write_parquet(str(file_path))

            # Embed metadata in Parquet file (if supported) or separate file
            dataset_metadata = dataset.to_dict()
            metadata_path = project_dir / f"{dataset_name}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(dataset_metadata, f, indent=2, default=str)

        # Create a zip archive
        zip_path = export_path / f"{project.name}_{timestamp}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in project_dir.rglob('*'):
                if file_path.is_file():
                    zipf.write(file_path, file_path.relative_to(project_dir))

        # Clean up
        import shutil
        shutil.rmtree(project_dir)

        return str(zip_path)

    @staticmethod
    def _export_json(project: Project, export_path: Path, timestamp: str) -> str:
        """Export project as JSON with embedded data."""
        project_data = project.to_dict()

        # Add dataframe data to JSON (as records)
        for ds_id, dataset in project.datasets.items():
            current_df = dataset.get_current_dataframe()
            if current_df is not None:
                # Convert to list of dicts for JSON serialization
                project_data["datasets"][ds_id]["data"] = current_df.to_dicts()

        file_path = export_path / f"{project.name}_{timestamp}.json"
        with open(file_path, 'w') as f:
            json.dump(project_data, f, indent=2, default=str)

        return str(file_path)

    @staticmethod
    def import_project(import_path: str) -> Project:
        """
        Import a project from an exported file.

        Args:
            import_path: Path to the exported project file

        Returns:
            Loaded Project instance
        """
        import_path = Path(import_path)

        if import_path.suffix == ".zip":
            return ProjectExporter._import_zip_project(import_path)
        elif import_path.suffix == ".json":
            return ProjectExporter._import_json_project(import_path)
        else:
            raise ValueError(f"Unsupported import format: {import_path.suffix}")

    @staticmethod
    def _import_zip_project(zip_path: Path) -> Project:
        """Import project from zip archive."""
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # Extract to temporary directory
            temp_dir = zip_path.parent / f"temp_import_{zip_path.stem}"
            temp_dir.mkdir(exist_ok=True)

            try:
                zipf.extractall(temp_dir)

                # Load project metadata
                project_file = temp_dir / "project.json"
                if not project_file.exists():
                    raise ValueError("Invalid project archive: missing project.json")

                with open(project_file, 'r') as f:
                    project_data = json.load(f)

                project = Project.from_dict(project_data)

                # Load datasets
                for file_path in temp_dir.glob("*_metadata.json"):
                    dataset_name = file_path.stem.replace("_metadata", "")

                    # Load metadata
                    with open(file_path, 'r') as f:
                        dataset_metadata = json.load(f)

                    # Load data file
                    data_file = temp_dir / f"{dataset_name}.xlsx"
                    if data_file.exists():
                        df = pl.read_excel(str(data_file))
                    else:
                        data_file = temp_dir / f"{dataset_name}.parquet"
                        if data_file.exists():
                            df = pl.read_parquet(str(data_file))
                        else:
                            raise ValueError(f"Data file not found for dataset {dataset_name}")

                    # Create dataset
                    dataset = Dataset.from_dict(dataset_metadata, df)
                    project.add_dataset(dataset)

                return project

            finally:
                # Clean up
                import shutil
                shutil.rmtree(temp_dir)

    @staticmethod
    def _import_json_project(json_path: Path) -> Project:
        """Import project from JSON file."""
        with open(json_path, 'r') as f:
            project_data = json.load(f)

        project = Project.from_dict(project_data)

        # Load datasets from embedded data
        for ds_id, dataset_data in project_data.get("datasets", {}).items():
            data_records = dataset_data.get("data", [])
            if data_records:
                df = pl.DataFrame(data_records)
                dataset = Dataset.from_dict(dataset_data, df)
                project.add_dataset(dataset)

        return project