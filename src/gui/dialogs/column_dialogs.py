"""
Column-related dialogs for CAATmaster
Includes: Rename Columns, Choose Columns, Change Data Type
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QWidget, QMessageBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QListWidget, QListWidgetItem, QAbstractItemView,
    QFrame, QSplitter, QRadioButton, QButtonGroup, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button
from ..theme import Colors


class RenameColumnsDialog(BaseModal):
    """Dialog for renaming columns - supports bulk operations"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Rename Columns", dataframe, parent)
        self.setMinimumSize(600, 500)

    def _setup_ui(self):
        # BaseModal.__init__ calls this once to build the dialog's one and
        # only layout — building it here (rather than after super().__init__()
        # returns) avoids installing a second QVBoxLayout(self) on top of
        # one BaseModal already set, which Qt silently ignores and leaves
        # the dialog showing nothing but the base placeholder label.
        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create content widget
        self.content_widget = QWidget()
        self._setup_ui_content()

        self.scroll_area.setWidget(self.content_widget)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.scroll_area)

        # Add buttons at bottom
        self._setup_buttons()

    def _setup_ui_content(self):
        layout = QVBoxLayout(self.content_widget)
        layout.setSpacing(15)

        # Preview section
        preview_group = QGroupBox("Column Renaming Preview")
        preview_layout = QVBoxLayout(preview_group)

        # Column mapping table
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(3)
        self.mapping_table.setHorizontalHeaderLabels(["Original Name", "New Name", "Preview"])
        self.mapping_table.horizontalHeader().setStretchLastSection(True)
        self.mapping_table.setRowCount(len(self.original_df.columns))

        for row, col in enumerate(self.original_df.columns):
            # Original name (read-only)
            orig_item = QTableWidgetItem(col)
            orig_item.setFlags(Qt.ItemIsEnabled)
            self.mapping_table.setItem(row, 0, orig_item)

            # New name (editable)
            new_item = QTableWidgetItem(f"{col}_renamed")
            self.mapping_table.setItem(row, 1, new_item)

            # Preview
            preview_item = QTableWidgetItem(f"{col} → {col}_renamed")
            preview_item.setFlags(Qt.ItemIsEnabled)
            preview_item.setForeground(Qt.gray)
            self.mapping_table.setItem(row, 2, preview_item)

        self.mapping_table.cellChanged.connect(self._on_new_name_changed)
        preview_layout.addWidget(self.mapping_table)

        layout.addWidget(preview_group)

        # Bulk operations section
        bulk_group = QGroupBox("Bulk Operations")
        bulk_layout = QGridLayout(bulk_group)

        # Prefix
        bulk_layout.addWidget(QLabel("Add Prefix:"), 0, 0)
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("e.g., 'new_'")
        self.prefix_edit.setMinimumWidth(200)
        self.prefix_edit.textChanged.connect(self._apply_bulk_changes)
        bulk_layout.addWidget(self.prefix_edit, 0, 1)

        # Suffix
        bulk_layout.addWidget(QLabel("Add Suffix:"), 1, 0)
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("e.g., '_old'")
        self.suffix_edit.setMinimumWidth(200)
        self.suffix_edit.textChanged.connect(self._apply_bulk_changes)
        bulk_layout.addWidget(self.suffix_edit, 1, 1)

        # Case conversion
        bulk_layout.addWidget(QLabel("Case:"), 2, 0)
        case_layout = QHBoxLayout()
        self.case_group = QButtonGroup()
        self.no_case_radio = QRadioButton("Keep")
        self.no_case_radio.setChecked(True)
        self.no_case_radio.toggled.connect(self._apply_bulk_changes)
        self.case_group.addButton(self.no_case_radio)
        case_layout.addWidget(self.no_case_radio)

        self.lower_radio = QRadioButton("lowercase")
        self.lower_radio.toggled.connect(self._apply_bulk_changes)
        self.case_group.addButton(self.lower_radio)
        case_layout.addWidget(self.lower_radio)

        self.upper_radio = QRadioButton("UPPERCASE")
        self.upper_radio.toggled.connect(self._apply_bulk_changes)
        self.case_group.addButton(self.upper_radio)
        case_layout.addWidget(self.upper_radio)

        case_layout.addStretch()
        bulk_layout.addLayout(case_layout, 2, 1)

        # Reset button
        reset_btn = QPushButton("Reset to Original")
        reset_btn.setStyleSheet("min-width: 140px; padding: 4px 8px;")
        reset_btn.clicked.connect(self._reset_mapping)
        bulk_layout.addWidget(reset_btn, 3, 0, 1, 2)

        layout.addWidget(bulk_group)

        # Info label
        self.info_label = QLabel("Edit individual names above or use bulk operations")
        self.info_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.info_label)

    def _setup_buttons(self):
        """Setup buttons at the bottom of the dialog"""
        btn_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = create_primary_button("Apply Renames")
        self.apply_btn.setStyleSheet("min-width: 120px; padding: 4px 8px;")
        self.apply_btn.clicked.connect(self._apply_renames)
        btn_layout.addWidget(self.apply_btn)

        # Add buttons to main layout (outside scroll area)
        self.layout().addLayout(btn_layout)

    def _on_new_name_changed(self, row, col):
        """Update preview when new name is edited"""
        if col == 1:  # New name column
            orig_item = self.mapping_table.item(row, 0)
            new_item = self.mapping_table.item(row, 1)
            if orig_item and new_item:
                preview_item = QTableWidgetItem(f"{orig_item.text()} → {new_item.text()}")
                preview_item.setFlags(Qt.ItemIsEnabled)
                preview_item.setForeground(Qt.gray)
                self.mapping_table.setItem(row, 2, preview_item)

    def _apply_bulk_changes(self):
        """Apply prefix, suffix, and case changes to all columns"""
        prefix = self.prefix_edit.text()
        suffix = self.suffix_edit.text()

        if self.lower_radio.isChecked():
            case_func = str.lower
        elif self.upper_radio.isChecked():
            case_func = str.upper
        else:
            case_func = lambda x: x

        for row in range(self.mapping_table.rowCount()):
            orig_item = self.mapping_table.item(row, 0)
            if orig_item:
                orig_name = orig_item.text()
                new_name = case_func(orig_name)
                new_name = f"{prefix}{new_name}{suffix}"
                self.mapping_table.blockSignals(True)
                self.mapping_table.setItem(row, 1, QTableWidgetItem(new_name))
                self.mapping_table.blockSignals(False)
                self._on_new_name_changed(row, 1)

    def _reset_mapping(self):
        """Reset all mappings to original names"""
        self.prefix_edit.clear()
        self.suffix_edit.clear()
        self.no_case_radio.setChecked(True)

        for row in range(self.mapping_table.rowCount()):
            orig_item = self.mapping_table.item(row, 0)
            if orig_item:
                new_item = QTableWidgetItem(orig_item.text())
                self.mapping_table.setItem(row, 1, new_item)
                self._on_new_name_changed(row, 1)

    def _apply_renames(self):
        """Validate and accept the renames"""
        # Check for duplicates
        new_names = []
        for row in range(self.mapping_table.rowCount()):
            new_item = self.mapping_table.item(row, 1)
            if new_item:
                new_name = new_item.text().strip()
                if not new_name:
                    QMessageBox.warning(self, "Error", f"Row {row + 1}: New name cannot be empty.")
                    return
                if new_name in new_names:
                    QMessageBox.warning(self, "Error", f"Duplicate name: '{new_name}'")
                    return
                new_names.append(new_name)

        self.accept()

    def get_parameters(self) -> dict:
        """Get the rename mappings"""
        renames = []
        for row in range(self.mapping_table.rowCount()):
            orig_item = self.mapping_table.item(row, 0)
            new_item = self.mapping_table.item(row, 1)
            if orig_item and new_item:
                renames.append({
                    "old_name": orig_item.text(),
                    "new_name": new_item.text().strip()
                })

        return {
            "renames": renames,
            "prefix": self.prefix_edit.text(),
            "suffix": self.suffix_edit.text(),
            "lowercase": self.lower_radio.isChecked(),
            "uppercase": self.upper_radio.isChecked()
        }

    def validate(self) -> bool:
        """Validate parameters"""
        return bool(self.mapping_table.rowCount() > 0)


class ChooseColumnsDialog(BaseModal):
    """Dialog for selecting, removing, or reordering columns"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Choose Columns", dataframe, parent)
        self.setMinimumSize(700, 500)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Action selection
        action_group = QGroupBox("Action")
        action_layout = QHBoxLayout(action_group)

        self.action_group = QButtonGroup()
        self.keep_radio = QRadioButton("Keep Selected Columns")
        self.keep_radio.setChecked(True)
        self.remove_radio = QRadioButton("Remove Selected Columns")
        self.reorder_radio = QRadioButton("Reorder Columns")

        self.action_group.addButton(self.keep_radio)
        self.action_group.addButton(self.remove_radio)
        self.action_group.addButton(self.reorder_radio)

        action_layout.addWidget(self.keep_radio)
        action_layout.addWidget(self.remove_radio)
        action_layout.addWidget(self.reorder_radio)
        action_layout.addStretch()

        self.keep_radio.toggled.connect(self._on_action_changed)
        self.remove_radio.toggled.connect(self._on_action_changed)
        self.reorder_radio.toggled.connect(self._on_action_changed)

        layout.addWidget(action_group)

        # Column selection
        selection_group = QGroupBox("Available Columns")
        selection_layout = QVBoxLayout(selection_group)

        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type to filter columns...")
        self.search_edit.textChanged.connect(self._filter_columns)
        search_layout.addWidget(self.search_edit)
        selection_layout.addLayout(search_layout)

        # Column lists
        lists_splitter = QSplitter(Qt.Horizontal)

        # Available columns
        available_widget = QWidget()
        available_layout = QVBoxLayout(available_widget)
        available_layout.addWidget(QLabel("Available Columns:"))
        self.selection_hint = QLabel()
        self.selection_hint.setWordWrap(True)
        self.selection_hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        available_layout.addWidget(self.selection_hint)
        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for col in self.original_df.columns:
            self.available_list.addItem(col)
        available_layout.addWidget(self.available_list)

        # Selected columns (reorder mode only - Keep/Remove select directly
        # in Available Columns above instead, since Apply reads highlighted
        # items there, not whatever's been moved into this list)
        self.selected_widget = QWidget()
        selected_layout = QVBoxLayout(self.selected_widget)
        selected_layout.addWidget(QLabel("Selected Columns (in order):"))
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.selected_list.setDragDropMode(QAbstractItemView.DragDrop)
        self.selected_list.setDefaultDropAction(Qt.MoveAction)
        selected_layout.addWidget(self.selected_list)

        lists_splitter.addWidget(available_widget)
        lists_splitter.addWidget(self.selected_widget)
        lists_splitter.setSizes([200, 200])

        selection_layout.addWidget(lists_splitter)
        layout.addWidget(selection_group)

        # Move buttons (reorder mode only - see selected_widget comment above)
        self.move_widget = QWidget()
        move_layout = QHBoxLayout(self.move_widget)
        move_layout.setContentsMargins(0, 0, 0, 0)

        # Explicit min-width on this whole row so none of these four
        # labels (the two multi-word ones especially) get squeezed below
        # readable size under a narrower window or Windows' wider
        # DPI-scaled font metrics - the window grows instead.
        add_btn = QPushButton("Add →")
        add_btn.setStyleSheet("min-width: 70px; padding: 4px 8px;")
        add_btn.clicked.connect(self._add_selected)
        move_layout.addWidget(add_btn)

        add_all_btn = QPushButton("Add All >>")
        add_all_btn.setStyleSheet("min-width: 100px; padding: 4px 8px;")
        add_all_btn.clicked.connect(self._add_all)
        move_layout.addWidget(add_all_btn)

        remove_btn = QPushButton("← Remove")
        remove_btn.setStyleSheet("min-width: 90px; padding: 4px 8px;")
        remove_btn.clicked.connect(self._remove_selected)
        move_layout.addWidget(remove_btn)

        remove_all_btn = QPushButton("<< Remove All")
        remove_all_btn.setStyleSheet("min-width: 120px; padding: 4px 8px;")
        remove_all_btn.clicked.connect(self._remove_all)
        move_layout.addWidget(remove_all_btn)

        move_layout.addStretch()
        layout.addWidget(self.move_widget)

        # Preview
        preview_group = QGroupBox("Column Order Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("No columns selected")
        self.preview_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.BG_SECONDARY};
                padding: 10px;
                border-radius: 4px;
                font-family: monospace;
            }}
        """)
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = create_primary_button("Apply")
        self.apply_btn.clicked.connect(self._apply_selection)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

        self._on_action_changed()
        self._update_preview()

    def _on_action_changed(self):
        """Update UI based on selected action. The Add/Remove move
        buttons and the "Selected Columns" list only make sense in
        Reorder mode - Apply's validation for Keep/Remove reads directly
        selected (highlighted) items in Available Columns, not whatever
        was moved into the (otherwise hidden) selected list, so both are
        hidden here to avoid the confusing "select column, click Add, it
        vanishes, Apply says nothing is selected" trap."""
        is_reorder = self.reorder_radio.isChecked()
        self.selected_widget.setVisible(is_reorder)
        self.move_widget.setVisible(is_reorder)
        if is_reorder:
            self.selection_hint.setText(
                "Click a column below, then 'Add →' to move it into your desired order on the right."
            )
        elif self.remove_radio.isChecked():
            self.selection_hint.setText(
                "Click a column to select it for removal - Ctrl+Click (or Shift+Click) to select multiple."
            )
        else:
            self.selection_hint.setText(
                "Click a column to select it to keep - Ctrl+Click (or Shift+Click) to select multiple."
            )

    def _filter_columns(self, text):
        """Filter available columns based on search text"""
        for i in range(self.available_list.count()):
            item = self.available_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _add_selected(self):
        """Move selected items from available to selected"""
        for item in self.available_list.selectedItems():
            self.available_list.takeItem(self.available_list.row(item))
            self.selected_list.addItem(item.text())
        self._update_preview()

    def _add_all(self):
        """Move all items from available to selected"""
        while self.available_list.count() > 0:
            item = self.available_list.takeItem(0)
            self.selected_list.addItem(item.text())
        self._update_preview()

    def _remove_selected(self):
        """Move selected items from selected back to available"""
        for item in self.selected_list.selectedItems():
            self.selected_list.takeItem(self.selected_list.row(item))
            # Add back to available in alphabetical order
            self.available_list.addItem(item.text())
        self.available_list.sortItems()
        self._update_preview()

    def _remove_all(self):
        """Move all items from selected back to available"""
        while self.selected_list.count() > 0:
            item = self.selected_list.takeItem(0)
            self.available_list.addItem(item.text())
        self.available_list.sortItems()
        self._update_preview()

    def _update_preview(self):
        """Update the column order preview"""
        if self.reorder_radio.isChecked():
            cols = [self.selected_list.item(i).text() for i in range(self.selected_list.count())]
        else:
            cols = [self.available_list.item(i).text() for i in range(self.available_list.count())
                    if not self.available_list.item(i).isHidden()]

        if cols:
            preview = " | ".join(cols)
            self.preview_label.setText(preview)
        else:
            self.preview_label.setText("No columns selected")

    def _apply_selection(self):
        """Validate and accept the selection"""
        if self.keep_radio.isChecked() or self.remove_radio.isChecked():
            selected = [self.available_list.item(i).text() for i in range(self.available_list.count())
                       if not self.available_list.item(i).isHidden() and self.available_list.item(i).isSelected()]
            if not selected:
                QMessageBox.warning(self, "Warning", "Please select at least one column.")
                return
        else:  # reorder
            if self.selected_list.count() == 0:
                QMessageBox.warning(self, "Warning", "Please select columns in the desired order.")
                return

        self.accept()

    def get_parameters(self) -> dict:
        """Get the selection parameters"""
        if self.reorder_radio.isChecked():
            column_order = [self.selected_list.item(i).text() for i in range(self.selected_list.count())]
            return {
                "action": "reorder",
                "column_order": column_order
            }
        elif self.keep_radio.isChecked():
            columns = [self.available_list.item(i).text() for i in range(self.available_list.count())
                      if not self.available_list.item(i).isHidden() and self.available_list.item(i).isSelected()]
            return {
                "action": "keep",
                "columns_to_keep": columns
            }
        else:
            columns = [self.available_list.item(i).text() for i in range(self.available_list.count())
                      if self.available_list.item(i).isSelected()]
            return {
                "action": "remove",
                "columns_to_remove": columns
            }

    def validate(self) -> bool:
        """Validate parameters"""
        params = self.get_parameters()
        if params["action"] == "reorder":
            return len(params.get("column_order", [])) > 0
        return True


class ChangeDataTypeDialog(BaseModal):
    """Dialog for converting column data types"""

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("Change Data Type", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 400)

    def _setup_ui(self):
        # BaseModal.__init__ calls this once to build the dialog's one and
        # only layout — building it here (rather than after super().__init__()
        # returns) avoids installing a second QVBoxLayout(self) on top of
        # one BaseModal already set, which Qt silently ignores and leaves
        # the dialog showing nothing but the base placeholder label.
        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create content widget
        self.content_widget = QWidget()
        self._setup_ui_content()

        self.scroll_area.setWidget(self.content_widget)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.scroll_area)

        # Add buttons at bottom
        self._setup_buttons()

        if self.selected_column and hasattr(self, 'column_selector'):
            self.column_selector.set_current_column(self.selected_column)

    def _setup_ui_content(self):
        layout = QVBoxLayout(self.content_widget)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Column Selection")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column to Convert:")
        col_layout.addWidget(self.column_selector)

        # Current type display
        self.current_type_label = QLabel("Current type: -")
        self.current_type_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        col_layout.addWidget(self.current_type_label)

        layout.addWidget(col_group)

        # New type selection
        type_group = QGroupBox("New Data Type")
        type_layout = QGridLayout(type_group)

        type_layout.addWidget(QLabel("Convert to:"), 0, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Int8 (8-bit integer)",
            "Int16 (16-bit integer)",
            "Int32 (32-bit integer)",
            "Int64 (64-bit integer)",
            "Float32 (32-bit float)",
            "Float64 (64-bit float)",
            "Utf8 (Text)",
            "Boolean",
            "Date (YYYY-MM-DD)",
            "Datetime",
            "Categorical"
        ])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo, 0, 1)

        # Format string for dates
        self.format_layout = QHBoxLayout()
        self.format_layout.addWidget(QLabel("Format:"))
        self.format_edit = QLineEdit()
        self.format_edit.setPlaceholderText("e.g., %Y-%m-%d for dates")
        self.format_layout.addWidget(self.format_edit)
        self.format_widget = QWidget()
        self.format_widget.setLayout(self.format_layout)
        self.format_widget.setVisible(False)
        type_layout.addWidget(self.format_widget, 1, 0, 1, 2)

        layout.addWidget(type_group)

        # Error handling
        error_group = QGroupBox("Error Handling")
        error_layout = QVBoxLayout(error_group)

        self.error_radio_group = QButtonGroup()
        self.fail_radio = QRadioButton("Fail if conversion fails")
        self.fail_radio.setChecked(True)
        error_layout.addWidget(self.fail_radio)
        self.error_radio_group.addButton(self.fail_radio)

        self.coerce_radio = QRadioButton("Coerce errors to null")
        error_layout.addWidget(self.coerce_radio)
        self.error_radio_group.addButton(self.coerce_radio)

        layout.addWidget(error_group)

        # Preview
        preview_group = QGroupBox("Conversion Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("Select a column to preview")
        self.preview_label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.BG_SECONDARY};
                padding: 10px;
                border-radius: 4px;
                font-family: monospace;
                min-height: 60px;
            }}
        """)
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(preview_group)

    def _setup_buttons(self):
        """Setup buttons at the bottom of the dialog"""
        btn_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = create_primary_button("Convert Type")
        self.apply_btn.clicked.connect(self._apply_conversion)
        btn_layout.addWidget(self.apply_btn)

        # Add buttons to main layout (outside scroll area)
        self.layout().addLayout(btn_layout)

    def _on_type_changed(self, index):
        """Show/hide format field based on selected type"""
        type_text = self.type_combo.currentText()
        show_format = "Date" in type_text
        self.format_widget.setVisible(show_format)

        # Update preview
        column = self.column_selector.get_column()
        if column:
            self._update_preview(column, type_text)

    def _update_preview(self, column: str, new_type: str):
        """Update the conversion preview"""
        if column not in self.original_df.columns:
            return

        try:
            current_dtype = self.original_df[column].dtype
            self.current_type_label.setText(f"Current type: {current_dtype}")

            # Attempt conversion on first 5 non-null values
            sample = self.original_df[column].drop_nulls().head(5).to_list()
            if not sample:
                self.preview_label.setText("Column is empty or all null")
                return

            self.preview_label.setText(f"Sample values: {sample[:3]}...")
        except Exception as e:
            self.preview_label.setText(f"Error reading column: {str(e)}")

    def _apply_conversion(self):
        """Validate and accept the conversion"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Warning", "Please select a column.")
            return

        type_text = self.type_combo.currentText()

        # Combo items are always "<TypeName>" or "<TypeName> (description)" -
        # the leading token is exactly the key DataProcessor.change_data_type_extended
        # expects (e.g. "Float64"). Passing the full display text (including
        # the "(64-bit float)" part) through as new_dtype fails every single
        # conversion, since it never matches that method's dtype_map keys.
        new_dtype = type_text.split()[0]
        valid_dtypes = {
            "Int8", "Int16", "Int32", "Int64", "Float32", "Float64",
            "Utf8", "Boolean", "Date", "Datetime", "Categorical"
        }
        if new_dtype not in valid_dtypes:
            QMessageBox.warning(self, "Warning", "Please select a valid data type.")
            return

        params = {
            "column": column,
            "new_dtype": new_dtype,
            "format_string": self.format_edit.text() if self.format_widget.isVisible() else "",
            # change_data_type_extended takes on_error as "coerce"/"raise",
            # not a boolean - translate the radio choice here rather than
            # relying on _map_parameters_to_method to coerce types.
            "on_error": "coerce" if self.coerce_radio.isChecked() else "raise"
        }

        self.current_params = params
        self.accept()

    def get_parameters(self) -> dict:
        """Get the conversion parameters"""
        return getattr(self, 'current_params', {})

    def validate(self) -> bool:
        """Validate parameters"""
        return bool(self.column_selector.get_column())

