"""AI Compliance Report Dialog - Check compliance and generate reports"""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QGroupBox, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QFrame,
    QSizePolicy, QFormLayout, QScrollArea, QTabWidget, QWidget, QSpacerItem
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont

from gui.theme import Colors
from gui.components.common_modals import create_primary_button, create_secondary_button, create_success_button
from gui.dialogs.rule_library_dialog import RuleLibraryMappingDialog, CosoHeatmapDialog
from core import compliance_rule_library as rule_library


class ComplianceReportDialog(QDialog):
    """Dialog for AI-powered compliance checking and report generation"""

    # Thread-safe signals for UI updates. Each tab (Policy Check, Rule
    # Detection, Generate Report) gets its own report/status signal so
    # results always land on the tab that produced them - they used to
    # all funnel into _reportReady/_statusReady, which only ever updated
    # widgets on the Generate Report tab, so running Policy Check or Rule
    # Detection appeared to silently do nothing unless you happened to
    # switch tabs.
    _reportReady = Signal(str)  # Generate Report tab's narrative ready
    _statusReady = Signal(str)  # Policy Check tab's status message
    _policyReportReady = Signal(str)  # Policy Check tab's detailed results
    _detectionStatusReady = Signal(str)  # Rule Detection tab's status message
    _detectionReportReady = Signal(str)  # Rule Detection tab's detailed results
    _reportStatusReady = Signal(str)  # Generate Report tab's status message - was
    # wrongly sharing _statusReady/policy_status (a different tab) before
    _checkComplete = Signal()  # Check complete
    _checkFailed = Signal(str)  # Check failed with error
    # Cross-thread delivery of the actual ComplianceFinding objects (not
    # just their text rendering), so per-finding action cards can be
    # built with real matched_df/mask data attached.
    _policyFindingsReady = Signal(object)  # List[Tuple[dataset_name, ComplianceFinding]]
    _detectionFindingsReady = Signal(object)  # List[Tuple[dataset_name, ComplianceFinding]]

    # Emitted when the user clicks a per-finding action button - handled
    # by whoever constructed this dialog (main_window.py), which has
    # access to the actual project/dataset objects this dialog doesn't.
    createDatasetFromFindingRequested = Signal(str, object)  # dataset_name, ComplianceFinding
    addColumnFromFindingRequested = Signal(str, object)  # dataset_name, ComplianceFinding

    def __init__(self, dataframes: dict, compliance_generator, parent=None, selected_keys: list = None):
        """Initialize dialog with multiple datasets

        Args:
            dataframes: Dictionary of {dataset_name: polars DataFrame}
            compliance_generator: AI compliance generator instance
            parent: Parent widget
            selected_keys: Keys initially checked in the dataset selector -
                Policy Check/Rule Detection run against all of them and
                combine results. Defaults to just the first dataset.
        """
        super().__init__(parent)
        self.dataframes = dataframes
        checked = [k for k in (selected_keys or []) if k in dataframes]
        if not checked:
            checked = [next(iter(dataframes))]
        self.selected_dataframes = {k: dataframes[k] for k in checked}
        # Generate Report (the narrative memo tab) still works against a
        # single dataframe - out of scope for multi-dataset reasoning,
        # unlike Policy Check/Rule Detection above. Uses the first checked
        # dataset.
        self.df = self.selected_dataframes[checked[0]]
        self.generator = compliance_generator
        self.report = None
        # Accumulates {"coso_component", "severity", "affected_pct", "title"}
        # dicts across every rule-library run this dialog session, so "View
        # COSO Heatmap" can aggregate across SOX/COSO/IFRS libraries run
        # back to back rather than just the last one.
        self._coso_findings_pool: list = []
        # Thread pool for async operations (no parent to avoid thread issues)
        from PySide6.QtCore import QThreadPool
        self.thread_pool = QThreadPool()
        self.setup_ui()

        # Connect thread-safe signals for UI updates
        self._reportReady.connect(self._on_report_ready, Qt.QueuedConnection)
        self._statusReady.connect(self._on_status_ready, Qt.QueuedConnection)
        self._policyReportReady.connect(self._on_policy_report_ready, Qt.QueuedConnection)
        self._detectionStatusReady.connect(self._on_detection_status_ready, Qt.QueuedConnection)
        self._detectionReportReady.connect(self._on_detection_report_ready, Qt.QueuedConnection)
        self._reportStatusReady.connect(self._on_report_status_ready, Qt.QueuedConnection)
        self._policyFindingsReady.connect(self._on_policy_findings_ready, Qt.QueuedConnection)
        self._detectionFindingsReady.connect(self._on_detection_findings_ready, Qt.QueuedConnection)
        self._checkComplete.connect(self._on_check_complete, Qt.QueuedConnection)
        self._checkFailed.connect(self._on_check_failed, Qt.QueuedConnection)

    def closeEvent(self, event):
        """Handle dialog close - wait for threads to finish"""
        self.thread_pool.waitForDone(3000)
        event.accept()

    # Thread-safe signal handlers
    def _on_report_ready(self, report: str):
        """Handle report ready signal"""
        self.report_output.setText(report)
        self.report = report

    def _on_status_ready(self, status: str):
        """Handle Policy Check tab's status message"""
        self.policy_status.setText(status)

    def _on_policy_report_ready(self, report: str):
        """Handle Policy Check tab's detailed results - separate from
        Generate Report's report_output, which lives on a different tab."""
        self.policy_results_output.setText(report)

    def _on_detection_status_ready(self, status: str):
        """Handle Rule Detection tab's status message"""
        self.detection_status.setVisible(True)
        self.detection_status.setText(status)

    def _on_detection_report_ready(self, report: str):
        """Handle Rule Detection tab's detailed results"""
        self.detection_results_output.setText(report)

    def _on_report_status_ready(self, status: str):
        """Handle Generate Report tab's status message"""
        self.report_status.setVisible(True)
        self.report_status.setText(status)

    def _build_findings_container(self):
        """A vertically-stacked container for per-finding action cards -
        shared by the Policy Check and Rule Detection tabs so both get the
        same "create dataset" / "add column" affordance. Not its own
        QScrollArea - each whole tab is one now (see create_policy_tab),
        so a nested scroll area here just meant two competing scrollbars
        without actually fixing the space-pressure squishing this was
        meant to avoid."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch()
        return container, layout

    def _populate_findings(self, layout, findings_with_ds):
        """Clear and rebuild a findings-scroll-area's cards."""
        while layout.count() > 1:  # keep the trailing stretch
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for dataset_name, finding in findings_with_ds:
            layout.insertWidget(layout.count() - 1, self._build_finding_card(dataset_name, finding))

    def _build_finding_card(self, dataset_name: str, finding) -> QWidget:
        """One finding's summary plus its own "create dataset from
        flagged rows" / "add flag column" actions - scoped to whichever
        dataset it came from, since a check can span more than one."""
        card = QFrame()
        card.setObjectName("ComplianceFindingCard")
        card.setStyleSheet(f"""
            QFrame#ComplianceFindingCard {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QLabel(f"<b>{finding.title}</b> ({finding.severity.upper()}) — {dataset_name}")
        header.setStyleSheet(f"QLabel {{ color: {Colors.TEXT_PRIMARY}; font-size: 13px; }}")
        layout.addWidget(header)

        detail_text = finding.finding
        if finding.computable:
            detail_text += f"\nAffected: {finding.affected_count:,} of {finding.total_count:,} rows ({finding.affected_pct}%)"
            if finding.affected_amount:
                detail_text += f" | Dollar impact: ${finding.affected_amount:,.2f}"
        detail = QLabel(detail_text)
        detail.setWordWrap(True)
        detail.setStyleSheet(f"QLabel {{ color: {Colors.TEXT_SECONDARY}; font-size: 12px; }}")
        layout.addWidget(detail)

        if finding.computable and finding.affected_count > 0:
            actions = QHBoxLayout()
            actions.setSpacing(8)

            if finding.matched_df is not None:
                create_btn = create_secondary_button("Create Dataset from Flagged Rows")
                create_btn.setCursor(Qt.PointingHandCursor)
                create_btn.clicked.connect(
                    lambda checked=False, n=dataset_name, f=finding: self.createDatasetFromFindingRequested.emit(n, f)
                )
                actions.addWidget(create_btn)

            if finding.mask is not None:
                add_col_btn = create_secondary_button(f"Add '{finding.title}' Column")
                add_col_btn.setCursor(Qt.PointingHandCursor)
                add_col_btn.clicked.connect(
                    lambda checked=False, n=dataset_name, f=finding: self.addColumnFromFindingRequested.emit(n, f)
                )
                actions.addWidget(add_col_btn)

            actions.addStretch()
            layout.addLayout(actions)

        return card

    def _on_policy_findings_ready(self, findings_with_ds):
        self._policy_findings = findings_with_ds
        self._populate_findings(self.policy_findings_layout, findings_with_ds)

    def _on_detection_findings_ready(self, findings_with_ds):
        self._detection_findings = findings_with_ds
        self._populate_findings(self.detection_findings_layout, findings_with_ds)

    def _add_results_to_report(self, results_text: str, source_label: str):
        """Append a Policy Check/Rule Detection run's results into the
        Generate Report tab's findings box, labeled by source, so a report
        can be drafted from real check output instead of retyping or
        copy-pasting it by hand. Appends rather than overwrites, so both
        tabs' results can be added without one clobbering the other."""
        results_text = results_text.strip()
        if not results_text:
            QMessageBox.warning(self, "No Results", f"Run {source_label} first - there's nothing to add yet.")
            return

        existing = self.findings_edit.toPlainText().strip()
        block = f"--- {source_label} ---\n{results_text}"
        self.findings_edit.setPlainText(f"{existing}\n\n{block}" if existing else block)

        self.tabs.setCurrentWidget(self.report_tab)

    def _on_check_complete(self):
        """Handle check complete signal"""
        self.run_check_btn.setEnabled(True)
        self.policy_progress.setVisible(False)
        self.generate_report_btn.setEnabled(True)
        self.report_progress.setVisible(False)

    def _on_check_failed(self, error: str):
        """Handle check failed signal - shared by Policy Check, Rule
        Detection, and Generate Report, so resets all three tabs' busy
        state regardless of which one raised it."""
        self.policy_status.setText(f"Error: {error}")
        self.run_check_btn.setEnabled(True)
        self.policy_progress.setVisible(False)
        self.generate_report_btn.setEnabled(True)
        self.report_progress.setVisible(False)
        self.run_detection_btn.setEnabled(True)
        self.detection_progress.setVisible(False)
        self.detection_status.setVisible(True)
        self.detection_status.setText(f"Error: {error}")
        self.report_status.setVisible(True)
        self.report_status.setText(f"Error: {error}")
        QMessageBox.critical(self, "Check Error", error)

    def _on_dataset_selection_changed(self, item):
        """Keep self.selected_dataframes in sync with the checklist -
        Policy Check/Rule Detection read from it directly."""
        checked = [
            self.dataset_list.item(i).text()
            for i in range(self.dataset_list.count())
            if self.dataset_list.item(i).checkState() == Qt.Checked
        ]
        if not checked:
            # Never allow zero datasets selected - nothing to run against.
            item.setCheckState(Qt.Checked)
            return
        self.selected_dataframes = {k: self.dataframes[k] for k in checked}
        self.df = self.selected_dataframes[checked[0]]
        # Stale results from the old selection would otherwise linger on
        # all three tabs, looking like they still reflect the current one.
        self.report_output.clear()
        self.policy_results_output.clear()
        self.detection_results_output.clear()
        self._populate_findings(self.policy_findings_layout, [])
        self._populate_findings(self.detection_findings_layout, [])
        self.report = None

    def setup_ui(self):
        self.setWindowTitle("AI Compliance Report Generator")
        self.setMinimumSize(800, 600)
        # Dialog background inherited from the app-wide QDialog rule in theme.py.

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title section
        title_layout = QHBoxLayout()
        title_icon = QLabel("⚖️")
        title_icon.setStyleSheet("font-size: 24px;")
        title_layout.addWidget(title_icon)

        title = QLabel("Compliance Report Generator")
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 700;
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Dataset selector (if multiple datasets available) - checklist
        # rather than a single-select combo, so Policy Check/Rule
        # Detection can run across more than one dataset and combine the
        # results. QGroupBox/QListWidget chrome inherited from theme.py.
        if len(self.dataframes) > 1:
            dataset_group = QGroupBox("Datasets to Check")
            dataset_layout = QVBoxLayout(dataset_group)
            dataset_layout.setContentsMargins(16, 20, 16, 16)

            hint = QLabel("Policy Check and Rule Detection run against every checked dataset below and combine the results.")
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
            dataset_layout.addWidget(hint)

            self.dataset_list = QListWidget()
            self.dataset_list.setMaximumHeight(100)
            self.dataset_list.setSelectionMode(QListWidget.NoSelection)
            for key in self.dataframes.keys():
                item = QListWidgetItem(key)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if key in self.selected_dataframes else Qt.Unchecked)
                self.dataset_list.addItem(item)
            self.dataset_list.itemChanged.connect(self._on_dataset_selection_changed)
            dataset_layout.addWidget(self.dataset_list)
            layout.addWidget(dataset_group)
        else:
            self.dataset_list = None

        # Tabs for different compliance modes - pane/border chrome
        # inherited from the app-wide QTabWidget rule; only sizing here.
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { padding: 10px 20px; }")

        # Tab 1: Policy Compliance Check
        self.policy_tab = self.create_policy_tab()
        self.tabs.addTab(self.policy_tab, "Policy Check")

        # Tab 2: Rule-Based Detection
        self.rules_tab = self.create_rules_tab()
        self.tabs.addTab(self.rules_tab, "Rule Detection")

        # Tab 3: Report Generation
        self.report_tab = self.create_report_tab()
        self.tabs.addTab(self.report_tab, "Generate Report")

        layout.addWidget(self.tabs)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("✕ Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def create_policy_tab(self) -> QWidget:
        """Create the policy compliance check tab. Wrapped in its own
        scroll area - this tab's total content (policy input, templates,
        results, and per-finding action cards) can be taller than the
        dialog when the multi-dataset checklist is also showing above the
        tabs. Without a scroll area, that space pressure didn't scroll
        anything - it squished the GroupBoxes down to just their title
        bar, making the policy input and template buttons invisible."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Policy text input - QGroupBox chrome inherited from theme.py.
        policy_group = QGroupBox("Compliance Policy")

        policy_layout = QVBoxLayout(policy_group)

        policy_layout.addWidget(QLabel("Enter the compliance policy or requirements:"))

        self.policy_edit = QTextEdit()
        self.policy_edit.setPlaceholderText(
            "Paste or type the compliance policy here...\n\n"
            "Example:\n"
            "• All transactions over $10,000 must be flagged for review\n"
            "• Vendor payments must have proper approval signatures\n"
            "• Expense reports must be submitted within 30 days"
        )
        self.policy_edit.setStyleSheet("QTextEdit { min-height: 150px; }")
        policy_layout.addWidget(self.policy_edit)

        layout.addWidget(policy_group)

        # Quick policy templates
        templates_group = QGroupBox("Policy Templates")

        templates_layout = QVBoxLayout(templates_group)

        template_buttons_layout = QHBoxLayout()

        templates = [
            ("SOX Compliance", self.sox_template()),
            ("Expense Policy", self.expense_template()),
            ("Payment Policy", self.payment_template()),
        ]

        for name, template in templates:
            btn = QPushButton(name)
            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 8px 16px;
                    background-color: {Colors.ACCENT_SOFT};
                    border: 1px solid {Colors.BG_SELECTED_STRONG};
                    border-radius: 4px;
                    font-size: 12px;
                    color: {Colors.ACCENT};
                }}
                QPushButton:hover {{
                    background-color: {Colors.BG_SELECTED_STRONG};
                }}
            """)
            btn.clicked.connect(lambda checked, t=template: self.policy_edit.setText(t))
            template_buttons_layout.addWidget(btn)

        templates_layout.addLayout(template_buttons_layout)
        layout.addWidget(templates_group)

        # Run check button
        self.run_check_btn = create_primary_button("🔍 Run Compliance Check")
        self.run_check_btn.clicked.connect(self.run_policy_check)
        layout.addWidget(self.run_check_btn)

        # Progress indicator
        self.policy_progress = QProgressBar()
        self.policy_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent;
            }
        """)
        self.policy_progress.setVisible(False)
        layout.addWidget(self.policy_progress)

        # Status label
        self.policy_status = QLabel()
        self.policy_status.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.TEXT_SECONDARY};
                padding: 8px;
                border-radius: 4px;
                background-color: {Colors.BG_SECONDARY};
            }}
        """)
        self.policy_status.setVisible(False)
        layout.addWidget(self.policy_status)

        # Results - separate from Generate Report's report_output (a
        # different tab entirely); this is where Run Compliance Check's
        # own detailed findings actually show up.
        self.policy_results_output = QTextEdit()
        self.policy_results_output.setReadOnly(True)
        self.policy_results_output.setPlaceholderText("Results will appear here after running the compliance check.")
        self.policy_results_output.setStyleSheet("QTextEdit { min-height: 120px; }")
        layout.addWidget(self.policy_results_output)

        add_to_report_btn = create_secondary_button("Add to Compliance Report")
        add_to_report_btn.setCursor(Qt.PointingHandCursor)
        add_to_report_btn.clicked.connect(
            lambda: self._add_results_to_report(self.policy_results_output.toPlainText(), "Policy Check")
        )
        layout.addWidget(add_to_report_btn, alignment=Qt.AlignLeft)

        # Per-finding actions - each finding that actually matched rows
        # gets its own "create a dataset from just these rows" / "add a
        # flag column back onto the dataset" buttons, scoped to whichever
        # dataset it came from.
        self.policy_findings_container, self.policy_findings_layout = self._build_findings_container()
        layout.addWidget(self.policy_findings_container)

        scroll.setWidget(tab)
        return scroll

    def create_rules_tab(self) -> QWidget:
        """Create the rule-based detection tab. Wrapped in its own scroll
        area - see create_policy_tab's docstring for why."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Rules input - QGroupBox chrome inherited from theme.py.
        rules_group = QGroupBox("Detection Rules")

        rules_layout = QVBoxLayout(rules_group)

        rules_layout.addWidget(QLabel("Define detection rules (one per line):"))

        self.rules_edit = QTextEdit()
        self.rules_edit.setPlaceholderText(
            "Enter rules in format: Rule Name | Condition | Severity\n\n"
            "Example:\n"
            "Large Transaction | amount > 10000 | high\n"
            "Weekend Transaction | day_of_week in [5, 6] | medium\n"
            "Round Amount | amount % 100 == 0 | low"
        )
        self.rules_edit.setStyleSheet("QTextEdit { min-height: 150px; }")
        rules_layout.addWidget(self.rules_edit)

        layout.addWidget(rules_group)

        # Rule Libraries - pre-built SOX/COSO/IFRS-adjacent rules that run
        # fully deterministically (no AI call, no AI provider required) via
        # core.compliance_rule_library. Separate from the free-text rules
        # box above, which still needs AI to translate a typed rule into a
        # condition.
        library_group = QGroupBox("Rule Libraries (no AI required)")
        library_layout = QVBoxLayout(library_group)

        library_hint = QLabel(
            "Pre-built SOX/COSO/IFRS-adjacent checks. These run as real Polars filters against "
            "your complete dataset with no AI call involved — only field mapping is needed."
        )
        library_hint.setWordWrap(True)
        library_hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        library_layout.addWidget(library_hint)

        library_row = QHBoxLayout()
        self.library_combo = QComboBox()
        self._libraries = rule_library.list_libraries()
        for lib in self._libraries:
            self.library_combo.addItem(f"{lib['display_name']} ({lib['framework']})", lib["id"])
        library_row.addWidget(self.library_combo, 1)

        run_library_btn = create_secondary_button("Configure & Run")
        run_library_btn.setCursor(Qt.PointingHandCursor)
        run_library_btn.clicked.connect(self.run_rule_library)
        library_row.addWidget(run_library_btn)

        self.view_coso_heatmap_btn = create_secondary_button("View COSO Heatmap")
        self.view_coso_heatmap_btn.setCursor(Qt.PointingHandCursor)
        self.view_coso_heatmap_btn.setEnabled(False)
        self.view_coso_heatmap_btn.clicked.connect(self.view_coso_heatmap)
        library_row.addWidget(self.view_coso_heatmap_btn)

        library_layout.addLayout(library_row)
        layout.addWidget(library_group)

        # Sample rules - NOT italic: an italicized "|" reads too much like
        # a "/" and can mislead users about the required pipe-delimited
        # syntax.
        sample_rules = QLabel("Sample: Large Transaction | amount > 10000 | high")
        sample_rules.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {Colors.TEXT_SECONDARY};
            }}
        """)
        layout.addWidget(sample_rules)

        # Run detection button - amber, distinct from the blue "Run
        # Compliance Check" primary action on the other tab.
        self.run_detection_btn = QPushButton("🎯 Detect Violations")
        self.run_detection_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 12px 24px;
                background-color: {Colors.WARNING_STRONG};
                color: {Colors.TEXT_ON_ACCENT};
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.WARNING};
            }}
        """)
        self.run_detection_btn.clicked.connect(self.run_rule_detection)
        layout.addWidget(self.run_detection_btn)

        # Progress indicator
        self.detection_progress = QProgressBar()
        self.detection_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent;
            }
        """)
        self.detection_progress.setVisible(False)
        layout.addWidget(self.detection_progress)

        # Status label - matches the Policy Check tab's pattern.
        self.detection_status = QLabel()
        self.detection_status.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.TEXT_SECONDARY};
                padding: 8px;
                border-radius: 4px;
                background-color: {Colors.BG_SECONDARY};
            }}
        """)
        self.detection_status.setVisible(False)
        layout.addWidget(self.detection_status)

        # Detected violations for this tab, shown here rather than in
        # the Generate Report tab's output box.
        self.detection_results_output = QTextEdit()
        self.detection_results_output.setReadOnly(True)
        self.detection_results_output.setPlaceholderText("Results will appear here after running detection.")
        self.detection_results_output.setStyleSheet("QTextEdit { min-height: 120px; }")
        layout.addWidget(self.detection_results_output)

        add_to_report_btn = create_secondary_button("Add to Compliance Report")
        add_to_report_btn.setCursor(Qt.PointingHandCursor)
        add_to_report_btn.clicked.connect(
            lambda: self._add_results_to_report(self.detection_results_output.toPlainText(), "Rule Detection")
        )
        layout.addWidget(add_to_report_btn, alignment=Qt.AlignLeft)

        # Per-finding actions - same pattern as the Policy Check tab.
        self.detection_findings_container, self.detection_findings_layout = self._build_findings_container()
        layout.addWidget(self.detection_findings_container)

        scroll.setWidget(tab)
        return scroll

    def create_report_tab(self) -> QWidget:
        """Create the report generation tab"""
        # This tab has more content (2 group boxes, a disclaimer, and a
        # 150px-min-height report output box) than fits inside the
        # dialog's own 800x600 minimum size - without a scroll area, Qt
        # compressed the "Report Options" combo boxes down to an
        # unreadable ~11px tall to make everything else fit instead of
        # letting the user scroll.
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer_layout.addWidget(scroll)

        tab = QWidget()
        scroll.setWidget(tab)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Report options - QGroupBox/QComboBox chrome inherited from
        # theme.py. QFormLayout (not QGridLayout) for the same reason
        # ProviderConfigWidget uses it elsewhere in this codebase - it
        # sizes label+field rows correctly by default, where the grid
        # layout needed extra fighting to stop rows overlapping.
        options_group = QGroupBox("Report Options")
        options_layout = QFormLayout(options_group)
        options_layout.setVerticalSpacing(10)

        # Engagement type
        self.engagement_combo = QComboBox()
        self.engagement_combo.addItems([
            "Financial Statement Audit",
            "Internal Controls Review",
            "Compliance Audit",
            "IT Audit",
            "Fraud Investigation",
            "Special Investigation"
        ])
        self.engagement_combo.setStyleSheet("QComboBox { min-width: 200px; }")
        options_layout.addRow("Engagement Type:", self.engagement_combo)

        # Report tone
        self.tone_combo = QComboBox()
        self.tone_combo.addItems(["Professional", "Formal", "Constructive", "Objective"])
        self.tone_combo.setStyleSheet("QComboBox { min-width: 200px; }")
        options_layout.addRow("Report Tone:", self.tone_combo)

        layout.addWidget(options_group)

        # Findings summary
        findings_group = QGroupBox("Audit Findings Summary")
        findings_layout = QVBoxLayout(findings_group)

        self.findings_edit = QTextEdit()
        self.findings_edit.setPlaceholderText(
            "Enter or paste your audit findings summary here...\n\n"
            "The AI will use this to help draft the report sections."
        )
        self.findings_edit.setStyleSheet("QTextEdit { min-height: 120px; }")
        findings_layout.addWidget(self.findings_edit)

        layout.addWidget(findings_group)

        # Generate report button
        self.generate_report_btn = create_success_button("📄 Generate Compliance Report")
        self.generate_report_btn.clicked.connect(self.generate_compliance_report)
        layout.addWidget(self.generate_report_btn)

        # Progress indicator
        self.report_progress = QProgressBar()
        self.report_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent;
            }
        """)
        self.report_progress.setVisible(False)
        layout.addWidget(self.report_progress)

        # Status label for this tab's own generation progress.
        self.report_status = QLabel()
        self.report_status.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.TEXT_SECONDARY};
                padding: 8px;
                border-radius: 4px;
                background-color: {Colors.BG_SECONDARY};
            }}
        """)
        self.report_status.setVisible(False)
        layout.addWidget(self.report_status)

        # AI-generated content disclaimer — persistent and visible above
        # the output, not just a one-time warning dialog, since the risk
        # (an unreviewed AI draft ending up in a real audit workpaper)
        # applies every time this dialog is used, not just the first.
        disclaimer = QLabel(
            "⚠ AI-generated draft. Affected counts/amounts/evidence above are computed from your "
            "complete dataset, but finding descriptions and recommendations are AI-drafted prose — "
            "review and edit before relying on this for audit conclusions. Full prompts/responses "
            "are in AI → AI Activity Log."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(
            f"color: {Colors.WARNING_STRONG}; background-color: {Colors.WARNING_SOFT}; "
            f"border: 1px solid {Colors.WARNING_STRONG}; border-radius: 4px; padding: 6px 10px; font-size: 11px;"
        )
        layout.addWidget(disclaimer)

        # Report output — editable (not read-only) so a reviewer can
        # correct or redact AI-drafted text before exporting it; a
        # read-only box meant whatever the AI produced went straight to
        # the export button with no way to fix it inline.
        self.report_output = QTextEdit()
        self.report_output.setPlaceholderText("Generated report will appear here — you can edit it before exporting.")
        self.report_output.setStyleSheet("QTextEdit { min-height: 150px; }")
        layout.addWidget(self.report_output)

        # Export button - a neutral utility action, not a primary/success
        # one, same convention as Reports view's "Export Current Report".
        export_btn = create_secondary_button("📥 Export Report")
        export_btn.clicked.connect(self.export_report)
        layout.addWidget(export_btn, alignment=Qt.AlignRight)

        layout.addStretch()
        return outer

    def sox_template(self) -> str:
        """Return SOX compliance template"""
        return """
SOX Compliance Requirements:

1. Internal Control Assessment
   - All material transactions must have proper authorization
   - Segregation of duties must be maintained
   - Access to financial systems must be restricted

2. Financial Reporting
   - All journal entries must be documented and approved
   - Period-end closing procedures must be followed
   - Reconciliation of account balances required

3. IT Controls
   - Change management procedures for financial systems
   - User access reviews quarterly
   - Backup and recovery testing
""".strip()

    def expense_template(self) -> str:
        """Return expense policy template"""
        return """
Expense Policy Requirements:

1. Authorization
   - Expenses under $100: Self-approved
   - Expenses $100-$1000: Manager approval required
   - Expenses over $1000: Director approval required

2. Documentation
   - Receipts required for all expenses over $25
   - Business purpose must be documented
   - Expense reports due within 30 days

3. Allowable Expenses
   - Travel: Economy class for domestic, business for international >6hrs
   - Meals: Per diem rates apply
   - Entertainment: Client-facing only with documentation
""".strip()

    def payment_template(self) -> str:
        """Return payment policy template"""
        return """
Payment Policy Requirements:

1. Payment Terms
   - Standard terms: Net 30
   - Early payment discount: 2/10, Net 30
   - Late payments subject to 1.5% monthly interest

2. Approval Thresholds
   - Under $1,000: AP Specialist approval
   - $1,000 - $10,000: Manager approval
   - Over $10,000: VP approval + two signatures

3. Required Documentation
   - Original invoice
   - Purchase order (for purchases >$500)
   - Receiving report for goods
""".strip()

    def run_policy_check(self):
        """Run compliance check against policy, across every currently
        checked dataset - combined into one report, with a per-dataset
        breakdown when more than one is checked."""
        policy = self.policy_edit.toPlainText().strip()
        if not policy:
            QMessageBox.warning(self, "No Policy", "Please enter a compliance policy to check against.")
            return

        # Check if AI is configured
        if not self.generator.ai.providers:
            QMessageBox.warning(
                self,
                "AI Not Configured",
                "Please configure an AI provider in Settings > AI Settings first."
            )
            return

        # Show progress
        self.run_check_btn.setEnabled(False)
        self.policy_progress.setVisible(True)
        self.policy_progress.setRange(0, 0)
        self.policy_status.setVisible(True)
        self.policy_status.setText("Analyzing data against policy...")

        targets = dict(self.selected_dataframes)
        multi = len(targets) > 1

        async def do_check():
            try:
                sections = []
                scores = []
                totals = {"high": 0, "medium": 0, "low": 0}
                errors = []
                all_findings = []  # (dataset_name, ComplianceFinding) - for the per-finding action cards

                for name, df in targets.items():
                    try:
                        report = await self.generator.generate_report(policy_text=policy, df=df)
                    except Exception as e:
                        errors.append(f"{name}: {e}")
                        continue

                    self.report = report
                    scores.append(report.overall_compliance_score)
                    totals["high"] += report.risk_summary.get('high_risk_count', 0)
                    totals["medium"] += report.risk_summary.get('medium_risk_count', 0)
                    totals["low"] += report.risk_summary.get('low_risk_count', 0)
                    all_findings.extend((name, f) for f in report.findings)

                    section = f"""
{f"=== {name} ===" if multi else ""}
(Every count and dollar figure below was computed over all {len(df):,} rows of the
complete dataset, not a sample — see AI Activity Log for the full prompts/responses behind
the drafted text.)

Compliance Score: {report.overall_compliance_score:.1f}%

Executive Summary:
{report.executive_summary}

Risk Summary:
- High Risk Findings: {report.risk_summary.get('high_risk_count', 0)}
- Medium Risk Findings: {report.risk_summary.get('medium_risk_count', 0)}
- Low Risk Findings: {report.risk_summary.get('low_risk_count', 0)}

Key Findings:
"""
                    for i, finding in enumerate(report.findings[:10], 1):
                        if not finding.computable:
                            section += f"""
{i}. {finding.title} — NOT COMPUTABLE
   Requirement: {finding.policy_requirement}
   Reason: {finding.finding}
   Recommendation: {finding.recommendation}
"""
                            continue
                        section += f"""
{i}. {finding.title} (Severity: {finding.severity.upper()})
   Requirement: {finding.policy_requirement}
   Finding: {finding.finding}
   Affected: {finding.affected_count} of {finding.total_count} records ({finding.affected_pct}%)
   Dollar Impact: ${finding.affected_amount:,.2f}
   Evidence (actual matching rows): {', '.join(finding.evidence[:5]) or 'none'}
   Recommendation: {finding.recommendation}
"""
                    sections.append(section)

                if not sections:
                    self._checkFailed.emit(
                        "Compliance check failed for every selected dataset:\n" + "\n".join(errors)
                    )
                    return

                results = "COMPLIANCE ASSESSMENT RESULTS\n"
                if multi:
                    avg_score = sum(scores) / len(scores)
                    results += (
                        f"\nChecked {len(sections)} of {len(targets)} selected dataset(s). "
                        f"Average Compliance Score: {avg_score:.1f}%\n"
                        f"Combined Risk Totals — High: {totals['high']}, Medium: {totals['medium']}, "
                        f"Low: {totals['low']}\n"
                    )
                    if errors:
                        results += "Skipped due to error: " + "; ".join(errors) + "\n"
                results += "\n" + "\n".join(sections)

                # Emit signals for thread-safe UI updates
                self._policyReportReady.emit(results)
                self._policyFindingsReady.emit(all_findings)
                self._statusReady.emit("Compliance check complete!")

            except Exception as e:
                self._checkFailed.emit(str(e))
                return

            self._checkComplete.emit()

        def run_async():
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(do_check())
            finally:
                loop.close()

        self.thread_pool.start(run_async)

    def run_rule_detection(self):
        """Run rule-based violation detection across every currently
        checked dataset, combined into one report."""
        rules_text = self.rules_edit.toPlainText().strip()
        if not rules_text:
            QMessageBox.warning(self, "No Rules", "Please define detection rules.")
            return

        # Check if AI is configured
        if not self.generator.ai.providers:
            QMessageBox.warning(
                self,
                "AI Not Configured",
                "Please configure an AI provider in Settings > AI Settings first."
            )
            return

        # Parse rules
        policy_rules = []
        for line in rules_text.split('\n'):
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    policy_rules.append({
                        "name": parts[0],
                        "description": parts[1],
                        "severity": parts[2] if len(parts) > 2 else "medium"
                    })

        if not policy_rules:
            QMessageBox.warning(self, "Invalid Rules", "Could not parse rules. Use format: Name | Description | Severity")
            return

        # Show progress
        self.run_detection_btn.setEnabled(False)
        self.detection_progress.setVisible(True)
        self.detection_progress.setRange(0, 0)

        targets = dict(self.selected_dataframes)
        multi = len(targets) > 1

        async def do_detect():
            try:
                sections = []
                errors = []
                all_findings = []  # (dataset_name, ComplianceFinding) - for the per-finding action cards

                for name, df in targets.items():
                    try:
                        violations = await self.generator.detect_violations(df=df, policy_rules=policy_rules)
                    except Exception as e:
                        errors.append(f"{name}: {e}")
                        continue

                    all_findings.extend((name, v) for v in violations)

                    section = f"{f'=== {name} ===' if multi else ''}\n"
                    section += (
                        f"Rules Analyzed: {len(policy_rules)}  |  "
                        f"Rows in dataset: {len(df):,} (every count below is computed over all of them, not a sample)\n\n"
                    )

                    for i, v in enumerate(violations, 1):
                        if not v.computable:
                            section += f"""
{i}. {v.title} — NOT COMPUTABLE
   Reason: {v.finding}
   Recommendation: {v.recommendation}
"""
                            continue
                        section += f"""
{i}. {v.title} (Severity: {v.severity.upper()})
   Finding: {v.finding}
   Evidence (actual matching rows): {', '.join(v.evidence[:5]) or 'none'}
   Affected Count: {v.affected_count} of {v.total_count} ({v.affected_pct}%)
   Dollar Impact: ${v.affected_amount:,.2f}
   Recommendation: {v.recommendation}
"""
                    sections.append(section)

                if not sections:
                    self._checkFailed.emit(
                        "Rule detection failed for every selected dataset:\n" + "\n".join(errors)
                    )
                    return

                results = "VIOLATION DETECTION RESULTS\n\n"
                if multi:
                    results += f"Checked {len(sections)} of {len(targets)} selected dataset(s).\n"
                    if errors:
                        results += "Skipped due to error: " + "; ".join(errors) + "\n"
                    results += "\n"
                results += "\n".join(sections)

                # Emit signals for thread-safe UI updates
                self._detectionReportReady.emit(results)
                self._detectionFindingsReady.emit(all_findings)
                self._detectionStatusReady.emit("Detection complete!")

            except Exception as e:
                self._checkFailed.emit(str(e))
                return

            # Enable buttons
            self.run_detection_btn.setEnabled(True)
            self.detection_progress.setVisible(False)

        def run_async():
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(do_detect())
            finally:
                loop.close()

        self.thread_pool.start(run_async)

    def run_rule_library(self):
        """Run a canned rule library (deterministic, no AI call) against
        every currently checked dataset, using the same result-rendering
        path as free-text Rule Detection above. Field mapping is confirmed
        once via RuleLibraryMappingDialog, against the first checked
        dataset's columns, then applied to every checked dataset — a rule
        whose mapped field doesn't exist in a particular dataset is simply
        reported as not-computable for that dataset rather than guessed at.
        """
        library_id = self.library_combo.currentData()
        if not library_id:
            return
        library = rule_library.get_library(library_id)
        field_specs = rule_library.get_field_specs(library_id)

        targets = dict(self.selected_dataframes)
        first_df = next(iter(targets.values()))
        suggested = rule_library.suggest_mapping(
            first_df.columns, field_specs["required_fields"], field_specs["optional_fields"]
        )

        dialog = RuleLibraryMappingDialog(
            df_columns=first_df.columns, library=library, field_specs=field_specs,
            suggested_mapping=suggested, parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        mapping = dialog.get_mapping()
        params = dialog.get_params()

        from services.ai_service import ComplianceFinding

        multi = len(targets) > 1
        sections = []
        all_findings = []  # (dataset_name, ComplianceFinding)

        for name, df in targets.items():
            try:
                results = rule_library.apply_library(df, library_id, mapping, params)
            except Exception as e:
                sections.append(f"{f'=== {name} ===' if multi else ''}\nError running library: {e}")
                continue

            section = f"{f'=== {name} ===' if multi else ''}\n"
            section += f"Library: {library['display_name']}  |  Rows in dataset: {len(df):,}\n"

            for i, entry in enumerate(results, 1):
                rule = entry["rule"]
                result = entry["result"]
                title = rule["name"]
                citation = rule.get("citation", "")

                if not result["computable"]:
                    section += f"\n{i}. {title} — NOT COMPUTABLE\n   Reason: {result['reason']}\n"
                    finding = ComplianceFinding(
                        title=title, severity="info", policy_requirement=citation,
                        finding=f"Not computable: {result['reason']}", evidence=[],
                        recommendation=rule.get("recommendation", ""), computable=False,
                    )
                else:
                    severity = rule.get("severity", "medium") if result["affected_count"] > 0 else "info"
                    finding_text = (
                        f"{result['affected_count']} of {result['total_count']} rows "
                        f"({result['affected_pct']}%) match: {rule['description']}"
                    )
                    section += (
                        f"\n{i}. {title} (Severity: {severity.upper()}) — {citation}\n"
                        f"   Finding: {finding_text}\n"
                        f"   Affected: {result['affected_count']} of {result['total_count']} ({result['affected_pct']}%)\n"
                        f"   Dollar Impact: ${result['affected_amount']:,.2f}\n"
                        f"   Evidence (actual matching rows): {', '.join(result['evidence'][:5]) or 'none'}\n"
                        f"   Recommendation: {rule.get('recommendation', '')}\n"
                    )
                    finding = ComplianceFinding(
                        title=title, severity=severity, policy_requirement=citation,
                        finding=finding_text, evidence=result["evidence"],
                        recommendation=rule.get("recommendation", ""),
                        affected_count=result["affected_count"], affected_amount=result["affected_amount"],
                        total_count=result["total_count"], affected_pct=result["affected_pct"],
                        computable=True, matched_df=result["matched_df"], mask=result["mask"],
                    )
                    if rule.get("coso_component"):
                        self._coso_findings_pool.append({
                            "coso_component": rule["coso_component"], "severity": severity,
                            "affected_pct": result["affected_pct"], "title": title,
                        })

                all_findings.append((name, finding))

            sections.append(section)

        results_text = "RULE LIBRARY RESULTS (deterministic — no AI call)\n\n" + "\n".join(sections)
        self._on_detection_report_ready(results_text)
        self._on_detection_findings_ready(all_findings)
        self._on_detection_status_ready("Rule library check complete!")

        if self._coso_findings_pool:
            self.view_coso_heatmap_btn.setEnabled(True)

    def view_coso_heatmap(self):
        """Show the COSO component heatmap built from every COSO-tagged
        rule-library finding run so far in this dialog session."""
        from services.coso_service import CosoService

        heatmap_df = CosoService().build_heatmap_from_findings(self._coso_findings_pool)
        if heatmap_df.height == 0:
            QMessageBox.information(
                self, "COSO Heatmap", "No COSO-tagged findings yet — run a rule library first."
            )
            return
        dialog = CosoHeatmapDialog(heatmap_df, parent=self)
        dialog.exec()

    def generate_compliance_report(self):
        """Generate a compliance report"""
        findings = self.findings_edit.toPlainText().strip()

        # Check if AI is configured
        if not self.generator.ai.providers:
            QMessageBox.warning(
                self,
                "AI Not Configured",
                "Please configure an AI provider in Settings > AI Settings first."
            )
            return

        # Show progress
        self.generate_report_btn.setEnabled(False)
        self.report_progress.setVisible(True)
        self.report_progress.setRange(0, 0)
        self.policy_status.setVisible(True)
        self.policy_status.setText("Generating report sections...")

        async def do_generate():
            try:
                from services.ai_service import ReportAssistant
                assistant = ReportAssistant(self.generator.ai)

                audit_results = {
                    "engagement_type": self.engagement_combo.currentText(),
                    "findings_summary": findings or "No specific findings entered.",
                    "data_analyzed": {
                        "records": len(self.df),
                        "columns": len(self.df.columns)
                    }
                }

                # Generate different sections
                sections = ["Executive Summary", "Scope and Objectives",
                           "Findings and Recommendations", "Conclusion"]

                report_text = f"COMPLIANCE REPORT\n"
                report_text += f"Engagement: {self.engagement_combo.currentText()}\n"
                report_text += f"Tone: {self.tone_combo.currentText()}\n"
                report_text += "=" * 50 + "\n\n"

                for section in sections:
                    draft = await assistant.draft_section(
                        section=section,
                        audit_results=audit_results,
                        tone=self.tone_combo.currentText().lower()
                    )
                    report_text += f"## {section}\n\n{draft}\n\n"

                # Emit signals for thread-safe UI updates
                self._reportReady.emit(report_text)
                self._reportStatusReady.emit("Report generated successfully!")

            except Exception as e:
                self._checkFailed.emit(str(e))
                return

            self._checkComplete.emit()

        def run_async():
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(do_generate())
            finally:
                loop.close()

        self.thread_pool.start(run_async)

    def export_report(self):
        """Export the report to a file"""
        report = self.report_output.toPlainText()
        if not report:
            QMessageBox.warning(self, "No Report", "No report to export.")
            return

        from PySide6.QtWidgets import QFileDialog
        from pathlib import Path

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            str(Path.home() / "Documents" / "compliance_report.txt"),
            "Text Files (*.txt);;Word Documents (*.docx);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(report)
                QMessageBox.information(self, "Export Complete", f"Report saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
