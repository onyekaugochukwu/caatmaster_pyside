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


class ComplianceReportDialog(QDialog):
    """Dialog for AI-powered compliance checking and report generation"""

    # Thread-safe signals for UI updates
    _reportReady = Signal(str)  # Report generated
    _statusReady = Signal(str)  # Status message
    _checkComplete = Signal()  # Check complete
    _checkFailed = Signal(str)  # Check failed with error

    def __init__(self, dataframes: dict, compliance_generator, parent=None, selected_key: str = None):
        """Initialize dialog with multiple datasets

        Args:
            dataframes: Dictionary of {dataset_name: polars DataFrame}
            compliance_generator: AI compliance generator instance
            parent: Parent widget
            selected_key: Key of initially selected dataset
        """
        super().__init__(parent)
        self.dataframes = dataframes
        self.df = dataframes.get(selected_key, list(dataframes.values())[0]) if selected_key else list(dataframes.values())[0]
        self.generator = compliance_generator
        self.report = None
        # Thread pool for async operations (no parent to avoid thread issues)
        from PySide6.QtCore import QThreadPool
        self.thread_pool = QThreadPool()
        self.setup_ui()

        # Connect thread-safe signals for UI updates
        self._reportReady.connect(self._on_report_ready, Qt.QueuedConnection)
        self._statusReady.connect(self._on_status_ready, Qt.QueuedConnection)
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
        """Handle status ready signal"""
        self.policy_status.setText(status)

    def _on_check_complete(self):
        """Handle check complete signal"""
        self.run_check_btn.setEnabled(True)
        self.policy_progress.setVisible(False)
        self.generate_report_btn.setEnabled(True)
        self.report_progress.setVisible(False)

    def _on_check_failed(self, error: str):
        """Handle check failed signal"""
        self.policy_status.setText(f"Error: {error}")
        self.run_check_btn.setEnabled(True)
        self.policy_progress.setVisible(False)
        self.generate_report_btn.setEnabled(True)
        self.report_progress.setVisible(False)
        QMessageBox.critical(self, "Check Error", error)

    def _on_dataset_changed(self, index: int):
        """Handle dataset selection change"""
        key = self.dataset_combo.itemData(index)
        if key and key in self.dataframes:
            self.df = self.dataframes[key]
            self.report_output.clear()
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

        # Dataset selector (if multiple datasets available) - QGroupBox/
        # QComboBox chrome inherited from the app-wide rules in theme.py.
        if len(self.dataframes) > 1:
            dataset_group = QGroupBox("Select Dataset")
            dataset_layout = QHBoxLayout(dataset_group)
            dataset_layout.setContentsMargins(16, 20, 16, 16)

            dataset_layout.addWidget(QLabel("Dataset:"))
            self.dataset_combo = QComboBox()
            self.dataset_combo.setStyleSheet("QComboBox { min-width: 200px; }")
            for key in self.dataframes.keys():
                self.dataset_combo.addItem(key, key)
            self.dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
            dataset_layout.addWidget(self.dataset_combo)
            dataset_layout.addStretch()
            layout.addWidget(dataset_group)
        else:
            self.dataset_combo = None

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
        """Create the policy compliance check tab"""
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

        layout.addStretch()
        return tab

    def create_rules_tab(self) -> QWidget:
        """Create the rule-based detection tab"""
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

        # Sample rules
        sample_rules = QLabel("Sample: Large Transaction | amount > 10000 | high")
        sample_rules.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {Colors.TEXT_SECONDARY};
                font-style: italic;
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

        layout.addStretch()
        return tab

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
        """Run compliance check against policy"""
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

        async def do_check():
            try:
                report = await self.generator.generate_report(
                    policy_text=policy,
                    df=self.df,
                )

                self.report = report

                # Show results
                results = f"""
COMPLIANCE ASSESSMENT RESULTS
(Every count and dollar figure below was computed over all {len(self.df):,} rows of the
complete dataset, not a sample — see AI Activity Log for the full prompts/responses behind
the drafted text.)

Overall Compliance Score: {report.overall_compliance_score:.1f}%

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
                        results += f"""
{i}. {finding.title} — NOT COMPUTABLE
   Requirement: {finding.policy_requirement}
   Reason: {finding.finding}
   Recommendation: {finding.recommendation}
"""
                        continue
                    results += f"""
{i}. {finding.title} (Severity: {finding.severity.upper()})
   Requirement: {finding.policy_requirement}
   Finding: {finding.finding}
   Affected: {finding.affected_count} of {finding.total_count} records ({finding.affected_pct}%)
   Dollar Impact: ${finding.affected_amount:,.2f}
   Evidence (actual matching rows): {', '.join(finding.evidence[:5]) or 'none'}
   Recommendation: {finding.recommendation}
"""

                # Emit signals for thread-safe UI updates
                self._reportReady.emit(results)
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
        """Run rule-based violation detection"""
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

        async def do_detect():
            try:
                violations = await self.generator.detect_violations(
                    df=self.df,
                    policy_rules=policy_rules
                )

                results = f"VIOLATION DETECTION RESULTS\n\n"
                results += (
                    f"Rules Analyzed: {len(policy_rules)}  |  "
                    f"Rows in dataset: {len(self.df):,} (every count below is computed over all of them, not a sample)\n\n"
                )

                for i, v in enumerate(violations, 1):
                    if not v.computable:
                        results += f"""
{i}. {v.title} — NOT COMPUTABLE
   Reason: {v.finding}
   Recommendation: {v.recommendation}
"""
                        continue
                    results += f"""
{i}. {v.title} (Severity: {v.severity.upper()})
   Finding: {v.finding}
   Evidence (actual matching rows): {', '.join(v.evidence[:5]) or 'none'}
   Affected Count: {v.affected_count} of {v.total_count} ({v.affected_pct}%)
   Dollar Impact: ${v.affected_amount:,.2f}
   Recommendation: {v.recommendation}
"""

                # Emit signals for thread-safe UI updates
                self._reportReady.emit(results)
                self._statusReady.emit("Detection complete!")

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
                self._statusReady.emit("Report generated successfully!")

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
