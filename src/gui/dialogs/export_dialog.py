"""
Export Dialog - Dialog for exporting data
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QCheckBox, QComboBox, QLineEdit,
    QSpinBox, QFileDialog, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt
from pathlib import Path


class ExportDialog(QDialog):
    """Dialog for exporting data in various formats"""

    def __init__(self, row_count: int = None, parent=None):
        super().__init__(parent if parent else None)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.row_count = row_count
        self.export_settings = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Export Data")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Export format
        format_group = QGroupBox("Export Format")
        format_layout = QFormLayout()

        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "CSV - Comma Separated Values",
            "Excel - XLSX Spreadsheet",
            "Parquet - High-performance format",
            "JSON - JavaScript Object Notation"
        ])
        format_layout.addRow("Format:", self.format_combo)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()

        self.include_index_cb = QCheckBox("Include row index")
        self.include_index_cb.setChecked(False)
        options_layout.addRow("", self.include_index_cb)

        self.include_summary_cb = QCheckBox("Generate HTML summary report")
        self.include_summary_cb.setChecked(True)
        options_layout.addRow("", self.include_summary_cb)

        self.limit_rows_cb = QCheckBox("Limit rows")
        self.limit_rows_cb.setChecked(False)
        self.limit_rows_cb.toggled.connect(self.toggle_limit)
        options_layout.addRow("", self.limit_rows_cb)

        self.limit_rows_spin = QSpinBox()
        self.limit_rows_spin.setRange(1, 10000000)
        self.limit_rows_spin.setValue(10000)
        self.limit_rows_spin.setEnabled(False)
        options_layout.addRow("Max rows:", self.limit_rows_spin)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # File location
        location_group = QGroupBox("File Location")
        location_layout = QVBoxLayout()

        location_input_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        location_input_layout.addWidget(self.file_path_input)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_file)
        location_input_layout.addWidget(self.browse_btn)

        location_layout.addLayout(location_input_layout)
        location_group.setLayout(location_layout)
        layout.addWidget(location_group)

        # Info
        if self.row_count:
            info_label = QLabel(f"Exporting {self.row_count:,} rows")
            info_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
            layout.addWidget(info_label)

        # Buttons
        buttons = QHBoxLayout()
        export_btn = QPushButton("Export")
        export_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #106ebe;
            }
        """)
        export_btn.clicked.connect(self.validate_and_accept)
        buttons.addWidget(export_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

    def toggle_limit(self, checked: bool):
        """Enable/disable limit spinner"""
        self.limit_rows_spin.setEnabled(checked)

    def browse_file(self):
        """Browse for file location"""
        # Get current format
        format_idx = self.format_combo.currentIndex()
        format_map = {
            0: "CSV Files (*.csv)",
            1: "Excel Files (*.xlsx)",
            2: "Parquet Files (*.parquet)",
            3: "JSON Files (*.json)"
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            "",
            format_map.get(format_idx, "All Files (*.*)")
        )

        if file_path:
            self.file_path_input.setText(file_path)

    def validate_and_accept(self):
        """Validate inputs and accept dialog"""
        file_path = self.file_path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "Validation Error", "Please specify a file location")
            return

        # Get format
        format_idx = self.format_combo.currentIndex()
        format_map = {0: "csv", 1: "excel", 2: "parquet", 3: "json"}
        fmt = format_map.get(format_idx, "csv")

        self.export_settings = {
            'file_path': file_path,
            'format': fmt,
            'include_index': self.include_index_cb.isChecked(),
            'include_summary': self.include_summary_cb.isChecked(),
            'limit_rows': self.limit_rows_spin.value() if self.limit_rows_cb.isChecked() else None
        }

        self.accept()

    def get_export_settings(self):
        """Return the export settings"""
        return self.export_settings
