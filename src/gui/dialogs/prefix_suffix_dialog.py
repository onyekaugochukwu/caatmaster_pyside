"""
Prefix/Suffix Dialog for CAATmaster
Add prefix or suffix to text columns
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QWidget, QMessageBox, QLineEdit,
    QRadioButton, QButtonGroup, QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt, QTimer

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button
from ..theme import Colors


class PrefixSuffixDialog(BaseModal):
    """
    Dialog for adding prefix or suffix to text columns
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None,
                 transform_type: str = "prefix"):
        self.original_df = dataframe
        self.transform_type = transform_type
        super().__init__("Add Prefix / Suffix", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(550, 450)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_modified")
            QTimer.singleShot(100, self.preview)

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if hasattr(self, 'column_selector'):
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_modified")
            QTimer.singleShot(100, self.preview)

    def _setup_ui(self):
        """Setup the prefix/suffix dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Container widget for scroll area
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column:")
        col_layout.addWidget(self.column_selector)

        scroll_layout.addWidget(col_group)

        # Operation type tabs
        self.tabs = QTabWidget()

        # Prefix tab
        self._create_prefix_tab()

        # Suffix tab
        self._create_suffix_tab()

        self.tabs.addTab(self.prefix_tab, "Add Prefix")
        self.tabs.addTab(self.suffix_tab, "Add Suffix")

        # operation_id ('text_add_prefix'/'text_add_suffix') decides
        # which method runs on Apply, independent of which tab is
        # showing. The matching tab is selected and the other is
        # disabled so the dialog cannot imply a choice Apply will not
        # honor.
        prefix_index, suffix_index = 0, 1
        self.tabs.setCurrentIndex(prefix_index if self.transform_type == "prefix" else suffix_index)
        self.tabs.setTabEnabled(suffix_index if self.transform_type == "prefix" else prefix_index, False)

        scroll_layout.addWidget(self.tabs)

        # Output options
        output_group = QGroupBox("Output Column")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("modified")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        scroll_layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        # Sample results
        self.sample_label = QLabel()
        self.sample_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;")
        preview_layout.addWidget(self.sample_label)

        scroll_layout.addWidget(preview_group)

        # Set scroll area content
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.apply_btn = create_primary_button("Apply")
        self.apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _create_prefix_tab(self):
        """Create prefix tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        options_group = QGroupBox("Prefix Options")
        options_layout = QGridLayout(options_group)

        options_layout.addWidget(QLabel("Prefix Text:"), 0, 0)
        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("Enter prefix text...")
        options_layout.addWidget(self.prefix_edit, 0, 1)

        # Common prefixes
        common_group = QGroupBox("Common Prefixes")
        common_layout = QHBoxLayout(common_group)

        prefixes = [("Mr.", "Mr."), ("Mrs.", "Mrs."), ("Dr.", "Dr."),
                    ("$", "$"), ("USD ", "USD "), ("#", "#")]
        self.prefix_presets = QButtonGroup()
        for label, value in prefixes:
            radio = QRadioButton(label)
            radio.toggled.connect(lambda checked, v=value: self._on_prefix_selected(v) if checked else None)
            common_layout.addWidget(radio)
            self.prefix_presets.addButton(radio)

        options_layout.addWidget(common_group, 1, 0, 1, 2)

        layout.addWidget(options_group)
        layout.addStretch()

        self.prefix_tab = tab

    def _create_suffix_tab(self):
        """Create suffix tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        options_group = QGroupBox("Suffix Options")
        options_layout = QGridLayout(options_group)

        options_layout.addWidget(QLabel("Suffix Text:"), 0, 0)
        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("Enter suffix text...")
        options_layout.addWidget(self.suffix_edit, 0, 1)

        # Common suffixes
        common_group = QGroupBox("Common Suffixes")
        common_layout = QHBoxLayout(common_group)

        suffixes = [(" Inc.", " Inc."), (" LLC", " LLC"), (" Corp.", " Corp."),
                    (" Ltd.", " Ltd."), (".00", ".00"), (" USD", " USD")]
        self.suffix_presets = QButtonGroup()
        for label, value in suffixes:
            radio = QRadioButton(label)
            radio.toggled.connect(lambda checked, v=value: self._on_suffix_selected(v) if checked else None)
            common_layout.addWidget(radio)
            self.suffix_presets.addButton(radio)

        options_layout.addWidget(common_group, 1, 0, 1, 2)

        layout.addWidget(options_group)
        layout.addStretch()

        self.suffix_tab = tab

    def _on_prefix_selected(self, value: str):
        """Handle prefix preset selection"""
        self.prefix_edit.setText(value)
        self.preview()

    def _on_suffix_selected(self, value: str):
        """Handle suffix preset selection"""
        self.suffix_edit.setText(value)
        self.preview()

    def get_parameters(self) -> dict:
        """Get the transform parameters"""
        tab_index = self.tabs.currentIndex()

        return {
            "column": self.column_selector.get_column(),
            "output_column": self.output_col_edit.text() or "modified",
            "operation_type": "prefix" if tab_index == 0 else "suffix",
            "prefix": self.prefix_edit.text(),
            "suffix": self.suffix_edit.text(),
        }

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column.")
            return False

        if column in self.original_df.columns:
            dtype = self.original_df[column].dtype
            if dtype not in [pl.Utf8]:
                QMessageBox.warning(self, "Validation Error",
                                  "Selected column must be text type.")
                return False

        tab_index = self.tabs.currentIndex()
        if tab_index == 0 and not self.prefix_edit.text():
            QMessageBox.warning(self, "Validation Error",
                              "Please enter a prefix text.")
            return False
        elif tab_index == 1 and not self.suffix_edit.text():
            QMessageBox.warning(self, "Validation Error",
                              "Please enter a suffix text.")
            return False

        return True

    def preview(self):
        """Generate preview of transformation"""
        try:
            params = self.get_parameters()
            column = params["column"]
            output_col = params["output_column"]

            if not column:
                return

            # Get data
            col_data = self.original_df[column].to_list()

            # Apply transformation
            if params["operation_type"] == "prefix":
                result = [f"{params['prefix']}{val}" if val else "" for val in col_data]
            else:
                result = [f"{val}{params['suffix']}" if val else "" for val in col_data]

            # Update preview
            preview_df = self.original_df[:10].clone()
            preview_df = preview_df.with_columns(
                pl.Series(name=output_col, values=result[:10])
            )
            self.preview_table.load_dataframe(preview_df)

            # Update sample label
            self.sample_label.setText(f"Sample: \"{result[0] if result else ''}\"")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
