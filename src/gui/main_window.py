"""
Main Application Window for CaatMaster
Modern UI inspired by data_workspace_app.py
"""
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QStatusBar, QMenuBar, QMenu,
    QSplitter, QMessageBox, QApplication, QFrame, QLabel
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence, QFont

# Import project management
from core.project_manager import Project, Dataset, ProjectExporter
from core.data_processor import LegacyDataProcessor
from services.export_service import ExportService
from gui.dialogs.project_dialog import NewProjectDialog, OpenProjectDialog, SaveProjectDialog, DatasetManagerDialog

# Import the new sidebar
from gui.components.sidebar import Sidebar


class MainWindow(QMainWindow):
    """Main application window with modern CaatMaster UI"""

    def __init__(self):
        super().__init__()
        self.current_project: Optional[Project] = None
        self.current_dataset: Optional[Dataset] = None
        self.auth_service = None
        self._apply_theme()
        self.setup_auth()
        self.setup_ui()
        self.create_menus()
        self.create_statusbar()
        self.show_login_dialog()

    def _apply_theme(self):
        """Apply the modern CaatMaster theme"""
        # Set application-wide font
        font = QFont("Inter", 10)
        if not font.exactMatch():
            font = QFont("Segoe UI", 10)
        QApplication.instance().setFont(font)

        # Apply base stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }
            QMenuBar {
                background-color: #f9fafb;
                border-bottom: 1px solid #e5e7eb;
                padding: 4px;
            }
            QMenuBar::item {
                color: #111827;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #e5e7eb;
            }
            QMenu {
                background-color: white;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                color: #111827;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #f3f4f6;
            }
            QStatusBar {
                background-color: #f9fafb;
                border-top: 1px solid #e5e7eb;
                color: #111827;
            }
        """)

    def setup_auth(self):
        """Initialize authentication service"""
        from services.auth_service import AuthService

        self.auth_service = AuthService()

        # Create default admin if no users exist
        self.auth_service.create_default_admin()

        # Try to load saved session
        if self.auth_service.load_session():
            # Session loaded successfully
            pass

    def setup_ui(self):
        """Set up the main window UI"""
        self.setWindowTitle("CaatMaster - Professional Audit Analytics Tool")
        self.setMinimumSize(1200, 800)
        self.setObjectName("MainWindow")

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create the new sidebar (inspired by data_workspace_app.py)
        self.sidebar = Sidebar()
        self.sidebar.navigation_requested.connect(self.on_navigation_requested)
        self.sidebar.dataset_selected.connect(self.on_dataset_selected)
        self.sidebar.upload_requested.connect(self.on_upload_requested)
        main_layout.addWidget(self.sidebar)

        # Content area (right side)
        content_area = QWidget()
        content_area.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
            }
        """)
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Create stacked widget for views
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("ContentStack")
        content_layout.addWidget(self.content_stack)

        main_layout.addWidget(content_area, 1)

        # Create main views
        self.create_views()

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
        from gui.views.sessions_view import SessionsView
        from gui.views.reports_view import ReportsView
        from gui.views.settings_view import SettingsView

        # Create and add views
        self.views = {
            "dashboard": DashboardView(),
            "data": DataView(),
            "transform": TransformView(),
            "sql": SQLTransformView(),
            "analyze": AnalyzeView(),
            "visualizations": VisualizationsView(),
            "query": QueryView(),
            "ml models": MLModelInventoryView(),
            "projects": ProjectsView(),
            "sessions": SessionsView(),
            "reports": ReportsView(),
            "settings": SettingsView(),
        }

        # Connect data view to other views that consume its data
        data_view = self.views["data"]
        transform_view = self.views["transform"]
        sql_view = self.views["sql"]
        viz_view = self.views["visualizations"]
        query_view = self.views["query"]
        reports_view = self.views["reports"]
        data_view.data_loaded.connect(transform_view.set_dataframe)
        data_view.data_loaded.connect(sql_view.set_dataframe)
        data_view.data_loaded.connect(viz_view.set_dataframe)
        data_view.data_loaded.connect(query_view.set_dataframe)
        data_view.data_loaded.connect(reports_view.set_dataframe)
        data_view.dataset_added.connect(self._on_dataset_added)

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

    @Slot(str)
    def on_navigation_requested(self, view_name):
        """Handle navigation requests from the sidebar"""
        if view_name in self.views:
            self.content_stack.setCurrentWidget(self.views[view_name])
            self.sidebar.set_active_button(view_name)
            self.statusBar().showMessage(f"Navigated to {view_name.title()}")
        elif view_name == "upload":
            # Navigate to data view and trigger upload
            self.content_stack.setCurrentWidget(self.views["data"])
            self.sidebar.set_active_button("data")
            data_view = self.views.get("data")
            if data_view and hasattr(data_view, "show_import_dialog"):
                data_view.show_import_dialog()
        elif view_name == "export_review":
            self.export_for_review()
        else:
            self.statusBar().showMessage(f"Navigation: {view_name}")

    @Slot(str)
    def on_dataset_selected(self, dataset_id):
        """Handle dataset selection from sidebar"""
        if not self.current_project:
            return

        dataset = self.current_project.datasets.get(dataset_id)
        if dataset:
            self.current_dataset = dataset
            df = dataset.get_current_dataframe()
            if df is not None:
                # Update all views with the dataset
                transform_view = self.views.get("transform")
                sql_view = self.views.get("sql")
                viz_view = self.views.get("visualizations")
                query_view = self.views.get("query")
                reports_view = self.views.get("reports")

                if transform_view:
                    transform_view.set_dataframe(df)
                if sql_view:
                    sql_view.set_dataframe(df)
                if viz_view:
                    viz_view.set_dataframe(df)
                if query_view:
                    query_view.set_dataframe(df)
                if reports_view:
                    reports_view.set_dataframe(df)

                self.statusBar().showMessage(f"Selected dataset: {dataset.name}")

    @Slot()
    def on_upload_requested(self):
        """Handle upload request from sidebar"""
        self.content_stack.setCurrentWidget(self.views["data"])
        self.sidebar.set_active_button("data")
        data_view = self.views.get("data")
        if data_view and hasattr(data_view, "show_import_dialog"):
            data_view.show_import_dialog()

    def _on_dataset_added(self, dataset):
        """Handle new dataset being added - update sidebar"""
        if hasattr(self, 'sidebar'):
            self.sidebar.add_dataset(dataset)
        self.statusBar().showMessage(f"Dataset '{dataset.name}' added to project")

    def create_menus(self):
        """Create application menu bar"""
        menubar = self.menuBar()
        menubar.setObjectName("MenuBar")

        # File menu
        file_menu = menubar.addMenu("&File")

        new_project_action = QAction("Create New Project", self)
        new_project_action.setShortcut(QKeySequence.New)
        new_project_action.setIcon(QIcon.fromTheme("folder-new"))
        new_project_action.triggered.connect(self.new_project)
        file_menu.addAction(new_project_action)

        open_project_action = QAction("Open Project", self)
        open_project_action.setShortcut(QKeySequence.Open)
        open_project_action.setIcon(QIcon.fromTheme("folder"))
        open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(open_project_action)

        save_project_action = QAction("Save Project", self)
        save_project_action.setShortcut(QKeySequence.Save)
        save_project_action.setIcon(QIcon.fromTheme("document-save"))
        save_project_action.triggered.connect(self.save_project)
        file_menu.addAction(save_project_action)

        file_menu.addSeparator()

        import_data_action = QAction("Import Data", self)
        import_data_action.setShortcut(QKeySequence("Ctrl+I"))
        import_data_action.setIcon(QIcon.fromTheme("document-open"))
        import_data_action.triggered.connect(self.import_data)
        file_menu.addAction(import_data_action)

        export_action = QAction("Export Data", self)
        export_action.setIcon(QIcon.fromTheme("document-save"))
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.setIcon(QIcon.fromTheme("application-exit"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Project menu
        project_menu = menubar.addMenu("&Project")

        manage_datasets_action = QAction("Manage Datasets", self)
        manage_datasets_action.setIcon(QIcon.fromTheme("folder"))
        manage_datasets_action.triggered.connect(self.manage_datasets)
        project_menu.addAction(manage_datasets_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.setIcon(QIcon.fromTheme("edit-undo"))
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.setIcon(QIcon.fromTheme("edit-redo"))
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        settings_action = QAction("Settings", self)
        settings_action.setIcon(QIcon.fromTheme("configure"))
        settings_action.triggered.connect(
            lambda: self.content_stack.setCurrentWidget(self.views["settings"])
        )
        edit_menu.addAction(settings_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        fullscreen_action = QAction("Fullscreen", self)
        fullscreen_action.setShortcut(QKeySequence.FullScreen)
        fullscreen_action.setIcon(QIcon.fromTheme("view-fullscreen"))
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        view_menu.addSeparator()

        # Add navigation actions to the View menu (only main views)
        view_names = ["dashboard", "data", "transform", "sql", "analyze", "visualizations", "query", "projects"]
        for name in view_names:
            view = self.views.get(name)
            if view:
                display_name = name.replace("_", " ").title()
                icon_map = {
                    "dashboard": "view-dashboard",
                    "data": "table",
                    "transform": "transform",
                    "sql": "code-braces",
                    "analyze": "chart",
                    "visualizations": "chart-line",
                    "query": "code-context",
                    "projects": "folder",
                }
                action = QAction(display_name, self)
                action.setIcon(QIcon.fromTheme(icon_map.get(name, "applications")))
                action.triggered.connect(
                    lambda checked=False, v=view: self.content_stack.setCurrentWidget(v)
                )
                view_menu.addAction(action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addSeparator()

        # Add tools to Tools menu
        tools_names = ["ml models", "reports", "sessions"]
        for name in tools_names:
            view = self.views.get(name)
            if view:
                display_name = name.replace("_", " ").title()
                icon_map = {
                    "ml models": "train",
                    "reports": "document-text",
                    "sessions": "document",
                }
                action = QAction(display_name, self)
                action.setIcon(QIcon.fromTheme(icon_map.get(name, "applications")))
                action.triggered.connect(
                    lambda checked=False, v=view: self.content_stack.setCurrentWidget(v)
                )
                tools_menu.addAction(action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("About CaatMaster", self)
        about_action.setIcon(QIcon.fromTheme("help-about"))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_statusbar(self):
        """Create status bar"""
        self.statusBar().setObjectName("StatusBar")
        self.statusBar().showMessage("Ready")

    # ========================================================================
    # Actions
    # ========================================================================

    def new_project(self):
        """Create a new project"""
        dialog = NewProjectDialog(self)
        if dialog.exec():
            project_data = dialog.get_project_data()
            self.current_project = Project(
                name=project_data['name'],
                description=project_data['description'],
                client_name=project_data.get('client_name'),
                phase=project_data.get('phase', 'planning'),
                engagement_type=project_data.get('engagement_type', 'financial audit'),
                risk_score=project_data.get('risk_score', 5),
                objectives=project_data.get('objectives')
            )
            self.set_project(self.current_project)
            self.refresh_dashboard_stats()
            self.statusBar().showMessage(f"Created project: {project_data['name']}")

    def new_session(self):
        """Create a new session"""
        QMessageBox.information(self, "New Session",
                               "Session management will be available in a future update.\n"
                               "For now, use projects to organize your work.")

    def open_project(self):
        """Open an existing project"""
        dialog = OpenProjectDialog(self)
        if dialog.exec():
            project = dialog.get_selected_project()
            if project:
                self.current_project = project
                self.set_project(self.current_project)
                self.refresh_dashboard_stats()
                self.statusBar().showMessage(f"Opened project: {project.name}")

                # Load first dataset if available
                datasets = project.list_datasets()
                if datasets:
                    self.current_dataset = datasets[0]
                    # Update views with the dataset
                    current_df = self.current_dataset.get_current_dataframe()
                    if current_df is not None:
                        self.views["transform"].set_dataframe(current_df)
                        self.views["sql"].set_dataframe(current_df)

    def save_project(self):
        """Save the current project"""
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "No project is currently open.")
            return

        dialog = SaveProjectDialog(self.current_project, self)
        if dialog.exec():
            save_options = dialog.get_save_options()
            try:
                exported_path = ProjectExporter.export_project(
                    self.current_project,
                    str(save_options["file_path"].parent),
                    save_options["format"]
                )
                self.statusBar().showMessage(f"Project saved to: {exported_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save project: {str(e)}")

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
        if dashboard and hasattr(dashboard, 'update_stats'):
            # For now, just count current project datasets
            # In a full implementation, this would query all projects
            projects_count = 1 if self.current_project else 0
            datasets_count = len(self.current_project.list_datasets()) if self.current_project else 0
            analyses_count = 0  # Would need to track completed analyses
            sessions_count = 0  # Would need to track saved sessions

            dashboard.update_stats(
                projects_count=projects_count,
                datasets_count=datasets_count,
                analyses_count=analyses_count,
                sessions_count=sessions_count
            )

    @Slot(object)
    def on_data_imported(self, dataframe):
        """Handle data import and add to current project"""
        if not self.current_project:
            return

        # Create a dataset name from a dialog or use default
        from PySide6.QtWidgets import QInputDialog
        dataset_name, ok = QInputDialog.getText(
            self, "Dataset Name",
            "Enter a name for this dataset:",
            text=f"Dataset_{len(self.current_project.list_datasets()) + 1}"
        )

        if ok and dataset_name:
            # Create dataset
            dataset = Dataset(name=dataset_name, dataframe=dataframe)

            # Add to project
            self.current_project.add_dataset(dataset)

            # Set as current dataset
            self.current_dataset = dataset

            # Update status
            self.statusBar().showMessage(f"Dataset '{dataset_name}' added to project '{self.current_project.name}'")

            # Update views with the new data
            self.views["transform"].set_dataframe(dataframe)
            self.views["sql"].set_dataframe(dataframe)

            # Refresh dashboard stats
            self.refresh_dashboard_stats()

    def import_data(self):
        """Import data from file"""
        self.content_stack.setCurrentWidget(self.views["data"])
        data_view = self.views.get("data")
        if data_view and hasattr(data_view, "show_import_dialog"):
            # Connect to data loaded signal to add to project
            data_view.data_loaded.connect(self.on_data_imported)
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
        self.setWindowTitle(f"CaatMaster - {project.name}")

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

    def set_dataset(self, dataset):
        """Set the current active dataset"""
        self.current_dataset = dataset

    # ========================================================================
    # Authentication Methods
    # ========================================================================

    def show_login_dialog(self):
        """Show login dialog if user not authenticated"""
        if not self.auth_service.is_authenticated():
            from gui.dialogs.login_dialog import LoginDialog

            dialog = LoginDialog(self.auth_service, self)
            dialog.login_success.connect(self.handle_login_success)
            dialog.exec()
            self.update_auth_ui()

    def handle_login_success(self, user):
        """Handle successful user login"""
        self.statusBar().showMessage(f"Welcome, {user.full_name}!")
        self.update_auth_ui()

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
