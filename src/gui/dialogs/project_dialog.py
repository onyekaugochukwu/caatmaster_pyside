"""
Project Management Dialogs
Dialogs for creating, opening, and managing CaatMaster projects.
"""

from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
    QLabel, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QGroupBox, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QComboBox, QSlider, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot
from typing import Optional, List
import os
from pathlib import Path

from core.project_manager import Project, Dataset, ProjectExporter
from core.caat_format import load_caat, is_caat_file, CaatFormatError
from gui.theme import Colors
from gui.components.common_modals import create_primary_button


class NewProjectDialog(QDialog):
    """Comprehensive dialog for creating a new project with all required fields."""

    def __init__(self, parent=None):
        super().__init__(parent if parent else None)
        self.project_data = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)  # Reduced since it's now scrollable
        self.setModal(True)

        # QDialog/QLabel/QLineEdit/QTextEdit/QComboBox/QSpinBox chrome
        # inherited from the app-wide rules in theme.py. QSlider has no
        # global rule (genuinely custom here), so it's kept and tokenized.
        self.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: 1px solid {Colors.BORDER_STRONG};
                background: {Colors.BG_SECONDARY};
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {Colors.ACCENT};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {Colors.ACCENT_PRESSED};
                border: 2px solid {Colors.BG_PRIMARY};
                width: 18px;
                height: 18px;
                margin: -7px 0;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {Colors.ACCENT_HOVER};
                width: 20px;
                height: 20px;
                margin: -8px 0;
            }}
            QFormLayout QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-weight: 500;
                font-size: 13px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Create scroll area for the main content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Scrollbar styling inherited from the app-wide QScrollBar rule in
        # theme.py - only the background is specific here.
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {Colors.BG_PRIMARY};
            }}
        """)

        # Create scroll content widget
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(16)

        # Basic Information Section
        basic_label = QLabel("Basic Information")
        basic_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {Colors.ACCENT};
            }}
        """)
        scroll_layout.addWidget(basic_label)

        basic_frame = QFrame()
        basic_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        basic_layout = QFormLayout(basic_frame)
        basic_layout.setContentsMargins(20, 20, 20, 20)
        basic_layout.setSpacing(16)

        # Project name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Q4 2024 Financial Audit")
        self.name_input.setMinimumWidth(400)
        basic_layout.addRow("Project Name*:", self.name_input)

        # Client name
        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("e.g., Better Days Corp")
        self.client_input.setMinimumWidth(400)
        basic_layout.addRow("Client Name*:", self.client_input)

        # Engagement type (Kind)
        self.engagement_combo = QComboBox()
        self.engagement_combo.addItems([
            "Financial Audit",
            "Compliance Review",
            "Internal Audit",
            "Investigation",
            "Consulting",
            "SOX Compliance",
            "ICFR Assessment",
            "Risk Assessment"
        ])
        self.engagement_combo.setMinimumWidth(400)
        basic_layout.addRow("Engagement Type:", self.engagement_combo)

        # Risk Score
        risk_layout = QHBoxLayout()
        self.risk_slider = QSlider(Qt.Horizontal)
        self.risk_slider.setRange(1, 10)
        self.risk_slider.setValue(5)
        self.risk_slider.setFixedWidth(300)
        self.risk_label = QLabel("5")
        self.risk_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 700;
                min-width: 24px;
            }}
        """)
        self.risk_slider.valueChanged.connect(lambda v: self.risk_label.setText(str(v)))
        risk_layout.addWidget(self.risk_slider)
        risk_layout.addWidget(self.risk_label)
        risk_layout.addSpacing(8)
        risk_layout.addWidget(QLabel("(1=Low, 10=High)"))
        risk_layout.addStretch()
        risk_frame = QFrame()
        risk_frame.setLayout(risk_layout)
        basic_layout.addRow("Risk Score:", risk_frame)

        scroll_layout.addWidget(basic_frame)

        # Description Section
        desc_label = QLabel("Description & Scope")
        desc_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {Colors.ACCENT};
            }}
        """)
        scroll_layout.addWidget(desc_label)

        desc_frame = QFrame()
        desc_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        desc_layout = QFormLayout(desc_frame)
        desc_layout.setContentsMargins(20, 20, 20, 20)
        desc_layout.setSpacing(16)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setMinimumHeight(80)
        self.description_input.setPlaceholderText("Describe the project objectives, scope, and key deliverables...")
        desc_layout.addRow("Description:", self.description_input)

        # Objectives
        self.objectives_input = QTextEdit()
        self.objectives_input.setMinimumHeight(60)
        self.objectives_input.setPlaceholderText("List the main audit objectives...")
        desc_layout.addRow("Objectives:", self.objectives_input)

        scroll_layout.addWidget(desc_frame)

        # Project Phase Section
        phase_label = QLabel("Project Phase")
        phase_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {Colors.ACCENT};
            }}
        """)
        scroll_layout.addWidget(phase_label)

        phase_frame = QFrame()
        phase_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        phase_layout = QFormLayout(phase_frame)
        phase_layout.setContentsMargins(20, 20, 20, 20)
        phase_layout.setSpacing(16)

        # Phase dropdown
        self.phase_combo = QComboBox()
        self.phase_combo.addItems([
            "Planning",
            "Fieldwork",
            "Analysis",
            "Reporting",
            "Completed"
        ])
        self.phase_combo.setMinimumWidth(400)
        phase_layout.addRow("Current Phase:", self.phase_combo)

        scroll_layout.addWidget(phase_frame)

        # Add some spacing at the bottom
        scroll_layout.addSpacing(16)

        # Set the scroll content as the scroll area widget
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)  # Give scroll area maximum space

        # Buttons (outside scroll area)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.setStyleSheet("""
            QDialogButtonBox {
                padding-top: 16px;
            }
        """)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)

        # Style the OK button - reuses the app-wide #PrimaryButton rule.
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setObjectName("PrimaryButton")
        ok_button.setStyleSheet("QPushButton#PrimaryButton { padding: 8px 24px; }")

        layout.addWidget(buttons)

    def validate_and_accept(self):
        """Validate inputs and accept dialog"""
        name = self.name_input.text().strip()
        client = self.client_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Project name is required")
            return

        if not client:
            QMessageBox.warning(self, "Validation Error", "Client name is required")
            return

        self.project_data = {
            'name': name,
            'client_name': client,
            'engagement_type': self.engagement_combo.currentText().lower(),
            'risk_score': self.risk_slider.value(),
            'description': self.description_input.toPlainText().strip() or None,
            'objectives': self.objectives_input.toPlainText().strip() or None,
            'phase': self.phase_combo.currentText().lower(),
        }

        self.accept()

    def get_project_data(self):
        """Return the project data"""
        return self.project_data


class OpenProjectDialog(QDialog):
    """Dialog for opening existing projects."""

    projectSelected = Signal(Project)

    def __init__(self, parent=None):
        super().__init__(parent if parent else None)
        self.setWindowTitle("Open Project")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.selected_project: Optional[Project] = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # File selection
        file_group = QGroupBox("Select Project File")
        file_layout = QHBoxLayout(file_group)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Click Browse to select a project file...")
        self.file_path_edit.setReadOnly(True)
        file_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # Project preview
        preview_group = QGroupBox("Project Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.project_info_text = QTextEdit()
        self.project_info_text.setReadOnly(True)
        self.project_info_text.setMaximumHeight(150)
        preview_layout.addWidget(self.project_info_text)

        # Datasets list
        self.datasets_table = QTableWidget()
        self.datasets_table.setColumnCount(4)
        self.datasets_table.setHorizontalHeaderLabels(["Name", "Rows", "Columns", "Transformations"])
        self.datasets_table.horizontalHeader().setStretchLastSection(True)
        self.datasets_table.setMaximumHeight(150)
        preview_layout.addWidget(self.datasets_table)

        layout.addWidget(preview_group)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Open | QDialogButtonBox.Cancel
        )
        self.button_box.button(QDialogButtonBox.Open).setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    @Slot()
    def browse_file(self):
        """Browse for a project file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(Path.home()),
            "CaatMaster Project (*.caat);;Legacy Project Files (*.zip *.json);;All Files (*)"
        )

        if file_path:
            self.file_path_edit.setText(file_path)
            self.load_project_preview(file_path)

    def load_project_preview(self, file_path: str):
        """Load and display project preview."""
        try:
            if is_caat_file(file_path):
                project = load_caat(file_path)
            else:
                # Legacy export format (.zip/.json from before .caat existed)
                project = ProjectExporter.import_project(file_path)
            self.selected_project = project

            # Update project info
            info_text = f"""Project: {project.name}
Description: {project.description}
Created: {project.metadata.get('created_at', 'Unknown')}
Last Modified: {project.metadata.get('last_modified', 'Unknown')}
Datasets: {len(project.list_datasets())}
"""

            self.project_info_text.setPlainText(info_text)

            # Update datasets table
            self.datasets_table.setRowCount(len(project.list_datasets()))
            for row, dataset in enumerate(project.list_datasets()):
                self.datasets_table.setItem(row, 0, QTableWidgetItem(dataset.name))
                self.datasets_table.setItem(row, 1, QTableWidgetItem(str(dataset.metadata.get('row_count', 0))))
                self.datasets_table.setItem(row, 2, QTableWidgetItem(str(dataset.metadata.get('column_count', 0))))

                # Count transformations
                transform_count = 0
                if dataset.transformation_pipeline:
                    transform_count = len(dataset.transformation_pipeline.get_steps())
                self.datasets_table.setItem(row, 3, QTableWidgetItem(str(transform_count)))

            self.datasets_table.resizeColumnsToContents()

            # Enable Open button
            self.button_box.button(QDialogButtonBox.Open).setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load project: {str(e)}")
            self.project_info_text.setPlainText("Error loading project.")
            self.button_box.button(QDialogButtonBox.Open).setEnabled(False)

    def get_selected_project(self) -> Optional[Project]:
        """Get the selected project."""
        return self.selected_project


class SaveProjectDialog(QDialog):
    """Dialog for saving projects."""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent if parent else None)
        self.project = project
        self.setWindowTitle("Save Project")
        self.setMinimumWidth(500)
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Save options
        options_group = QGroupBox("Save Options")
        options_layout = QFormLayout(options_group)

        self.file_path_edit = QLineEdit()
        suggested_name = f"{self.project.name.replace(' ', '_')}_export"
        self.file_path_edit.setText(suggested_name)
        options_layout.addRow("File Name:", self.file_path_edit)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["excel+metadata", "parquet", "json"])
        self.format_combo.setCurrentText("excel+metadata")
        options_layout.addRow("Format:", self.format_combo)

        layout.addWidget(options_group)

        # Save location
        location_group = QGroupBox("Save Location")
        location_layout = QHBoxLayout(location_group)

        self.location_edit = QLineEdit()
        self.location_edit.setText(str(Path.home() / "Documents"))
        location_layout.addWidget(self.location_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_location)
        location_layout.addWidget(browse_btn)

        layout.addWidget(location_group)

        # Project summary
        summary_group = QGroupBox("Project Summary")
        summary_layout = QVBoxLayout(summary_group)

        summary_text = f"""Project: {self.project.name}
Datasets: {len(self.project.list_datasets())}
Total Transformations: {sum(len(ds.transformation_pipeline.get_steps()) if ds.transformation_pipeline else 0 for ds in self.project.list_datasets())}
"""

        summary_label = QLabel(summary_text)
        summary_label.setWordWrap(True)
        summary_layout.addWidget(summary_label)

        layout.addWidget(summary_group)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    @Slot()
    def browse_location(self):
        """Browse for save location."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Save Location",
            self.location_edit.text()
        )

        if directory:
            self.location_edit.setText(directory)

    def get_save_options(self) -> dict:
        """Get the save options from the dialog."""
        file_name = self.file_path_edit.text().strip()
        if not file_name:
            file_name = f"{self.project.name.replace(' ', '_')}_export"

        return {
            "file_path": Path(self.location_edit.text()) / file_name,
            "format": self.format_combo.currentText()
        }

    def validate(self) -> bool:
        """Validate the save options."""
        save_path = Path(self.location_edit.text())
        if not save_path.exists():
            QMessageBox.warning(self, "Invalid Location", "Selected save location does not exist.")
            return False

        if not save_path.is_dir():
            QMessageBox.warning(self, "Invalid Location", "Selected path is not a directory.")
            return False

        return True

    def accept(self):
        """Handle dialog acceptance with validation."""
        if self.validate():
            super().accept()


class DatasetManagerDialog(QDialog):
    """Dialog for managing datasets within a project."""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent if parent else None)
        self.project = project
        self.setWindowTitle(f"Manage Datasets - {project.name}")
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        self.setup_ui()
        self.refresh_datasets()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar_layout = QHBoxLayout()

        add_btn = QPushButton("Add Dataset")
        add_btn.clicked.connect(self.add_dataset)
        toolbar_layout.addWidget(add_btn)

        remove_btn = QPushButton("Remove Dataset")
        remove_btn.clicked.connect(self.remove_dataset)
        toolbar_layout.addWidget(remove_btn)

        export_btn = QPushButton("Export Dataset")
        export_btn.clicked.connect(self.export_dataset)
        toolbar_layout.addWidget(export_btn)

        toolbar_layout.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_datasets)
        toolbar_layout.addWidget(refresh_btn)

        layout.addLayout(toolbar_layout)

        # Datasets table
        self.datasets_table = QTableWidget()
        self.datasets_table.setColumnCount(5)
        self.datasets_table.setHorizontalHeaderLabels([
            "Name", "Rows", "Columns", "Transformations", "Size (MB)"
        ])
        self.datasets_table.horizontalHeader().setStretchLastSection(True)
        self.datasets_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.datasets_table.setAlternatingRowColors(True)

        layout.addWidget(self.datasets_table)

        # Dataset details
        details_group = QGroupBox("Dataset Details")
        details_layout = QVBoxLayout(details_group)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)

        layout.addWidget(details_group)

        # Connect selection change
        self.datasets_table.itemSelectionChanged.connect(self.show_dataset_details)

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def refresh_datasets(self):
        """Refresh the datasets table."""
        datasets = self.project.list_datasets()
        self.datasets_table.setRowCount(len(datasets))

        for row, dataset in enumerate(datasets):
            self.datasets_table.setItem(row, 0, QTableWidgetItem(dataset.name))

            # Get current dataframe for stats
            try:
                current_df = dataset.get_current_dataframe()
                if current_df is not None:
                    row_count = current_df.shape[0]
                    col_count = current_df.shape[1]
                    # Estimate size (rough calculation)
                    size_mb = (current_df.estimated_size() / (1024 * 1024))
                else:
                    row_count = col_count = size_mb = 0
            except:
                row_count = col_count = size_mb = 0

            self.datasets_table.setItem(row, 1, QTableWidgetItem(str(row_count)))
            self.datasets_table.setItem(row, 2, QTableWidgetItem(str(col_count)))

            # Transformation count
            transform_count = 0
            if dataset.transformation_pipeline:
                transform_count = len(dataset.transformation_pipeline.get_steps())
            self.datasets_table.setItem(row, 3, QTableWidgetItem(str(transform_count)))

            self.datasets_table.setItem(row, 4, QTableWidgetItem(".2f"))

        self.datasets_table.resizeColumnsToContents()

    def show_dataset_details(self):
        """Show details for the selected dataset."""
        selected_rows = set()
        for item in self.datasets_table.selectedItems():
            selected_rows.add(item.row())

        if len(selected_rows) == 1:
            row = list(selected_rows)[0]
            datasets = self.project.list_datasets()
            if row < len(datasets):
                dataset = datasets[row]

                details = f"""Dataset: {dataset.name}
ID: {dataset.id}
Created: {dataset.metadata.get('created_at', 'Unknown')}

Data Statistics:
- Original Rows: {dataset.metadata.get('row_count', 0)}
- Original Columns: {dataset.metadata.get('column_count', 0)}
- Columns: {', '.join(dataset.metadata.get('columns', []))}

Transformations:
"""

                if dataset.transformation_pipeline:
                    for step in dataset.transformation_pipeline.get_steps():
                        details += f"- Step {step.step_number}: {step.operation_id}\n"
                        if step.created_columns:
                            details += f"  Created: {', '.join(step.created_columns)}\n"
                else:
                    details += "No transformations applied."

                self.details_text.setPlainText(details)
        else:
            self.details_text.clear()

    @Slot()
    def add_dataset(self):
        """Add a new dataset to the project."""
        QMessageBox.information(self, "Add Dataset",
                               "Use File → Import Data to add datasets to the current project.")

    @Slot()
    def remove_dataset(self):
        """Remove the selected dataset."""
        selected_rows = set()
        for item in self.datasets_table.selectedItems():
            selected_rows.add(item.row())

        if len(selected_rows) == 1:
            row = list(selected_rows)[0]
            datasets = self.project.list_datasets()
            if row < len(datasets):
                dataset = datasets[row]
                reply = QMessageBox.question(
                    self, "Remove Dataset",
                    f"Are you sure you want to remove dataset '{dataset.name}'?",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    self.project.remove_dataset(dataset.id)
                    self.refresh_datasets()
                    self.details_text.clear()

    @Slot()
    def export_dataset(self):
        """Export the selected dataset."""
        QMessageBox.information(self, "Export Dataset",
                               "Use File → Export Data to export the current dataset.")