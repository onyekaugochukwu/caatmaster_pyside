"""Data View - Data import and management with CaatMaster styling"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QLineEdit, QInputDialog, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor

from core.project_manager import Dataset
from gui.theme import Colors, Spacing, Typography


# Keyword -> (background, text color) for status pill rendering. Matched
# case-insensitively against the whole cell value; first match wins.
_STATUS_PILL_COLORS = [
    (("approved", "complete", "completed", "passed", "valid", "active", "resolved"),
     (Colors.SUCCESS_SOFT, Colors.SUCCESS)),
    (("pending", "in progress", "in review", "review", "processing", "open"),
     (Colors.WARNING_SOFT, Colors.WARNING_STRONG)),
    (("rejected", "failed", "invalid", "error", "denied", "cancelled", "canceled"),
     (Colors.DANGER_SOFT, Colors.DANGER)),
]


def make_status_pill(value: str) -> QWidget:
    """A small colored pill for a Status-like cell - state should be
    visible at a glance in a grid this dense, not just more plain text
    indistinguishable from every other column. Falls back to a neutral
    gray pill (rather than plain text) for values that don't match a
    recognized keyword, so the column still reads as a consistent set of
    states either way."""
    lowered = value.strip().lower()
    bg, fg = Colors.BG_TERTIARY, Colors.TEXT_SECONDARY
    for keywords, colors in _STATUS_PILL_COLORS:
        if any(kw in lowered for kw in keywords):
            bg, fg = colors
            break

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(8, 0, 8, 0)

    label = QLabel(value)
    label.setStyleSheet(f"""
        QLabel {{
            background-color: {bg};
            color: {fg};
            font-size: 11px;
            font-weight: 600;
            border-radius: 9px;
            padding: 2px 10px;
        }}
    """)
    layout.addWidget(label)
    layout.addStretch()
    return container


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
        data_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {Colors.BG_PRIMARY};
            }}
        """)

        # Data table - only overrides what needs to differ from the
        # app-wide QTableWidget rule in theme.py (no border, since it's
        # already wrapped in a borderless scroll area; a bit more row
        # padding, since this is the primary data grid). Colors all come
        # from theme.py's tokens rather than being hardcoded again here.
        self.data_table = QTableWidget()
        self.data_table.setStyleSheet(f"""
            QTableWidget {{
                border: none;
            }}
            QTableWidget::item {{
                padding: {Spacing.SM}px;
            }}
            QHeaderView::section {{
                border-bottom: 2px solid {Colors.ACCENT};
                font-weight: 600;
            }}
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
            "All Supported Files (*.csv *.txt *.dat *.xlsx *.xls *.json *.parquet);;"
            "CSV Files (*.csv);;Text Files (*.txt *.dat);;Excel Files (*.xlsx *.xls);;"
            "JSON Files (*.json);;Parquet Files (*.parquet)"
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

            elif file_path.endswith(('.txt', '.dat')):
                from core.data_processor import LegacyDataProcessor
                detection = LegacyDataProcessor.detect_text_file_format(file_path)
                if detection["format"] == "fixed_width":
                    # Auto-detected column alignment isn't always reliable
                    # (a value wider than earlier rows suggested can shift
                    # the boundaries) - let the auditor review/adjust before
                    # anything is actually imported.
                    from gui.dialogs.fixed_width_import_dialog import FixedWidthImportDialog
                    dialog = FixedWidthImportDialog(file_path, self)
                    if dialog.exec() and dialog.result_df is not None:
                        self.load_data(file_path, preloaded_df=dialog.result_df)
                    return

            self.load_data(file_path, sheet_name)

    def load_data(self, file_path: str, sheet_name: str = None, preloaded_df=None):
        """Load data from file. `preloaded_df` skips the normal read_file()
        call - used when a dialog (e.g. the fixed-width text import
        review) has already produced the confirmed dataframe itself."""
        try:
            from core.data_processor import LegacyDataProcessor

            if self.data_processor is None:
                self.data_processor = LegacyDataProcessor()

            # Load the data
            if preloaded_df is not None:
                df = LegacyDataProcessor._trim_column_names(preloaded_df)
            else:
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

            # Create dataset — remember where it came from so it can be
            # refreshed (re-read + steps replayed) later
            dataset = Dataset(
                name=dataset_name.strip(), dataframe=df,
                source_file_path=file_path, source_sheet_name=sheet_name
            )
            self._finalize_new_dataset(dataset, df)

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to load data:\n{str(e)}")

    def paste_from_clipboard(self):
        """Create a new dataset directly from clipboard text (e.g. a range
        copied from a spreadsheet) — no file save required first."""
        from PySide6.QtWidgets import QApplication, QMessageBox

        if not self.current_project:
            QMessageBox.warning(
                self, "No Project Selected",
                "Please create or open a project before pasting a dataset."
            )
            return

        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text or not clipboard_text.strip():
            QMessageBox.information(self, "Clipboard Empty", "Copy some cells from a spreadsheet first, then try again.")
            return

        try:
            from core.data_processor import parse_clipboard_text
            df = parse_clipboard_text(clipboard_text)
        except Exception as e:
            QMessageBox.critical(self, "Paste Failed", f"Could not parse clipboard contents as a table:\n{str(e)}")
            return

        if df is None or len(df.columns) == 0:
            QMessageBox.warning(self, "Empty Data", "The clipboard contents don't look like tabular data.")
            return

        self.current_dataframe = df

        dataset_name, ok = QInputDialog.getText(
            self, "Dataset Name",
            "Enter a name for this pasted dataset:",
            text=f"Pasted_{len(self.current_project.list_datasets()) + 1}"
        )
        if not ok or not dataset_name.strip():
            dataset_name = f"Pasted_{len(self.current_project.list_datasets()) + 1}"

        # Pasted data has no source file — can't be refreshed later, only re-pasted
        dataset = Dataset(name=dataset_name.strip(), dataframe=df)
        self._finalize_new_dataset(dataset, df)

    def import_folder_listing(self):
        """Create a new dataset by listing every file in a folder - name,
        path, extension, size, modified/created dates - the classic
        "inventory the evidence folder" audit test (ACL's DIRECTORY
        command)."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QCheckBox

        if not self.current_project:
            QMessageBox.warning(
                self, "No Project Selected",
                "Please create or open a project before importing a folder listing."
            )
            return

        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to List")
        if not folder_path:
            return

        recursive = QMessageBox.question(
            self, "Include Subfolders?",
            "Include files in subfolders as well?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes

        try:
            from core.data_processor import list_directory_as_dataframe
            df = list_directory_as_dataframe(folder_path, recursive=recursive)
        except Exception as e:
            QMessageBox.critical(self, "Listing Failed", f"Could not list the folder:\n{str(e)}")
            return

        if df.height == 0:
            QMessageBox.information(self, "No Files Found", "No files were found in that folder.")
            return

        self.current_dataframe = df

        from pathlib import Path
        default_name = f"Files_{Path(folder_path).name}"
        dataset_name, ok = QInputDialog.getText(
            self, "Dataset Name",
            "Enter a name for this folder listing:",
            text=default_name
        )
        if not ok or not dataset_name.strip():
            dataset_name = default_name

        dataset = Dataset(name=dataset_name.strip(), dataframe=df, source_file_path=folder_path)
        self._finalize_new_dataset(dataset, df)

    def _finalize_new_dataset(self, dataset: Dataset, df):
        """Shared tail for creating a dataset from any source (file import,
        clipboard paste): unique-name it, attach to the project, and update
        the views that need to know."""
        # Ensure unique name within project
        if self.current_project:
            base_name = dataset.name
            unique_name = base_name
            counter = 1
            existing_names = {ds.name for ds in self.current_project.list_datasets()}
            while unique_name in existing_names:
                unique_name = f"{base_name} ({counter})"
                counter += 1
            dataset.name = unique_name

            self.current_project.add_dataset(dataset)
            self.current_dataset = dataset
            self.dataset_added.emit(dataset)
            self.show_transform_requested.emit()

        self.populate_table(df)
        self.data_loaded.emit(df)

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

        numeric_cols = {col for col in df.columns if df[col].dtype.is_numeric()}
        status_cols = {col for col in df.columns if col.strip().lower() == "status"}

        for row_idx in range(len(display_df)):
            for col_idx, col_name in enumerate(df.columns):
                value = display_df[row_idx, col_idx]
                if col_name in status_cols and value is not None:
                    self.data_table.setCellWidget(row_idx, col_idx, make_status_pill(str(value)))
                    continue
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.UserRole, value)  # Store original value
                if col_name in numeric_cols:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.data_table.setItem(row_idx, col_idx, item)

        # Resize columns
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.data_table.resizeColumnsToContents()
        self._fill_leftover_width()

    def _fill_leftover_width(self):
        """Give any leftover horizontal space to the last column instead of
        leaving it as dead background - only when the columns don't already
        need the full width (a genuinely wide dataset still scrolls
        normally, since this never shrinks a column, only grows the last
        one to use space that would otherwise go unused)."""
        col_count = self.data_table.columnCount()
        if col_count == 0:
            return
        total_width = sum(self.data_table.columnWidth(c) for c in range(col_count))
        viewport_width = self.data_table.viewport().width()
        if total_width < viewport_width:
            last_col = col_count - 1
            extra = viewport_width - total_width
            self.data_table.setColumnWidth(last_col, self.data_table.columnWidth(last_col) + extra)
