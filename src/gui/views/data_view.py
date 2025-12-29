"""Data View - Data import and management with CaatMaster styling"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTextEdit, QComboBox, QFrame,
    QLineEdit, QInputDialog
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor, QPalette
from pathlib import Path

from core.project_manager import Dataset


class DataView(QWidget):
    """Data import and management view with CaatMaster UI"""

    data_loaded = Signal(object)  # Signal when data is loaded
    dataset_added = Signal(Dataset)  # Signal when dataset is added to project

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
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        # Header section
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        title = QLabel("Data Workspace")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 600;
                color: #1f2937;
            }
        """)
        header_layout.addWidget(title)

        subtitle = QLabel("Transform data with right-click menus and visual tools")
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #374151;
            }
        """)
        header_layout.addWidget(subtitle)

        main_layout.addWidget(header)

        # Tabs section
        tabs_widget = QWidget()
        tabs_layout = QHBoxLayout(tabs_widget)
        tabs_layout.setContentsMargins(0, 16, 0, 0)
        tabs_layout.setSpacing(0)

        # Worksheets tab
        self.worksheets_tab = QPushButton("📄 Worksheets (1)")
        self.worksheets_tab.setCheckable(True)
        self.worksheets_tab.setChecked(True)
        self.worksheets_tab.setCursor(Qt.PointingHandCursor)
        self.worksheets_tab.setMinimumHeight(32)
        self.worksheets_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #1f2937;
                border: none;
                border-bottom: 2px solid #3b82f6;
                border-radius: 0px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        tabs_layout.addWidget(self.worksheets_tab)

        # Datasets tab
        datasets_tab = QPushButton("📊 Datasets (15)")
        datasets_tab.setCheckable(True)
        datasets_tab.setCursor(Qt.PointingHandCursor)
        datasets_tab.setMinimumHeight(32)
        datasets_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #374151;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #111827;
                border-bottom: 2px solid #9ca3af;
            }
        """)
        tabs_layout.addWidget(datasets_tab)

        # Applied Steps tab
        applied_tab = QPushButton("📋 Applied Steps (0)")
        applied_tab.setCheckable(True)
        applied_tab.setCursor(Qt.PointingHandCursor)
        applied_tab.setMinimumHeight(32)
        applied_tab.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #374151;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #111827;
                border-bottom: 2px solid #9ca3af;
            }
        """)
        tabs_layout.addWidget(applied_tab)

        tabs_layout.addStretch()
        main_layout.addWidget(tabs_widget)

        # Worksheet info section
        worksheet_info = QWidget()
        ws_layout = QHBoxLayout(worksheet_info)
        ws_layout.setContentsMargins(0, 8, 0, 0)
        ws_layout.setSpacing(12)

        worksheet_btn = QPushButton("📄 denormalized_ta...")
        worksheet_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9fafb;
                color: #1f2937;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
        """)
        worksheet_btn.setMinimumWidth(200)
        ws_layout.addWidget(worksheet_btn)

        plus_btn = QPushButton("+")
        plus_btn.setFixedSize(36, 36)
        plus_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9fafb;
                color: #374151;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                font-size: 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
                color: #111827;
            }
        """)
        ws_layout.addWidget(plus_btn)

        ws_layout.addStretch()
        main_layout.addWidget(worksheet_info)

        # Stats section
        stats = QWidget()
        stats_layout = QHBoxLayout(stats)
        stats_layout.setContentsMargins(0, 8, 0, 0)
        stats_layout.setSpacing(32)

        # Rows stat
        rows_layout = QVBoxLayout()
        rows_label = QLabel("Rows")
        rows_label.setStyleSheet("color: #374151; font-size: 12px;")
        self.rows_value = QLabel("0")
        self.rows_value.setStyleSheet("color: #111827; font-size: 20px; font-weight: 600;")
        rows_layout.addWidget(rows_label)
        rows_layout.addWidget(self.rows_value)
        stats_layout.addLayout(rows_layout)

        # Columns stat
        cols_layout = QVBoxLayout()
        cols_label = QLabel("Columns")
        cols_label.setStyleSheet("color: #374151; font-size: 12px;")
        self.cols_value = QLabel("0")
        self.cols_value.setStyleSheet("color: #111827; font-size: 20px; font-weight: 600;")
        cols_layout.addWidget(cols_label)
        cols_layout.addWidget(self.cols_value)
        stats_layout.addLayout(cols_layout)

        stats_layout.addStretch()
        main_layout.addWidget(stats)

        # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 12, 0, 8)

        # Import button
        self.import_btn = QPushButton("Import Data")
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.import_btn.clicked.connect(self.show_import_dialog)
        actions_layout.addWidget(self.import_btn)

        # Export button
        self.export_btn = QPushButton("Export Data")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9fafb;
                color: #1f2937;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
        """)
        self.export_btn.clicked.connect(self.show_export_dialog)
        self.export_btn.setEnabled(False)
        actions_layout.addWidget(self.export_btn)

        actions_layout.addStretch()

        # Table info
        info_label = QLabel("0 rows    0 columns")
        info_label.setStyleSheet("""
            QLabel {
                color: #1f2937;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        actions_layout.addWidget(info_label)

        scroll_label = QLabel("No data loaded")
        scroll_label.setStyleSheet("""
            QLabel {
                color: #374151;
                font-size: 12px;
            }
        """)
        actions_layout.addWidget(scroll_label)

        main_layout.addLayout(actions_layout)

        # Data preview table
        self.data_table = QTableWidget()
        self.data_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background-color: white;
                gridline-color: #f3f4f6;
            }
            QTableWidget::item {
                padding: 8px;
                color: #1f2937;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1f2937;
            }
            QHeaderView::section {
                background-color: #f9fafb;
                color: #374151;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                border-right: 1px solid #f3f4f6;
                padding: 10px 8px;
            }
        """)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.verticalHeader().setVisible(False)
        self.data_table.verticalHeader().setDefaultSectionSize(36)
        self.data_table.setSelectionBehavior(QTableWidget.SelectRows)
        main_layout.addWidget(self.data_table, 1)

    def show_import_dialog(self):
        """Show file import dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Data",
            "",
            "All Supported Files (*.csv *.xlsx *.xls *.json *.parquet);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;JSON Files (*.json);;Parquet Files (*.parquet)"
        )

        if file_path:
            self.load_data(file_path)

    def load_data(self, file_path: str, sheet_name: str = None):
        """Load data from file"""
        try:
            from core.data_processor import LegacyDataProcessor

            if self.data_processor is None:
                self.data_processor = LegacyDataProcessor()

            # Load the data
            df = self.data_processor.read_file(file_path, sheet_name)
            self.current_dataframe = df

            # Get file name for default dataset name
            file_name = Path(file_path).stem

            # Ask for dataset name
            dataset_name, ok = QInputDialog.getText(
                self, "Dataset Name",
                "Enter a name for this dataset:",
                text=file_name
            )

            if not ok or not dataset_name.strip():
                dataset_name = f"Dataset_{len(self.current_project.datasets) + 1}" if self.current_project else "Imported Data"

            # Create dataset
            dataset = Dataset(name=dataset_name.strip(), dataframe=df)

            # Add to project if project is set
            if self.current_project:
                self.current_project.add_dataset(dataset)
                self.current_dataset = dataset
                self.dataset_added.emit(dataset)

            # Update UI
            self.populate_table(df)
            self.update_stats(df)

            # Enable export button
            self.export_btn.setEnabled(True)

            self.data_loaded.emit(df)

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to load data:\n{str(e)}")

    def update_stats(self, df):
        """Update the stats display"""
        self.rows_value.setText(f"{len(df):,}")
        self.cols_value.setText(str(len(df.columns)))

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
