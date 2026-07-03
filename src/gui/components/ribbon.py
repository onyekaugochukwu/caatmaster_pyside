"""
Ribbon Interface Components for CaatMaster
============================================
Power Query-style ribbon: light theme, real vector icons (qtawesome),
tokens from gui.theme instead of hardcoded colors.
"""
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QButtonGroup, QToolButton
)
from PySide6.QtCore import Qt, Signal, QSize

from gui.theme import Colors


def _icon(name: str, color: str = Colors.TEXT_SECONDARY):
    """Build a qtawesome icon in the given token color."""
    return qta.icon(name, color=color)


class RibbonButton(QToolButton):
    """Large button for ribbon with icon on top and text below."""

    def __init__(self, text, icon="", parent=None, action_callback=None):
        super().__init__(parent)
        self.setText(text)
        self.action_callback = action_callback

        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setCursor(Qt.PointingHandCursor)

        if icon:
            self.setIcon(_icon(icon))
            self.setIconSize(QSize(22, 22))

        if action_callback:
            self.clicked.connect(action_callback)

        self.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 3px 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
                min-width: 64px;
                min-height: 48px;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
            QToolButton:pressed {{
                background-color: {Colors.BG_PRESSED};
            }}
        """)


class SmallRibbonButton(QPushButton):
    """Small button for ribbon interface, icon-left / text-right."""

    def __init__(self, text, icon="", parent=None, action_callback=None):
        super().__init__(parent)
        self.setText(text)

        if icon:
            self.setIcon(_icon(icon))
            self.setIconSize(QSize(14, 14))

        self.setCursor(Qt.PointingHandCursor)
        self.action_callback = action_callback

        if action_callback:
            self.clicked.connect(action_callback)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
                text-align: left;
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
            QPushButton:pressed {{
                background-color: {Colors.BG_PRESSED};
            }}
        """)


class RibbonTab(QPushButton):
    """Tab button for ribbon."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.update_style(False)

    def update_style(self, selected):
        if selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.BG_PRIMARY};
                    color: {Colors.TEXT_PRIMARY};
                    border: none;
                    border-bottom: 2px solid {Colors.ACCENT};
                    padding: 6px 12px 4px 12px;
                    font-size: 12px;
                    font-weight: 600;
                    width: 100px;
                    text-align: center;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Colors.TEXT_SECONDARY};
                    border: none;
                    padding: 6px 12px 4px 12px;
                    font-size: 12px;
                    width: 100px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    color: {Colors.TEXT_PRIMARY};
                }}
            """)


class RibbonGroup(QFrame):
    """Group of related buttons with a caption label underneath."""

    def __init__(self, title, parent=None):
        super().__init__(parent)

        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 4px 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(2)
        layout.addLayout(self.content_layout, 1)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
            }}
        """)
        layout.addWidget(title_label)

    def add_button(self, button):
        self.content_layout.addWidget(button)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)


class ApplicationMenu(QFrame):
    """Application-level menu bar with File button and app branding."""

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setFixedHeight(40)

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_PRIMARY};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(16)

        # App branding
        app_label = QLabel("CaatMaster")
        app_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
                padding: 0px 8px;
            }}
        """)
        layout.addWidget(app_label)

        # File button
        self.file_btn = QPushButton(" File")
        self.file_btn.setIcon(_icon("fa5s.bars", color=Colors.TEXT_PRIMARY))
        self.file_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.TEXT_PRIMARY};
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
        """)
        self.file_btn.setCursor(Qt.PointingHandCursor)
        self.file_btn.clicked.connect(self._on_file_clicked)
        layout.addWidget(self.file_btn)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Plain)
        divider.setStyleSheet(f"""
            QFrame {{
                border-left: 1px solid {Colors.BORDER_STRONG};
                margin: 4px 2px;
            }}
        """)
        layout.addWidget(divider)

        layout.addStretch()

    def _on_file_clicked(self):
        """Handle File button click - toggle backstage"""
        if self.main_window and hasattr(self.main_window, 'toggle_backstage'):
            self.main_window.toggle_backstage()


class RibbonBar(QFrame):
    """Main ribbon bar with tabs and groups."""

    action_requested = Signal(str)

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SECONDARY};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Top row: Tabs only (File button moved to ApplicationMenu)
        top_row = QWidget()
        top_row.setStyleSheet(f"background-color: {Colors.BG_SECONDARY};")
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(4, 0, 0, 0)
        top_row_layout.setSpacing(0)

        # Tabs area
        self.tabs_widget = QWidget()
        self.tabs_widget.setStyleSheet("background-color: transparent;")
        self.tabs_layout = QHBoxLayout(self.tabs_widget)
        self.tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs_layout.setSpacing(0)
        top_row_layout.addWidget(self.tabs_widget)

        top_row_layout.addStretch()
        self.main_layout.addWidget(top_row)

        # Content area
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {Colors.BG_PRIMARY};
            }}
        """)
        self.main_layout.addWidget(self.content_stack)

        self.tab_group = QButtonGroup()
        self.tab_buttons = []
        self.create_tabs()

    def _add_vertical_divider(self, layout):
        """Add a vertical divider line to the layout."""
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Plain)
        divider.setStyleSheet(f"""
            QFrame {{
                border-left: 1px solid {Colors.BORDER_STRONG};
                margin: 4px 2px;
            }}
        """)
        layout.addWidget(divider)

    def create_tabs(self):
        """Create ribbon tabs."""
        tabs = ["Home", "Extract Column", "Statistics", "Reports", "AI", "ML", "View"]

        for i, tab_name in enumerate(tabs):
            tab = RibbonTab(tab_name)
            tab.clicked.connect(lambda checked, idx=i: self.switch_tab(idx))

            self.tab_group.addButton(tab)
            self.tab_buttons.append(tab)
            self.tabs_layout.addWidget(tab)

            content = self.create_tab_content(tab_name)
            self.content_stack.addWidget(content)

        self.tabs_layout.addStretch()

        self.tab_buttons[0].setChecked(True)
        self.tab_buttons[0].update_style(True)

    def switch_tab(self, index):
        self.content_stack.setCurrentIndex(index)

        for i, button in enumerate(self.tab_buttons):
            button.setChecked(i == index)
            button.update_style(i == index)

    def create_tab_content(self, tab_name):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 0, 4)
        layout.setSpacing(0)

        if tab_name == "Home":
            self.create_home_tab(layout)
        elif tab_name == "Extract Column":
            self.create_add_column_tab(layout)
        elif tab_name == "Statistics":
            self.create_statistics_tab(layout)
        elif tab_name == "Reports":
            self.create_reports_tab(layout)
        elif tab_name == "AI":
            self.create_ai_tab(layout)
        elif tab_name == "ML":
            self.create_ml_tab(layout)
        elif tab_name == "View":
            self.create_view_tab(layout)

        layout.addStretch()
        return widget

    def emit_action(self, action_name):
        self.action_requested.emit(action_name)
        if self.main_window and hasattr(self.main_window, 'handle_ribbon_action'):
            self.main_window.handle_ribbon_action(action_name)

    # ========================================================================
    # HOME TAB - Simplified
    # ========================================================================

    def create_home_tab(self, layout):
        """Create Home tab - only File operations."""
        # File Operations group - stacked vertically
        file_group = RibbonGroup("File")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(2)
        file_layout.addWidget(RibbonButton("Import", "fa5s.file-import", self, lambda: self.emit_action("import_data")))
        file_layout.addWidget(RibbonButton("Export", "fa5s.file-export", self, lambda: self.emit_action("export_data")))
        file_layout.addWidget(RibbonButton("Quick Export", "fa5s.share-square", self, lambda: self.emit_action("export_data")))
        file_group.add_layout(file_layout)
        layout.addWidget(file_group)
        self._add_vertical_divider(layout)

        # Transform group - combine all transformations
        transform_group = RibbonGroup("Transform")
        transform_layout = QVBoxLayout()
        transform_layout.setSpacing(2)
        transform_layout.addWidget(SmallRibbonButton("Sort", "fa5s.sort-amount-down", self, lambda: self.emit_action("sort_asc")))
        transform_layout.addWidget(SmallRibbonButton("Remove", "fa5s.eraser", self, lambda: self.emit_action("remove_rows")))
        transform_layout.addWidget(SmallRibbonButton("Filter", "fa5s.filter", self, lambda: self.emit_action("filter")))
        transform_group.add_layout(transform_layout)
        layout.addWidget(transform_group)
        self._add_vertical_divider(layout)

        # Text group
        text_group = RibbonGroup("Text")
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.addWidget(SmallRibbonButton("Upper/Lower", "fa5s.font", self, lambda: self.emit_action("text_upper")))
        text_layout.addWidget(SmallRibbonButton("Split", "fa5s.columns", self, lambda: self.emit_action("split_comma")))
        text_layout.addWidget(SmallRibbonButton("Trim", "fa5s.cut", self, lambda: self.emit_action("text_trim")))
        text_group.add_layout(text_layout)
        layout.addWidget(text_group)
        self._add_vertical_divider(layout)

        # Numbers group
        number_group = RibbonGroup("Number")
        number_layout = QVBoxLayout()
        number_layout.setSpacing(2)
        number_layout.addWidget(SmallRibbonButton("Round", "fa5s.circle-notch", self, lambda: self.emit_action("math_round")))
        number_layout.addWidget(SmallRibbonButton("Abs", "fa5s.arrows-alt-h", self, lambda: self.emit_action("math_abs")))
        number_layout.addWidget(SmallRibbonButton("Sqrt", "fa5s.square-root-alt", self, lambda: self.emit_action("math_sqrt")))
        number_group.add_layout(number_layout)
        layout.addWidget(number_group)
        self._add_vertical_divider(layout)

        # Date group
        date_group = RibbonGroup("Date")
        date_layout = QVBoxLayout()
        date_layout.setSpacing(2)
        date_layout.addWidget(SmallRibbonButton("Year/Month", "fa5s.calendar-alt", self, lambda: self.emit_action("extract_year")))
        date_layout.addWidget(SmallRibbonButton("Weekday", "fa5s.calendar-week", self, lambda: self.emit_action("extract_weekday")))
        date_layout.addWidget(SmallRibbonButton("Age", "fa5s.hourglass-half", self, lambda: self.emit_action("date_age")))
        date_group.add_layout(date_layout)
        layout.addWidget(date_group)
        self._add_vertical_divider(layout)

        # Pivot group
        pivot_group = RibbonGroup("Pivot")
        pivot_layout = QVBoxLayout()
        pivot_layout.setSpacing(2)
        pivot_layout.addWidget(SmallRibbonButton("Pivot", "fa5s.table", self, lambda: self.emit_action("pivot")))
        pivot_layout.addWidget(SmallRibbonButton("Unpivot", "fa5s.stream", self, lambda: self.emit_action("unpivot")))
        pivot_group.add_layout(pivot_layout)
        layout.addWidget(pivot_group)
        self._add_vertical_divider(layout)

        # Column group
        col_group = RibbonGroup("Column")
        col_layout = QVBoxLayout()
        col_layout.setSpacing(2)
        col_layout.addWidget(SmallRibbonButton("Type", "fa5s.exchange-alt", self, lambda: self.emit_action("change_dtype")))
        col_layout.addWidget(SmallRibbonButton("Rename", "fa5s.pen", self, lambda: self.emit_action("rename_col")))
        col_layout.addWidget(SmallRibbonButton("Reorder", "fa5s.arrows-alt-h", self, lambda: self.emit_action("reorder_cols")))
        col_layout.addWidget(SmallRibbonButton("Select", "fa5s.check-square", self, lambda: self.emit_action("select_cols")))
        col_group.add_layout(col_layout)
        layout.addWidget(col_group)
        self._add_vertical_divider(layout)

        # Audit group
        audit_group = RibbonGroup("Audit")
        audit_layout = QVBoxLayout()
        audit_layout.setSpacing(2)
        audit_layout.addWidget(SmallRibbonButton("Z-Score", "fa5s.chart-line", self, lambda: self.emit_action("stat_zscore")))
        audit_layout.addWidget(SmallRibbonButton("Benford", "fa5s.sort-numeric-down", self, lambda: self.emit_action("benford_law")))
        audit_layout.addWidget(SmallRibbonButton("Duplicates", "fa5s.clone", self, lambda: self.emit_action("audit_duplicates")))
        audit_layout.addWidget(SmallRibbonButton("Gaps", "fa5s.ellipsis-h", self, lambda: self.emit_action("audit_gaps")))
        audit_layout.addWidget(SmallRibbonButton("Round #s", "fa5s.coins", self, lambda: self.emit_action("audit_round_numbers")))
        audit_group.add_layout(audit_layout)
        layout.addWidget(audit_group)

    # ========================================================================
    # EXTRACT COLUMN TAB
    # ========================================================================

    def create_add_column_tab(self, layout):
        """Create Extract Column tab."""
        # General group
        general_group = RibbonGroup("General")
        general_layout = QVBoxLayout()
        general_layout.setSpacing(2)
        general_layout.addWidget(SmallRibbonButton("Custom", "fa5s.magic", self, lambda: self.emit_action("custom_col")))
        general_layout.addWidget(SmallRibbonButton("Index", "fa5s.list-ol", self, lambda: self.emit_action("index_col")))
        general_group.add_layout(general_layout)
        layout.addWidget(general_group)
        self._add_vertical_divider(layout)

        # From Text group
        from_text_group = RibbonGroup("Text")
        from_text_layout = QVBoxLayout()
        from_text_layout.setSpacing(2)
        from_text_layout.addWidget(SmallRibbonButton("Length", "fa5s.ruler-horizontal", self, lambda: self.emit_action("text_length")))
        from_text_layout.addWidget(SmallRibbonButton("Extract", "fa5s.crop-alt", self, lambda: self.emit_action("text_extract")))
        from_text_group.add_layout(from_text_layout)
        layout.addWidget(from_text_group)
        self._add_vertical_divider(layout)

        # From Number group
        from_num_group = RibbonGroup("Number")
        from_num_layout = QVBoxLayout()
        from_num_layout.setSpacing(2)
        from_num_layout.addWidget(SmallRibbonButton("Stats", "fa5s.calculator", self, lambda: self.emit_action("stat_quick")))
        from_num_layout.addWidget(SmallRibbonButton("Round", "fa5s.circle-notch", self, lambda: self.emit_action("math_round")))
        from_num_group.add_layout(from_num_layout)
        layout.addWidget(from_num_group)
        self._add_vertical_divider(layout)

        # From Date group
        from_date_group = RibbonGroup("Date")
        from_date_layout = QVBoxLayout()
        from_date_layout.setSpacing(2)
        from_date_layout.addWidget(SmallRibbonButton("Quarter", "fa5s.calendar-day", self, lambda: self.emit_action("date_quarter")))
        from_date_layout.addWidget(SmallRibbonButton("Hour", "fa5s.clock", self, lambda: self.emit_action("extract_hour")))
        from_date_group.add_layout(from_date_layout)
        layout.addWidget(from_date_group)

    # ========================================================================
    # STATISTICS TAB
    # ========================================================================

    def create_statistics_tab(self, layout):
        """Create Statistics tab."""
        descriptive_group = RibbonGroup("Descriptive")
        descriptive_layout = QVBoxLayout()
        descriptive_layout.setSpacing(2)
        descriptive_layout.addWidget(SmallRibbonButton("Summary", "fa5s.chart-pie", self, lambda: self.emit_action("stat_summary")))
        descriptive_layout.addWidget(SmallRibbonButton("Mean/Median", "fa5s.ruler-combined", self, lambda: self.emit_action("stat_central")))
        descriptive_layout.addWidget(SmallRibbonButton("Variance", "fa5s.wave-square", self, lambda: self.emit_action("stat_variance")))
        descriptive_group.add_layout(descriptive_layout)
        layout.addWidget(descriptive_group)
        self._add_vertical_divider(layout)

        hypothesis_group = RibbonGroup("Hypothesis")
        hypothesis_layout = QVBoxLayout()
        hypothesis_layout.setSpacing(2)
        hypothesis_layout.addWidget(SmallRibbonButton("T-Test", "fa5s.vial", self, lambda: self.emit_action("stat_ttest")))
        hypothesis_layout.addWidget(SmallRibbonButton("ANOVA", "fa5s.flask", self, lambda: self.emit_action("stat_anova")))
        hypothesis_layout.addWidget(SmallRibbonButton("Chi-Square", "fa5s.percentage", self, lambda: self.emit_action("stat_chisquare")))
        hypothesis_group.add_layout(hypothesis_layout)
        layout.addWidget(hypothesis_group)
        self._add_vertical_divider(layout)

        correlation_group = RibbonGroup("Correlation")
        correlation_layout = QVBoxLayout()
        correlation_layout.setSpacing(2)
        correlation_layout.addWidget(SmallRibbonButton("Pearson", "fa5s.link", self, lambda: self.emit_action("stat_pearson")))
        correlation_layout.addWidget(SmallRibbonButton("Spearman", "fa5s.project-diagram", self, lambda: self.emit_action("stat_spearman")))
        correlation_layout.addWidget(SmallRibbonButton("Heatmap", "fa5s.fire", self, lambda: self.emit_action("stat_heatmap")))
        correlation_group.add_layout(correlation_layout)
        layout.addWidget(correlation_group)
        self._add_vertical_divider(layout)

        distribution_group = RibbonGroup("Distribution")
        distribution_layout = QVBoxLayout()
        distribution_layout.setSpacing(2)
        distribution_layout.addWidget(SmallRibbonButton("Normal", "fa5s.bell", self, lambda: self.emit_action("stat_normal")))
        distribution_layout.addWidget(SmallRibbonButton("Binomial", "fa5s.dice", self, lambda: self.emit_action("stat_binomial")))
        distribution_layout.addWidget(SmallRibbonButton("Poisson", "fa5s.chart-bar", self, lambda: self.emit_action("stat_poisson")))
        distribution_group.add_layout(distribution_layout)
        layout.addWidget(distribution_group)

    # ========================================================================
    # REPORTS TAB
    # ========================================================================

    def create_reports_tab(self, layout):
        """Create Reports tab with LLM integration."""
        audit_group = RibbonGroup("Audit Reports")
        audit_layout = QVBoxLayout()
        audit_layout.setSpacing(2)
        audit_layout.addWidget(SmallRibbonButton("Generate Audit", "fa5s.clipboard-check", self, lambda: self.emit_action("report_audit")))
        audit_layout.addWidget(SmallRibbonButton("LLM Analysis", "fa5s.brain", self, lambda: self.emit_action("report_llm")))
        audit_layout.addWidget(SmallRibbonButton("Export PDF", "fa5s.file-pdf", self, lambda: self.emit_action("report_pdf")))
        audit_group.add_layout(audit_layout)
        layout.addWidget(audit_group)
        self._add_vertical_divider(layout)

        system_group = RibbonGroup("System Reports")
        system_layout = QVBoxLayout()
        system_layout.setSpacing(2)
        system_layout.addWidget(SmallRibbonButton("Data Profile", "fa5s.chart-bar", self, lambda: self.emit_action("report_profile")))
        system_layout.addWidget(SmallRibbonButton("Transformation Log", "fa5s.history", self, lambda: self.emit_action("report_transformation")))
        system_layout.addWidget(SmallRibbonButton("Quality Metrics", "fa5s.check-double", self, lambda: self.emit_action("report_quality")))
        system_group.add_layout(system_layout)
        layout.addWidget(system_group)
        self._add_vertical_divider(layout)

        export_group = RibbonGroup("Export Formats")
        export_layout = QVBoxLayout()
        export_layout.setSpacing(2)
        export_layout.addWidget(SmallRibbonButton("Word (.docx)", "fa5s.file-word", self, lambda: self.emit_action("report_word")))
        export_layout.addWidget(SmallRibbonButton("Excel (.xlsx)", "fa5s.file-excel", self, lambda: self.emit_action("report_excel")))
        export_layout.addWidget(SmallRibbonButton("PDF (.pdf)", "fa5s.file-pdf", self, lambda: self.emit_action("report_pdf")))
        export_group.add_layout(export_layout)
        layout.addWidget(export_group)

    # ========================================================================
    # AI TAB
    # ========================================================================

    def create_ai_tab(self, layout):
        """Create AI tab."""
        ai_group = RibbonGroup("AI Operations")
        ai_layout = QVBoxLayout()
        ai_layout.setSpacing(2)
        ai_layout.addWidget(SmallRibbonButton("AI Explain", "fa5s.lightbulb", self, lambda: self.emit_action("ai_explain")))
        ai_layout.addWidget(SmallRibbonButton("AI Sentiment", "fa5s.smile", self, lambda: self.emit_action("ai_sentiment")))
        ai_layout.addWidget(SmallRibbonButton("AI Extract", "fa5s.search", self, lambda: self.emit_action("ai_extract")))
        ai_layout.addWidget(SmallRibbonButton("AI Pattern", "fa5s.brain", self, lambda: self.emit_action("ai_pattern")))
        ai_group.add_layout(ai_layout)
        layout.addWidget(ai_group)
        self._add_vertical_divider(layout)

        ai_classify_group = RibbonGroup("AI Classify")
        ai_classify_layout = QVBoxLayout()
        ai_classify_layout.setSpacing(2)
        ai_classify_layout.addWidget(SmallRibbonButton("Text Classify", "fa5s.tags", self, lambda: self.emit_action("ai_classify")))
        ai_classify_layout.addWidget(SmallRibbonButton("Summarize", "fa5s.align-left", self, lambda: self.emit_action("ai_summarize")))
        ai_classify_layout.addWidget(SmallRibbonButton("Enrich", "fa5s.magic", self, lambda: self.emit_action("ai_enrich")))
        ai_classify_group.add_layout(ai_classify_layout)
        layout.addWidget(ai_classify_group)
        self._add_vertical_divider(layout)

        analysis_group = RibbonGroup("Analysis")
        analysis_layout = QVBoxLayout()
        analysis_layout.setSpacing(2)
        analysis_layout.addWidget(SmallRibbonButton("Text Analysis", "fa5s.file-alt", self, lambda: self.emit_action("ai_explain")))
        analysis_layout.addWidget(SmallRibbonButton("Data Insights", "fa5s.lightbulb", self, lambda: self.emit_action("ai_extract")))
        analysis_group.add_layout(analysis_layout)
        layout.addWidget(analysis_group)

    # ========================================================================
    # ML TAB
    # ========================================================================

    def create_ml_tab(self, layout):
        """Create ML tab - organized by category."""
        linear_group = RibbonGroup("Linear Models")
        linear_layout = QVBoxLayout()
        linear_layout.setSpacing(2)
        linear_layout.addWidget(SmallRibbonButton("Linear Regression", "fa5s.chart-line", self, lambda: self.emit_action("ml_linear_regression")))
        linear_layout.addWidget(SmallRibbonButton("GLM", "fa5s.chart-area", self, lambda: self.emit_action("ml_glm")))
        linear_group.add_layout(linear_layout)
        layout.addWidget(linear_group)
        self._add_vertical_divider(layout)

        tree_group = RibbonGroup("Tree-Based")
        tree_layout = QVBoxLayout()
        tree_layout.setSpacing(2)
        tree_layout.addWidget(SmallRibbonButton("Decision Tree", "fa5s.sitemap", self, lambda: self.emit_action("ml_decision_tree")))
        tree_layout.addWidget(SmallRibbonButton("Random Forest", "fa5s.tree", self, lambda: self.emit_action("ml_random_forest")))
        tree_layout.addWidget(SmallRibbonButton("Gradient Boosting", "fa5s.chart-line", self, lambda: self.emit_action("ml_gradient_boosting")))
        tree_layout.addWidget(SmallRibbonButton("XGBoost", "fa5s.bolt", self, lambda: self.emit_action("ml_xgboost")))
        tree_layout.addWidget(SmallRibbonButton("LightGBM", "fa5s.feather", self, lambda: self.emit_action("ml_lightgbm")))
        tree_group.add_layout(tree_layout)
        layout.addWidget(tree_group)
        self._add_vertical_divider(layout)

        cluster_group = RibbonGroup("Clustering")
        cluster_layout = QVBoxLayout()
        cluster_layout.setSpacing(2)
        cluster_layout.addWidget(SmallRibbonButton("K-Means", "fa5s.object-group", self, lambda: self.emit_action("ml_cluster")))
        cluster_layout.addWidget(SmallRibbonButton("DBSCAN", "fa5s.dot-circle", self, lambda: self.emit_action("ml_dbscan")))
        cluster_layout.addWidget(SmallRibbonButton("Gaussian Mixture", "fa5s.chart-bar", self, lambda: self.emit_action("ml_gmm")))
        cluster_group.add_layout(cluster_layout)
        layout.addWidget(cluster_group)
        self._add_vertical_divider(layout)

        timeseries_group = RibbonGroup("Time Series")
        timeseries_layout = QVBoxLayout()
        timeseries_layout.setSpacing(2)
        timeseries_layout.addWidget(SmallRibbonButton("ARIMA", "fa5s.chart-line", self, lambda: self.emit_action("ml_arima")))
        timeseries_layout.addWidget(SmallRibbonButton("Exp. Smoothing", "fa5s.wave-square", self, lambda: self.emit_action("ml_ets")))
        timeseries_group.add_layout(timeseries_layout)
        layout.addWidget(timeseries_group)
        self._add_vertical_divider(layout)

        anomaly_group = RibbonGroup("Anomaly")
        anomaly_layout = QVBoxLayout()
        anomaly_layout.setSpacing(2)
        anomaly_layout.addWidget(SmallRibbonButton("Isolation Forest", "fa5s.exclamation-triangle", self, lambda: self.emit_action("ml_anomaly_iforest")))
        anomaly_layout.addWidget(SmallRibbonButton("Z-Score", "fa5s.ruler", self, lambda: self.emit_action("ml_anomaly_zscore")))
        anomaly_layout.addWidget(SmallRibbonButton("IQR", "fa5s.ruler-combined", self, lambda: self.emit_action("ml_anomaly_iqr")))
        anomaly_layout.addWidget(SmallRibbonButton("LOF", "fa5s.map-marker-alt", self, lambda: self.emit_action("ml_lof")))
        anomaly_group.add_layout(anomaly_layout)
        layout.addWidget(anomaly_group)

    # ========================================================================
    # VIEW TAB
    # ========================================================================

    def create_view_tab(self, layout):
        """Create View tab."""
        layout_group = RibbonGroup("Layout")
        layout_layout = QVBoxLayout()
        layout_layout.setSpacing(2)
        layout_layout.addWidget(SmallRibbonButton("Settings", "fa5s.cog", self, lambda: self.emit_action("query_settings")))
        layout_layout.addWidget(SmallRibbonButton("Dependencies", "fa5s.project-diagram", self, lambda: self.emit_action("dependencies")))
        layout_group.add_layout(layout_layout)
        layout.addWidget(layout_group)
        self._add_vertical_divider(layout)

        preview_group = RibbonGroup("Preview")
        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(2)
        preview_layout.addWidget(SmallRibbonButton("Quality", "fa5s.check-circle", self, lambda: self.emit_action("col_quality")))
        preview_layout.addWidget(SmallRibbonButton("Profile", "fa5s.chart-bar", self, lambda: self.emit_action("col_profile")))
        preview_group.add_layout(preview_layout)
        layout.addWidget(preview_group)
        self._add_vertical_divider(layout)

        show_group = RibbonGroup("Show")
        show_layout = QVBoxLayout()
        show_layout.setSpacing(2)
        show_layout.addWidget(SmallRibbonButton("Formula", "fa5s.superscript", self, lambda: self.emit_action("formula_bar")))
        show_layout.addWidget(SmallRibbonButton("Steps", "fa5s.list", self, lambda: self.emit_action("steps_panel")))
        show_group.add_layout(show_layout)
        layout.addWidget(show_group)
