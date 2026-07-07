"""
Sidebar for CaatMaster — the "Queries" pane.
Light, clean navigation with dataset management.

Structure follows the "Sidebar, Dashboard & Workspace Refresh" design
proposal: a project card, a dataset list with a real active-row state
(left accent rail + count badge), a Data/SQL Query segmented control
(they're mutually-exclusive modes, not menu items), and the action list
split into labeled, color-coded clusters (Combine / Analyze / Import /
Lineage & Export) instead of one flat, unsorted list.
"""
from typing import List

import qtawesome as qta
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QToolButton, QListWidget, QListWidgetItem,
    QScrollArea, QMenu, QSizePolicy
)

from gui.theme import Colors


def _icon(name: str, color: str = Colors.TEXT_SECONDARY):
    return qta.icon(name, color=color)


def _icon_chip(icon_name: str, bg: str, fg: str, size: int = 22) -> QIcon:
    """Compose a small rounded-square, tinted background behind a qtawesome
    glyph. Used to color-code sidebar action groups and the dataset row
    icon (e.g. blue for Combine, green for Analyze) so the list scans by
    color instead of everything being the same flat gray."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(bg))
    painter.drawRoundedRect(0, 0, size, size, 5, 5)
    glyph_size = size - 8
    glyph = qta.icon(icon_name, color=fg).pixmap(glyph_size, glyph_size)
    x = (size - glyph.width()) // 2
    y = (size - glyph.height()) // 2
    painter.drawPixmap(x, y, glyph)
    painter.end()
    return QIcon(pm)


class SidebarButton(QPushButton):
    """Custom styled button for sidebar. Pass icon_bg to give the icon a
    tinted chip background (used for the grouped action clusters); leave
    it unset for a plain flat-colored glyph (nav items, bottom buttons)."""
    def __init__(self, text, icon_name="", parent=None, icon_bg=None, icon_fg=None):
        super().__init__(parent)
        self.setText(f"  {text}")
        if icon_name:
            if icon_bg:
                self.setIcon(_icon_chip(icon_name, icon_bg, icon_fg or Colors.TEXT_SECONDARY, size=20))
                self.setIconSize(QSize(20, 20))
            else:
                self.setIcon(_icon(icon_name))
                self.setIconSize(QSize(14, 14))
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(34)
        self.update_style(False)

    def update_style(self, selected):
        if selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.ACCENT_SOFT};
                    color: {Colors.ACCENT_PRESSED};
                    border: none;
                    border-radius: 4px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {Colors.BG_SELECTED_STRONG};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Colors.TEXT_PRIMARY};
                    border: none;
                    border-radius: 4px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {Colors.BG_TERTIARY};
                    color: {Colors.TEXT_PRIMARY};
                }}
            """)


class SegmentedControl(QWidget):
    """A pill-style toggle between mutually-exclusive modes (Data / SQL
    Query) - these aren't items in an action menu, so they shouldn't look
    like menu buttons stacked in a list."""

    segmentClicked = Signal(str)  # segment key

    def __init__(self, segments: list, parent=None):
        """segments: list of (key, label) tuples."""
        super().__init__(parent)
        self._buttons = {}
        self._active_key = segments[0][0] if segments else None

        # A plain QWidget subclass doesn't paint its own QSS
        # background/border by default (unlike QFrame/QPushButton, which
        # Qt knows how to style natively) - without this, the container
        # falls back to whatever's behind it instead of the white pill.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SegmentedControl {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 9px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)

        for key, label in segments:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(28)
            btn.clicked.connect(lambda checked, k=key: self._on_clicked(k))
            layout.addWidget(btn, 1)
            self._buttons[key] = btn

        self.set_active(self._active_key)

    def _on_clicked(self, key):
        self.set_active(key)
        self.segmentClicked.emit(key)

    def set_active(self, key):
        self._active_key = key
        for k, btn in self._buttons.items():
            active = (k == key)
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Colors.ACCENT};
                        color: {Colors.TEXT_ON_ACCENT};
                        border: none;
                        border-radius: 6px;
                        font-size: 12.5px;
                        font-weight: 600;
                        padding: 6px 0px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {Colors.TEXT_PRIMARY};
                        border: none;
                        border-radius: 6px;
                        font-size: 12.5px;
                        font-weight: 600;
                        padding: 6px 0px;
                    }}
                    QPushButton:hover {{
                        background-color: {Colors.BG_TERTIARY};
                    }}
                """)


class DatasetRowWidget(QWidget):
    """A single row in the sidebar's dataset list - an icon chip, the
    dataset name, and a quiet row-count badge, with a real active state
    (left accent rail + accent-colored bold name) instead of relying on
    QListWidget's native selection highlight, which has no way to draw a
    rail. setItemWidget() doesn't forward mouse clicks to the list's own
    selection handling, so this widget resolves and emits them itself."""

    clicked = Signal()
    doubleClicked = Signal()

    def __init__(self, name: str, row_count: int, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_Hover, True)
        # Same reason as SegmentedControl - a plain QWidget needs this to
        # actually paint its own QSS background/border at all, otherwise
        # hover and the active-row rail silently don't render.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self._active = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(22, 22)
        layout.addWidget(self.icon_label)

        self.name_label = QLabel(name)
        layout.addWidget(self.name_label, 1)

        self.count_label = QLabel(f"{row_count:,}")
        self.count_label.setStyleSheet(f"""
            QLabel {{
                font-size: 10.5px;
                color: {Colors.TEXT_TERTIARY};
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 1px 7px;
            }}
        """)
        layout.addWidget(self.count_label)

        self._apply_style()

    def set_active(self, active: bool):
        if active == self._active:
            return
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.icon_label.setPixmap(
                _icon_chip("fa5s.table", Colors.BG_SELECTED_STRONG, Colors.ACCENT).pixmap(22, 22)
            )
            self.name_label.setStyleSheet(f"font-size: 12.5px; font-weight: 700; color: {Colors.ACCENT};")
            self.setStyleSheet(f"""
                DatasetRowWidget {{
                    background-color: {Colors.BG_PRIMARY};
                    border-left: 3px solid {Colors.ACCENT};
                    border-radius: 4px;
                }}
            """)
        else:
            self.icon_label.setPixmap(
                _icon_chip("fa5s.table", Colors.BG_TERTIARY, Colors.TEXT_TERTIARY).pixmap(22, 22)
            )
            self.name_label.setStyleSheet(f"font-size: 12.5px; font-weight: 500; color: {Colors.TEXT_PRIMARY};")
            self.setStyleSheet(f"""
                DatasetRowWidget {{
                    background-color: transparent;
                    border-left: 3px solid transparent;
                    border-radius: 4px;
                }}
                DatasetRowWidget:hover {{
                    background-color: {Colors.BG_TERTIARY};
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


class Sidebar(QFrame):
    """Main sidebar widget for CaatMaster navigation with dataset management"""

    # Navigation signals
    navigation_requested = Signal(str)  # view_name
    dataset_selected = Signal(str)  # dataset_id
    dataset_rename_requested = Signal(str)  # dataset_id
    dataset_duplicate_requested = Signal(str)  # dataset_id
    dataset_delete_requested = Signal(str)  # dataset_id
    dataset_split_sheet_requested = Signal(str)  # dataset_id
    dataset_refresh_requested = Signal(str)  # dataset_id
    dataset_visualize_requested = Signal(str)  # dataset_id
    join_datasets_requested = Signal(str)  # source_dataset_id
    append_datasets_requested = Signal(str)  # source_dataset_id
    compare_datasets_requested = Signal(str)  # source_dataset_id
    fuzzy_match_datasets_requested = Signal(str)  # source_dataset_id
    profile_dataset_requested = Signal(str)  # source_dataset_id
    import_folder_listing_requested = Signal()
    verify_data_requested = Signal(str)  # source_dataset_id
    cvs_dialog_requested = Signal(str)  # source_dataset_id (may be None)
    upload_requested = Signal()  # Request to upload dataset
    cleaning_wizard_requested = Signal()  # Request to open the Data Cleaning Wizard
    financial_import_wizard_requested = Signal()  # Request to open the Financial Data Import Wizard
    paste_requested = Signal()  # Request to create a dataset from clipboard
    project_edit_requested = Signal()  # Request to edit current project
    project_delete_requested = Signal()  # Request to delete current project
    toggle_ai_panel = Signal()  # Request to toggle AI panel visibility
    audit_programs_requested = Signal()  # Request to open the Audit Programs gallery

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.current_project = None
        self.current_dataset_id = None
        self.dataset_items = {}  # dataset_id -> list widget item
        self.dataset_row_widgets = {}  # dataset_id -> DatasetRowWidget
        self._setup_ui()

    def set_project(self, project):
        """Set the current project and update sidebar display"""
        self.current_project = project
        self._update_project_info()
        self._update_datasets_list()

    def _update_project_info(self):
        """Update the project info labels"""
        if self.current_project:
            project_name = self.current_project.name if self.current_project.name else "No Project Selected"
            self.project_label.setText(project_name)

            client_name = self.current_project.client_name if self.current_project.client_name else "No Client"
            self.client_label.setText(client_name)

            self.edit_project_btn.setVisible(True)
            self.delete_project_btn.setVisible(True)
        else:
            self.project_label.setText("No Project Selected")
            self.client_label.setText("No Client")

            self.edit_project_btn.setVisible(False)
            self.delete_project_btn.setVisible(False)

    def _update_datasets_list(self):
        """Update the datasets list with current project's datasets"""
        self.datasets_list.clear()
        self.dataset_items.clear()
        self.dataset_row_widgets.clear()

        if not self.current_project:
            return

        datasets = self.current_project.list_datasets()

        if not datasets:
            return

        for dataset in datasets:
            self._add_dataset_row(dataset)

        if datasets and not self.current_dataset_id:
            self.current_dataset_id = datasets[0].id
        self._refresh_active_dataset_visual()

    def _add_dataset_row(self, dataset):
        """Create the list item + custom row widget for one dataset and
        wire up its click/double-click signals."""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, dataset.id)
        item.setSizeHint(QSize(0, 36))

        row_count = dataset.metadata.get('row_count', 0)
        row_widget = DatasetRowWidget(dataset.name, row_count)
        row_widget.clicked.connect(lambda ds_id=dataset.id: self._on_dataset_row_clicked(ds_id))
        row_widget.doubleClicked.connect(lambda ds_id=dataset.id: self._on_dataset_row_double_clicked(ds_id))

        self.datasets_list.addItem(item)
        self.datasets_list.setItemWidget(item, row_widget)
        self.dataset_items[dataset.id] = item
        self.dataset_row_widgets[dataset.id] = row_widget

    def _refresh_active_dataset_visual(self):
        """Update every dataset row's active/inactive visual state to match
        self.current_dataset_id - the left accent rail, bold accent text,
        and tinted icon chip all live on the row widget, not on the list
        item's native (rail-less) selection highlight."""
        for ds_id, row_widget in self.dataset_row_widgets.items():
            row_widget.set_active(ds_id == self.current_dataset_id)

    def select_dataset(self, dataset_id: str):
        """Highlight a specific dataset in the list — used when reopening a
        project to resume on whichever dataset was active when it was last
        saved, instead of always defaulting to the first one."""
        item = self.dataset_items.get(dataset_id)
        if item:
            self.current_dataset_id = dataset_id
            self.datasets_list.setCurrentItem(item)
            self._refresh_active_dataset_visual()

    def _on_dataset_row_clicked(self, dataset_id: str):
        """Handle a click on a dataset row widget (setItemWidget doesn't
        forward clicks to the list's native selection, so this replaces
        itemClicked for dataset rows)."""
        self.current_dataset_id = dataset_id
        item = self.dataset_items.get(dataset_id)
        if item:
            self.datasets_list.setCurrentItem(item)
        self._refresh_active_dataset_visual()
        self.dataset_selected.emit(dataset_id)

    def _on_dataset_row_double_clicked(self, dataset_id: str):
        """Handle a double-click on a dataset row - navigate to transform view"""
        self._on_dataset_row_clicked(dataset_id)
        self.navigation_requested.emit("transform")

    def _on_datasetContextMenu(self, pos):
        """Handle right-click context menu for dataset items"""
        from PySide6.QtGui import QAction

        item = self.datasets_list.itemAt(pos)
        if not item:
            return

        dataset_id = item.data(Qt.UserRole)
        row_widget = self.dataset_row_widgets.get(dataset_id)
        dataset_name = row_widget.name_label.text() if row_widget else ""

        menu = QMenu(self)

        info_action = QAction(_icon("fa5s.table", color=Colors.TEXT_TERTIARY), dataset_name, self)
        info_action.setEnabled(False)
        menu.addAction(info_action)
        menu.addSeparator()

        view_action = QAction(_icon("fa5s.eye"), "View Data", self)
        view_action.triggered.connect(lambda: self.dataset_selected.emit(dataset_id))
        menu.addAction(view_action)

        rename_action = QAction(_icon("fa5s.pen"), "Rename", self)
        rename_action.triggered.connect(lambda: self.dataset_rename_requested.emit(dataset_id))
        menu.addAction(rename_action)

        duplicate_action = QAction(_icon("fa5s.clone"), "Duplicate", self)
        duplicate_action.triggered.connect(lambda: self.dataset_duplicate_requested.emit(dataset_id))
        menu.addAction(duplicate_action)

        split_action = QAction(_icon("fa5s.cut"), "Split Sheet", self)
        split_action.triggered.connect(lambda: self.dataset_split_sheet_requested.emit(dataset_id))
        menu.addAction(split_action)

        refresh_action = QAction(_icon("fa5s.sync-alt"), "Refresh from Source", self)
        refresh_action.triggered.connect(lambda: self.dataset_refresh_requested.emit(dataset_id))
        menu.addAction(refresh_action)

        visualize_action = QAction(_icon("fa5s.chart-bar"), "Visualize This Dataset...", self)
        visualize_action.triggered.connect(lambda: self.dataset_visualize_requested.emit(dataset_id))
        menu.addAction(visualize_action)

        menu.addSeparator()

        delete_action = QAction(_icon("fa5s.trash-alt", color=Colors.DANGER), "Delete", self)
        delete_action.triggered.connect(lambda: self.dataset_delete_requested.emit(dataset_id))
        menu.addAction(delete_action)

        # Menu styling comes from the global stylesheet (QMenu rules in gui.theme)
        menu.exec_(self.mapToGlobal(pos))

    def _setup_ui(self):
        """Setup the sidebar UI"""
        self.setObjectName("Sidebar")
        # Scoped to #Sidebar specifically - QLabel is itself a QFrame
        # subclass in Qt, so a blanket "QFrame { background-color: ... }"
        # here would cascade down and paint that same solid fill behind
        # every QLabel anywhere in the sidebar (project card, dataset
        # names, row-count text, section headers - all of them).
        self.setStyleSheet(f"""
            QFrame#Sidebar {{
                background-color: {Colors.BG_SECONDARY};
                border-right: 1px solid {Colors.BORDER};
            }}
            QListWidget {{
                background-color: transparent;
                border: none;
            }}
            QListWidget::item {{
                background-color: transparent;
                border: none;
                padding: 0px;
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QToolTip {{
                background-color: {Colors.TEXT_PRIMARY};
                color: {Colors.BG_PRIMARY};
                border: none;
                padding: 4px 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMinimumHeight(200)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        scroll_content = QWidget()
        scroll_content.setObjectName("SidebarScrollContent")
        scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Scoped to its own objectName - an unscoped, no-selector
        # setStyleSheet() call here doesn't just paint this one widget, it
        # cascades its background down to every descendant QLabel (since
        # QLabel is itself a QFrame in Qt), which is exactly what caused
        # the project card and dataset rows to show a solid gray fill
        # behind their text instead of transparent labels.
        scroll_content.setStyleSheet(f"QWidget#SidebarScrollContent {{ background-color: {Colors.BG_SECONDARY}; }}")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 8, 16, 16)
        scroll_layout.setSpacing(8)

        section_label_style = f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
        """

        # ---------------------------------------------------------------
        # Project card - a distinct raised card instead of plain labels
        # blended into the sidebar background.
        # ---------------------------------------------------------------
        project_card = QFrame()
        project_card.setObjectName("ProjectCard")
        # Scoped to #ProjectCard specifically - QLabel is itself a QFrame
        # subclass in Qt, so a blanket "QFrame { border: ... }" selector
        # here would cascade down and draw the same outline around every
        # QLabel nested inside this card too.
        project_card.setStyleSheet(f"""
            QFrame#ProjectCard {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        project_card_layout = QVBoxLayout(project_card)
        project_card_layout.setContentsMargins(12, 10, 12, 10)
        project_card_layout.setSpacing(2)

        project_label_tag = QLabel("PROJECT")
        project_label_tag.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """)
        project_card_layout.addWidget(project_label_tag)

        project_row = QHBoxLayout()
        project_row.setContentsMargins(0, 0, 0, 0)
        project_row.setSpacing(8)

        self.project_label = QLabel("No Project Selected")
        self.project_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13.5px;
                font-weight: 700;
            }}
        """)
        project_row.addWidget(self.project_label, 1)

        self.project_actions_widget = QWidget()
        project_actions_layout = QHBoxLayout(self.project_actions_widget)
        project_actions_layout.setContentsMargins(0, 0, 0, 0)
        project_actions_layout.setSpacing(4)

        def _small_icon_button(icon_name):
            btn = QToolButton()
            btn.setFixedSize(22, 22)
            btn.setIcon(_icon(icon_name, color=Colors.TEXT_TERTIARY))
            btn.setIconSize(QSize(12, 12))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                }}
                QToolButton:hover {{
                    background-color: {Colors.BG_TERTIARY};
                }}
            """)
            return btn

        self.edit_project_btn = _small_icon_button("fa5s.pen")
        self.edit_project_btn.clicked.connect(self.project_edit_requested.emit)
        self.edit_project_btn.setVisible(False)
        project_actions_layout.addWidget(self.edit_project_btn)

        self.delete_project_btn = _small_icon_button("fa5s.trash-alt")
        self.delete_project_btn.clicked.connect(self.project_delete_requested.emit)
        self.delete_project_btn.setVisible(False)
        project_actions_layout.addWidget(self.delete_project_btn)

        project_row.addWidget(self.project_actions_widget)
        project_card_layout.addLayout(project_row)

        self.client_label = QLabel("No Client")
        self.client_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 11.5px;
            }}
        """)
        project_card_layout.addWidget(self.client_label)

        scroll_layout.addWidget(project_card)

        # ---------------------------------------------------------------
        # Datasets section
        # ---------------------------------------------------------------
        datasets_header = QHBoxLayout()

        datasets_label = QLabel("DATASETS")
        datasets_label.setStyleSheet(section_label_style.replace("}", "padding-top: 16px; }"))
        datasets_header.addWidget(datasets_label)

        datasets_header.addStretch()

        add_dataset_btn = QToolButton()
        add_dataset_btn.setFixedSize(22, 22)
        add_dataset_btn.setIcon(_icon("fa5s.plus", color=Colors.TEXT_ON_ACCENT))
        add_dataset_btn.setIconSize(QSize(11, 11))
        add_dataset_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {Colors.ACCENT};
                border: none;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: {Colors.ACCENT_HOVER};
            }}
            QToolTip {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 4px 8px;
            }}
        """)
        add_dataset_btn.setCursor(Qt.PointingHandCursor)
        add_dataset_btn.clicked.connect(self.upload_requested.emit)
        add_dataset_btn.setToolTip("Import a dataset from file")
        datasets_header.addWidget(add_dataset_btn)

        paste_dataset_btn = QToolButton()
        paste_dataset_btn.setFixedSize(22, 22)
        paste_dataset_btn.setIcon(_icon("fa5s.paste", color=Colors.TEXT_TERTIARY))
        paste_dataset_btn.setIconSize(QSize(11, 11))
        paste_dataset_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
            QToolTip {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 4px 8px;
            }}
        """)
        paste_dataset_btn.setCursor(Qt.PointingHandCursor)
        paste_dataset_btn.clicked.connect(self.paste_requested.emit)
        paste_dataset_btn.setToolTip("Paste a dataset from clipboard (Ctrl+Shift+V)")
        datasets_header.addWidget(paste_dataset_btn)

        cleaning_wizard_btn = QToolButton()
        cleaning_wizard_btn.setFixedSize(22, 22)
        cleaning_wizard_btn.setIcon(_icon("fa5s.magic", color=Colors.TEXT_TERTIARY))
        cleaning_wizard_btn.setIconSize(QSize(11, 11))
        cleaning_wizard_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
            QToolTip {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 4px 8px;
            }}
        """)
        cleaning_wizard_btn.setCursor(Qt.PointingHandCursor)
        cleaning_wizard_btn.clicked.connect(self.cleaning_wizard_requested.emit)
        cleaning_wizard_btn.setToolTip("Import & Clean... (Data Cleaning Wizard for messy files)")
        datasets_header.addWidget(cleaning_wizard_btn)

        financial_wizard_btn = QToolButton()
        financial_wizard_btn.setFixedSize(22, 22)
        financial_wizard_btn.setIcon(_icon("fa5s.file-invoice-dollar", color=Colors.TEXT_TERTIARY))
        financial_wizard_btn.setIconSize(QSize(11, 11))
        financial_wizard_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
            QToolTip {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 4px 8px;
            }}
        """)
        financial_wizard_btn.setCursor(Qt.PointingHandCursor)
        financial_wizard_btn.clicked.connect(self.financial_import_wizard_requested.emit)
        financial_wizard_btn.setToolTip(
            "Import Financial Data... (GL/JE detail, trial balance, financial statement, chart of accounts)"
        )
        datasets_header.addWidget(financial_wizard_btn)

        datasets_header_widget = QWidget()
        datasets_header_widget.setLayout(datasets_header)
        scroll_layout.addWidget(datasets_header_widget)

        # Datasets list
        self.datasets_list = QListWidget()
        self.datasets_list.setMinimumHeight(100)
        self.datasets_list.setMaximumHeight(300)
        self.datasets_list.setSelectionMode(QListWidget.NoSelection)
        self.datasets_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.datasets_list.customContextMenuRequested.connect(self._on_datasetContextMenu)
        scroll_layout.addWidget(self.datasets_list)

        # ---------------------------------------------------------------
        # Workspace mode - Data / SQL Query are mutually-exclusive modes,
        # not menu items, so they get a segmented control instead of two
        # stacked buttons.
        # ---------------------------------------------------------------
        mode_label = QLabel("WORKSPACE MODE")
        mode_label.setStyleSheet(section_label_style.replace("}", "padding: 16px 0px 8px 0px; }"))
        scroll_layout.addWidget(mode_label)

        self.workspace_mode_control = SegmentedControl([("data", "Data"), ("sql", "SQL Query")])
        self.workspace_mode_control.segmentClicked.connect(self.navigation_requested.emit)
        scroll_layout.addWidget(self.workspace_mode_control)

        # ---------------------------------------------------------------
        # Actions - grouped into labeled, color-coded clusters instead of
        # one flat list (the original "junk drawer" problem: ten features
        # all landed in a single undifferentiated "Actions" section).
        # ---------------------------------------------------------------
        def _group_label(text):
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(f"""
                QLabel {{
                    color: {Colors.TEXT_PRIMARY};
                    font-size: 10px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                    padding: 14px 0px 6px 0px;
                    border-bottom: 1px solid {Colors.BORDER};
                    margin-bottom: 2px;
                }}
            """)
            return lbl

        # Combine - accent tint
        scroll_layout.addWidget(_group_label("Combine"))

        self.join_datasets_btn = SidebarButton(
            "Join Datasets", "fa5s.link", icon_bg=Colors.ACCENT_SOFT, icon_fg=Colors.ACCENT)
        self.join_datasets_btn.clicked.connect(self._on_join_datasets_clicked)
        scroll_layout.addWidget(self.join_datasets_btn)

        self.append_datasets_btn = SidebarButton(
            "Append Datasets", "fa5s.layer-group", icon_bg=Colors.ACCENT_SOFT, icon_fg=Colors.ACCENT)
        self.append_datasets_btn.clicked.connect(self._on_append_datasets_clicked)
        scroll_layout.addWidget(self.append_datasets_btn)

        self.compare_datasets_btn = SidebarButton(
            "Compare Datasets", "fa5s.not-equal", icon_bg=Colors.ACCENT_SOFT, icon_fg=Colors.ACCENT)
        self.compare_datasets_btn.clicked.connect(self._on_compare_datasets_clicked)
        scroll_layout.addWidget(self.compare_datasets_btn)

        self.fuzzy_match_btn = SidebarButton(
            "Fuzzy Match Datasets", "fa5s.search-plus", icon_bg=Colors.ACCENT_SOFT, icon_fg=Colors.ACCENT)
        self.fuzzy_match_btn.clicked.connect(self._on_fuzzy_match_datasets_clicked)
        scroll_layout.addWidget(self.fuzzy_match_btn)

        # Analyze - success tint
        scroll_layout.addWidget(_group_label("Analyze"))

        self.profile_dataset_btn = SidebarButton(
            "Profile Dataset", "fa5s.chart-bar", icon_bg=Colors.SUCCESS_SOFT, icon_fg=Colors.SUCCESS)
        self.profile_dataset_btn.clicked.connect(self._on_profile_dataset_clicked)
        scroll_layout.addWidget(self.profile_dataset_btn)

        self.verify_data_btn = SidebarButton(
            "Verify Data", "fa5s.check-double", icon_bg=Colors.SUCCESS_SOFT, icon_fg=Colors.SUCCESS)
        self.verify_data_btn.clicked.connect(self._on_verify_data_clicked)
        scroll_layout.addWidget(self.verify_data_btn)

        self.cvs_dialog_btn = SidebarButton(
            "Variables Sampling", "fa5s.calculator", icon_bg=Colors.SUCCESS_SOFT, icon_fg=Colors.SUCCESS)
        self.cvs_dialog_btn.clicked.connect(self._on_cvs_dialog_clicked)
        scroll_layout.addWidget(self.cvs_dialog_btn)

        self.audit_programs_btn = SidebarButton(
            "Audit Programs", "fa5s.clipboard-list", icon_bg=Colors.SUCCESS_SOFT, icon_fg=Colors.SUCCESS)
        self.audit_programs_btn.clicked.connect(self.audit_programs_requested.emit)
        scroll_layout.addWidget(self.audit_programs_btn)

        # Import - warning tint
        scroll_layout.addWidget(_group_label("Import"))

        self.import_folder_listing_btn = SidebarButton(
            "Import Folder Listing", "fa5s.folder-open", icon_bg=Colors.WARNING_SOFT, icon_fg=Colors.WARNING_STRONG)
        self.import_folder_listing_btn.clicked.connect(self.import_folder_listing_requested.emit)
        scroll_layout.addWidget(self.import_folder_listing_btn)

        # Lineage & Export - neutral tint
        scroll_layout.addWidget(_group_label("Lineage & Export"))

        self.project_lineage_btn = SidebarButton(
            "Project Lineage", "fa5s.project-diagram", icon_bg=Colors.BG_TERTIARY, icon_fg=Colors.TEXT_SECONDARY)
        self.project_lineage_btn.clicked.connect(lambda: self.navigation_requested.emit("project_lineage"))
        scroll_layout.addWidget(self.project_lineage_btn)

        self.export_review_btn = SidebarButton(
            "Export for Review", "fa5s.share-square", icon_bg=Colors.BG_TERTIARY, icon_fg=Colors.TEXT_SECONDARY)
        self.export_review_btn.clicked.connect(lambda: self.navigation_requested.emit("export_review"))
        scroll_layout.addWidget(self.export_review_btn)

        scroll_layout.addSpacing(16)

        # Bottom buttons (INSIDE scroll area for full scrollability)
        self.back_btn = SidebarButton("Projects", "fa5s.folder")
        self.back_btn.setCheckable(False)
        self.back_btn.clicked.connect(lambda: self.navigation_requested.emit("projects"))
        scroll_layout.addWidget(self.back_btn)

        self.settings_btn = SidebarButton("Settings", "fa5s.cog")
        self.settings_btn.setCheckable(False)
        self.settings_btn.clicked.connect(lambda: self.navigation_requested.emit("settings"))
        scroll_layout.addWidget(self.settings_btn)

        self.ai_btn = SidebarButton("AI Assistant", "fa5s.robot")
        self.ai_btn.setCheckable(False)
        self.ai_btn.clicked.connect(self.toggle_ai_panel.emit)
        scroll_layout.addWidget(self.ai_btn)

        scroll_layout.addSpacing(16)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def set_active_button(self, button_name):
        """Set the active navigation button"""
        button_map = {
            "data": "data",
            "transform": "data",  # Share Data button highlight
            "sql": "sql",
        }
        if button_name in button_map:
            self.workspace_mode_control.set_active(button_map[button_name])

    def add_dataset(self, dataset):
        """Add a dataset to the sidebar list"""
        if not self.current_project:
            return

        self._add_dataset_row(dataset)

        self.current_dataset_id = dataset.id
        self._refresh_active_dataset_visual()
        self.dataset_selected.emit(dataset.id)

    def _on_join_datasets_clicked(self):
        """Handle Join Datasets button click"""
        if self.current_dataset_id:
            self.join_datasets_requested.emit(self.current_dataset_id)
        else:
            self.join_datasets_requested.emit(None)

    def _on_append_datasets_clicked(self):
        """Handle Append Datasets button click"""
        if self.current_dataset_id:
            self.append_datasets_requested.emit(self.current_dataset_id)
        else:
            self.append_datasets_requested.emit(None)

    def _on_compare_datasets_clicked(self):
        """Handle Compare Datasets button click"""
        if self.current_dataset_id:
            self.compare_datasets_requested.emit(self.current_dataset_id)
        else:
            self.compare_datasets_requested.emit(None)

    def _on_fuzzy_match_datasets_clicked(self):
        """Handle Fuzzy Match Datasets button click"""
        if self.current_dataset_id:
            self.fuzzy_match_datasets_requested.emit(self.current_dataset_id)
        else:
            self.fuzzy_match_datasets_requested.emit(None)

    def _on_profile_dataset_clicked(self):
        """Handle Profile Dataset button click"""
        if self.current_dataset_id:
            self.profile_dataset_requested.emit(self.current_dataset_id)
        else:
            self.profile_dataset_requested.emit(None)

    def _on_verify_data_clicked(self):
        """Handle Verify Data button click"""
        if self.current_dataset_id:
            self.verify_data_requested.emit(self.current_dataset_id)
        else:
            self.verify_data_requested.emit(None)

    def _on_cvs_dialog_clicked(self):
        """Handle Variables Sampling button click"""
        if self.current_dataset_id:
            self.cvs_dialog_requested.emit(self.current_dataset_id)
        else:
            self.cvs_dialog_requested.emit(None)

    def get_dataset_names(self) -> List[str]:
        """Get list of dataset names in the current project"""
        if not self.current_project:
            return []
        return [ds.name for ds in self.current_project.list_datasets()]
