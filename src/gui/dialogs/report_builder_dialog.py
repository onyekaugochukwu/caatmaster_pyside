"""
Report Builder Dialog - Configure and generate reports
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QCheckBox, QComboBox, QLineEdit,
    QSpinBox, QGroupBox, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path


class ReportSectionItem:
    """Represents a report section item"""

    def __init__(self, title: str, section_type: str, config: dict = None):
        self.title = title
        self.section_type = section_type
        self.config = config or {}

    def to_dict(self):
        return {
            'title': self.title,
            'section_type': self.section_type,
            'config': self.config
        }


class ChartConfigDialog(QDialog):
    """Dialog for configuring chart sections"""

    def __init__(self, df_columns: list, numeric_cols: list, categorical_cols: list, parent=None):
        super().__init__(parent)
        self.df_columns = df_columns
        self.numeric_cols = numeric_cols
        self.categorical_cols = categorical_cols
        self.chart_config = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Configure Chart")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Form layout
        form_layout = QFormLayout()

        # Chart type
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems([
            "Bar Chart", "Line Chart", "Scatter Plot",
            "Histogram", "Pie Chart", "Box Plot", "Heatmap", "Area Chart"
        ])
        self.chart_type_combo.currentIndexChanged.connect(self.on_chart_type_changed)
        form_layout.addRow("Chart Type:", self.chart_type_combo)

        # Title
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("My Chart")
        form_layout.addRow("Title:", self.title_input)

        # X axis
        self.x_column_combo = QComboBox()
        self.x_column_combo.addItems(self.df_columns)
        form_layout.addRow("X Axis:", self.x_column_combo)

        # Y axis
        self.y_column_combo = QComboBox()
        self.y_column_combo.addItems(self.numeric_cols)
        form_layout.addRow("Y Axis:", self.y_column_combo)

        # Value column (for histogram/box/pie)
        self.value_column_combo = QComboBox()
        self.value_column_combo.addItems(self.numeric_cols)
        form_layout.addRow("Value Column:", self.value_column_combo)

        # Label column (for pie)
        self.label_column_combo = QComboBox()
        self.label_column_combo.addItems(self.df_columns)
        form_layout.addRow("Label Column:", self.label_column_combo)

        # Group column
        self.group_column_combo = QComboBox()
        self.group_column_combo.addItems(self.df_columns)
        form_layout.addRow("Group/Color:", self.group_column_combo)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QHBoxLayout()
        ok_btn = QPushButton("Add")
        ok_btn.clicked.connect(self.validate_and_accept)
        buttons.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

        # Initialize state
        self.on_chart_type_changed(0)

    def on_chart_type_changed(self, index):
        """Handle chart type change"""
        chart_types = ["bar", "line", "scatter", "histogram", "pie", "box", "heatmap", "area"]
        chart_type = chart_types[index]

        # Show/hide relevant fields
        self.x_column_combo.setVisible(True)
        self.y_column_combo.setVisible(False)
        self.value_column_combo.setVisible(False)
        self.label_column_combo.setVisible(False)
        self.group_column_combo.setVisible(True)

        if chart_type in ["bar", "line", "scatter", "area"]:
            self.y_column_combo.setVisible(True)
        elif chart_type == "histogram":
            self.x_column_combo.setVisible(False)
            self.value_column_combo.setVisible(True)
            self.group_column_combo.setVisible(False)
        elif chart_type == "pie":
            self.x_column_combo.setVisible(False)
            self.label_column_combo.setVisible(True)
            self.value_column_combo.setVisible(True)
            self.group_column_combo.setVisible(False)
        elif chart_type == "box":
            self.x_column_combo.setVisible(False)
            self.value_column_combo.setVisible(True)
        elif chart_type == "heatmap":
            self.x_column_combo.setVisible(False)
            self.group_column_combo.setVisible(False)

    def validate_and_accept(self):
        """Validate and accept dialog"""
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation Error", "Please enter a title")
            return

        chart_types = ["bar", "line", "scatter", "histogram", "pie", "box", "heatmap", "area"]
        chart_type = chart_types[self.chart_type_combo.currentIndex()]

        self.chart_config = {
            'title': title,
            'type': chart_type,
            'x_column': self.x_column_combo.currentText(),
            'y_column': self.y_column_combo.currentText(),
            'value_column': self.value_column_combo.currentText(),
            'label_column': self.label_column_combo.currentText(),
            'group_column': self.group_column_combo.currentText() or None,
            'figsize': (10, 6)
        }

        # Validate required fields based on chart type
        if chart_type in ["bar", "line", "scatter", "area"]:
            if not self.chart_config['x_column'] or not self.chart_config['y_column']:
                QMessageBox.warning(self, "Validation Error", "Please select X and Y columns")
                return
        elif chart_type == "histogram":
            if not self.chart_config['value_column']:
                QMessageBox.warning(self, "Validation Error", "Please select a value column")
                return
        elif chart_type == "pie":
            if not self.chart_config['label_column'] or not self.chart_config['value_column']:
                QMessageBox.warning(self, "Validation Error", "Please select label and value columns")
                return
        elif chart_type == "box":
            if not self.chart_config['value_column']:
                QMessageBox.warning(self, "Validation Error", "Please select a value column")
                return

        self.accept()

    def get_config(self):
        return self.chart_config


class ReportBuilderDialog(QDialog):
    """Dialog for building and generating reports"""

    def __init__(self, df, parent=None):
        super().__init__(parent)
        self.df = df
        self.sections = []
        self.setup_ui()
        self.load_dataframe_info()

    def setup_ui(self):
        self.setWindowTitle("Report Builder")
        self.setMinimumSize(900, 600)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Report info
        info_group = QGroupBox("Report Information")
        info_layout = QFormLayout()

        self.report_title_input = QLineEdit()
        self.report_title_input.setText("Data Analysis Report")
        info_layout.addRow("Report Title:", self.report_title_input)

        self.author_input = QLineEdit()
        self.author_input.setText("CAATmaster")
        info_layout.addRow("Author:", self.author_input)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Add sections
        left_panel = QGroupBox("Add Sections")
        left_layout = QVBoxLayout()

        # Section buttons
        self.add_summary_btn = QPushButton("Add Summary Section")
        self.add_summary_btn.clicked.connect(self.add_summary_section)
        left_layout.addWidget(self.add_summary_btn)

        self.add_text_btn = QPushButton("Add Text Section")
        self.add_text_btn.clicked.connect(self.add_text_section)
        left_layout.addWidget(self.add_text_btn)

        self.add_chart_btn = QPushButton("Add Chart Section")
        self.add_chart_btn.clicked.connect(self.add_chart_section)
        left_layout.addWidget(self.add_chart_btn)

        self.add_table_btn = QPushButton("Add Data Table")
        self.add_table_btn.clicked.connect(self.add_table_section)
        left_layout.addWidget(self.add_table_btn)

        left_layout.addStretch()

        # Quick report checkbox
        self.quick_report_cb = QCheckBox("Generate Quick Report")
        self.quick_report_cb.setChecked(True)
        self.quick_report_cb.setToolTip("Auto-generate a report with summary, chart, and table")
        left_layout.addWidget(self.quick_report_cb)

        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)

        # Right panel - Sections list
        right_panel = QGroupBox("Report Sections (in order)")
        right_layout = QVBoxLayout()

        self.sections_list = QListWidget()
        self.sections_list.setDragDropMode(QListWidget.InternalMove)
        right_layout.addWidget(self.sections_list)

        # Section controls
        section_controls = QHBoxLayout()

        self.remove_section_btn = QPushButton("Remove")
        self.remove_section_btn.clicked.connect(self.remove_section)
        section_controls.addWidget(self.remove_section_btn)

        self.move_up_btn = QPushButton("Move Up")
        self.move_up_btn.clicked.connect(lambda: self.move_section(-1))
        section_controls.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("Move Down")
        self.move_down_btn.clicked.connect(lambda: self.move_section(1))
        section_controls.addWidget(self.move_down_btn)

        right_layout.addLayout(section_controls)

        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # Buttons
        buttons = QHBoxLayout()

        generate_btn = QPushButton("Generate Report")
        generate_btn.setStyleSheet("""
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
        generate_btn.clicked.connect(self.generate_report)
        buttons.addWidget(generate_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

    def load_dataframe_info(self):
        """Load DataFrame column info"""
        import polars as pl

        self.numeric_cols = []
        self.categorical_cols = []

        for col in self.df.columns:
            if self.df[col].dtype in [pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                                      pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                                      pl.Float32, pl.Float64]:
                self.numeric_cols.append(col)
            else:
                self.categorical_cols.append(col)

        self.all_columns = list(self.df.columns)

    def add_summary_section(self):
        """Add a summary statistics section"""
        item = QListWidgetItem("📊 Summary Statistics")
        item.setData(Qt.UserRole, ReportSectionItem(
            "Data Overview",
            "summary"
        ))
        self.sections_list.addItem(item)

    def add_text_section(self):
        """Add a custom text section"""
        from PySide6.QtWidgets import QInputDialog

        title, ok = QInputDialog.getText(self, "Text Section", "Section Title:")
        if ok and title:
            content, ok = QInputDialog.getText(self, "Text Section", "Content:")
            if ok:
                item = QListWidgetItem(f"📝 {title}")
                item.setData(Qt.UserRole, ReportSectionItem(
                    title,
                    "text",
                    {'content': content}
                ))
                self.sections_list.addItem(item)

    def add_chart_section(self):
        """Add a chart section"""
        dialog = ChartConfigDialog(
            self.all_columns,
            self.numeric_cols,
            self.categorical_cols,
            self
        )

        if dialog.exec():
            config = dialog.get_config()
            chart_type_names = {
                'bar': 'Bar Chart',
                'line': 'Line Chart',
                'scatter': 'Scatter Plot',
                'histogram': 'Histogram',
                'pie': 'Pie Chart',
                'box': 'Box Plot',
                'heatmap': 'Heatmap',
                'area': 'Area Chart'
            }

            item = QListWidgetItem(f"📈 {config['title']} ({chart_type_names.get(config['type'], 'Chart')})")
            item.setData(Qt.UserRole, ReportSectionItem(
                config['title'],
                "chart",
                config
            ))
            self.sections_list.addItem(item)

    def add_table_section(self):
        """Add a data table section"""
        from PySide6.QtWidgets import QInputDialog

        title, ok = QInputDialog.getText(self, "Table Section", "Section Title:", text="Sample Data")
        if ok:
            max_rows, ok = QInputDialog.getInt(self, "Table Section", "Maximum rows:", 100, 1, 10000)
            if ok:
                item = QListWidgetItem(f"📋 {title}")
                item.setData(Qt.UserRole, ReportSectionItem(
                    title,
                    "table",
                    {'max_rows': max_rows}
                ))
                self.sections_list.addItem(item)

    def remove_section(self):
        """Remove selected section"""
        current_row = self.sections_list.currentRow()
        if current_row >= 0:
            self.sections_list.takeItem(current_row)

    def move_section(self, direction):
        """Move section up or down"""
        current_row = self.sections_list.currentRow()
        if current_row < 0:
            return

        new_row = current_row + direction
        if 0 <= new_row < self.sections_list.count():
            item = self.sections_list.takeItem(current_row)
            self.sections_list.insertItem(new_row, item)
            self.sections_list.setCurrentRow(new_row)

    def generate_report(self):
        """Generate the report"""
        title = self.report_title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Validation Error", "Please enter a report title")
            return

        # Collect sections
        sections = []
        for i in range(self.sections_list.count()):
            item = self.sections_list.item(i)
            section_item = item.data(Qt.UserRole)
            sections.append(section_item)

        # If quick report and no sections, add defaults
        if self.quick_report_cb.isChecked() and not sections:
            sections.append(ReportSectionItem("Data Overview", "summary"))
            sections.append(ReportSectionItem("Sample Data", "table", {'max_rows': 100}))

        if not sections:
            QMessageBox.warning(self, "No Sections", "Please add at least one section to the report")
            return

        # Ask for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            str(Path.home() / f"{title.replace(' ', '_')}.html"),
            "HTML Files (*.html)"
        )

        if not file_path:
            return

        try:
            from services.report_service import ReportService, ReportSection

            report_service = ReportService()

            # Convert ReportSectionItems to ReportSections
            report_sections = []
            for section_item in sections:
                report_sections.append(ReportSection(
                    section_item.title,
                    section_item.section_type,
                    section_item.config.get('content'),
                    section_item.config,
                    section_item.config
                ))

            # Generate report
            html = report_service.generate_report(
                self.df,
                title,
                report_sections,
                self.author_input.text(),
                output_path=file_path
            )

            QMessageBox.information(
                self,
                "Report Generated",
                f"Report successfully generated!\n\nSaved to:\n{file_path}"
            )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Generation Error",
                f"Failed to generate report:\n{str(e)}"
            )
