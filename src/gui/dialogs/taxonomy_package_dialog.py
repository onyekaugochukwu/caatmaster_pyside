"""
Manage Taxonomy Packages Dialog - register/remove local XBRL Taxonomy
Package .zip files (as published by the SEC, the IFRS Foundation, and
other taxonomy publishers) so XBRL/iXBRL parsing resolves that taxonomy
entirely from disk, with no network dependency - see
services.xbrl_import_service's module docstring for how that's verified.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog
)

from gui.theme import Colors
from gui.components.common_modals import create_primary_button, create_secondary_button


class TaxonomyPackageDialog(QDialog):
    """Dialog for registering/removing local XBRL Taxonomy Packages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Taxonomy Packages")
        self.setMinimumSize(700, 450)
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Manage Taxonomy Packages")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        hint = QLabel(
            "A registered taxonomy package lets XBRL/iXBRL import resolve that taxonomy's schema "
            "and linkbases entirely from this local file, with no network access needed - required "
            "for parsing a filing on a machine with no internet connection. Download an official "
            "package (e.g. from the SEC or the IFRS Foundation) as a .zip and add it below; it "
            "stays registered across app restarts."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Version", "Publisher", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        add_btn = create_primary_button("Add Package...")
        add_btn.clicked.connect(self._add_package)
        btn_row.addWidget(add_btn)
        remove_btn = create_secondary_button("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _refresh_table(self):
        from services.xbrl_import_service import list_taxonomy_packages

        packages = list_taxonomy_packages()
        self.table.setRowCount(len(packages))
        for row, pkg in enumerate(packages):
            self.table.setItem(row, 0, QTableWidgetItem(pkg.name))
            self.table.setItem(row, 1, QTableWidgetItem(pkg.version or ""))
            self.table.setItem(row, 2, QTableWidgetItem(pkg.publisher or ""))
            self.table.setItem(row, 3, QTableWidgetItem(pkg.status))

    def _add_package(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Taxonomy Package", "", "Taxonomy Package (*.zip)"
        )
        if not file_path:
            return

        from services.xbrl_import_service import add_taxonomy_package
        try:
            info = add_taxonomy_package(file_path)
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Package", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to register package:\n{e}")
            return

        QMessageBox.information(
            self, "Package Registered",
            f"'{info.name}' (v{info.version or 'unknown'}) is now registered for local resolution."
        )
        self._refresh_table()

    def _remove_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Select a package to remove.")
            return
        row = selected[0].row()
        name = self.table.item(row, 0).text()

        confirm = QMessageBox.question(
            self, "Remove Package",
            f"Remove '{name}'? Filings using this taxonomy will need network access again "
            "unless another registered package covers it."
        )
        if confirm != QMessageBox.Yes:
            return

        from services.xbrl_import_service import remove_taxonomy_package
        remove_taxonomy_package(name)
        self._refresh_table()
