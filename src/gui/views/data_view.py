"""Data View - Data import and management with CaatMaster styling"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QLineEdit, QInputDialog, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor

from core.project_manager import Dataset


class DataView(QWidget):
    """Data import and management view with CaatMaster UI"""

    data_loaded = Signal(object)  # Signal when data is loaded
    dataset_added = Signal(Dataset)  # Signal when dataset is added to project
    show_transform_requested = Signal()  # Signal to show transform view after upload

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_dataframe = None
        self.current_dataset = None
        self.data_processor = None
        self.current_project = None
        self.setup_ui()

    def set_project(self, project):
        """Set the current project"""
        self.current_project = project

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Wrap data table in scroll area for proper horizontal scrolling
        data_scroll = QScrollArea()
        data_scroll.setWidgetResizable(True)
        data_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        data_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        data_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
        """)

        # Data table - Light mode
        self.data_table = QTableWidget()
        self.data_table.setStyleSheet("""
            QTableWidget {
                border: none;
                background-color: white;
                gridline-color: #e5e7eb;
                color: #111827;
            }
            QTableWidget::item {
                padding: 8px;
                color: #111827;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #111827;
            }
            QHeaderView::section {
                background-color: #f9fafb;
                color: #374151;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                border-right: 1px solid #e5e7eb;
                padding: 10px 8px;
            }
        """)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.verticalHeader().setVisible(False)
        self.data_table.verticalHeader().setDefaultSectionSize(36)
        self.data_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.data_table.horizontalHeader().setStretchLastSection(False)
        self.data_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

        data_scroll.setWidget(self.data_table)
        main_layout.addWidget(data_scroll, 1)

    def show_import_dialog(self):
        """Show file import dialog"""
        # Enforce project requirement - no project = no upload
        if not self.current_project:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "No Project Selected",
                "Please create or open a project before importing a dataset.\n\n"
                "Projects are required to organize and track your audit work."
            )
            return

        file_path, selected_filter = QFileDialog.getOpenFileName(
            self,
            "Import Data",
            "",
            "All Supported Files (*.csv *.xlsx *.xls *.json *.parquet);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;JSON Files (*.json);;Parquet Files (*.parquet)"
        )

        if file_path:
            sheet_name = None

            # Check if Excel file and has multiple sheets
            if file_path.endswith(('.xlsx', '.xls')):
                from core.data_processor import LegacyDataProcessor
                if self.data_processor is None:
                    self.data_processor = LegacyDataProcessor()

                try:
                    sheets = self.data_processor.get_excel_sheets(file_path)
                    if len(sheets) > 1:
                        # Show sheet selection dialog
                        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QVBoxLayout, QLabel

                        dialog = QDialog(self)
                        dialog.setWindowTitle("Select Worksheet")
                        dialog.setMinimumWidth(300)
                        layout = QVBoxLayout(dialog)

                        layout.addWidget(QLabel(f"Select a worksheet from '{file_path.split('/')[-1]}':"))

                        sheet_combo = QComboBox()
                        sheet_combo.addItems(sheets)
                        layout.addWidget(sheet_combo)

                        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                        buttons.accepted.connect(dialog.accept)
                        buttons.rejected.connect(dialog.reject)
                        layout.addWidget(buttons)

                        if dialog.exec() == QDialog.Accepted:
                            sheet_name = sheet_combo.currentText()
                        else:
                            return  # User cancelled
                except Exception as e:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Warning", f"Could not read Excel sheets: {str(e)}\nLoading first sheet.")
                    sheet_name = None

            self.load_data(file_path, sheet_name)

    def load_data(self, file_path: str, sheet_name: str = None):
        """Load data from file"""
        try:
            from core.data_processor import LegacyDataProcessor

            if self.data_processor is None:
                self.data_processor = LegacyDataProcessor()

            # Load the data
            df = self.data_processor.read_file(file_path, sheet_name)
            
            if df is None or len(df.columns) == 0:
                QMessageBox.warning(self, "Empty Data", "The selected file/sheet contains no columns or data.")
                return

            self.current_dataframe = df

            # Get file name for default dataset name
            from pathlib import Path
            file_name = Path(file_path).stem

            # Ask for dataset name
            dataset_name, ok = QInputDialog.getText(
                self, "Dataset Name",
                "Enter a name for this dataset:",
                text=file_name
            )

            if not ok or not dataset_name.strip():
                dataset_name = f"Dataset_{len(self.current_project.datasets) + 1}" if self.current_project else "Imported Data"

            # Ensure unique name within project
            if self.current_project:
                base_name = dataset_name.strip()
                unique_name = base_name
                counter = 1
                existing_names = {ds.name for ds in self.current_project.list_datasets()}
                while unique_name in existing_names:
                    unique_name = f"{base_name} ({counter})"
                    counter += 1
                dataset_name = unique_name

            # Create dataset
            dataset = Dataset(name=dataset_name.strip(), dataframe=df)

            # Add to project if project is set
            if self.current_project:
                self.current_project.add_dataset(dataset)
                self.current_dataset = dataset
                self.dataset_added.emit(dataset)

                # Emit signal to show transform view with applied steps
                self.show_transform_requested.emit()

            # Update UI
            self.populate_table(df)

            self.data_loaded.emit(df)

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to load data:\n{str(e)}")

    def show_export_dialog(self):
        """Show export dialog"""
        if self.current_dataframe is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Data", "Please load data first")
            return

        from ..dialogs.export_dialog import ExportDialog

        dialog = ExportDialog(row_count=len(self.current_dataframe), parent=self)
        if dialog.exec():
            settings = dialog.get_export_settings()
            self.export_data(settings)

    def export_data(self, settings: dict):
        """Export data with the given settings"""
        try:
            from services.export_service import ExportService

            export_service = ExportService()

            # Apply limit if specified
            df = self.current_dataframe
            if settings.get('limit_rows'):
                df = df.head(settings['limit_rows'])

            # Export
            if settings.get('include_summary'):
                # Create export package
                package_name = Path(settings['file_path']).stem
                base_path = Path(settings['file_path']).parent

                package_dir, files = export_service.create_export_package(
                    df,
                    base_path=str(base_path),
                    package_name=package_name,
                    formats=[settings['format']]
                )

                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Data exported to:\n{package_dir}\n\nFiles created:\n" + "\n".join(files)
                )
            else:
                # Simple export
                file_path = export_service.export_dataframe(
                    df,
                    settings['file_path'],
                    settings['format'],
                    settings.get('include_index', False)
                )

                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Data exported to:\n{file_path}"
                )

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export data:\n{str(e)}"
            )

    def populate_table(self, df):
        """Populate table with dataframe data"""
        # Limit to first 1000 rows for display
        display_df = df.head(1000)

        self.data_table.setRowCount(len(display_df))
        self.data_table.setColumnCount(len(df.columns))
        self.data_table.setHorizontalHeaderLabels(df.columns)

        for row_idx in range(len(display_df)):
            for col_idx, col_name in enumerate(df.columns):
                value = display_df[row_idx, col_idx]
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.UserRole, value)  # Store original value
                self.data_table.setItem(row_idx, col_idx, item)

        # Resize columns
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
