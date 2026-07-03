"""Dashboard View - Beautiful landing page design with accurate metrics"""
from datetime import datetime
import polars as pl
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea, QGraphicsDropShadowEffect,
    QButtonGroup, QRadioButton
)
from PySide6.QtCore import Qt, QSize, Signal, Slot
from PySide6.QtGui import QFont, QColor, QPainter, QLinearGradient


class MetricCard(QFrame):
    """Card widget for displaying metrics"""
    def __init__(self, title, value, subtitle="", icon="", trend=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: none;
            }
        """)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Header with icon and title
        header_layout = QHBoxLayout()

        if icon:
            icon_label = QLabel(icon)
            icon_label.setStyleSheet("""
                QLabel {
                    font-size: 28px;
                    padding: 8px;
                    background-color: #deecf9;
                    border-radius: 8px;
                }
            """)
            icon_label.setFixedSize(52, 52)
            icon_label.setAlignment(Qt.AlignCenter)
            header_layout.addWidget(icon_label)

        header_layout.addStretch()

        # Trend indicator
        if trend:
            trend_label = QLabel(trend)
            trend_color = "#10b981" if "↑" in trend else "#ef4444"
            trend_label.setStyleSheet(f"""
                QLabel {{
                    color: {trend_color};
                    font-size: 14px;
                    font-weight: 600;
                    padding: 4px 8px;
                    background-color: {"#d1fae5" if "↑" in trend else "#fee2e2"};
                    border-radius: 6px;
                }}
            """)
            header_layout.addWidget(trend_label)

        layout.addLayout(header_layout)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #605e5c;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        layout.addWidget(title_label)

        # Value
        value_label = QLabel(value)
        value_label.setStyleSheet("""
            QLabel {
                color: #201f1e;
                font-size: 32px;
                font-weight: 700;
            }
        """)
        layout.addWidget(value_label)

        # Subtitle
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet("""
                QLabel {
                    color: #605e5c;
                    font-size: 12px;
                }
            """)
            layout.addWidget(subtitle_label)

        layout.addStretch()


class DatasetCard(QFrame):
    """Card widget for displaying dataset information"""
    datasetClicked = Signal(dict)  # Signal emitted when card is clicked, with dataset info

    def __init__(self, dataset_info, parent=None):
        super().__init__(parent)
        self._dataset_info = dataset_info
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: none;
            }
            QFrame:hover {
                background-color: #f3f2f1;
            }
        """)

        # Extract values from dataset_info
        dataset_name = dataset_info.get("name", "Unknown")
        row_count = dataset_info.get("rows", 0)
        col_count = dataset_info.get("columns", 0)
        last_modified = dataset_info.get("modified", "Just now")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Dataset name with icon
        name_layout = QHBoxLayout()
        icon_label = QLabel("📊")
        icon_label.setStyleSheet("font-size: 20px;")
        name_layout.addWidget(icon_label)

        name_label = QLabel(dataset_name)
        name_label.setStyleSheet("""
            QLabel {
                color: #201f1e;
                font-size: 15px;
                font-weight: 600;
            }
        """)
        name_layout.addWidget(name_label, 1)
        layout.addLayout(name_layout)

        # Stats row
        stats_layout = QHBoxLayout()

        rows_label = QLabel(f"{row_count:,} rows")
        rows_label.setStyleSheet("""
            QLabel {
                color: #605e5c;
                font-size: 12px;
                background-color: #edebe9;
                padding: 4px 10px;
                border-radius: 6px;
            }
        """)
        stats_layout.addWidget(rows_label)

        cols_label = QLabel(f"{col_count} cols")
        cols_label.setStyleSheet("""
            QLabel {
                color: #605e5c;
                font-size: 12px;
                background-color: #edebe9;
                padding: 4px 10px;
                border-radius: 6px;
            }
        """)
        stats_layout.addWidget(cols_label)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Last modified
        modified_label = QLabel(f"Modified {last_modified}")
        modified_label.setStyleSheet("""
            QLabel {
                color: #605e5c;
                font-size: 11px;
            }
        """)
        layout.addWidget(modified_label)

        # Add subtle shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 10))
        self.setGraphicsEffect(shadow)

    def mousePressEvent(self, event):
        """Handle mouse click - emit signal with dataset info"""
        if event.button() == Qt.LeftButton:
            self.datasetClicked.emit(self._dataset_info)
        super().mousePressEvent(event)


class ActivityItem(QFrame):
    """Widget for displaying recent activity"""
    def __init__(self, action, dataset, time, user="You", icon="📁", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-bottom: 1px solid #edebe9;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(16)

        # Activity icon
        icon_label = QLabel(icon)
        icon_label.setFixedSize(36, 36)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("""
            QLabel {
                background-color: #deecf9;
                border-radius: 18px;
                font-size: 16px;
            }
        """)
        layout.addWidget(icon_label)

        # Activity details
        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)

        action_label = QLabel(f"<b>{action}</b>")
        action_label.setStyleSheet("""
            QLabel {
                color: #201f1e;
                font-size: 13px;
            }
        """)
        details_layout.addWidget(action_label)

        dataset_label = QLabel(dataset)
        dataset_label.setStyleSheet("""
            QLabel {
                color: #605e5c;
                font-size: 12px;
            }
        """)
        details_layout.addWidget(dataset_label)

        layout.addLayout(details_layout, 1)

        # Time
        time_label = QLabel(time)
        time_label.setStyleSheet("""
            QLabel {
                color: #8a8886;
                font-size: 11px;
            }
        """)
        layout.addWidget(time_label)


class ProgressBar(QWidget):
    """Custom progress bar widget"""
    def __init__(self, value, max_value, label, color="#0078d4", parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.label_text = label
        self.color = color
        self.setFixedHeight(50)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw label
        painter.setPen(QColor("#605e5c"))
        font = QFont()
        font.setPixelSize(13)
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        painter.drawText(0, 0, self.width(), 18, Qt.AlignLeft, self.label_text)

        # Draw value
        percentage = int((self.value / self.max_value) * 100) if self.max_value > 0 else 0
        painter.setPen(QColor("#201f1e"))
        font.setPixelSize(13)
        font.setWeight(QFont.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, self.width(), 18, Qt.AlignRight, f"{percentage}%")

        # Draw background bar
        bar_y = 24
        bar_height = 8
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#edebe9"))
        painter.drawRoundedRect(0, bar_y, self.width(), bar_height, 4, 4)

        # Draw progress bar
        progress_width = int((self.value / self.max_value) * self.width()) if self.max_value > 0 else 0
        gradient = QLinearGradient(0, bar_y, progress_width, bar_y)
        gradient.setColorAt(0, QColor(self.color))
        gradient.setColorAt(1, QColor(self.color).lighter(110))
        painter.setBrush(gradient)
        painter.drawRoundedRect(0, bar_y, max(progress_width, 0), bar_height, 4, 4)


class DashboardView(QWidget):
    """Main dashboard view with accurate metrics"""

    # Signals
    auditStatusChanged = Signal(str)  # When audit status changes
    uploadRequested = Signal()  # When user wants to upload/import data
    viewProjectsRequested = Signal()  # When user wants to view projects
    datasetSelected = Signal(str)  # When a dataset is selected (emits dataset_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project = None
        self.datasets = []
        self.activities = []
        self.stat_labels = {}
        self.setup_ui()

    def set_project(self, project):
        """Set the current project and update display"""
        self.current_project = project
        self._update_from_project()
        self._update_header()

    def refresh(self):
        """Refresh dashboard data without changing project"""
        # Always refresh - if no project, it will clear the display
        self._update_from_project()

    def showEvent(self, event):
        """Refresh dashboard when it becomes visible"""
        super().showEvent(event)
        self.refresh()

    def _update_from_project(self):
        """Update dashboard data from current project"""
        if not self.current_project:
            self.datasets = []
            self.activities = []
            self._refresh_metrics()
            return

        # Get datasets from project
        self.datasets = []
        for dataset in self.current_project.list_datasets():
            df = dataset.get_current_dataframe()
            if df is not None:
                self.datasets.append({
                    "id": dataset.id,
                    "name": dataset.name,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "modified": "Just now",
                    "dataframe": df
                })

        # Refresh activities from the project's activity log
        self._refresh_activities()

        # Refresh metrics display
        self._refresh_metrics()

        # Refresh datasets section
        self._refresh_datasets()

    def _refresh_activities(self):
        """Refresh activities from project activity log"""
        self.activities = []

        if not self.current_project:
            return

        # Get activities from project
        activities = getattr(self.current_project, 'activities', []) or []

        for activity in activities[-10:]:  # Last 10 activities
            self.activities.append({
                "action": activity.get("action", "Unknown action"),
                "dataset": activity.get("dataset", ""),
                "time": activity.get("time", "Just now"),
                "icon": activity.get("icon", "📁")
            })

        # If no activities, add a placeholder
        if not self.activities:
            self.activities = [{
                "action": "Started audit",
                "dataset": self.current_project.name,
                "time": "Just now",
                "icon": "🚀"
            }]

    def _refresh_metrics(self):
        """Calculate and update all metrics"""
        if not self.current_project:
            # Reset to empty values
            self._update_metric_values(0, 0, "0%", "Never")
            return

        # Calculate total datasets
        datasets_count = len(self.datasets)

        # Calculate total records
        total_records = sum(d.get("rows", 0) for d in self.datasets)

        # Calculate data quality
        quality_score = self._calculate_data_quality()

        # Get last audit time
        last_audit = self._get_last_audit_time()

        self._update_metric_values(datasets_count, total_records, quality_score, last_audit)

    def _update_metric_values(self, datasets, records, quality, last_audit):
        """Update metric card values"""
        if "Total Datasets" in self.stat_labels:
            self.stat_labels["Total Datasets"].setText(str(datasets))

        if "Total Records" in self.stat_labels:
            self.stat_labels["Total Records"].setText(f"{records:,}")

        if "Data Quality" in self.stat_labels:
            self.stat_labels["Data Quality"].setText(quality)

        if "Last Audit" in self.stat_labels:
            self.stat_labels["Last Audit"].setText(last_audit)

        # Also update audit progress section
        self._update_audit_progress()

    def _calculate_data_quality(self) -> str:
        """Calculate data quality percentage based on null/NaN values"""
        if not self.datasets:
            return "0%"

        total_datasets = len(self.datasets)
        quality_scores = []

        for dataset_info in self.datasets:
            df = dataset_info.get("dataframe")
            if df is None:
                continue

            # Calculate null percentage for this dataset
            total_cells = len(df) * len(df.columns)
            if total_cells == 0:
                continue

            # Count nulls
            null_count = 0
            for col in df.columns:
                null_count += df[col].null_count()

            # Count empty strings in string columns
            for col in df.columns:
                if df[col].dtype == pl.Utf8:
                    null_count += (df[col].str.len_chars() == 0).sum()

            null_percentage = (null_count / total_cells) * 100
            quality_score = 100 - null_percentage
            quality_scores.append(quality_score)

        if not quality_scores:
            return "0%"

        avg_quality = sum(quality_scores) / len(quality_scores)
        return f"{avg_quality:.1f}%"

    def _get_last_audit_time(self) -> str:
        """Get last audit time from activities"""
        if not self.activities:
            return "Never"

        # Get the most recent activity time
        for activity in self.activities:
            time_str = activity.get("time", "")
            if time_str and time_str != "Never":
                return time_str

        return "Just now"

    def _format_timestamp(self, timestamp):
        """Format datetime for display (e.g., '2 hours ago')"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        diff = now - timestamp
        if diff.days > 0:
            return f"{diff.days} days ago"
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = diff.seconds // 60
        if minutes > 0:
            return f"{minutes}m ago"
        return "Just now"

    def _update_header(self):
        """Update the header with project info"""
        if self.current_project:
            project_name = self.current_project.name if self.current_project.name else "Dashboard"
            self.header_title.setText(project_name)

            client_name = getattr(self.current_project, 'client_name', None) or ""
            if client_name:
                self.header_subtitle.setText(f"Audit - {client_name}")
            else:
                self.header_subtitle.setText("Dashboard")
        else:
            self.header_title.setText("Dashboard")
            self.header_subtitle.setText("Overview")

    def _refresh_datasets(self):
        """Refresh the datasets section with current datasets"""
        # Clear existing dataset cards
        for i in range(self.datasets_layout.count()):
            item = self.datasets_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        if not self.datasets:
            # Empty state
            empty_label = QLabel("No datasets yet\nImport data to get started")
            empty_label.setStyleSheet("""
                QLabel {
                    color: #605e5c;
                    font-size: 13px;
                    padding: 24px;
                    text-align: center;
                }
            """)
            empty_label.setAlignment(Qt.AlignCenter)
            self.datasets_layout.addWidget(empty_label)
        else:
            # Add dataset cards (show up to 5 most recent)
            for dataset in sorted(self.datasets, key=lambda x: x.get("modified", ""), reverse=True)[:5]:
                card = DatasetCard(dataset)
                # Connect card click to emit dataset selected signal
                card.datasetClicked.connect(self._on_dataset_card_clicked)
                self.datasets_layout.addWidget(card)

    def _on_dataset_card_clicked(self, dataset_info):
        """Handle dataset card click - emit dataset selected signal"""
        dataset_id = dataset_info.get("id", "")
        if dataset_id:
            self.datasetSelected.emit(dataset_id)

    def _update_audit_progress(self):
        """Update audit progress based on project status and datasets"""
        if not self.current_project:
            return

        # Clear existing progress bars
        for i in range(self.progress_layout.count()):
            item = self.progress_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), ProgressBar):
                item.widget().deleteLater()

        # Calculate progress based on project status
        project_status = getattr(self.current_project, 'status', 'planning')

        if project_status == "completed":
            # All phases complete
            progress_items = [
                ("Data Collection", 100, 100, "#10b981"),
                ("Data Validation", 100, 100, "#10b981"),
                ("Analysis Complete", 100, 100, "#10b981"),
                ("Reports Generated", 100, 100, "#10b981"),
            ]
        else:
            # Calculate progress based on datasets
            total_datasets = len(self.datasets)
            completed_datasets = sum(1 for d in self.datasets if d.get("rows", 0) > 0)

            # Estimate progress
            collection_pct = min(100, int((completed_datasets / max(1, total_datasets)) * 50))
            validation_pct = min(100, int((completed_datasets / max(1, total_datasets)) * 75))
            analysis_pct = min(100, int((completed_datasets / max(1, total_datasets)) * 100))
            reports_pct = 0  # Only when audit is completed

            progress_items = [
                ("Data Collection", collection_pct, 100, "#0078d4"),
                ("Data Validation", validation_pct, 100, "#f59e0b"),
                ("Analysis Complete", analysis_pct, 100, "#8b5cf6"),
                ("Reports Generated", reports_pct, 100, "#605e5c"),
            ]

        for label, value, max_value, color in progress_items:
            progress = ProgressBar(value, max_value, label, color)
            self.progress_layout.addWidget(progress)

    def _toggle_audit_status(self, status):
        """Toggle audit completion status"""
        if not self.current_project:
            return

        self.current_project.status = status
        self._refresh_metrics()
        self._update_audit_progress()
        self.auditStatusChanged.emit(status)

        # Update status button styles
        self._update_status_button_styles(status)

    def _update_status_button_styles(self, status):
        """Update the visual style of status buttons"""
        active_style = """
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #edebe9;
                color: #605e5c;
                border: 1px solid #e1dfdd;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
        """

        if status == "completed":
            self.status_completed.setStyleSheet(active_style)
            self.status_active.setStyleSheet(inactive_style)
        else:
            self.status_completed.setStyleSheet(inactive_style)
            self.status_active.setStyleSheet(active_style)

    def update_stats(self, projects_count: int = 0, datasets_count: int = 0,
                    analyses_count: int = 0, sessions_count: int = 0):
        """Update the dashboard statistics (legacy method for compatibility)"""
        if self.current_project:
            self._refresh_metrics()

    def setup_ui(self):
        """Set up the dashboard UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(24)

        # Header
        header = self.create_header()
        main_layout.addWidget(header)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(24)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        # Metrics cards
        metrics = self.create_metrics_section()
        scroll_layout.addWidget(metrics)

        # Two column layout for datasets and activity
        content_row = QHBoxLayout()
        content_row.setSpacing(24)

        # Left column - Datasets
        datasets_section = self.create_datasets_section()
        content_row.addWidget(datasets_section, 2)

        # Right column - Activity and Progress
        right_column = QVBoxLayout()
        right_column.setSpacing(24)

        activity_section = self.create_activity_section()
        right_column.addWidget(activity_section)

        progress_section = self.create_progress_section()
        right_column.addWidget(progress_section)

        right_widget = QWidget()
        right_widget.setLayout(right_column)
        content_row.addWidget(right_widget, 1)

        scroll_layout.addLayout(content_row)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

    def create_header(self):
        """Create the dashboard header"""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        # Left side - Title
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        self.header_title = QLabel("Dashboard")
        self.header_title.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 700;
                color: #201f1e;
            }
        """)
        left_layout.addWidget(self.header_title)

        self.header_subtitle = QLabel("Overview")
        self.header_subtitle.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #605e5c;
            }
        """)
        left_layout.addWidget(self.header_subtitle)

        layout.addLayout(left_layout, 1)

        # Right side - Status toggle and Actions
        right_layout = QHBoxLayout()
        right_layout.setSpacing(12)

        # Audit status toggle
        status_label = QLabel("Audit Status:")
        status_label.setStyleSheet("color: #605e5c; font-size: 13px; font-weight: 500;")
        right_layout.addWidget(status_label)

        self.status_active = QPushButton("In Progress")
        self.status_active.setCheckable(True)
        self.status_active.setChecked(True)
        self.status_active.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
        """)
        self.status_active.clicked.connect(lambda: self._toggle_audit_status("active"))
        right_layout.addWidget(self.status_active)

        self.status_completed = QPushButton("Completed")
        self.status_completed.setCheckable(True)
        self.status_completed.setStyleSheet("""
            QPushButton {
                background-color: #edebe9;
                color: #605e5c;
                border: 1px solid #e1dfdd;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
        """)
        self.status_completed.clicked.connect(lambda: self._toggle_audit_status("completed"))
        right_layout.addWidget(self.status_completed)

        right_layout.addSpacing(20)

        # New Dataset button
        new_dataset_btn = QPushButton("+ New Dataset")
        new_dataset_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        new_dataset_btn.setCursor(Qt.PointingHandCursor)
        new_dataset_btn.clicked.connect(self.uploadRequested.emit)
        right_layout.addWidget(new_dataset_btn)

        # View Projects button (replaces "Open Workspace")
        projects_btn = QPushButton("View Projects →")
        projects_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #605e5c;
                border: 1px solid #d2d0ce;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #f3f2f1;
                border-color: #8a8886;
            }
        """)
        projects_btn.setCursor(Qt.PointingHandCursor)
        projects_btn.clicked.connect(self.viewProjectsRequested.emit)
        right_layout.addWidget(projects_btn)

        layout.addLayout(right_layout)

        return header

    def create_metrics_section(self):
        """Create the metrics cards section"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create metric cards with initial values
        metrics = [
            MetricCard("Total Datasets", "0", "Active in workspace", "📊"),
            MetricCard("Total Records", "0", "Across all datasets", "📈"),
            MetricCard("Data Quality", "0%", "Completion rate", "✓"),
            MetricCard("Last Audit", "Never", "", "📅"),
        ]

        # Store references to value labels for updates
        metric_titles = ["Total Datasets", "Total Records", "Data Quality", "Last Audit"]
        for i, card in enumerate(metrics):
            card.setMinimumHeight(160)
            layout.addWidget(card, 0, i)
            # Find the value label
            for child in card.findChildren(QLabel):
                if child.text() in metric_titles:
                    continue
                # Skip labels with icons or trends
                if child.text() and not any(c in child.text() for c in ["📊", "📈", "✓", "📅", "↑", "↓"]):
                    if "Just now" not in child.text() and "Never" not in child.text():
                        self.stat_labels[metric_titles[i]] = child
                        break
                elif child.text() in ["0", "0%", "Never"]:
                    # These are the value labels we want to track
                    self.stat_labels[metric_titles[i]] = child
                    break

        return widget

    def create_datasets_section(self):
        """Create the datasets section"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: none;
            }
        """)

        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 15))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Section header
        header_layout = QHBoxLayout()

        title = QLabel("Recent Datasets")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: #201f1e;
            }
        """)
        header_layout.addWidget(title)

        header_layout.addStretch()

        view_all = QLabel("<a href='#' style='color: #0078d4; text-decoration: none;'>View all →</a>")
        view_all.setStyleSheet("font-size: 13px; font-weight: 600;")
        view_all.setOpenExternalLinks(False)
        view_all.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(view_all)

        layout.addLayout(header_layout)

        # Dataset cards container layout
        self.datasets_layout = QVBoxLayout()
        self.datasets_layout.setSpacing(12)
        layout.addLayout(self.datasets_layout)

        # Initial empty state
        empty_label = QLabel("No datasets yet\nImport data to get started")
        empty_label.setStyleSheet("""
            QLabel {
                color: #605e5c;
                font-size: 13px;
                padding: 24px;
                text-align: center;
            }
        """)
        empty_label.setAlignment(Qt.AlignCenter)
        self.datasets_layout.addWidget(empty_label)

        return container

    def create_activity_section(self):
        """Create the recent activity section"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: none;
            }
        """)

        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 15))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)

        # Section header
        title = QLabel("Recent Activity")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: #201f1e;
                padding-bottom: 16px;
            }
        """)
        layout.addWidget(title)

        # Activity items
        self.activity_items = []
        for i in range(4):
            item = ActivityItem(
                "No activity yet",
                "",
                "",
                icon="📋"
            )
            item.hide()
            layout.addWidget(item)
            self.activity_items.append(item)

        # Add stretch to fill space
        layout.addStretch()

        return container

    def create_progress_section(self):
        """Create the audit progress section"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: none;
            }
        """)

        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 15))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Section header
        title = QLabel("Audit Progress")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: #201f1e;
            }
        """)
        layout.addWidget(title)

        # Progress bars container
        self.progress_layout = QVBoxLayout()
        self.progress_layout.setSpacing(16)
        layout.addLayout(self.progress_layout)

        # Initial empty progress bars
        for label in ["Data Collection", "Data Validation", "Analysis Complete", "Reports Generated"]:
            progress = ProgressBar(0, 100, label, "#0078d4")
            self.progress_layout.addWidget(progress)

        return container

    def add_activity(self, action: str, dataset_name: str = "", icon: str = "📁"):
        """Add a new activity to the dashboard"""
        from datetime import datetime

        activity = {
            "action": action,
            "dataset": dataset_name,
            "time": "Just now",
            "icon": icon
        }

        # Add to beginning of list
        self.activities.insert(0, activity)

        # Keep only last 10 activities
        self.activities = self.activities[:10]

        # Update activity display
        self._refresh_activities_display()

    def _refresh_activities_display(self):
        """Refresh the activity items display"""
        # Hide all items first
        for item in self.activity_items:
            item.hide()

        # Show activities (up to 4)
        for i, activity in enumerate(self.activities[:4]):
            if i < len(self.activity_items):
                item = self.activity_items[i]
                # Update the item content
                for child in item.findChildren(QLabel):
                    text = child.text()
                    if "<b>" in text:
                        child.setText(f"<b>{activity.get('action', 'Unknown')}</b>")
                    elif "rows" not in text and "cols" not in text and "Modified" not in text:
                        if child.text() and not any(c in child.text() for c in ["Just now", "Never"]):
                            # This is the dataset label
                            child.setText(activity.get("dataset", ""))
                        elif child.text() in ["Just now", "Never", ""] or ":" in child.text():
                            # This is the time label
                            child.setText(activity.get("time", ""))

                # Update icon
                for child in item.findChildren(QLabel):
                    if child.text() in ["📁", "📊", "📈", "✅", "🚀", "📋"]:
                        child.setText(activity.get("icon", "📁"))
                        break

                item.show()

    def refresh(self):
        """Refresh the dashboard display"""
        self._update_from_project()
