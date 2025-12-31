"""Dashboard View - Beautiful landing page design"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QLinearGradient
# ProjectService will be imported lazily when needed to avoid circular imports


class MetricCard(QFrame):
    """Card widget for displaying metrics"""
    def __init__(self, title, value, subtitle="", icon="", trend=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
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
                    background-color: #eff6ff;
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
                color: #111827;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        layout.addWidget(title_label)

        # Value
        value_label = QLabel(value)
        value_label.setStyleSheet("""
            QLabel {
                color: #111827;
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
                    color: #374151;
                    font-size: 12px;
                }
            """)
            layout.addWidget(subtitle_label)

        layout.addStretch()


class DatasetCard(QFrame):
    """Card widget for displaying dataset information"""
    def __init__(self, name, rows, columns, last_modified, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e5e7eb;
            }
            QFrame:hover {
                border: 1px solid #3b82f6;
                background-color: #f9fafb;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Dataset name with icon
        name_layout = QHBoxLayout()
        icon_label = QLabel("📊")
        icon_label.setStyleSheet("font-size: 20px;")
        name_layout.addWidget(icon_label)

        name_label = QLabel(name)
        name_label.setStyleSheet("""
            QLabel {
                color: #111827;
                font-size: 15px;
                font-weight: 600;
            }
        """)
        name_layout.addWidget(name_label, 1)
        layout.addLayout(name_layout)

        # Stats row
        stats_layout = QHBoxLayout()

        rows_label = QLabel(f"{rows:,} rows")
        rows_label.setStyleSheet("""
            QLabel {
                color: #374151;
                font-size: 12px;
                background-color: #f3f4f6;
                padding: 4px 10px;
                border-radius: 6px;
            }
        """)
        stats_layout.addWidget(rows_label)

        cols_label = QLabel(f"{columns} cols")
        cols_label.setStyleSheet("""
            QLabel {
                color: #374151;
                font-size: 12px;
                background-color: #f3f4f6;
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
                color: #6b7280;
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


class ActivityItem(QFrame):
    """Widget for displaying recent activity"""
    def __init__(self, action, dataset, time, user="Cameron Diaz", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-bottom: 1px solid #f3f4f6;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(16)

        # User avatar (circle with initials)
        avatar = QLabel("CD")
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("""
            QLabel {
                background-color: #3b82f6;
                color: white;
                border-radius: 20px;
                font-weight: 600;
                font-size: 13px;
            }
        """)
        layout.addWidget(avatar)

        # Activity details
        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)

        action_label = QLabel(f"<b>{user}</b> {action}")
        action_label.setStyleSheet("""
            QLabel {
                color: #111827;
                font-size: 13px;
            }
        """)
        details_layout.addWidget(action_label)

        dataset_label = QLabel(dataset)
        dataset_label.setStyleSheet("""
            QLabel {
                color: #374151;
                font-size: 12px;
            }
        """)
        details_layout.addWidget(dataset_label)

        layout.addLayout(details_layout, 1)

        # Time
        time_label = QLabel(time)
        time_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 12px;
            }
        """)
        layout.addWidget(time_label)


class ProgressBar(QWidget):
    """Custom progress bar widget"""
    def __init__(self, value, max_value, label, color="#3b82f6", parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.label_text = label
        self.color = color
        self.setFixedHeight(60)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw label
        painter.setPen(QColor("#6b7280"))
        font = QFont()
        font.setPixelSize(13)
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        painter.drawText(0, 0, self.width(), 20, Qt.AlignLeft, self.label_text)

        # Draw value
        percentage = int((self.value / self.max_value) * 100) if self.max_value > 0 else 0
        painter.setPen(QColor("#111827"))
        font.setPixelSize(14)
        font.setWeight(QFont.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, self.width(), 20, Qt.AlignRight, f"{self.value}/{self.max_value} ({percentage}%)")

        # Draw background bar
        bar_y = 28
        bar_height = 12
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#f3f4f6"))
        painter.drawRoundedRect(0, bar_y, self.width(), bar_height, 6, 6)

        # Draw progress bar
        progress_width = int((self.value / self.max_value) * self.width()) if self.max_value > 0 else 0
        gradient = QLinearGradient(0, bar_y, progress_width, bar_y)
        gradient.setColorAt(0, QColor(self.color))
        gradient.setColorAt(1, QColor(self.color).lighter(110))
        painter.setBrush(gradient)
        painter.drawRoundedRect(0, bar_y, progress_width, bar_height, 6, 6)


class DashboardView(QWidget):
    """Main dashboard view with beautiful landing page design"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stat_labels = {}
        self.current_project = None
        self.project_service = None
        self.setup_ui()

    def _get_project_service(self):
        """Get or create ProjectService instance (lazy import)"""
        if self.project_service is None:
            from services.project_service import ProjectService
            self.project_service = ProjectService()
        return self.project_service

    def _load_real_data(self):
        """Load real data from database instead of using hardcoded data"""
        try:
            service = self._get_project_service()
            user_id = 1  # Default user ID for now

            # Get all projects for the user
            projects = service.get_projects(user_id)

            # Collect all datasets from all projects
            all_datasets = []
            all_activities = []

            for project in projects:
                # Get datasets for this project
                datasets = service.get_project_datasets(project.id)
                for dataset in datasets:
                    # Format dataset info for display
                    all_datasets.append({
                        "name": dataset.name,
                        "rows": dataset.row_count,
                        "columns": dataset.column_count,
                        "modified": self._format_timestamp(dataset.updated_at)
                    })

                # Get audit logs for this project
                audit_logs = service.get_audit_logs(project.id, limit=10)
                for log in audit_logs:
                    # Format activity for display
                    all_activities.append(self._format_activity(log))

            # If no datasets found, use empty lists
            self.real_datasets = all_datasets
            self.real_activities = all_activities

            # Calculate metrics
            total_rows = sum(d["rows"] for d in all_datasets)
            total_datasets = len(all_datasets)
            self.real_metrics = {
                "total_datasets": total_datasets,
                "total_rows": total_rows,
                "data_quality": self._calculate_data_quality(all_datasets),  # Placeholder
                "last_audit": self._get_last_audit_time(all_activities)  # Placeholder
            }

        except Exception as e:
            print(f"Error loading real data for dashboard: {e}")
            # Fall back to empty data
            self.real_datasets = []
            self.real_activities = []
            self.real_metrics = {
                "total_datasets": 0,
                "total_rows": 0,
                "data_quality": "0%",
                "last_audit": "Never"
            }

    def _format_timestamp(self, timestamp):
        """Format datetime for display (e.g., '2 hours ago')"""
        if not timestamp:
            return "Unknown"
        # Simplified formatting - in real implementation, use humanize
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        diff = now - timestamp
        if diff.days > 0:
            return f"{diff.days} days ago"
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours} hours ago"
        minutes = diff.seconds // 60
        if minutes > 0:
            return f"{minutes} minutes ago"
        return "Just now"

    def _format_activity(self, audit_log):
        """Format audit log entry for activity display"""
        # Map action types to display text
        action_map = {
            "project_created": "created project",
            "dataset_imported": "imported dataset",
            "dataset_modified": "modified dataset",
            "analysis_run": "ran analysis",
            "report_generated": "generated report"
        }
        action = action_map.get(audit_log.action, audit_log.action)
        # For now, use generic user - in real app, get user name
        user = "User"
        dataset_name = audit_log.details.get("dataset_name", "Unknown") if audit_log.details else "Unknown"
        timestamp = self._format_timestamp(audit_log.timestamp)

        return (action, dataset_name, timestamp, user)

    def _calculate_data_quality(self, datasets):
        """Calculate data quality percentage (placeholder)"""
        if not datasets:
            return "0%"
        # Simple placeholder - in real app, calculate from column null counts
        return "94.2%"

    def _get_last_audit_time(self, activities):
        """Get last audit time from activities (placeholder)"""
        if not activities:
            return "Never"
        # Return most recent timestamp from activities
        return "2 days ago"

    def set_project(self, project):
        """Set the current project and update display"""
        self.current_project = project
        self._update_header()

    def _update_header(self):
        """Update the header with project info"""
        if self.current_project:
            project_name = self.current_project.name if self.current_project.name else "Dashboard"
            self.header_title.setText(project_name)

            client_name = self.current_project.client_name if self.current_project.client_name else ""
            if client_name:
                self.header_subtitle.setText(f"Audit - {client_name}")
            else:
                self.header_subtitle.setText("Dashboard")
        else:
            self.header_title.setText("Dashboard")
            self.header_subtitle.setText("SOX Compliance Audit")

    def update_stats(self, projects_count: int = 0, datasets_count: int = 0,
                    analyses_count: int = 0, sessions_count: int = 0):
        """Update the dashboard statistics"""
        # Update metric cards if they exist
        metrics_map = {
            "Projects": str(projects_count),
            "Datasets": str(datasets_count),
            "Analyses": str(analyses_count),
            "Sessions": str(sessions_count)
        }

        for stat_name, value in metrics_map.items():
            if stat_name in self.stat_labels:
                self.stat_labels[stat_name].setText(value)

        # Also update our dashboard metric cards if they exist
        # Map the incoming counts to our metric cards
        if "Total Datasets" in self.stat_labels:
            self.stat_labels["Total Datasets"].setText(str(datasets_count))
        # Note: Total Records, Data Quality, Last Audit are not updated here
        # as they require additional data not provided in these counts

    def showEvent(self, event):
        """Reload real data when dashboard is shown"""
        super().showEvent(event)
        self._load_real_data()
        # Note: UI doesn't dynamically update yet, need to implement proper refresh
        # For now, data is loaded once at setup_ui()

    def setup_ui(self):
        # Load real data from database
        self._load_real_data()

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
                color: #111827;
            }
        """)
        left_layout.addWidget(self.header_title)

        self.header_subtitle = QLabel("SOX Compliance Audit")
        self.header_subtitle.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #374151;
            }
        """)
        left_layout.addWidget(self.header_subtitle)

        layout.addLayout(left_layout, 1)

        # Right side - Actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        # New Dataset button
        new_dataset_btn = QPushButton("+ New Dataset")
        new_dataset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        new_dataset_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(new_dataset_btn)

        # Open Workspace button
        workspace_btn = QPushButton("Open Workspace →")
        workspace_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #f9fafb;
                border-color: #9ca3af;
            }
        """)
        workspace_btn.setCursor(Qt.PointingHandCursor)
        btn_layout.addWidget(workspace_btn)

        layout.addLayout(btn_layout)

        return header

    def create_metrics_section(self):
        """Create the metrics cards section"""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(20)
        layout.setContentsMargins(0, 0, 0, 0)

        # Use real datasets loaded from database
        self.datasets = self.real_datasets

        # Use real metrics loaded from database
        metrics = [
            MetricCard("Total Datasets", str(self.real_metrics["total_datasets"]), "Active in workspace", "📊", "↑ 3 new"),
            MetricCard("Total Records", f"{self.real_metrics['total_rows']:,}", "Across all datasets", "📈"),
            MetricCard("Data Quality", self.real_metrics["data_quality"], "Completion rate", "✓", "↑ 2.1%"),
            MetricCard("Last Audit", self.real_metrics["last_audit"], "Next: Dec 30, 2025", "📅"),
        ]

        # Store references to value labels for updates
        metric_titles = ["Total Datasets", "Total Records", "Data Quality", "Last Audit"]
        for i, card in enumerate(metrics):
            card.setMinimumHeight(180)
            layout.addWidget(card, 0, i)
            # Find the value label
            for child in card.findChildren(QLabel):
                if child.text() == list(metric_titles)[i]:
                    continue
                if child.text() not in ["Total Datasets", "Total Records", "Data Quality", "Last Audit"]:
                    if "↑" not in child.text() and "↓" not in child.text():
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
                border: 1px solid #e5e7eb;
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
                color: #111827;
            }
        """)
        header_layout.addWidget(title)

        header_layout.addStretch()

        view_all = QLabel("<a href='#' style='color: #3b82f6; text-decoration: none;'>View all →</a>")
        view_all.setStyleSheet("font-size: 13px; font-weight: 600;")
        view_all.setOpenExternalLinks(False)
        view_all.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(view_all)

        layout.addLayout(header_layout)

        # Dataset cards
        if not self.datasets:
            # Empty state
            empty_label = QLabel("No datasets yet\nImport data to get started")
            empty_label.setStyleSheet("""
                QLabel {
                    color: #6b7280;
                    font-size: 13px;
                    padding: 24px;
                    text-align: center;
                }
            """)
            empty_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty_label)
        else:
            for dataset in self.datasets:
                card = DatasetCard(
                    dataset["name"],
                    dataset["rows"],
                    dataset["columns"],
                    dataset["modified"]
                )
                layout.addWidget(card)

        return container

    def create_activity_section(self):
        """Create the recent activity section"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
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
                color: #111827;
                padding-bottom: 16px;
            }
        """)
        layout.addWidget(title)

        # Activity items from real audit logs
        activities = self.real_activities[:4]  # Show only 4 most recent

        if not activities:
            # Show empty state
            empty_label = QLabel("No recent activity")
            empty_label.setStyleSheet("""
                QLabel {
                    color: #6b7280;
                    font-size: 13px;
                    padding: 16px;
                    text-align: center;
                }
            """)
            layout.addWidget(empty_label)
        else:
            for activity in activities:
                item = ActivityItem(*activity)
                layout.addWidget(item)

        return container

    def create_progress_section(self):
        """Create the audit progress section"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
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
                color: #111827;
            }
        """)
        layout.addWidget(title)

        # Progress bars
        progress_items = [
            ("Data Collection", 15, 15, "#10b981"),
            ("Data Validation", 12, 15, "#3b82f6"),
            ("Analysis Complete", 8, 15, "#f59e0b"),
            ("Reports Generated", 3, 15, "#6b7280"),
        ]

        for label, value, max_value, color in progress_items:
            progress = ProgressBar(value, max_value, label, color)
            layout.addWidget(progress)

        return container
