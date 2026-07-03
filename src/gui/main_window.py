"""
Main Application Window for CaatMaster
Modern UI inspired by data_workspace_app.py
"""
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QStatusBar, QDialog,
    QSplitter, QMessageBox, QApplication, QFrame, QLabel,
    QPushButton, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QThreadPool
from PySide6.QtGui import QFont, QShortcut, QKeySequence

# Import project management
from core.project_manager import Project, Dataset, ProjectExporter
from core.data_processor import LegacyDataProcessor
from services.export_service import ExportService
from services.ai_service import AIManager, DatasetInterpreter, ColumnGenerator, ComplianceReportGenerator
from gui.dialogs.project_dialog import NewProjectDialog, OpenProjectDialog, SaveProjectDialog, DatasetManagerDialog
from gui.dialogs.ai_settings_dialog import AISettingsDialog
from gui.dialogs.column_generator_dialog import ColumnGeneratorDialog
from gui.dialogs.compliance_report_dialog import ComplianceReportDialog

# Import the sidebar, menu/toolbar chrome, and backstage
from gui.components.sidebar import Sidebar
from gui.components.app_menu import CommandRegistry, build_menu_bar
from gui.components.backstage import BackstageView
from gui.components.ai_panel import AIPanel


class MainWindow(QMainWindow):
    """Main application window with modern CaatMaster UI"""

    # operation_ids that count as "running an audit" for the dashboard's
    # Last Audit tile — the actual audit/statistical-flag checks, not every
    # transformation (a rename or a sort shouldn't bump "last audit").
    AUDIT_OPERATION_IDS = {
        "audit_benford_law", "audit_duplicate_detection", "audit_gap_analysis",
        "audit_outlier_detection", "audit_round_numbers", "audit_flag_rows",
        "stat_zscore", "stat_percent_rank", "stat_rank", "stat_add_group_stats",
    }

    def __init__(self):
        super().__init__()
        self.current_project: Optional[Project] = None
        self.current_project_path: Optional[str] = None  # .caat file this project was opened from / last saved to
        self.current_dataset: Optional[Dataset] = None
        self.project_dirty: bool = False  # True if there are changes since the last save
        self.auth_service = None
        self.ai_manager: Optional[AIManager] = None
        self.ai_interpreter: Optional[DatasetInterpreter] = None
        self.ai_column_generator: Optional[ColumnGenerator] = None
        self.ai_compliance: Optional[ComplianceReportGenerator] = None
        self._login_successful = False  # Track if login was successful
        self._apply_theme()
        self.setup_auth()
        self.setup_ai()
        self.setup_ui()
        self.setup_backstage()
        self.create_statusbar()
        self.setup_autosave()
        # Hide window until login is complete
        self.hide()
        self.show_login_dialog()

    def _apply_theme(self):
        """Set the application-wide font. Colors/borders come from the global
        stylesheet (src/gui/theme.py), applied once in main.py — this method
        intentionally does not set its own stylesheet so it can't drift from it."""
        font = QFont("Segoe UI", 10)
        QApplication.instance().setFont(font)

    def setup_auth(self):
        """Initialize authentication service"""
        from services.auth_service import AuthService

        self.auth_service = AuthService()

        # Create default admin if no users exist
        self.auth_service.create_default_admin()

        # Note: We do NOT auto-load saved sessions
        # User must login every time the app starts for security

    def setup_ai(self):
        """Initialize AI services"""
        self.ai_manager = AIManager()
        self.ai_interpreter = DatasetInterpreter(self.ai_manager)
        self.ai_column_generator = ColumnGenerator(self.ai_manager)
        self.ai_compliance = ComplianceReportGenerator(self.ai_manager)

        # Load any saved API keys from secure storage
        self._load_ai_credentials()

    def _load_ai_credentials(self):
        """Load AI credentials from secure storage"""
        try:
            from services.ai_service import load_stored_providers
            load_stored_providers(self.ai_manager)
            # Update AI panel with current provider info (only if ai_panel exists)
            if hasattr(self, 'ai_panel') and self.ai_panel:
                self._update_ai_panel_provider()
        except Exception as e:
            print(f"Warning: Could not load AI credentials: {e}")

    def _update_ai_panel_provider(self):
        """Update the AI panel with current provider info"""
        if not hasattr(self, 'ai_panel') or not self.ai_panel:
            return
        if self.ai_manager and self.ai_manager.default_provider:
            provider = self.ai_manager.get_provider(self.ai_manager.default_provider)
            if provider:
                display_name = provider.provider_name.title()
                model_name = provider.model or "Unknown"
                self.ai_panel.set_provider(display_name, model_name)

    def _save_ai_credentials(self):
        """Save AI credentials to secure storage"""
        try:
            from services.ai_service import save_ai_credentials

            for provider in self.ai_manager.providers.values():
                save_ai_credentials(provider.provider_name, provider.api_key, provider.model)

        except Exception as e:
            print(f"Warning: Could not save AI credentials: {e}")

    def setup_ui(self):
        """Set up the main window UI"""
        self.setWindowTitle("CaatMaster - Professional Audit Analytics Tool")

        # Calculate minimum size based on available screen geometry
        screen_geometry = QApplication.instance().screenAt(self.pos()).availableGeometry()
        min_width = max(800, int(screen_geometry.width() * 0.5))  # At least 50% of screen width
        min_height = max(500, int(screen_geometry.height() * 0.6))  # At least 60% of screen height
        self.setMinimumSize(min_width, min_height)

        self.setObjectName("MainWindow")

        # Native menu bar (classic Office 2003-style chrome) — every command
        # is a QAction defined once in CommandRegistry and shared between the
        # menu and (via handle_ribbon_action) the Ctrl+K command palette.
        # No toolbar: with everything organized into menus, a row of icon
        # buttons duplicating a subset of them was just clutter.
        self.command_registry = CommandRegistry(self)
        self.setMenuBar(build_menu_bar(self, self.command_registry))

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout - vertical stack: sidebar+content (menu/toolbar are
        # native QMainWindow chrome, added above, not part of this layout)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create scroll area for middle content (sidebar + content area)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Styling (background, scrollbars) comes from the global stylesheet
        # (src/gui/theme.py) — QScrollArea/QScrollBar rules are defined there.

        # Thread pool for async AI operations (no parent to avoid thread issues)
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(2)  # Limit to 2 concurrent threads

        # Middle area: sidebar + content area
        middle_area = QWidget()
        middle_layout = QHBoxLayout(middle_area)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)

        # Create the new sidebar
        self.sidebar = Sidebar()
        self.sidebar.navigation_requested.connect(self.on_navigation_requested)
        self.sidebar.dataset_selected.connect(self.on_dataset_selected)
        self.sidebar.dataset_rename_requested.connect(self.on_dataset_rename_requested)
        self.sidebar.dataset_duplicate_requested.connect(self.on_dataset_duplicate_requested)
        self.sidebar.dataset_delete_requested.connect(self.on_dataset_delete_requested)
        self.sidebar.dataset_split_sheet_requested.connect(self.on_dataset_split_sheet_requested)
        self.sidebar.dataset_refresh_requested.connect(self.on_dataset_refresh_requested)
        self.sidebar.join_datasets_requested.connect(self.on_join_datasets_requested)
        self.sidebar.append_datasets_requested.connect(self.on_append_datasets_requested)
        self.sidebar.upload_requested.connect(self.on_upload_requested)
        self.sidebar.paste_requested.connect(self.on_paste_requested)
        self.sidebar.project_edit_requested.connect(self.edit_current_project)
        self.sidebar.project_delete_requested.connect(self.delete_current_project)
        self.sidebar.toggle_ai_panel.connect(self.toggle_ai_panel)
        self.sidebar.ai_chat_requested.connect(self._on_ai_chat_requested)
        self.sidebar.audit_programs_requested.connect(self._on_audit_programs_requested)
        middle_layout.addWidget(self.sidebar)

        # Content area (right side) - Light mode
        content_area = QWidget()
        content_area.setObjectName("ContentArea")
        # Styling (background, table/header colors) comes from the global
        # stylesheet (src/gui/theme.py) — no local override here.
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Create stacked widget for views
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("ContentStack")
        content_layout.addWidget(self.content_stack)

        middle_layout.addWidget(content_area, 1)

        # Applied Steps panel — persistent across every data-workspace page
        # (Data, Transform, SQL, Visualizations, Reports, Query), so it never
        # disappears just because you switched pages. Visibility is toggled
        # in on_navigation_requested(); TransformView renders into this
        # shared instance regardless of which page is currently on screen.
        from gui.components.applied_steps_panel import AppliedStepsPanel
        self.applied_steps_panel = AppliedStepsPanel()
        self.applied_steps_panel.setVisible(False)
        middle_layout.addWidget(self.applied_steps_panel)

        # AI Panel (right sidebar) - initially hidden
        self.ai_panel = AIPanel()
        self.ai_panel.setFixedWidth(320)
        self.ai_panel.setVisible(False)
        self.ai_panel.sendMessage.connect(self._on_ai_message)
        self.ai_panel.cancelRequest.connect(self._on_ai_cancel_request)
        self.ai_panel.analyzeDataset.connect(self._on_ai_analyze_dataset)
        self.ai_panel.generateColumn.connect(self._on_ai_generate_column)
        self.ai_panel.complianceCheck.connect(self._on_ai_compliance_check)
        self.ai_panel.showSettings.connect(self._on_ai_show_settings)
        middle_layout.addWidget(self.ai_panel)

        # Set the middle_area as the scroll area's widget
        scroll_area.setWidget(middle_area)
        main_layout.addWidget(scroll_area, 1)

        # Create main views
        self.create_views()

        # Paste a clipboard range directly into a new dataset
        paste_shortcut = QShortcut(QKeySequence("Ctrl+Shift+V"), self)
        paste_shortcut.activated.connect(self.on_paste_requested)

        # Command palette: search every transformation/report/nav action
        palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        palette_shortcut.activated.connect(self.show_command_palette)

    def setup_backstage(self):
        """Setup the backstage view overlay"""
        # Backstage view (full screen overlay)
        self.backstage_view = BackstageView()
        self.backstage_view.setVisible(False)

        # Connect backstage signals
        self.backstage_view.new_project.connect(self.new_project)
        self.backstage_view.open_project.connect(self.open_project)
        self.backstage_view.save_project.connect(self.save_project)
        self.backstage_view.export_data.connect(self.export_data)
        self.backstage_view.export_review.connect(self.export_for_review)
        self.backstage_view.settings.connect(self._on_settings)
        self.backstage_view.help_requested.connect(self._on_help_requested)
        self.backstage_view.dashboard_requested.connect(lambda: self.on_navigation_requested("dashboard"))
        self.backstage_view.close.connect(self.toggle_backstage)

        # Add backstage as overlay on top of everything
        self.backstage_view.setParent(self.centralWidget())
        self.backstage_view.setGeometry(0, 0, self.width(), self.height())

    def toggle_backstage(self):
        """Toggle the backstage view"""
        if hasattr(self, 'backstage_view'):
            is_visible = self.backstage_view.isVisible()
            self.backstage_view.setVisible(not is_visible)
            self.backstage_view.setGeometry(0, 0, self.width(), self.height())

    def show_backstage(self):
        """Show the backstage view"""
        if hasattr(self, 'backstage_view'):
            self.backstage_view.setVisible(True)
            self.backstage_view.setGeometry(0, 0, self.width(), self.height())

    def hide_backstage(self):
        """Hide the backstage view"""
        if hasattr(self, 'backstage_view'):
            self.backstage_view.setVisible(False)

    def resizeEvent(self, event):
        """Handle window resize"""
        super().resizeEvent(event)
        # Update backstage geometry (check if attribute exists first)
        if hasattr(self, 'backstage_view') and self.backstage_view.isVisible():
            self.backstage_view.setGeometry(0, 0, self.width(), self.height())

    def closeEvent(self, event):
        """Handle window close - offer to save unsaved changes first, then
        wait for threads to finish. Without this, closing the window with
        pending transformations silently discarded them — autosave only
        writes to a separate recovery file, never the project itself."""
        if self.project_dirty and self.current_project:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"'{self.current_project.name}' has unsaved changes. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Save:
                self.save_project()
                if self.project_dirty:
                    # Save was cancelled (e.g. user backed out of the file
                    # dialog on first save) — don't close after all.
                    event.ignore()
                    return

        # Wait for any running AI threads to complete (max 5 seconds)
        self.thread_pool.waitForDone(5000)
        event.accept()

    def mark_project_dirty(self):
        """Flag that the current project has unsaved changes."""
        self.project_dirty = True

    def mark_project_clean(self):
        """Flag that the current project matches what's on disk."""
        self.project_dirty = False

    def _on_settings(self):
        """Navigate to settings"""
        self.hide_backstage()
        self.content_stack.setCurrentWidget(self.views["settings"])
        self.sidebar.set_active_button("settings")

    def _on_help_requested(self, help_option):
        """Handle help option selection"""
        self.hide_backstage()
        # Show appropriate help content based on option
        if "User Guide" in help_option:
            self.statusBar().showMessage("Opening user guide...")
            # TODO: implement user guide viewer
        elif "Tutorials" in help_option:
            self.statusBar().showMessage("Opening tutorials...")
        elif "Keyboard Shortcuts" in help_option:
            self.statusBar().showMessage("Opening keyboard shortcuts reference...")
        elif "Check for Updates" in help_option:
            self.statusBar().showMessage("Checking for updates...")
        elif "About" in help_option:
            self.show_about()

    # ========================================================================
    # AI Panel Signal Handlers
    # ========================================================================

    def toggle_ai_panel(self, visible: bool = None):
        """Toggle the AI panel visibility"""
        if visible is None:
            visible = not self.ai_panel.isVisible()
        self.ai_panel.setVisible(visible)

    def toggle_sidebar(self, visible: bool = None):
        """Toggle the Queries sidebar's visibility (View > Show Sidebar, Ctrl+B)."""
        if visible is None:
            visible = not self.sidebar.isVisible()
        self.sidebar.setVisible(visible)
        if hasattr(self, "sidebar_toggle_action") and self.sidebar_toggle_action.isChecked() != visible:
            self.sidebar_toggle_action.setChecked(visible)

    @Slot(str)
    def _on_ai_message(self, message: str):
        """Handle AI chat message"""
        if not self._check_ai_available():
            return

        # Get current dataset info for context
        context = self._get_ai_context()

        def run_async():
            """Run async code in a new event loop"""
            import asyncio

            async def send_to_ai():
                try:
                    # Show typing indicator (via signal for thread safety)
                    self.ai_panel._typingIndicatorNeeded.emit()

                    # Build context-enhanced prompt
                    full_prompt = f"{context}\n\nUser Question: {message}"

                    response = await self.ai_manager.complete(
                        prompt=full_prompt,
                        task_type="general",
                        temperature=0.3
                    )

                    # Remove typing indicator and show response (via signal for thread safety)
                    self.ai_panel._responseReady.emit(response.content)

                except Exception as e:
                    self.ai_panel._errorReady.emit(str(e))

            # Run in new event loop (don't set as global loop)
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(send_to_ai())
            finally:
                loop.close()

        # Run async using thread pool
        self.thread_pool.start(run_async)

    @Slot()
    def _on_ai_cancel_request(self):
        """Handle cancel request - stop ongoing AI operation"""
        # Note: For true cancellation, we would need to track and cancel the asyncio tasks
        # For now, we show a message and reset the UI state
        self.ai_panel.set_processing(False)
        self.ai_panel._responseReady.emit("Request cancelled.")
        self.statusBar().showMessage("AI request cancelled")

    @Slot()
    def _on_ai_analyze_dataset(self):
        """Handle analyze dataset request"""
        if not self._check_data_loaded():
            return
        if not self._check_ai_available():
            return

        def run_async():
            """Run async code in a new event loop"""
            import asyncio

            async def analyze():
                try:
                    self.statusBar().showMessage("Analyzing dataset with AI...")
                    df = self.current_dataset.get_current_dataframe()

                    # Get project context if available
                    context = ""
                    if self.current_project:
                        context = f"Project: {self.current_project.name}\nClient: {self.current_project.client_name or 'N/A'}"

                    summary = await self.ai_interpreter.analyze_dataset(df, context)

                    # Show results in AI panel (via signal for thread safety)
                    response = f"## Dataset Analysis\n\n**Executive Summary:**\n{summary.executive_summary}\n\n"
                    response += f"**Data Quality Score:** {summary.data_quality.get('overall_score', 'N/A')}/100\n\n"
                    response += f"**Key Fields:** {', '.join(summary.key_fields)}\n\n"
                    response += "**Audit Insights:**\n"
                    for insight in summary.audit_insights[:5]:
                        response += f"- **{insight.get('title', 'Unknown')}** ({insight.get('severity', 'unknown')} risk)\n"
                        response += f"  {insight.get('description', '')}\n\n"

                    self.ai_panel._responseReady.emit(response)
                    self.statusBar().showMessage("Dataset analysis complete")

                except Exception as e:
                    self.ai_panel._errorReady.emit(str(e))
                    self.statusBar().showMessage("Analysis failed")

            # Run in new event loop (don't set as global loop)
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(analyze())
            finally:
                loop.close()

        # Run async using thread pool
        self.thread_pool.start(run_async)

    @Slot()
    def _on_ai_generate_column(self):
        """Open AI column generator dialog"""
        if not self._check_data_loaded():
            return

        # Get all datasets from current project
        dataframes = {}
        if self.current_project and hasattr(self.current_project, 'datasets'):
            # datasets is a Dict[str, Dataset], iterate over values to get Dataset objects
            for ds in self.current_project.datasets.values():
                dataframes[ds.name] = ds.get_current_dataframe()
        elif self.current_dataset:
            # Fallback to current dataset only
            dataframes[self.current_dataset.name] = self.current_dataset.get_current_dataframe()

        if not dataframes:
            QMessageBox.warning(self, "No Data", "No dataset available to generate column for.")
            return

        # Use current dataset name as selected key if available
        selected_key = self.current_dataset.name if self.current_dataset and self.current_dataset.name in dataframes else None

        dialog = ColumnGeneratorDialog(
            dataframes,
            self.ai_column_generator,
            self,
            selected_key=selected_key
        )
        dialog.column_applied.connect(self._on_column_applied)
        dialog.exec()

    @Slot()
    def _on_ai_compliance_check(self):
        """Open AI compliance check dialog"""
        if not self._check_data_loaded():
            return
        if not self._check_ai_available():
            return

        # Get all datasets from current project
        dataframes = {}
        if self.current_project and hasattr(self.current_project, 'datasets'):
            # datasets is a Dict[str, Dataset], iterate over values to get Dataset objects
            for ds in self.current_project.datasets.values():
                dataframes[ds.name] = ds.get_current_dataframe()
        elif self.current_dataset:
            dataframes[self.current_dataset.name] = self.current_dataset.get_current_dataframe()

        if not dataframes:
            QMessageBox.warning(self, "No Data", "No data available for compliance check.")
            return

        # Determine selected key
        selected_key = self.current_dataset.name if self.current_dataset else None

        dialog = ComplianceReportDialog(
            dataframes,
            self.ai_compliance,
            self,
            selected_key=selected_key
        )
        dialog.exec()

    @Slot()
    def _on_ai_show_settings(self):
        """Open AI settings dialog"""
        dialog = AISettingsDialog(self.ai_manager, self)
        dialog.settingsChanged.connect(self._on_ai_settings_changed)
        dialog.exec()

    def _on_ai_settings_changed(self):
        """Handle AI settings changes"""
        self._save_ai_credentials()

        # Reload AI providers from storage
        try:
            from services.ai_service import load_stored_providers, get_ai_credentials
            # First load providers, then set default provider
            load_stored_providers(self.ai_manager)

            # Load and set the default provider (after providers are loaded)
            default_creds = get_ai_credentials("default_provider")
            if default_creds and default_creds.get("api_key"):
                provider_name = default_creds["api_key"]
                # Verify this provider exists before setting it
                if provider_name in self.ai_manager.providers:
                    self.ai_manager.default_provider = provider_name
                else:
                    # Provider not loaded yet, try to add it
                    self.ai_manager.default_provider = provider_name

            # Update AI panel with current provider info
            self._update_ai_panel_provider()
        except Exception as e:
            print(f"Warning: Could not reload AI credentials: {e}")

        self.statusBar().showMessage("AI settings updated")

        # Update AI info in settings view if it's visible
        settings_view = self.views.get("settings")
        if settings_view and hasattr(settings_view, 'refresh_ai_info'):
            settings_view.refresh_ai_info()

    @Slot()
    def _on_ai_chat_requested(self):
        """Open AI Chat dialog"""
        from gui.dialogs.ai_chat_dialog import AIChatDialog

        # Get current dataframe if available
        current_df = None
        if self.current_dataset:
            current_df = self.current_dataset.get_current_dataframe()

        dialog = AIChatDialog(current_df, self)
        dialog.exec()

    @Slot()
    def _on_audit_programs_requested(self):
        """Open the Audit Programs gallery: save the current dataset's
        Applied Steps as a reusable template, or apply a saved one."""
        from gui.dialogs.audit_programs_dialog import AuditProgramsDialog

        current_steps = []
        if self.current_dataset and self.current_dataset.transformation_pipeline:
            current_steps = [
                {"operation_id": s.operation_id, "params": s.params}
                for s in self.current_dataset.transformation_pipeline.get_steps()
            ]

        dialog = AuditProgramsDialog(current_steps, self)
        dialog.programApplied.connect(self._on_audit_program_applied)
        dialog.exec()

    def _on_audit_program_applied(self, steps):
        """Replay a saved Audit Program's steps against the active dataset."""
        transform_view = self.views.get("transform")
        if not transform_view or not transform_view.pipeline:
            QMessageBox.warning(self, "No Data", "Please load a dataset first.")
            return

        applied = 0
        for step in steps:
            try:
                transform_view.apply_transformation(step["operation_id"], step["params"])
                applied += 1
            except Exception as e:
                QMessageBox.warning(
                    self, "Step Failed",
                    f"Stopped after {applied} step(s) — '{step['operation_id']}' failed:\n{str(e)}"
                )
                break

        self.statusBar().showMessage(f"Applied {applied} step(s) from Audit Program")

    def _on_column_applied(self, data: dict):
        """Handle when a column is applied"""
        if not self.current_dataset:
            return

        column_name = data.get("column_name")  # Final column name (user's or AI's)
        code = data.get("code")
        instruction = data.get("instruction")
        original_ai_name = data.get("original_ai_name")  # AI's suggested name

        # Add step to transformation pipeline
        if self.current_dataset.transformation_pipeline is None:
            from core.data_processor import TransformationPipeline
            self.current_dataset.set_pipeline(TransformationPipeline(self.current_dataset.original_dataframe))

        # Add the step to the pipeline
        step_params = {
            "column_name": column_name,
            "instruction": instruction,
            "generated_code": code
        }

        try:
            print(f"Adding step with params: {step_params}")
            created = self.current_dataset.transformation_pipeline.add_step("ai_generate_column", step_params)
            print(f"Step added successfully: {created}")

            # Fix column tracking if user renamed the column
            if original_ai_name and original_ai_name != column_name:
                steps = self.current_dataset.transformation_pipeline.get_steps()
                if steps:
                    last_step = steps[-1]
                    # Update created_columns to use the user's column name
                    if original_ai_name in last_step.created_columns:
                        last_step.created_columns.remove(original_ai_name)
                        last_step.created_columns.append(column_name)
                    # Update column tracking
                    if original_ai_name in self.current_dataset.transformation_pipeline._column_tracking:
                        tracking = self.current_dataset.transformation_pipeline._column_tracking.pop(original_ai_name)
                        self.current_dataset.transformation_pipeline._column_tracking[column_name] = tracking
                    print(f"Column tracking updated: {original_ai_name} -> {column_name}")

            print(f"Pipeline now has {len(self.current_dataset.transformation_pipeline.get_steps())} steps")

            # Update the dataset's dataframe to include the new column
            self.current_dataset.original_dataframe = self.current_dataset.get_current_dataframe()

            # Refresh the transform view to show the new step
            transform_view = self.views.get("transform")
            print(f"Transform view found: {transform_view}")
            if transform_view:
                transform_view.set_dataframe(self.current_dataset.get_current_dataframe(),
                                            self.current_dataset.transformation_pipeline)
                print("Transform view refreshed")

            self.statusBar().showMessage(f"Column '{column_name}' added to dataset - step recorded")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Column added but failed to record step: {e}")

    def _check_ai_available(self) -> bool:
        """Check if AI is available (configured)"""
        if not self.ai_manager or not self.ai_manager.providers:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "AI Not Configured",
                "Please configure an AI provider in Settings > AI Settings first."
            )
            # Open settings dialog
            self._on_ai_show_settings()
            return False
        return True

    def _get_ai_context(self) -> str:
        """Get context information for AI queries"""
        context_parts = []

        if self.current_project:
            context_parts.append(f"Project: {self.current_project.name}")
            if self.current_project.client_name:
                context_parts.append(f"Client: {self.current_project.client_name}")

        if self.current_dataset:
            df = self.current_dataset.get_current_dataframe()
            if df is not None:
                context_parts.append(f"Dataset: {self.current_dataset.name}")
                context_parts.append(f"Rows: {len(df):,}")
                context_parts.append(f"Columns: {len(df.columns)}")
                context_parts.append(f"Columns: {', '.join(df.columns[:10])}")
                if len(df.columns) > 10:
                    context_parts.append(f"And {len(df.columns) - 10} more columns...")

        return "\n".join(context_parts) if context_parts else "No project or dataset loaded."

    def create_views(self):
        """Create all main views and add them to the stacked widget"""
        # Import view classes (lazy loading)
        from gui.views.dashboard_view import DashboardView
        from gui.views.data_view import DataView
        from gui.views.transform_view import TransformView
        from gui.views.sql_transform_view import SQLTransformView
        from gui.views.analyze_view import AnalyzeView
        from gui.views.visualizations_view import VisualizationsView
        from gui.views.query_view import QueryView
        from gui.views.ml_models_view import MLModelInventoryView
        from gui.views.projects_view import ProjectsView
        from gui.views.reports_view import ReportsView
        from gui.views.settings_view import SettingsView

        # Create and add views
        # Note: there is no separate "Sessions" concept — a Project *is* the
        # unit of work and its .caat file *is* the session (opening it
        # resumes where you left off). See claude_plan.md §7.
        self.views = {
            "dashboard": DashboardView(),
            "data": DataView(),
            "transform": TransformView(applied_steps_panel=self.applied_steps_panel),
            "sql": SQLTransformView(),
            "analyze": AnalyzeView(),
            "visualizations": VisualizationsView(),
            "query": QueryView(),
            "ml models": MLModelInventoryView(),
            "projects": ProjectsView(),
            "reports": ReportsView(),
            "settings": SettingsView(self),
        }

        # Connect dashboard signals
        dashboard_view = self.views["dashboard"]
        dashboard_view.uploadRequested.connect(self.on_upload_requested)
        dashboard_view.viewProjectsRequested.connect(lambda: self.on_navigation_requested("projects"))
        dashboard_view.datasetSelected.connect(self.on_dataset_selected)

        # Connect ProjectsView signal
        projects_view = self.views["projects"]
        if hasattr(projects_view, 'project_open_requested'):
            projects_view.project_open_requested.connect(self.on_project_open_requested)

        # Connect data view to other views that consume its data
        data_view = self.views["data"]
        transform_view = self.views["transform"]
        sql_view = self.views["sql"]
        viz_view = self.views["visualizations"]
        query_view = self.views["query"]
        reports_view = self.views["reports"]
        data_view.data_loaded.connect(transform_view.set_dataframe)
        # sql_view is NOT wired to data_loaded — unlike the other views, it
        # keeps a multi-table catalog (Model Query), and set_dataframe()
        # wipes every other registered table each time it's called. Every
        # dataset gets registered by name instead, via _on_dataset_added.
        data_view.data_loaded.connect(viz_view.set_dataframe)
        data_view.data_loaded.connect(query_view.set_dataframe)
        data_view.data_loaded.connect(reports_view.set_dataframe)
        data_view.dataset_added.connect(self._on_dataset_added)
        # Also refresh dashboard when dataset is added
        data_view.dataset_added.connect(lambda d: self.views["dashboard"].refresh() if "dashboard" in self.views else None)
        data_view.show_transform_requested.connect(self._on_show_transform_after_upload)
        transform_view.pipelineChanged.connect(self._on_pipeline_changed)
        transform_view.dataChanged.connect(self._on_transform_data_changed)
        sql_view.applyToPipelineRequested.connect(self._on_sql_apply_to_pipeline)

        # Set project on data_view
        data_view.set_project(self.current_project) if self.current_project else None

        # Connect authentication service to settings view for logout functionality
        settings_view = self.views["settings"]
        settings_view.set_auth_service(self.auth_service)
        settings_view.logout_requested.connect(self.handle_logout)

        for view in self.views.values():
            self.content_stack.addWidget(view)

        # Set a default view
        self.content_stack.setCurrentWidget(self.views["dashboard"])

        # Belt-and-suspenders: keep the Applied Steps panel's visibility in
        # sync with whatever page is actually showing, no matter which of
        # the many navigation code paths switched it (not just the ones that
        # go through on_navigation_requested).
        self.content_stack.currentChanged.connect(self._sync_applied_steps_panel_visibility)
        self._sync_applied_steps_panel_visibility(self.content_stack.currentIndex())

    def _sync_applied_steps_panel_visibility(self, index: int):
        """Show the Applied Steps panel only on data-workspace pages."""
        current_widget = self.content_stack.widget(index)
        view_name = next((name for name, w in self.views.items() if w is current_widget), None)
        self.applied_steps_panel.setVisible(view_name in self.PIPELINE_VIEWS)

    # Data-workspace pages where the Applied Steps panel stays pinned —
    # anywhere you're actively working with a dataset's pipeline. Hidden on
    # Dashboard/Projects/Settings/ML Models, which have no dataset context.
    PIPELINE_VIEWS = {"data", "transform", "sql", "visualizations", "reports", "query"}

    @Slot(str)
    def on_navigation_requested(self, view_name):
        """Handle navigation requests from the sidebar"""
        if view_name in self.views:
            self.content_stack.setCurrentWidget(self.views[view_name])
            self.sidebar.set_active_button(view_name)

            self.applied_steps_panel.setVisible(view_name in self.PIPELINE_VIEWS)

            display_name = view_name.replace("_", " ").title()
            self.statusBar().showMessage(f"Navigated to {display_name}")
        elif view_name == "upload":
            # Navigate to data view and trigger upload
            self.content_stack.setCurrentWidget(self.views["data"])
            self.sidebar.set_active_button("data")
            self.applied_steps_panel.setVisible(True)
            data_view = self.views.get("data")
            if data_view and hasattr(data_view, "show_import_dialog"):
                data_view.show_import_dialog()
        elif view_name == "export_review":
            self.export_for_review()
        else:
            self.statusBar().showMessage(f"Navigation: {view_name}")

    @Slot(str)
    def on_dataset_selected(self, dataset_id):
        """Handle dataset selection from sidebar or dashboard"""
        if not self.current_project:
            return

        dataset = self.current_project.datasets.get(dataset_id)
        if dataset:
            self.current_dataset = dataset
            if dataset.transformation_pipeline:
                dataset.transformation_pipeline.set_parameters(self.current_project.parameters)
            df = dataset.get_current_dataframe()
            if df is not None:
                # Navigate to transform view
                self.content_stack.setCurrentWidget(self.views["transform"])
                self.sidebar.set_active_button("transform")

                # Update all views with the dataset
                transform_view = self.views.get("transform")
                sql_view = self.views.get("sql")
                viz_view = self.views.get("visualizations")
                query_view = self.views.get("query")
                reports_view = self.views.get("reports")

                if transform_view:
                    # Pass the dataset's pipeline if it exists to preserve transformations
                    transform_view.set_dataframe(df, dataset.transformation_pipeline)
                if sql_view:
                    sql_view.refresh_dataset(dataset.name, df, dataset_id=dataset.id)
                if viz_view:
                    viz_view.set_dataframe(df)
                if query_view:
                    query_view.set_dataframe(df)
                if reports_view:
                    reports_view.set_dataframe(df)

                self.statusBar().showMessage(f"Selected dataset: {dataset.name}")

    @Slot(str)
    def on_dataset_rename_requested(self, dataset_id):
        """Handle dataset rename request"""
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        if not self.current_project:
            return

        dataset = self.current_project.datasets.get(dataset_id)
        if not dataset:
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename Dataset", "Enter new name:",
            text=dataset.name
        )

        if ok and new_name and new_name.strip():
            old_name = dataset.name
            dataset.name = new_name.strip()
            self.mark_project_dirty()

            sql_view = self.views.get("sql")
            if sql_view:
                sql_view.rename_dataset(dataset.id, old_name, dataset.name, dataset.get_current_dataframe())

            # Update sidebar
            self.sidebar.set_project(self.current_project)
            self.statusBar().showMessage(f"Dataset renamed to: {new_name}")

    @Slot(str)
    def on_dataset_duplicate_requested(self, dataset_id):
        """Handle dataset duplicate request"""
        if not self.current_project:
            return

        dataset = self.current_project.datasets.get(dataset_id)
        if not dataset:
            return

        # Create a copy of the dataset
        new_dataset = dataset.duplicate()
        # Ensure unique name
        base_name = f"{dataset.name} (copy)"
        unique_name = base_name
        counter = 1
        existing_names = {ds.name for ds in self.current_project.list_datasets()}
        while unique_name in existing_names:
            unique_name = f"{base_name} ({counter})"
            counter += 1
        new_dataset.name = unique_name
        self.current_project.add_dataset(new_dataset)
        self.mark_project_dirty()

        sql_view = self.views.get("sql")
        if sql_view:
            sql_view.refresh_dataset(new_dataset.name, new_dataset.get_current_dataframe(), dataset_id=new_dataset.id)

        self.sidebar.set_project(self.current_project)
        self.statusBar().showMessage(f"Dataset duplicated: {new_dataset.name}")

    @Slot(str)
    def on_dataset_delete_requested(self, dataset_id):
        """Handle dataset delete request"""
        from PySide6.QtWidgets import QMessageBox

        if not self.current_project:
            return

        dataset = self.current_project.datasets.get(dataset_id)
        if not dataset:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self, "Delete Dataset",
            f"Are you sure you want to delete '{dataset.name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            del self.current_project.datasets[dataset_id]
            self.mark_project_dirty()

            sql_view = self.views.get("sql")
            if sql_view:
                sql_view.remove_dataset(dataset_id, dataset.name)

            # Clear current dataset if it was the deleted one
            if self.current_dataset and self.current_dataset.id == dataset_id:
                self.current_dataset = None
                self._clear_data_view()

            self.sidebar.set_project(self.current_project)
            self.statusBar().showMessage(f"Dataset deleted: {dataset.name}")

    def _clear_data_view(self):
        """Clear the data view (table, steps, info) when no dataset is selected."""
        transform_view = self.views.get("transform")
        if transform_view:
            # Clear the table
            transform_view.populate_table(None)
            # Clear the steps list
            transform_view.steps_panel.set_pipeline(None)
            # Update the info label
            transform_view.info_label.setText("No data loaded. Select or import a dataset to begin.")
            transform_view.pipeline = None
            transform_view.original_dataframe = None

    @Slot(str)
    def on_dataset_split_sheet_requested(self, dataset_id):
        """Handle split sheet request - opens dialog to split dataset by column values"""
        if not self.current_project:
            return

        dataset = self.current_project.datasets.get(dataset_id)
        if not dataset:
            return

        # Get the current dataframe
        current_df = dataset.get_current_dataframe()
        if current_df is None or current_df.is_empty():
            QMessageBox.warning(self, "No Data", "The dataset is empty.")
            return

        # Open the split sheet dialog from table_dialogs
        from gui.dialogs.table_dialogs import SplitSheetDialog
        dialog = SplitSheetDialog(current_df, self)
        if dialog.exec():
            # Get the split datasets
            split_datasets = dialog.get_split_datasets()
            if not split_datasets:
                return

            # Create new datasets from the split
            for name, df in split_datasets:
                # Create a new Dataset object
                from core.project_manager import Dataset
                new_dataset = Dataset(
                    id=str(uuid.uuid4()),
                    name=name,
                    dataframe=df,
                    source_dataset_ids=[dataset.id],
                    source_operation="split"
                )

                # Set metadata
                new_dataset.metadata = dataset.metadata.copy()
                new_dataset.metadata["created_at"] = datetime.now().isoformat()
                new_dataset.metadata["version"] = "1.0"
                new_dataset.metadata["row_count"] = len(df)
                new_dataset.metadata["column_count"] = len(df.columns)
                new_dataset.metadata["columns"] = list(df.columns)

                # Add to project
                self.current_project.add_dataset(new_dataset)

                sql_view = self.views.get("sql")
                if sql_view:
                    sql_view.refresh_dataset(new_dataset.name, df, dataset_id=new_dataset.id)

            self.mark_project_dirty()

            # Update the sidebar
            self.sidebar.set_project(self.current_project)

            # Update status
            num_splits = len(split_datasets)
            self.statusBar().showMessage(f"Split dataset into {num_splits} new datasets")

    @Slot(str)
    def on_dataset_refresh_requested(self, dataset_id):
        """Re-read a dataset's original source file and replay all of its
        transformation steps against the fresh data — a "Refresh" for a
        dataset whose source file has changed since import."""
        if not self.current_project:
            return

        dataset = self.current_project.datasets.get(dataset_id)
        if not dataset:
            return

        if not dataset.can_refresh():
            QMessageBox.information(
                self, "Cannot Refresh",
                f"'{dataset.name}' has no known source file to refresh from "
                "(e.g. it was pasted, generated, or produced by a join/append/split)."
            )
            return

        try:
            refreshed_df = dataset.refresh_from_source()
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.warning(self, "Refresh Failed", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Refresh Failed", f"Failed to refresh dataset:\n{str(e)}")
            return

        # Keep this dataset's SQL table in sync regardless of whether it's
        # the active one — a stale registration would silently return old
        # data to a join/query that references it by name.
        sql_view = self.views.get("sql")
        if sql_view:
            sql_view.refresh_dataset(dataset.name, refreshed_df, dataset_id=dataset.id)

        # If this is the active dataset, also update the views showing it
        if self.current_dataset and self.current_dataset.id == dataset_id:
            transform_view = self.views.get("transform")
            if transform_view:
                transform_view.set_dataframe(refreshed_df, dataset.transformation_pipeline)

        self.mark_project_dirty()
        self.sidebar.set_project(self.current_project)
        self.statusBar().showMessage(
            f"Refreshed '{dataset.name}' from source and replayed {len(dataset.transformation_pipeline.get_steps()) if dataset.transformation_pipeline else 0} step(s)"
        )

    @Slot(str)
    def on_join_datasets_requested(self, source_dataset_id):
        """Handle join datasets request from sidebar"""
        if not self.current_project:
            return

        # Get source dataset
        source_dataset = None
        if source_dataset_id:
            source_dataset = self.current_project.datasets.get(source_dataset_id)

        if not source_dataset:
            QMessageBox.warning(self, "No Dataset", "Please select a dataset first.")
            return

        # Get current dataframe
        current_df = source_dataset.get_current_dataframe()
        if current_df is None or current_df.is_empty():
            QMessageBox.warning(self, "No Data", "The dataset is empty.")
            return

        # Get list of available datasets
        dataset_names = self.sidebar.get_dataset_names()

        if len(dataset_names) < 2:
            QMessageBox.warning(self, "Not Enough Datasets",
                              "You need at least 2 datasets to perform a join.")
            return

        # Open the join dialog
        from gui.dialogs.table_dialogs import JoinDatasetsDialog
        dialog = JoinDatasetsDialog(
            current_df,
            self,
            available_datasets=dataset_names,
            source_dataset_name=source_dataset.name
        )

        if dialog.exec():
            params = dialog.get_parameters()
            right_dataset_name = params["right_dataset"]

            # Find the right dataset
            right_dataset = None
            for ds in self.current_project.list_datasets():
                if ds.name == right_dataset_name:
                    right_dataset = ds
                    break

            if not right_dataset:
                QMessageBox.warning(self, "Dataset Not Found",
                                  f"Could not find dataset: {right_dataset_name}")
                return

            # Perform the join
            right_df = right_dataset.get_current_dataframe()
            join_type = params["join_type"]
            left_key = params["left_key"]
            right_key = params["right_key"]
            suffix = params["suffix"]

            try:
                from core.data_processor import DataProcessor
                processor = DataProcessor()

                joined_df = processor.join_datasets(
                    current_df, right_df, left_key, right_key, join_type, suffix
                )

                # Create new dataset for the joined result
                new_dataset = Dataset(
                    id=str(uuid.uuid4()),
                    name=f"{source_dataset.name} + {right_dataset.name}",
                    dataframe=joined_df,
                    source_dataset_ids=[source_dataset.id, right_dataset.id],
                    source_operation="join"
                )

                new_dataset.metadata = source_dataset.metadata.copy()
                new_dataset.metadata["created_at"] = datetime.now().isoformat()
                new_dataset.metadata["version"] = "1.0"
                new_dataset.metadata["row_count"] = len(joined_df)
                new_dataset.metadata["column_count"] = len(joined_df.columns)
                new_dataset.metadata["columns"] = list(joined_df.columns)

                # Add to project
                self.current_project.add_dataset(new_dataset)
                self.mark_project_dirty()

                sql_view = self.views.get("sql")
                if sql_view:
                    sql_view.refresh_dataset(new_dataset.name, joined_df, dataset_id=new_dataset.id)

                self.sidebar.set_project(self.current_project)
                self.statusBar().showMessage(f"Joined datasets: {new_dataset.name} ({len(joined_df):,} rows)")

            except Exception as e:
                QMessageBox.critical(self, "Join Failed", f"Failed to join datasets: {str(e)}")

    @Slot(str)
    def on_append_datasets_requested(self, source_dataset_id):
        """Handle append datasets request from sidebar"""
        if not self.current_project:
            return

        # Get source dataset
        source_dataset = None
        if source_dataset_id:
            source_dataset = self.current_project.datasets.get(source_dataset_id)

        if not source_dataset:
            QMessageBox.warning(self, "No Dataset", "Please select a dataset first.")
            return

        # Get current dataframe
        current_df = source_dataset.get_current_dataframe()
        if current_df is None or current_df.is_empty():
            QMessageBox.warning(self, "No Data", "The dataset is empty.")
            return

        # Get list of available datasets
        dataset_names = self.sidebar.get_dataset_names()

        if len(dataset_names) < 2:
            QMessageBox.warning(self, "Not Enough Datasets",
                              "You need at least 2 datasets to perform an append.")
            return

        # Build dataset columns map for schema comparison
        dataset_columns = {}
        for ds in self.current_project.list_datasets():
            df = ds.get_current_dataframe()
            if df is not None:
                dataset_columns[ds.name] = list(df.columns)

        # Open the append dialog
        from gui.dialogs.table_dialogs import AppendDatasetsDialog
        dialog = AppendDatasetsDialog(
            current_df,
            self,
            available_datasets=dataset_names,
            source_dataset_name=source_dataset.name,
            dataset_columns=dataset_columns
        )

        if dialog.exec():
            params = dialog.get_parameters()
            selected_datasets = params["source_datasets"]

            # Collect all dataframes
            dataframes = [current_df]
            appended_dataset_ids = [source_dataset.id]

            for ds_name in selected_datasets:
                for ds in self.current_project.list_datasets():
                    if ds.name == ds_name:
                        df = ds.get_current_dataframe()
                        if df is not None:
                            dataframes.append(df)
                            appended_dataset_ids.append(ds.id)
                        break

            if len(dataframes) < 2:
                QMessageBox.warning(self, "No Data", "No valid datasets to append.")
                return

            # Perform the append
            try:
                from core.data_processor import DataProcessor
                processor = DataProcessor()

                # Append with automatic column alignment (nulls for missing columns)
                appended_df = processor.append_datasets(dataframes, align_columns=True, fill_missing=True)

                # Create new dataset for the appended result
                new_dataset = Dataset(
                    id=str(uuid.uuid4()),
                    name=f"{source_dataset.name} (Appended)",
                    dataframe=appended_df,
                    source_dataset_ids=appended_dataset_ids,
                    source_operation="append"
                )

                new_dataset.metadata = source_dataset.metadata.copy()
                new_dataset.metadata["created_at"] = datetime.now().isoformat()
                new_dataset.metadata["version"] = "1.0"
                new_dataset.metadata["row_count"] = len(appended_df)
                new_dataset.metadata["column_count"] = len(appended_df.columns)
                new_dataset.metadata["columns"] = list(appended_df.columns)

                # Add to project
                self.current_project.add_dataset(new_dataset)
                self.mark_project_dirty()

                sql_view = self.views.get("sql")
                if sql_view:
                    sql_view.refresh_dataset(new_dataset.name, appended_df, dataset_id=new_dataset.id)

                self.sidebar.set_project(self.current_project)
                self.statusBar().showMessage(f"Appended datasets: {new_dataset.name} ({len(appended_df):,} rows)")

            except Exception as e:
                QMessageBox.critical(self, "Append Failed", f"Failed to append datasets: {str(e)}")

    @Slot(object)
    def _on_pipeline_changed(self, pipeline):
        """Handle pipeline changes - save to current dataset"""
        if self.current_dataset and pipeline:
            self.current_dataset.set_pipeline(pipeline)
            self.mark_project_dirty()
            self.statusBar().showMessage(f"Transformations saved to dataset: {self.current_dataset.name}")

    @Slot(object)
    def _on_transform_data_changed(self, df):
        """Keep SQL/Visualizations/Reports/Query in sync whenever the active
        dataset's data changes from the Transform page (apply/undo/toggle/
        clear a step) — otherwise those pages silently show stale data once
        the Applied Steps panel became reachable from every page, not just
        Transform."""
        viz_view = self.views.get("visualizations")
        query_view = self.views.get("query")
        reports_view = self.views.get("reports")
        sql_view = self.views.get("sql")

        if viz_view:
            viz_view.set_dataframe(df)
        if query_view:
            query_view.set_dataframe(df)
        if reports_view:
            reports_view.set_dataframe(df)
        if sql_view and self.current_dataset:
            # Re-register only this dataset's table — preserves any other
            # datasets checked for a cross-dataset Model Query.
            sql_view.refresh_dataset(self.current_dataset.name, df)

    @Slot(str, str)
    def _on_sql_apply_to_pipeline(self, query: str, table_name: str):
        """Record a SQL query from the SQL view as a step on the active
        dataset's pipeline, so it shows up in Applied Steps and replays on
        refresh like any other transformation."""
        transform_view = self.views.get("transform")
        if not transform_view or not transform_view.pipeline:
            QMessageBox.warning(self, "No Data", "Please load a dataset first.")
            return

        try:
            transform_view.apply_transformation('sql_query', {'query': query, 'table_name': table_name})
            self.statusBar().showMessage("SQL query applied to dataset pipeline")
        except Exception as e:
            QMessageBox.critical(self, "Apply Failed", f"Failed to apply SQL query to pipeline:\n{str(e)}")

    @Slot()
    def on_upload_requested(self):
        """Handle upload request from sidebar"""
        self.content_stack.setCurrentWidget(self.views["data"])
        self.sidebar.set_active_button("data")
        data_view = self.views.get("data")
        if data_view and hasattr(data_view, "show_import_dialog"):
            data_view.show_import_dialog()

    @Slot()
    def on_paste_requested(self):
        """Handle "paste dataset from clipboard" request from the sidebar or Ctrl+Shift+V"""
        self.content_stack.setCurrentWidget(self.views["data"])
        self.sidebar.set_active_button("data")
        data_view = self.views.get("data")
        if data_view and hasattr(data_view, "paste_from_clipboard"):
            data_view.paste_from_clipboard()

    def show_command_palette(self):
        """Open the Ctrl+K command palette — searches every transformation,
        report, and navigation action in the app by name."""
        from gui.components.command_palette import CommandPalette, build_ribbon_commands

        commands = build_ribbon_commands(self.handle_ribbon_action)

        for view_key in self.views.keys():
            commands.append((
                f"Go to {view_key.title()}", "Navigate",
                lambda v=view_key: self.on_navigation_requested(v)
            ))

        commands.extend([
            ("New Project", "File", self.new_project),
            ("Open Project", "File", self.open_project),
            ("Save Project", "File", self.save_project),
            ("Save Project As...", "File", self.save_project_as),
            ("Export for Review", "File", self.export_for_review),
        ])

        palette = CommandPalette(commands, parent=self)
        palette.move(
            self.geometry().center().x() - palette.width() // 2,
            self.geometry().top() + 120
        )
        palette.exec()

    def _on_show_transform_after_upload(self):
        """Navigate to transform view after dataset upload"""
        self.content_stack.setCurrentWidget(self.views["transform"])
        self.sidebar.set_active_button("transform")
        self.statusBar().showMessage("Data uploaded successfully. Use the Applied Steps panel to start transforming your data.")

    def _resolve_active_dataset(self, project):
        """Which dataset should become active when a project is opened:
        whichever one was active when it was last saved (project.
        last_active_dataset_id, set by caat_format.load_caat), falling back
        to the first dataset if that id is missing or no longer valid."""
        datasets = project.list_datasets()
        if not datasets:
            return None
        active_id = getattr(project, "last_active_dataset_id", None)
        if active_id:
            match = project.datasets.get(active_id)
            if match:
                return match
        return datasets[0]

    def on_project_open_requested(self, payload):
        """Handle project open request from ProjectsView. `payload` is either
        None (create new) or a (project, file_path) tuple — the path is
        needed so subsequent Save/Ctrl+S and session-resume know where this
        project lives on disk."""
        if payload is None:
            self.new_project()
            return

        project, file_path = payload
        if project is None:
            self.new_project()
            return

        # Load the existing project
        self.current_project = project
        self.current_project_path = file_path
        self.mark_project_clean()
        self.set_project(self.current_project)
        self.refresh_dashboard_stats()
        self.statusBar().showMessage(f"Opened project: {project.name}")

        if file_path:
            from core.recent_projects import add_recent
            from core.session_state import set_active_project
            add_recent(file_path, project.name)
            set_active_project(file_path)

        # Resume on whichever dataset was active when this was last saved
        self.current_dataset = self._resolve_active_dataset(project)
        if self.current_dataset:
            self.sidebar.select_dataset(self.current_dataset.id)
            if self.current_dataset.transformation_pipeline:
                self.current_dataset.transformation_pipeline.set_parameters(project.parameters)
            # Update the transform view with the dataset - include pipeline
            # to preserve steps. The SQL view already has every dataset
            # registered by name from set_project() above — re-registering
            # just this one here would wipe out all the others.
            current_df = self.current_dataset.get_current_dataframe()
            if current_df is not None:
                self.views["transform"].set_dataframe(current_df, self.current_dataset.transformation_pipeline)

        # Navigate to dashboard
        self.content_stack.setCurrentWidget(self.views["dashboard"])

    def _on_dataset_added(self, dataset):
        """Handle new dataset being added - update sidebar, make it the
        active dataset, and register it in the SQL view under its own name
        so it's immediately queryable (and joinable with other datasets)
        without disturbing anything already registered there."""
        if hasattr(self, 'sidebar'):
            self.sidebar.add_dataset(dataset)
        self.current_dataset = dataset
        sql_view = self.views.get("sql")
        if sql_view:
            sql_view.refresh_dataset(dataset.name, dataset.get_current_dataframe(), dataset_id=dataset.id)
        self.mark_project_dirty()
        self.statusBar().showMessage(f"Dataset '{dataset.name}' added to project")

    def create_statusbar(self):
        """Create status bar"""
        self.statusBar().setObjectName("StatusBar")
        self.statusBar().showMessage("Ready")

    def setup_autosave(self):
        """Periodically save a recovery copy of the current project —
        separate from the user's own Save, and never overwrites their
        actual .caat file."""
        from PySide6.QtCore import QTimer
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(2 * 60 * 1000)  # 2 minutes
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start()

    def _autosave(self):
        """Write a recovery snapshot to '<project>.caat.autosave' if a
        project is open and has a known save location. Silent on failure —
        autosave should never interrupt the user with a dialog."""
        if not self.current_project or not self.current_project_path:
            return
        try:
            from core.caat_format import save_caat
            autosave_path = self.current_project_path + ".autosave"
            active_id = self.current_dataset.id if self.current_dataset else None
            save_caat(self.current_project, autosave_path, author=self._current_username(),
                      active_dataset_id=active_id)
            self.statusBar().showMessage("Autosaved recovery copy", 3000)
        except Exception as e:
            print(f"Warning: autosave failed: {e}")

    def _current_username(self) -> Optional[str]:
        """Best-effort current user name for attribution in saved files."""
        try:
            if self.auth_service:
                user = self.auth_service.get_current_user()
                if user:
                    return user.username
        except Exception:
            pass
        return None

    # ========================================================================
    # Ribbon Actions
    # ========================================================================

    def handle_ribbon_action(self, action_name: str):
        """Handle ribbon button actions.

        Args:
            action_name (str): Name of the action to execute
        """
        action_handlers = {
            # File operations
            "import_data": self.import_data,
            "export_data": self.export_data,
            "export_review": self.export_for_review,

            # Sort actions
            "sort_asc": self._on_sort_asc,
            "sort_desc": self._on_sort_desc,

            # Remove actions
            "remove_rows": self._on_remove_rows,
            "remove_cols": self._on_remove_cols,

            # Reduce rows
            "keep_top": self._on_keep_top,
            "keep_bottom": self._on_keep_bottom,

            # Text transformations
            "text_upper": lambda: self._on_transform("text_uppercase"),
            "text_lower": lambda: self._on_transform("text_lowercase"),
            "text_title": lambda: self._on_transform("text_titlecase"),
            "text_length": lambda: self._on_transform("text_length"),
            "text_extract": lambda: self._on_transform("text_extract_numbers"),
            "text_trim": lambda: self._on_transform("text_trim"),

            # Split operations
            "split_comma": lambda: self._on_transform("split_comma"),
            "split_space": lambda: self._on_transform("split_space"),
            "split_custom": lambda: self._on_transform("split_custom"),

            # Date/Time operations
            "extract_year": lambda: self._on_transform("datetime_year"),
            "extract_month": lambda: self._on_transform("datetime_month"),
            "extract_weekday": lambda: self._on_transform("datetime_weekday"),
            "extract_hour": lambda: self._on_transform("datetime_hour"),
            "date_age": lambda: self._on_transform("datetime_age_days"),
            "date_quarter": lambda: self._on_transform("datetime_quarter"),

            # Pivot operations
            "pivot": self._on_pivot,
            "unpivot": self._on_unpivot,

            # Column operations
            "rename_col": self._on_rename_column,
            "change_dtype": self._on_change_dtype,
            "reorder_cols": self._on_reorder_cols,
            "select_cols": self._on_select_cols,
            "filter": self._on_filter,

            # Add column operations
            "custom_col": self._on_custom_column,
            "index_col": self._on_index_column,
            "stat_quick": self._on_stat_quick,

            # Math operations
            "math_round": lambda: self._on_transform("math_round"),
            "math_abs": lambda: self._on_transform("math_abs"),
            "math_sqrt": lambda: self._on_transform("math_sqrt"),

            # AI operations
            "ai_explain": lambda: self._on_transform("ai_explain"),
            "ai_sentiment": lambda: self._on_transform("ai_sentiment"),
            "ai_extract": lambda: self._on_transform("ai_extract"),
            "ai_pattern": lambda: self._on_transform("ai_pattern_learn"),
            "ai_classify": lambda: self._on_transform("ai_classify"),
            "ai_summarize": lambda: self._on_transform("ai_summarize"),
            "ai_enrich": lambda: self._on_transform("ai_enrich"),

            # ML operations
            "ml_anomaly_iforest": lambda: self._on_transform("ml_anomaly_iforest"),
            "ml_anomaly_zscore": lambda: self._on_transform("ml_anomaly_zscore"),
            "ml_anomaly_iqr": lambda: self._on_transform("ml_anomaly_iqr"),
            "ml_kmeans": lambda: self._on_transform("ml_cluster"),
            "ml_forecast": lambda: self._on_transform("ml_forecast"),
            "ml_lof": lambda: self._on_transform("ml_anomaly_lof"),
            "ml_train": self._on_ml_train,
            "ml_classify": lambda: self._on_transform("ml_classify"),
            "ml_risk_score": lambda: self._on_transform("ml_risk_score"),
            "ml_predict": lambda: self._on_transform("ml_predict"),

            # ML operations reachable from the ML menu — implemented in
            # data_processor.py and registered in operation_registry.py
            # already; only the menu-to-dispatch wiring was missing.
            "ml_linear_regression": lambda: self._on_transform("ml_linear_regression"),
            "ml_glm": lambda: self._on_transform("ml_glm"),
            "ml_decision_tree": lambda: self._on_transform("ml_decision_tree"),
            "ml_random_forest": lambda: self._on_transform("ml_random_forest"),
            "ml_gradient_boosting": lambda: self._on_transform("ml_gradient_boosting"),
            "ml_xgboost": lambda: self._on_transform("ml_xgboost"),
            "ml_lightgbm": lambda: self._on_transform("ml_lightgbm"),
            "ml_cluster": lambda: self._on_transform("ml_cluster"),
            "ml_dbscan": lambda: self._on_transform("ml_dbscan"),
            "ml_gmm": lambda: self._on_transform("ml_gmm"),
            "ml_arima": lambda: self._on_transform("ml_arima"),
            "ml_ets": lambda: self._on_transform("ml_ets"),

            # Audit operations
            "stat_zscore": lambda: self._on_transform("stat_zscore"),
            "stat_pct_rank": lambda: self._on_transform("stat_percent_rank"),
            "stat_rank": lambda: self._on_transform("stat_rank"),
            "benford_law": lambda: self._on_transform("audit_benford_law"),
            "audit_flag": self._on_audit_flag,
            "audit_duplicates": lambda: self._on_transform("audit_duplicate_detection"),
            "audit_gaps": lambda: self._on_transform("audit_gap_analysis"),
            "audit_outliers": lambda: self._on_transform("audit_outlier_detection"),
            "audit_round_numbers": lambda: self._on_transform("audit_round_numbers"),

            # Statistics operations
            "stat_group_stats": lambda: self._on_transform("stat_add_group_stats"),
            "stat_summary": lambda: self._on_statistics("stat_summary"),
            "stat_central": lambda: self._on_statistics("stat_central"),
            "stat_variance": lambda: self._on_statistics("stat_variance"),
            "stat_ttest": lambda: self._on_statistics("stat_ttest"),
            "stat_anova": lambda: self._on_statistics("stat_anova"),
            "stat_chisquare": lambda: self._on_statistics("stat_chisquare"),
            "stat_pearson": lambda: self._on_statistics("stat_pearson"),
            "stat_spearman": lambda: self._on_statistics("stat_spearman"),
            "stat_heatmap": lambda: self._on_statistics("stat_heatmap"),
            "stat_normal": lambda: self._on_statistics("stat_normal"),
            "stat_binomial": lambda: self._on_statistics("stat_binomial"),
            "stat_poisson": lambda: self._on_statistics("stat_poisson"),

            # View operations
            "query_settings": self._on_query_settings,
            "dependencies": self._on_dependencies,
            "col_quality": self._on_col_quality,
            "col_dist": self._on_col_dist,
            "col_profile": self._on_col_profile,
            "formula_bar": self._on_formula_bar,

            # Report operations
            "report_audit": self._on_report_audit,
            "report_llm": self._on_ai_compliance_check,
            "report_profile": self._on_col_profile,
            "report_quality": self._on_col_quality,
            "report_transformation": self._on_report_transformation_log,
            "report_word": lambda: self._on_report_export("word"),
            "report_excel": lambda: self._on_report_export("excel"),
            "report_pdf": lambda: self._on_report_export("pdf"),
        }

        if action_name in action_handlers:
            handler = action_handlers[action_name]
            if callable(handler):
                handler()
            self.statusBar().showMessage(f"Executed: {action_name.replace('_', ' ').title()}")
        else:
            self.statusBar().showMessage(f"Action '{action_name}' not yet implemented")

    def _on_sort_asc(self):
        """Open the sort dialog defaulting to ascending order."""
        self._on_transform('sort_column', extra_params={'ascending': True})

    def _on_sort_desc(self):
        """Open the sort dialog defaulting to descending order."""
        self._on_transform('sort_column', extra_params={'ascending': False})

    def _on_remove_rows(self):
        """Open the Remove Rows dialog (remove specific rows by index)."""
        self._on_transform('remove_rows')

    def _on_remove_cols(self):
        """Open Choose Columns, pre-set to Remove mode, to drop one or more columns."""
        if not self._check_data_loaded():
            return
        from gui.dialogs.column_dialogs import ChooseColumnsDialog
        dialog = ChooseColumnsDialog(self.current_dataset.get_current_dataframe(), self)
        dialog.remove_radio.setChecked(True)
        if dialog.exec():
            params = dialog.get_parameters()
            if params is not None:
                transform_view = self.views.get("transform")
                transform_view.apply_transformation('choose_columns', params)

    def _on_keep_top(self):
        """Open Select N Rows, defaulting to keeping the first N rows."""
        self._on_transform('select_n_rows', extra_params={'selection_type': 'first'})

    def _on_keep_bottom(self):
        """Open Select N Rows, defaulting to keeping the last N rows."""
        self._on_transform('select_n_rows', extra_params={'selection_type': 'last'})

    def _on_transform(self, operation_id: str, extra_params: dict = None):
        """Apply transformation by opening a dialog or using the selected column."""
        if not self._check_data_loaded():
            return

        # Navigate to transform view
        self.content_stack.setCurrentWidget(self.views["transform"])

        # Get the transform view
        transform_view = self.views.get("transform")
        if not transform_view or not transform_view.pipeline:
            self.statusBar().showMessage("No data loaded. Please load a dataset first.")
            return

        # Get the selected column from the transform view table
        table = transform_view.data_table
        selected_columns = []

        # Try to get selected column from horizontal header
        header = table.horizontalHeader()
        current_col = header.currentIndex()
        if current_col.isValid():
            column_name = table.horizontalHeaderItem(current_col.column()).text()
            selected_columns.append(column_name)

        # If no column selected, use the first column
        if not selected_columns and table.columnCount() > 0:
            column_name = table.horizontalHeaderItem(0).text()
            selected_columns.append(column_name)

        if not selected_columns:
            self.statusBar().showMessage("No columns available. Please load data first.")
            return

        column_name = selected_columns[0]

        # Create the transformation dialog - use transformed dataframe so new columns appear
        from gui.dialogs.transformation_dialog_factory import TransformationDialogFactory

        # Get the current transformed dataframe from the pipeline
        current_df = transform_view.pipeline.apply() if transform_view.pipeline else transform_view.original_dataframe

        initial_params = {'column': column_name}
        if extra_params:
            initial_params.update(extra_params)

        dialog = TransformationDialogFactory.create_dialog(
            operation_id=operation_id,
            dataframe=current_df,
            parent=self,
            initial_params=initial_params
        )

        if dialog and dialog.exec():
            params = dialog.get_parameters()
            if params is not None:
                transform_view.apply_transformation(operation_id, params)
                if operation_id in self.AUDIT_OPERATION_IDS:
                    self._record_audit_run()
                self.statusBar().showMessage(f"Applied {operation_id} transformation")
        else:
            self.statusBar().showMessage("Transformation cancelled")

    def _record_audit_run(self):
        """Mark that an audit check was just run — drives the dashboard's
        Last Audit tile. Stored in project.metadata (not a new top-level
        Project field) so it round-trips through the existing .caat
        serialization for free."""
        if not self.current_project:
            return
        from datetime import datetime
        self.current_project.metadata["last_audit_at"] = datetime.now().isoformat()
        self.mark_project_dirty()
        dashboard = self.views.get("dashboard")
        if dashboard and hasattr(dashboard, "refresh"):
            dashboard.refresh()

    def _on_pivot(self):
        """Open pivot table dialog and apply the result to the pipeline."""
        self._on_transform('pivot_table')

    def _on_unpivot(self):
        """Open unpivot dialog and apply the result to the pipeline."""
        self._on_transform('unpivot_table')

    def _on_rename_column(self):
        """Open the Rename Columns dialog and apply the result."""
        self._on_transform('rename_columns')

    def _on_change_dtype(self):
        """Open the Change Data Type dialog and apply the result."""
        self._on_transform('change_dtype')

    def _on_custom_column(self):
        """Open the Custom Column (formula/expression) dialog and apply the result."""
        self._on_transform('custom_column_from_math')

    def _on_index_column(self):
        """Add a sequential index column."""
        self._on_transform("add_index_column")

    def _on_reorder_cols(self):
        """Open Choose Columns, pre-set to Reorder mode, to change column order."""
        if not self._check_data_loaded():
            return
        from gui.dialogs.column_dialogs import ChooseColumnsDialog
        dialog = ChooseColumnsDialog(self.current_dataset.get_current_dataframe(), self)
        dialog.reorder_radio.setChecked(True)
        if dialog.exec():
            params = dialog.get_parameters()
            if params is not None:
                transform_view = self.views.get("transform")
                transform_view.apply_transformation('choose_columns', params)

    def _on_select_cols(self):
        """Open Choose Columns (defaults to Keep mode) to pick which columns to keep."""
        if not self._check_data_loaded():
            return
        from gui.dialogs.column_dialogs import ChooseColumnsDialog
        dialog = ChooseColumnsDialog(self.current_dataset.get_current_dataframe(), self)
        if dialog.exec():
            params = dialog.get_parameters()
            if params is not None:
                transform_view = self.views.get("transform")
                transform_view.apply_transformation('choose_columns', params)

    def _on_filter(self):
        """Open the Advanced Filter dialog (multi-condition, AND/OR)."""
        self._on_transform('filter_advanced')

    def _on_stat_quick(self):
        """Quick statistics."""
        self._on_transform("stat_quick_stats")

    def _on_ml_train(self):
        """Open ML training dialog."""
        from gui.dialogs.ml_training_dialog import MLTrainingDialog
        if not self._check_data_loaded():
            return
        dialog = MLTrainingDialog(self.current_dataset.get_current_dataframe(), self)
        dialog.exec()

    def _on_statistics(self, stat_type: str):
        """Open the Statistics dialog for a specific analysis (summary,
        hypothesis test, correlation, or distribution check). These compute
        and display a result — they don't modify the dataset, so they don't
        go through the transformation pipeline like a normal operation."""
        if not self._check_data_loaded():
            return
        from gui.dialogs.statistics_dialog import StatisticsDialog
        df = self.current_dataset.get_current_dataframe()
        dialog = StatisticsDialog(stat_type, df, self)
        dialog.exec()

    def _on_report_audit(self):
        """Open the report builder for a configurable audit report."""
        if not self._check_data_loaded():
            return
        self.content_stack.setCurrentWidget(self.views["reports"])
        reports_view = self.views.get("reports")
        if reports_view and hasattr(reports_view, "build_custom_report"):
            reports_view.build_custom_report()

    def _on_report_transformation_log(self):
        """Show the active dataset's applied steps as a report."""
        if not self._check_data_loaded():
            return
        pipeline = self.current_dataset.transformation_pipeline
        steps = pipeline.get_steps() if pipeline else []
        if not steps:
            QMessageBox.information(self, "Transformation Log", "No transformation steps have been applied to this dataset yet.")
            return

        from core.operation_registry import OPERATION_REGISTRY
        lines = [f"Transformation Log — {self.current_dataset.name}", f"{len(steps)} step(s)", ""]
        for i, step in enumerate(steps, start=1):
            op_name = OPERATION_REGISTRY.get(step.operation_id, {}).get('display_name', step.operation_id)
            status = "enabled" if step.enabled else "disabled"
            timing = f", {step.execution_time * 1000:.0f} ms" if step.execution_time is not None else ""
            params_str = ", ".join(f"{k}={v}" for k, v in step.params.items())
            lines.append(f"{i}. {op_name} ({status}{timing})")
            lines.append(f"   {step.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            if params_str:
                lines.append(f"   Parameters: {params_str}")
            lines.append("")

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        dialog = QDialog(self)
        dialog.setWindowTitle("Transformation Log")
        dialog.setMinimumSize(560, 480)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    def _on_report_export(self, fmt: str):
        """Quick-export the active dataset (+ summary stats) as Word/Excel/PDF."""
        if not self._check_data_loaded():
            return

        from PySide6.QtWidgets import QFileDialog
        ext_map = {"word": ("docx", "Word Document (*.docx)"),
                   "excel": ("xlsx", "Excel Workbook (*.xlsx)"),
                   "pdf": ("pdf", "PDF Document (*.pdf)")}
        ext, file_filter = ext_map[fmt]
        default_name = f"{self.current_dataset.name.replace(' ', '_')}_report.{ext}"
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Report", str(Path.home() / default_name), file_filter)
        if not file_path:
            return
        if not file_path.endswith(f".{ext}"):
            file_path += f".{ext}"

        try:
            from services import quick_export_service
            df = self.current_dataset.get_current_dataframe()
            exporter = {"word": quick_export_service.export_word,
                        "excel": quick_export_service.export_excel,
                        "pdf": quick_export_service.export_pdf}[fmt]
            exporter(df, self.current_dataset.name, file_path)
            self.statusBar().showMessage(f"Report exported to: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export report:\n{str(e)}")

    def _on_audit_flag(self):
        """Open the Audit Flag dialog to mark rows matching a condition."""
        self._on_transform('audit_flag_rows')

    def _on_query_settings(self):
        """Manage the project's reusable query parameters (materiality
        threshold, period dates, etc.) that SQL steps can reference."""
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "Please create or open a project first.")
            return

        from gui.dialogs.parameters_dialog import ParametersDialog
        dialog = ParametersDialog(self.current_project.parameters, self)
        if dialog.exec():
            self.current_project.parameters = dialog.get_parameters()
            self.mark_project_dirty()
            self._sync_pipeline_parameters()
            self.statusBar().showMessage(
                f"Saved {len(self.current_project.parameters)} query parameter(s)"
            )

    def _sync_pipeline_parameters(self):
        """Push the current project's parameters into the active dataset's
        pipeline so SQL steps referencing {{name}} pick up the latest value."""
        if not self.current_dataset or not self.current_dataset.transformation_pipeline:
            return
        self.current_dataset.transformation_pipeline.set_parameters(self.current_project.parameters)
        transform_view = self.views.get("transform")
        if transform_view and transform_view.pipeline is self.current_dataset.transformation_pipeline:
            transform_view.populate_table(transform_view.pipeline.apply())
            transform_view.update_info()

    def _on_dependencies(self):
        """Show the active dataset's lineage: where its data came from
        (file/sheet import, or join/append/split ancestry), and which
        other datasets in the project were derived from it."""
        if not self._check_data_loaded():
            return

        project = self.current_project
        dataset = self.current_dataset
        lines = [f"Dataset: {dataset.name}", ""]

        lines.append("SOURCE")
        if dataset.source_dataset_ids:
            op = (dataset.source_operation or "derived").title()
            source_names = []
            for sid in dataset.source_dataset_ids:
                src = project.datasets.get(sid) if project else None
                source_names.append(src.name if src else f"<deleted dataset {sid[:8]}>")
            lines.append(f"  {op} of: {', '.join(source_names)}")
        elif dataset.source_file_path:
            sheet = f" (sheet: {dataset.source_sheet_name})" if dataset.source_sheet_name else ""
            lines.append(f"  Imported from: {dataset.source_file_path}{sheet}")
        else:
            lines.append("  Pasted or generated directly (no external source)")

        lines.append("")
        lines.append("DERIVED DATASETS (created from this one)")
        derived = [d for d in project.list_datasets() if dataset.id in (d.source_dataset_ids or [])] if project else []
        if derived:
            for d in derived:
                op = (d.source_operation or "derived").title()
                lines.append(f"  {d.name} ({op})")
        else:
            lines.append("  None")

        pipeline = dataset.transformation_pipeline
        steps = pipeline.get_steps() if pipeline else []
        lines.append("")
        lines.append(f"APPLIED STEPS ({len(steps)})")
        if steps:
            from core.operation_registry import OPERATION_REGISTRY
            for i, step in enumerate(steps, start=1):
                op_name = OPERATION_REGISTRY.get(step.operation_id, {}).get('display_name', step.operation_id)
                lines.append(f"  {i}. {op_name}")
        else:
            lines.append("  None")

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Dependencies — {dataset.name}")
        dialog.setMinimumSize(520, 460)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

    def _on_col_quality(self):
        """Show column quality (valid/empty bars for every column)."""
        self._show_column_profile_dialog(initial_tab="quality")

    def _on_col_dist(self):
        """Show column distribution chart for the selected column."""
        self._show_column_profile_dialog(initial_tab="profile")

    def _on_col_profile(self):
        """Show detailed column profile for the selected column."""
        self._show_column_profile_dialog(initial_tab="profile")

    def _show_column_profile_dialog(self, initial_tab: str = "quality"):
        """Open the Column Quality / Distribution / Profile dialog."""
        if not self._check_data_loaded():
            return

        transform_view = self.views.get("transform")
        if not transform_view or not transform_view.pipeline:
            QMessageBox.information(self, "No Data", "Load a dataset first.")
            return

        current_df = transform_view.pipeline.apply() if transform_view.pipeline else transform_view.original_dataframe
        if current_df is None:
            QMessageBox.information(self, "No Data", "Load a dataset first.")
            return

        selected_column = None
        table = transform_view.data_table
        header = table.horizontalHeader()
        current_col = header.currentIndex()
        if current_col.isValid() and table.horizontalHeaderItem(current_col.column()):
            selected_column = table.horizontalHeaderItem(current_col.column()).text()

        from gui.dialogs.column_profile_dialog import ColumnProfileDialog
        dialog = ColumnProfileDialog(current_df, self, selected_column=selected_column, initial_tab=initial_tab)
        dialog.exec()

    def _on_formula_bar(self):
        """Toggle the formula bar in the Transform view."""
        self.content_stack.setCurrentWidget(self.views["transform"])
        transform_view = self.views.get("transform")
        if transform_view:
            transform_view.toggle_formula_bar()

    def _check_data_loaded(self) -> bool:
        """Check if data is loaded."""
        if not self.current_dataset:
            QMessageBox.warning(self, "No Data", "Please load data first.")
            return False

        df = self.current_dataset.get_current_dataframe()
        if df is None:
            QMessageBox.warning(self, "No Data", "Please load data first.")
            return False

        return True

    # ========================================================================
    # Actions
    # ========================================================================

    def new_project(self):
        """Create a new project using the proper dialog"""
        dialog = NewProjectDialog(self)
        if dialog.exec():
            project_data = dialog.get_project_data()
            self.current_project = Project(
                name=project_data['name'],
                description=project_data.get('description'),
                client_name=project_data.get('client_name'),
                phase=project_data.get('phase', 'planning'),
                engagement_type=project_data.get('engagement_type', 'financial audit'),
                risk_score=project_data.get('risk_score', 5),
                objectives=project_data.get('objectives')
            )
            self.set_project(self.current_project)
            self.refresh_dashboard_stats()
            self.statusBar().showMessage(f"Created project: {project_data['name']}")

            # Save the project to a default location
            self._save_new_project(self.current_project)

            # Close backstage view if it's open and navigate to dashboard
            self.backstage_view.setVisible(False)
            self.content_stack.setCurrentWidget(self.views["dashboard"])

    def _save_new_project(self, project):
        """Save a newly created project as a native .caat file to the
        default projects directory, so it has a real home from creation —
        including its (currently empty) datasets, not just name/metadata."""
        from core.caat_format import save_caat
        from pathlib import Path

        projects_dir = Path.home() / "Documents" / "CaatMaster" / "Projects"
        projects_dir.mkdir(parents=True, exist_ok=True)

        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in project.name)
        project_file = projects_dir / f"{safe_name}.caat"

        try:
            saved_path = save_caat(project, str(project_file), author=self._current_username())
            self.current_project_path = saved_path
            self.mark_project_clean()
            from core.recent_projects import add_recent
            from core.session_state import set_active_project
            add_recent(saved_path, project.name)
            set_active_project(saved_path)
            self.statusBar().showMessage(f"Created and saved project: {project.name} to {saved_path}")
        except Exception as e:
            QMessageBox.warning(self, "Save Warning", f"Project created, but the initial save failed:\n{str(e)}")


    def open_project(self):
        """Open an existing project"""
        # Check if Backstage View has pending project path
        if hasattr(self.backstage_view, '_pending_project_path'):
            project_path = self.backstage_view._pending_project_path
            delattr(self.backstage_view, '_pending_project_path')

            # Load project from the specified path
            from core.project_manager import ProjectExporter
            from core.caat_format import load_caat, is_caat_file
            try:
                if is_caat_file(project_path):
                    project = load_caat(project_path)
                    self.current_project_path = project_path
                    from core.recent_projects import add_recent
                    from core.session_state import set_active_project
                    add_recent(project_path, project.name)
                    set_active_project(project_path)
                else:
                    project = ProjectExporter.import_project(project_path)
                    self.current_project_path = None
                if project:
                    self.current_project = project
                    self.mark_project_clean()
                    self.set_project(self.current_project)
                    self.refresh_dashboard_stats()
                    self.statusBar().showMessage(f"Opened project: {project.name}")

                    # Resume on whichever dataset was active when this was last saved
                    self.current_dataset = self._resolve_active_dataset(project)
                    if self.current_dataset:
                        self.sidebar.select_dataset(self.current_dataset.id)
                        if self.current_dataset.transformation_pipeline:
                            self.current_dataset.transformation_pipeline.set_parameters(project.parameters)
                        # Update the transform view with the dataset - the
                        # SQL view already has every dataset registered by
                        # name from set_project() above.
                        current_df = self.current_dataset.get_current_dataframe()
                        if current_df is not None:
                            self.views["transform"].set_dataframe(current_df, self.current_dataset.transformation_pipeline)

                    # Close backstage view and navigate to dashboard
                    self.backstage_view.setVisible(False)
                    self.content_stack.setCurrentWidget(self.views["dashboard"])
                    return
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open project:\n{str(e)}")
                return

        # Fall back to dialog
        dialog = OpenProjectDialog(self)
        if dialog.exec():
            project = dialog.get_selected_project()
            if project:
                self.current_project = project
                self.mark_project_clean()
                opened_path = dialog.file_path_edit.text().strip()
                from core.caat_format import is_caat_file
                if opened_path and is_caat_file(opened_path):
                    self.current_project_path = opened_path
                    from core.recent_projects import add_recent
                    from core.session_state import set_active_project
                    add_recent(opened_path, project.name)
                    set_active_project(opened_path)
                else:
                    self.current_project_path = None
                self.set_project(self.current_project)
                self.refresh_dashboard_stats()
                self.statusBar().showMessage(f"Opened project: {project.name}")

                # Resume on whichever dataset was active when this was last saved
                self.current_dataset = self._resolve_active_dataset(project)
                if self.current_dataset:
                    self.sidebar.select_dataset(self.current_dataset.id)
                    if self.current_dataset.transformation_pipeline:
                        self.current_dataset.transformation_pipeline.set_parameters(project.parameters)
                    # Update the transform view with the dataset - the SQL
                    # view already has every dataset registered by name
                    # from set_project() above.
                    current_df = self.current_dataset.get_current_dataframe()
                    if current_df is not None:
                        self.views["transform"].set_dataframe(current_df, self.current_dataset.transformation_pipeline)

                # Close backstage view and navigate to dashboard
                self.backstage_view.setVisible(False)
                self.content_stack.setCurrentWidget(self.views["dashboard"])

    def edit_current_project(self):
        """Edit the current project"""
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "No project is currently open.")
            return

        from PySide6.QtWidgets import QInputDialog
        # For simplicity, use input dialogs - could be enhanced with a proper edit dialog
        new_name, ok = QInputDialog.getText(
            self, "Edit Project Name",
            "Enter new project name:",
            text=self.current_project.name
        )

        if ok and new_name.strip():
            self.current_project.name = new_name.strip()
            self.mark_project_dirty()
            self.set_project(self.current_project)
            self.refresh_dashboard_stats()
            self.statusBar().showMessage(f"Project renamed to: {new_name}")

    def delete_current_project(self):
        """Close the current project (clears it from the workspace — does
        not delete the .caat file on disk)."""
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "No project is currently open.")
            return

        if self.project_dirty:
            save_reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"'{self.current_project.name}' has unsaved changes. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            if save_reply == QMessageBox.Cancel:
                return
            if save_reply == QMessageBox.Save:
                self.save_project()
                if self.project_dirty:
                    return  # save was cancelled partway through

        reply = QMessageBox.question(
            self,
            "Close Project",
            f"Close the project '{self.current_project.name}'?\n\n"
            "This removes it from the workspace but does not delete the saved file.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            project_name = self.current_project.name

            # Clear the current project
            self.current_project = None
            self.current_dataset = None
            self.current_project_path = None
            self.mark_project_clean()

            # Explicit close: don't resume this project on next launch
            from core.session_state import set_active_project
            set_active_project(None)

            # Update UI
            self.set_project(None)
            self.refresh_dashboard_stats()

            # Navigate to dashboard
            self.content_stack.setCurrentWidget(self.views["dashboard"])

            self.statusBar().showMessage(f"Project '{project_name}' deleted")

    def save_project(self, save_as: bool = False):
        """Save the current project as a native .caat file.

        Saves silently to the known file if one exists (like Ctrl+S in any
        normal app); prompts for a location on first save or "Save As".
        """
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "No project is currently open.")
            return

        from core.caat_format import save_caat

        target_path = self.current_project_path
        if save_as or not target_path:
            from PySide6.QtWidgets import QFileDialog
            from pathlib import Path
            default_name = f"{self.current_project.name.replace(' ', '_')}.caat"
            default_dir = Path(self.current_project_path).parent if self.current_project_path \
                else Path.home() / "Documents" / "CaatMaster" / "Projects"
            default_dir.mkdir(parents=True, exist_ok=True)
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Project",
                str(default_dir / default_name),
                "CaatMaster Project (*.caat)"
            )
            if not file_path:
                return
            if not file_path.endswith(".caat"):
                file_path += ".caat"
            target_path = file_path

        try:
            active_id = self.current_dataset.id if self.current_dataset else None
            saved_path = save_caat(self.current_project, target_path, author=self._current_username(),
                                    active_dataset_id=active_id)
            self.current_project_path = saved_path
            self.mark_project_clean()
            from core.recent_projects import add_recent
            from core.session_state import set_active_project
            add_recent(saved_path, self.current_project.name)
            set_active_project(saved_path)
            self.statusBar().showMessage(f"Project saved to: {saved_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{str(e)}")

    def save_project_as(self):
        """Save the current project to a new .caat file location."""
        self.save_project(save_as=True)

    def manage_datasets(self):
        """Open dataset management dialog"""
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "No project is currently open.")
            return

        dialog = DatasetManagerDialog(self.current_project, self)
        dialog.exec()

    def refresh_dashboard_stats(self):
        """Refresh dashboard statistics"""
        dashboard = self.views.get("dashboard")
        if dashboard and hasattr(dashboard, 'refresh'):
            # Use the refresh method which updates without changing project
            dashboard.refresh()
        elif dashboard and hasattr(dashboard, 'set_project'):
            # Fallback: use set_project
            dashboard.set_project(self.current_project)

    def import_data(self):
        """Import data from file"""
        self.content_stack.setCurrentWidget(self.views["data"])
        data_view = self.views.get("data")
        if data_view and hasattr(data_view, "show_import_dialog"):
            # data_view's own dataset_added/data_loaded signals (connected
            # once in create_views()) already add the imported dataset to
            # the project and update every view — nothing more to wire here.
            data_view.show_import_dialog()
        else:
            QMessageBox.warning(self, "Data View Not Available", "The data import view is not available.")

    def export_data(self):
        """Export data to file"""
        if not self.current_dataset:
            QMessageBox.warning(self, "No Data", "Please load a dataset first.")
            return

        # Use the project exporter to export the current dataset
        dialog = SaveProjectDialog(self.current_project, self)
        if dialog.exec():
            save_options = dialog.get_save_options()
            try:
                exported_path = ProjectExporter.export_project(
                    self.current_project,
                    str(save_options["file_path"].parent),
                    save_options["format"]
                )
                self.statusBar().showMessage(f"Data exported to: {exported_path}")
                QMessageBox.information(self, "Export Successful",
                                      f"Project exported successfully to:\n{exported_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export data: {str(e)}")

    def export_for_review(self):
        """Export project for senior auditor review - includes data + transformation steps"""
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "No project is currently open.")
            return

        from PySide6.QtWidgets import QFileDialog
        from pathlib import Path

        # Ask user for save location
        default_name = f"{self.current_project.name.replace(' ', '_')}_for_review"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export for Review",
            str(Path.home() / "Documents" / default_name),
            "Excel with Metadata (*.xlsx);;Parquet Package (*.parquet);;JSON Package (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            from datetime import datetime

            export_service = ExportService()
            export_format = Path(file_path).suffix.lower().lstrip('.')

            if export_format == 'xlsx':
                # Export with transformation steps for review
                self._export_excel_for_review(file_path, export_service)
            elif export_format == 'parquet':
                # Export as parquet package with metadata
                self._export_parquet_for_review(file_path, export_service)
            elif export_format == 'json':
                # Export as JSON with full audit trail
                self._export_json_for_review(file_path, export_service)
            else:
                # Default to Excel
                self._export_excel_for_review(file_path, export_service)

            self.statusBar().showMessage(f"Exported for review: {file_path}")
            QMessageBox.information(
                self,
                "Export Complete",
                f"Project exported for senior auditor review.\n\n"
                f"Location: {file_path}\n\n"
                f"The export includes:\n"
                f"• Current data state\n"
                f"• All transformation steps\n"
                f"• Column lineage information\n"
                f"• Project metadata"
            )

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export for review:\n{str(e)}")

    def _export_excel_for_review(self, file_path: str, export_service: ExportService):
        """Export project as Excel with transformation audit trail"""
        import pandas as pd
        from datetime import datetime

        # Get current dataset
        if not self.current_dataset:
            raise ValueError("No dataset to export")

        df = self.current_dataset.get_current_dataframe()
        if df is None:
            raise ValueError("Dataset has no data")

        # Create Excel writer
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Sheet 1: Data
            df_pandas = df.to_pandas()
            df_pandas.to_excel(writer, sheet_name='Data', index=False)

            # Sheet 2: Transformation Steps
            self._create_transformation_steps_sheet(writer, df_pandas)

            # Sheet 3: Column Lineage
            self._create_column_lineage_sheet(writer, df)

            # Sheet 4: Project Info
            self._create_project_info_sheet(writer)

    def _create_transformation_steps_sheet(self, writer, df_pandas):
        """Create transformation steps audit sheet"""
        import pandas as pd

        steps_data = []
        if self.current_dataset.transformation_pipeline:
            for i, step in enumerate(self.current_dataset.transformation_pipeline.get_steps()):
                steps_data.append({
                    'Step Number': i + 1,
                    'Operation': step.operation_id,
                    'Parameters': str(step.params),
                    'Timestamp': step.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'Created Columns': ', '.join(step.created_columns) if step.created_columns else ''
                })

        steps_df = pd.DataFrame(steps_data)
        steps_df.to_excel(writer, sheet_name='Transformation Steps', index=False)

    def _create_column_lineage_sheet(self, writer, df):
        """Create column lineage/audit sheet"""
        import pandas as pd

        lineage_data = []
        for col in df.columns:
            lineage_data.append({
                'Column Name': col,
                'Data Type': str(df[col].dtype),
                'Non-Null Count': df[col].null_count() if hasattr(df[col], 'null_count') else 0,
                'Unique Values': df[col].n_unique()
            })

        lineage_df = pd.DataFrame(lineage_data)
        lineage_df.to_excel(writer, sheet_name='Column Lineage', index=False)

    def _create_project_info_sheet(self, writer):
        """Create project metadata sheet"""
        import pandas as pd

        project = self.current_project
        info_data = [
            ['Project Name', project.name],
            ['Client Name', project.client_name or 'N/A'],
            ['Engagement Type', project.engagement_type],
            ['Risk Score', project.risk_score],
            ['Phase', project.phase],
            ['Description', project.description or 'N/A'],
            ['Created', project.metadata.get('created_at', 'N/A')],
            ['Exported For Review', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]

        info_df = pd.DataFrame(info_data, columns=['Field', 'Value'])
        info_df.to_excel(writer, sheet_name='Project Info', index=False)

    def _export_parquet_for_review(self, file_path: str, export_service: ExportService):
        """Export as Parquet with transformation metadata"""
        from pathlib import Path
        import json

        if not self.current_dataset:
            raise ValueError("No dataset to export")

        df = self.current_dataset.get_current_dataframe()
        if df is None:
            raise ValueError("Dataset has no data")

        # Create package directory
        package_dir = Path(file_path).parent / Path(file_path).stem
        package_dir.mkdir(parents=True, exist_ok=True)

        # Export data as parquet
        df.write_parquet(str(package_dir / "data.parquet"))

        # Export transformation steps as JSON
        steps_data = []
        if self.current_dataset.transformation_pipeline:
            for i, step in enumerate(self.current_dataset.transformation_pipeline.get_steps()):
                steps_data.append({
                    'step_number': i + 1,
                    'operation': step.operation_id,
                    'params': step.params,
                    'timestamp': step.timestamp.isoformat(),
                    'created_columns': step.created_columns
                })

        with open(package_dir / "transformation_steps.json", 'w') as f:
            json.dump(steps_data, f, indent=2)

        # Export project metadata
        project_info = {
            'name': self.current_project.name,
            'client_name': self.current_project.client_name,
            'engagement_type': self.current_project.engagement_type,
            'risk_score': self.current_project.risk_score,
            'phase': self.current_project.phase,
            'exported_at': datetime.now().isoformat()
        }

        with open(package_dir / "project_info.json", 'w') as f:
            json.dump(project_info, f, indent=2)

    def _export_json_for_review(self, file_path: str, export_service: ExportService):
        """Export as JSON with full audit trail"""
        import json
        from datetime import datetime

        if not self.current_dataset:
            raise ValueError("No dataset to export")

        df = self.current_dataset.get_current_dataframe()
        if df is None:
            raise ValueError("Dataset has no data")

        export_data = {
            'project': {
                'name': self.current_project.name,
                'client_name': self.current_project.client_name,
                'engagement_type': self.current_project.engagement_type,
                'risk_score': self.current_project.risk_score,
                'phase': self.current_project.phase,
                'description': self.current_project.description,
                'objectives': self.current_project.objectives,
                'exported_at': datetime.now().isoformat()
            },
            'data': df.to_dicts(),
            'columns': list(df.columns),
            'column_types': {col: str(df[col].dtype) for col in df.columns},
            'transformation_steps': [],
            'column_lineage': {}
        }

        # Add transformation steps
        if self.current_dataset.transformation_pipeline:
            for i, step in enumerate(self.current_dataset.transformation_pipeline.get_steps()):
                export_data['transformation_steps'].append({
                    'step_number': i + 1,
                    'operation': step.operation_id,
                    'params': step.params,
                    'timestamp': step.timestamp.isoformat(),
                    'created_columns': step.created_columns
                })

        # Add column lineage
        for col in df.columns:
            export_data['column_lineage'][col] = {
                'type': str(df[col].dtype),
                'null_count': int(df[col].null_count()),
                'unique_count': int(df[col].n_unique())
            }

        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)

    def run_analysis(self):
        """Run the current analysis"""
        self.statusBar().showMessage("Running analysis...")

    def undo(self):
        """Undo last action"""
        # Get current view and try to undo
        current = self.content_stack.currentWidget()
        if hasattr(current, 'undo'):
            current.undo()
        else:
            self.statusBar().showMessage("Nothing to undo")

    def redo(self):
        """Redo last action"""
        current = self.content_stack.currentWidget()
        if hasattr(current, 'redo'):
            current.redo()
        else:
            self.statusBar().showMessage("Nothing to redo")

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.windowState() & Qt.WindowFullScreen:
            self.setWindowState(self.windowState() & ~Qt.WindowFullScreen)
        else:
            self.setWindowState(self.windowState() | Qt.WindowFullScreen)

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About CaatMaster",
            """
            <div style="text-align: center;">
                <h2 style="color: #3b82f6;">CaatMaster</h2>
                <p><b>Professional Continuous Audit Analytics Tool</b></p>
                <p>Version 1.0.0</p>
                <hr style="border-color: #3f3f46;">
                <p>A powerful desktop application for audit professionals
                to perform sophisticated data analysis with ML and AI capabilities.</p>
                <p style="color: #71717a;">Built with PySide 6 and Polars</p>
            </div>
            """
        )

    def set_project(self, project):
        """Set the current active project"""
        self.current_project = project

        if project:
            self.setWindowTitle(f"CaatMaster - {project.name}")
        else:
            self.setWindowTitle("CaatMaster - Professional Audit Analytics Tool")

        # Update backstage view
        self.backstage_view.set_project(project)

        # Update sidebar with project info
        self.sidebar.set_project(project)

        # Update dashboard with project info
        dashboard = self.views.get("dashboard")
        if dashboard and hasattr(dashboard, 'set_project'):
            dashboard.set_project(project)

        # Update data_view with project
        data_view = self.views.get("data")
        if data_view and hasattr(data_view, 'set_project'):
            data_view.set_project(project)

        # Update SQL views with project
        sql_view = self.views.get("sql")
        if sql_view and hasattr(sql_view, 'set_project'):
            sql_view.set_project(project)
        query_view = self.views.get("query")
        if query_view and hasattr(query_view, 'set_project'):
            query_view.set_project(project)

    def set_dataset(self, dataset):
        """Set the current active dataset"""
        self.current_dataset = dataset

    # ========================================================================
    # Authentication Methods
    # ========================================================================

    def show_login_dialog(self):
        """Show login dialog if user not authenticated"""
        if self.auth_service.is_authenticated():
            # User already logged in, show window maximized
            user = self.auth_service.get_current_user()
            self.statusBar().showMessage(f"Welcome back, {user.full_name}!")
            self.update_auth_ui()
            self.setWindowState(Qt.WindowMaximized)
        else:
            from gui.dialogs.login_dialog import LoginDialog

            dialog = LoginDialog(self.auth_service, self)
            dialog.login_success.connect(self.handle_login_success)

            # If dialog is rejected (closed/cancelled), exit app
            if not dialog.exec():
                self.close()
                QApplication.instance().quit()
                return

            # If we get here, login was successful
            if not self.auth_service.is_authenticated():
                # Should not happen, but be safe
                self.close()
                QApplication.instance().quit()
                return

    def handle_login_success(self, user):
        """Handle successful user login"""
        self._login_successful = True
        self.statusBar().showMessage(f"Welcome, {user.full_name}!")
        self.update_auth_ui()
        # Show window maximized after successful login
        self.setWindowState(Qt.WindowMaximized)
        self._resume_last_project()

    def _resume_last_project(self):
        """Reopen whichever project was active when the app last closed —
        like reopening a document — unless it was explicitly closed first
        (session_state.get_active_project() returns None in that case).
        Fails gracefully if the file went missing or won't load: clears the
        stale pointer so it doesn't keep failing on every future launch, and
        leaves the user on an empty Dashboard instead of crashing."""
        from core.session_state import get_active_project, set_active_project

        path = get_active_project()
        if not path:
            return

        if not Path(path).exists():
            set_active_project(None)
            self.statusBar().showMessage(
                f"Couldn't resume your last project — '{Path(path).name}' no longer exists.", 8000
            )
            return

        try:
            from core.caat_format import load_caat
            project = load_caat(path)
        except Exception as e:
            set_active_project(None)
            QMessageBox.warning(
                self, "Couldn't Resume Last Project",
                f"Your last project couldn't be reopened:\n{e}\n\n"
                "Starting with an empty workspace instead."
            )
            return

        self.on_project_open_requested((project, path))

    def handle_logout(self):
        """Handle user logout"""
        self.auth_service.logout()
        self.auth_service.clear_session()
        self.statusBar().showMessage("Logged out")
        self.update_auth_ui()
        self.show_login_dialog()

    def update_auth_ui(self):
        """Update UI based on authentication state"""
        user = self.auth_service.get_current_user()

        # Update window title
        if user:
            self.setWindowTitle(f"CaatMaster - {user.full_name}")
        else:
            self.setWindowTitle("CaatMaster - Professional Audit Analytics Tool")

        # Update settings view
        settings_view = self.views.get("settings")
        if settings_view:
            settings_view.refresh_user_info()
