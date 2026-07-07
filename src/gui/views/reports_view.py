"""
Reports View - Generate comprehensive reports with charts and tables
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from pathlib import Path

from gui.theme import Colors
from gui.components.common_modals import create_primary_button, create_secondary_button, EmptyStateOverlay


class ReportsView(QWidget):
    """Report generation view"""

    data_loaded = Signal(object)  # Signal when data is loaded

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_dataframe = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Report Generation")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Info panel
        info_group = QGroupBox("Generate Reports")
        info_layout = QVBoxLayout()

        info_text = QLabel(
            "Create comprehensive reports with embedded charts, data tables, "
            "and statistical summaries. Reports are generated as HTML files "
            "that can be opened in any web browser or printed to PDF."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; padding: 10px;")
        info_layout.addWidget(info_text)

        # Report options - one primary action plus two equally-valid
        # secondary ones, not three different colors implying a priority
        # (green/blue/gray) these three actions don't actually have.
        options_layout = QVBoxLayout()

        self.quick_report_btn = create_primary_button("🚀  Generate Quick Report")
        self.quick_report_btn.clicked.connect(self.generate_quick_report)
        options_layout.addWidget(self.quick_report_btn)

        self.custom_report_btn = create_secondary_button("📊  Build Custom Report")
        self.custom_report_btn.clicked.connect(self.build_custom_report)
        options_layout.addWidget(self.custom_report_btn)

        self.export_btn = create_secondary_button("💾  Export Current Report")
        self.export_btn.clicked.connect(self.export_report)
        self.export_btn.setEnabled(False)
        options_layout.addWidget(self.export_btn)

        info_layout.addLayout(options_layout)
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # Recent reports
        recent_group = QGroupBox("Recent Reports")
        recent_layout = QVBoxLayout()

        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self.open_report)
        recent_layout.addWidget(self.recent_list)
        self._recent_empty_state = EmptyStateOverlay(
            self.recent_list,
            'No reports generated yet. Use "Generate Quick Report" above to create your first one.'
        )

        # Recent reports controls
        recent_controls = QHBoxLayout()

        self.open_btn = QPushButton("Open")
        self.open_btn.clicked.connect(self.open_selected_report)
        self.open_btn.setEnabled(False)
        recent_controls.addWidget(self.open_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_report)
        self.delete_btn.setEnabled(False)
        recent_controls.addWidget(self.delete_btn)

        recent_controls.addStretch()

        self.recent_list.itemSelectionChanged.connect(self.on_recent_selection_changed)

        recent_layout.addLayout(recent_controls)
        recent_group.setLayout(recent_layout)
        main_layout.addWidget(recent_group)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; padding: 5px;")
        main_layout.addWidget(self.status_label)

        # Load recent reports
        self.load_recent_reports()

    def set_dataframe(self, df):
        """Set the current data for reports"""
        self.current_dataframe = df
        self.quick_report_btn.setEnabled(True)
        self.custom_report_btn.setEnabled(True)
        self.status_label.setText(f"Ready to generate reports ({len(df):,} rows loaded)")

    def generate_quick_report(self):
        """Generate a quick report with default sections"""
        if self.current_dataframe is None:
            QMessageBox.warning(self, "No Data", "Please load data first")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Quick Report",
            str(Path.home() / "quick_report.html"),
            "HTML Files (*.html)"
        )

        if not file_path:
            return

        try:
            from services.report_service import ReportService

            report_service = ReportService()
            report_service.create_quick_report(
                self.current_dataframe,
                title="Quick Data Analysis Report",
                output_path=file_path
            )

            self.status_label.setText(f"Quick report generated: {file_path}")
            self.add_recent_report(file_path)

            QMessageBox.information(
                self,
                "Report Generated",
                f"Quick report successfully generated!\n\nSaved to:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Generation Error",
                f"Failed to generate report:\n{str(e)}"
            )

    def build_custom_report(self):
        """Open the custom report builder dialog"""
        if self.current_dataframe is None:
            QMessageBox.warning(self, "No Data", "Please load data first")
            return

        from ..dialogs.report_builder_dialog import ReportBuilderDialog

        dialog = ReportBuilderDialog(self.current_dataframe, self)
        if dialog.exec():
            file_path = dialog.result()  # File path is saved during generation
            self.add_recent_report(file_path)
            self.status_label.setText(f"Custom report generated: {file_path}")

    def export_report(self):
        """Export the current report"""
        # This would be used if we had a current report in memory
        QMessageBox.information(self, "Export", "Use Generate or Build to create a new report")

    def load_recent_reports(self):
        """Load recent reports from file"""
        self.recent_list.clear()
        self.recent_reports_file = Path.home() / ".caatmaster_recent_reports.txt"

        if self.recent_reports_file.exists():
            try:
                with open(self.recent_reports_file, 'r') as f:
                    recent_reports = f.read().strip().split('\n')

                for report_path in recent_reports:
                    if Path(report_path).exists():
                        item = QListWidgetItem(Path(report_path).name)
                        item.setData(Qt.UserRole, report_path)
                        item.setToolTip(report_path)
                        self.recent_list.addItem(item)
            except Exception as e:
                print(f"Error loading recent reports: {e}")

        self._recent_empty_state.set_visible(self.recent_list.count() == 0)

    def add_recent_report(self, file_path: str):
        """Add a report to the recent list"""
        self.recent_reports_file = Path.home() / ".caatmaster_recent_reports.txt"

        # Read existing
        recent_reports = []
        if self.recent_reports_file.exists():
            try:
                with open(self.recent_reports_file, 'r') as f:
                    recent_reports = f.read().strip().split('\n')
            except:
                pass

        # Add new report at the beginning
        recent_reports.insert(0, file_path)

        # Keep only last 10
        recent_reports = recent_reports[:10]

        # Save
        try:
            self.recent_reports_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.recent_reports_file, 'w') as f:
                f.write('\n'.join(recent_reports))
        except Exception as e:
            print(f"Error saving recent reports: {e}")

        # Reload list
        self.load_recent_reports()

    def open_report(self, item: QListWidgetItem):
        """Open a report in the default browser"""
        file_path = item.data(Qt.UserRole)

        if not Path(file_path).exists():
            QMessageBox.warning(self, "File Not Found", f"The report file no longer exists:\n{file_path}")
            return

        try:
            import webbrowser
            import os

            # Convert to file:// URL
            file_url = f"file:///{os.path.abspath(file_path).replace(os.sep, '/')}"
            webbrowser.open(file_url)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Open Error",
                f"Failed to open report:\n{str(e)}"
            )

    def open_selected_report(self):
        """Open the selected report"""
        current_item = self.recent_list.currentItem()
        if current_item:
            self.open_report(current_item)

    def delete_report(self):
        """Delete the selected report"""
        current_item = self.recent_list.currentItem()
        if not current_item:
            return

        file_path = current_item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self,
            "Delete Report",
            f"Delete this report?\n\n{Path(file_path).name}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Delete file
                Path(file_path).unlink()

                # Remove from list
                self.recent_list.takeItem(self.recent_list.row(current_item))
                self._recent_empty_state.set_visible(self.recent_list.count() == 0)

            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete report:\n{str(e)}")

    def on_recent_selection_changed(self):
        """Handle selection change in recent reports"""
        has_selection = self.recent_list.currentItem() is not None
        self.open_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
