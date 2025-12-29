"""
RIBBON INTERFACE COMPONENTS
============================
This file contains all the components needed to create a Microsoft-style 
ribbon interface in PySide6, similar to Power Query and Microsoft 365 apps.

Components included:
- RibbonButton: Large button with icon and text underneath
- SmallRibbonButton: Compact button for secondary actions
- RibbonTab: Tab selector at the top of the ribbon
- RibbonGroup: Container for related buttons with a label
- RibbonBar: Main ribbon container with tabs and content areas
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QStackedWidget, QButtonGroup, QToolButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPainter


# ============================================================================
# RIBBON BUTTON COMPONENTS
# ============================================================================

class RibbonButton(QToolButton):
    """
    Large button for ribbon interface with icon on top and text underneath.

    Similar to Excel's primary ribbon buttons.

    Args:
        text (str): Button text displayed under the icon
        icon (str): Emoji or character to display as icon
        parent (QWidget): Parent widget

    Example:
        button = RibbonButton("Save", "💾")
        button.clicked.connect(self.save_file)
    """
    def __init__(self, text, icon="", parent=None):
        super().__init__(parent)
        self.setText(text)

        # This makes text appear below the icon
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setCursor(Qt.PointingHandCursor)

        # Store icon text for custom painting
        if icon:
            self.icon_text = icon

        # Styling - Microsoft-style with tighter spacing
        self.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 2px 6px;
                color: #323130;
                font-size: 11px;
                min-width: 56px;
                min-height: 52px;
            }
            QToolButton:hover {
                background-color: #eff6fc;
                border: 1px solid #c7e0f4;
            }
            QToolButton:pressed, QToolButton:checked {
                background-color: #deecf9;
                border: 1px solid #2b579a;
            }
        """)
    
    def paintEvent(self, event):
        """
        Custom paint event to draw the icon text.
        This is called automatically by Qt when the widget needs to be redrawn.
        """
        # Draw icon text if present
        if hasattr(self, 'icon_text'):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            # Set font for icon (larger than text)
            font = QFont()
            font.setPixelSize(18)
            painter.setFont(font)

            # Use Microsoft-blue for icon when hovered/pressed, dark gray otherwise
            if self.isDown() or self.isChecked():
                painter.setPen(QColor("#005a9e"))
            else:
                painter.setPen(QColor("#605e5c"))

            # Draw icon in upper portion of button
            icon_rect = self.rect()
            icon_rect.setHeight(24)
            icon_rect.adjust(0, 2, 0, 0)
            painter.drawText(icon_rect, Qt.AlignCenter, self.icon_text)

        # Call parent paint event to draw the text underneath
        super().paintEvent(event)


class SmallRibbonButton(QPushButton):
    """
    Small button for ribbon interface - used for secondary actions.

    These are typically stacked 2-3 high in a ribbon group.

    Args:
        text (str): Button text
        icon (str): Optional icon to display before text
        parent (QWidget): Parent widget

    Example:
        button = SmallRibbonButton("Cut", "✂")
        button.clicked.connect(self.cut_selection)
    """
    def __init__(self, text, icon="", parent=None):
        super().__init__(parent)

        # Add icon before text if provided
        if icon:
            self.setText(f"{icon} {text}")
        else:
            self.setText(text)

        self.setCursor(Qt.PointingHandCursor)

        # Styling - more compact, Microsoft-style
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 2px 8px 2px 6px;
                color: #323130;
                font-size: 12px;
                text-align: left;
                min-height: 22px;
                min-width: 0;
            }
            QPushButton:hover {
                background-color: #eff6fc;
                border: 1px solid #c7e0f4;
            }
            QPushButton:pressed, QPushButton:checked {
                background-color: #deecf9;
                border: 1px solid #2b579a;
            }
        """)


# ============================================================================
# RIBBON TAB COMPONENT
# ============================================================================

class RibbonTab(QPushButton):
    """
    Tab button for ribbon - appears at the top to switch between ribbon pages.

    Args:
        text (str): Tab label
        parent (QWidget): Parent widget

    Example:
        home_tab = RibbonTab("Home")
        home_tab.clicked.connect(lambda: self.switch_to_home())
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)  # Tabs can be selected/deselected
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)  # Remove default button styling
        self.update_style(False)  # Start unselected

    def update_style(self, selected):
        """
        Update the visual style based on selection state.

        Args:
            selected (bool): Whether this tab is currently selected
        """
        if selected:
            # Active tab style - white background with blue underline
            self.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #323130;
                    border: none;
                    border-bottom: 2px solid #0078d4;
                    padding: 6px 12px 4px 12px;
                    font-size: 12px;
                    font-weight: 600;
                    margin-bottom: -1px;
                }
            """)
        else:
            # Inactive tab style - transparent with hover effect
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #605e5c;
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 6px 12px 4px 12px;
                    font-size: 12px;
                    font-weight: 500;
                    margin-bottom: -1px;
                }
                QPushButton:hover {
                    background-color: #f3f2f1;
                    color: #323130;
                }
            """)


# ============================================================================
# RIBBON GROUP COMPONENT
# ============================================================================

class RibbonGroup(QFrame):
    """
    Group of related buttons in a ribbon, with a label at the bottom.

    This is like the sections in Excel ribbon (e.g., "Font", "Alignment", "Number").

    Args:
        title (str): Label for this group
        parent (QWidget): Parent widget

    Example:
        sort_group = RibbonGroup("Sort")
        sort_group.add_button(RibbonButton("Sort A-Z", "↑"))
        sort_group.add_button(RibbonButton("Sort Z-A", "↓"))
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)

        # Styling - Microsoft-style with refined separator
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-right: 1px solid #e1dfdd;
            }
        """)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 9, 4)
        layout.setSpacing(2)

        # Content area where buttons will be added
        self.content_layout = QHBoxLayout()
        self.content_layout.setSpacing(2)
        layout.addLayout(self.content_layout, 1)

        # Title label at the bottom
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #605e5c;
                font-size: 11px;
                font-weight: 500;
                padding-top: 0px;
            }
        """)
        layout.addWidget(title_label)
    
    def add_button(self, button):
        """
        Add a button to this group.
        
        Args:
            button: RibbonButton or SmallRibbonButton instance
        """
        self.content_layout.addWidget(button)
    
    def add_layout(self, layout):
        """
        Add a layout to this group (useful for stacking small buttons).
        
        Args:
            layout: QLayout instance containing buttons
        """
        self.content_layout.addLayout(layout)


# ============================================================================
# MAIN RIBBON BAR
# ============================================================================

class RibbonBar(QFrame):
    """
    Main ribbon bar containing tabs and groups - the complete ribbon interface.

    This is the top-level container that holds everything:
    - Tab buttons at the top
    - Content areas for each tab
    - All the groups and buttons within each tab

    Example:
        ribbon = RibbonBar()
        # Ribbon automatically creates tabs and content
        # Access specific tabs to customize them
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main styling - Microsoft Fluent colors
        self.setStyleSheet("""
            QFrame {
                background-color: #f3f2f1;
                border-bottom: 1px solid #e1dfdd;
            }
        """)

        # Main layout (vertical: tabs on top, content below)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ============================================================
        # TABS ROW (Home, Transform, Add Column, etc.)
        # ============================================================
        tabs_widget = QWidget()
        tabs_widget.setStyleSheet("background-color: transparent;")
        self.tabs_layout = QHBoxLayout(tabs_widget)
        self.tabs_layout.setContentsMargins(4, 0, 0, 0)
        self.tabs_layout.setSpacing(0)

        self.main_layout.addWidget(tabs_widget)

        # ============================================================
        # CONTENT AREA (changes based on selected tab)
        # ============================================================
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: transparent;
                border-bottom: 1px solid #edebe9;
            }
        """)
        self.main_layout.addWidget(self.content_stack)

        # Button group to manage tab selection (only one tab active at a time)
        self.tab_group = QButtonGroup()
        self.tab_buttons = []

        # Create all tabs and their content
        self.create_tabs()
    
    def create_tabs(self):
        """
        Create all the ribbon tabs and their content.
        
        This creates:
        1. Tab buttons at the top
        2. Content widget for each tab
        3. Connects them so clicking a tab shows its content
        """
        # Define tab names
        tabs = [
            "Home",
            "Transform",
            "Add Column",
            "View",
            "Tools"
        ]
        
        # Create each tab
        for i, tab_name in enumerate(tabs):
            # Create tab button
            tab = RibbonTab(tab_name)
            tab.clicked.connect(lambda checked, idx=i: self.switch_tab(idx))
            
            # Add to button group (for exclusive selection)
            self.tab_group.addButton(tab)
            self.tab_buttons.append(tab)
            self.tabs_layout.addWidget(tab)
            
            # Create content for this tab
            content = self.create_tab_content(tab_name)
            self.content_stack.addWidget(content)
        
        # Add stretch to push tabs to the left
        self.tabs_layout.addStretch()
        
        # Select first tab by default
        self.tab_buttons[0].setChecked(True)
        self.tab_buttons[0].update_style(True)
    
    def switch_tab(self, index):
        """
        Switch to a different tab.
        
        Args:
            index (int): Index of the tab to switch to
        """
        # Show the corresponding content
        self.content_stack.setCurrentIndex(index)
        
        # Update visual state of all tab buttons
        for i, button in enumerate(self.tab_buttons):
            button.setChecked(i == index)
            button.update_style(i == index)
    
    def create_tab_content(self, tab_name):
        """
        Create the content widget for a specific tab.

        Args:
            tab_name (str): Name of the tab

        Returns:
            QWidget: Widget containing all groups and buttons for this tab
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 0, 2)
        layout.setSpacing(0)

        # Call the appropriate method to populate this tab
        if tab_name == "Home":
            self.create_home_tab(layout)
        elif tab_name == "Transform":
            self.create_transform_tab(layout)
        elif tab_name == "Add Column":
            self.create_add_column_tab(layout)
        elif tab_name == "View":
            self.create_view_tab(layout)
        elif tab_name == "Tools":
            self.create_tools_tab(layout)

        # Add stretch to push groups to the left
        layout.addStretch()
        return widget
    
    # ========================================================================
    # TAB CONTENT CREATION METHODS
    # ========================================================================
    
    def create_home_tab(self, layout):
        """
        Create Home tab content - basic operations.

        Groups:
        - Close & Load: Save and close operations
        - Sort: Ascending/descending sorting
        - Remove: Remove rows or columns
        - Reduce Rows: Keep top/bottom rows
        """
        # Close & Load group
        close_load_group = RibbonGroup("Close & Load")
        close_load_group.add_button(RibbonButton("Close & Load", "📊"))
        close_load_group.add_button(RibbonButton("Close", "✕"))
        layout.addWidget(close_load_group)

        # Sort group with stacked small buttons
        sort_group = RibbonGroup("Sort")
        sort_layout = QVBoxLayout()
        sort_layout.setSpacing(0)
        sort_layout.addWidget(SmallRibbonButton("Sort Ascending", "↑"))
        sort_layout.addWidget(SmallRibbonButton("Sort Descending", "↓"))
        sort_group.add_layout(sort_layout)
        layout.addWidget(sort_group)

        # Remove group
        remove_group = RibbonGroup("Remove")
        remove_layout = QVBoxLayout()
        remove_layout.setSpacing(0)
        remove_layout.addWidget(SmallRibbonButton("Remove Rows", "🗑"))
        remove_layout.addWidget(SmallRibbonButton("Remove Columns", "⊟"))
        remove_group.add_layout(remove_layout)
        layout.addWidget(remove_group)

        # Reduce Rows group
        reduce_group = RibbonGroup("Reduce Rows")
        reduce_layout = QVBoxLayout()
        reduce_layout.setSpacing(0)
        reduce_layout.addWidget(SmallRibbonButton("Keep Top Rows", "⬆"))
        reduce_layout.addWidget(SmallRibbonButton("Keep Bottom Rows", "⬇"))
        reduce_group.add_layout(reduce_layout)
        layout.addWidget(reduce_group)
    
    def create_transform_tab(self, layout):
        """
        Create Transform tab content - data transformation operations.

        Groups:
        - Data Type: Change column data types
        - Text Column: Text manipulation
        - Number Column: Number operations
        - Date & Time: Date/time transformations
        - Structured Column: Work with nested data
        """
        # Data Type group
        type_group = RibbonGroup("Data Type")
        type_group.add_button(RibbonButton("Data Type", "🔤"))
        layout.addWidget(type_group)

        # Text Column group
        text_group = RibbonGroup("Text Column")
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.addWidget(SmallRibbonButton("Format", "✎"))
        text_layout.addWidget(SmallRibbonButton("Split Column", "⚏"))
        text_layout.addWidget(SmallRibbonButton("Extract", "📝"))
        text_group.add_layout(text_layout)
        layout.addWidget(text_group)

        # Number Column group
        number_group = RibbonGroup("Number Column")
        number_layout = QVBoxLayout()
        number_layout.setSpacing(0)
        number_layout.addWidget(SmallRibbonButton("Statistics", "∑"))
        number_layout.addWidget(SmallRibbonButton("Standard", "123"))
        number_layout.addWidget(SmallRibbonButton("Scientific", "x²"))
        number_group.add_layout(number_layout)
        layout.addWidget(number_group)

        # Date & Time group
        date_group = RibbonGroup("Date & Time")
        date_layout = QVBoxLayout()
        date_layout.setSpacing(0)
        date_layout.addWidget(SmallRibbonButton("Date", "📅"))
        date_layout.addWidget(SmallRibbonButton("Time", "🕐"))
        date_layout.addWidget(SmallRibbonButton("Duration", "⏱"))
        date_group.add_layout(date_layout)
        layout.addWidget(date_group)

        # Structured Column group
        struct_group = RibbonGroup("Structured Column")
        struct_layout = QVBoxLayout()
        struct_layout.setSpacing(0)
        struct_layout.addWidget(SmallRibbonButton("Expand", "⤢"))
        struct_layout.addWidget(SmallRibbonButton("Aggregate", "≡"))
        struct_group.add_layout(struct_layout)
        layout.addWidget(struct_group)
    
    def create_add_column_tab(self, layout):
        """
        Create Add Column tab content - create new columns.

        Groups:
        - General: Custom columns and indexes
        - From Text: Derive columns from text
        - From Number: Derive columns from numbers
        - From Date & Time: Derive columns from dates
        """
        # General group
        general_group = RibbonGroup("General")
        general_layout = QVBoxLayout()
        general_layout.setSpacing(0)
        general_layout.addWidget(SmallRibbonButton("Custom Column", "➕"))
        general_layout.addWidget(SmallRibbonButton("Invoke Custom", "⚡"))
        general_layout.addWidget(SmallRibbonButton("Index Column", "#"))
        general_group.add_layout(general_layout)
        layout.addWidget(general_group)

        # From Text group
        text_group = RibbonGroup("From Text")
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.addWidget(SmallRibbonButton("Length", "↔"))
        text_layout.addWidget(SmallRibbonButton("Position", "📍"))
        text_layout.addWidget(SmallRibbonButton("Range", "⇿"))
        text_group.add_layout(text_layout)
        layout.addWidget(text_group)

        # From Number group
        number_group = RibbonGroup("From Number")
        number_layout = QVBoxLayout()
        number_layout.setSpacing(0)
        number_layout.addWidget(SmallRibbonButton("Statistics", "∑"))
        number_layout.addWidget(SmallRibbonButton("Rounding", "≈"))
        number_layout.addWidget(SmallRibbonButton("Information", "ℹ"))
        number_group.add_layout(number_layout)
        layout.addWidget(number_group)

        # From Date & Time group
        date_group = RibbonGroup("From Date & Time")
        date_layout = QVBoxLayout()
        date_layout.setSpacing(0)
        date_layout.addWidget(SmallRibbonButton("Date", "📅"))
        date_layout.addWidget(SmallRibbonButton("Time", "🕐"))
        date_layout.addWidget(SmallRibbonButton("Age", "⌛"))
        date_group.add_layout(date_layout)
        layout.addWidget(date_group)
    
    def create_view_tab(self, layout):
        """
        Create View tab content - control what's visible.

        Groups:
        - Layout: Query settings and dependencies
        - Data Preview: Quality and distribution views
        - Show: Toggle interface elements
        """
        # Layout group
        layout_group = RibbonGroup("Layout")
        layout_layout = QVBoxLayout()
        layout_layout.setSpacing(0)
        layout_layout.addWidget(SmallRibbonButton("Query Settings", "⚙"))
        layout_layout.addWidget(SmallRibbonButton("Query Dependencies", "🔗"))
        layout_layout.addWidget(SmallRibbonButton("Properties", "📋"))
        layout_group.add_layout(layout_layout)
        layout.addWidget(layout_group)

        # Data Preview group
        preview_group = RibbonGroup("Data Preview")
        preview_layout = QVBoxLayout()
        preview_layout.setSpacing(0)
        preview_layout.addWidget(SmallRibbonButton("Column Quality", "✓"))
        preview_layout.addWidget(SmallRibbonButton("Column Distribution", "📊"))
        preview_layout.addWidget(SmallRibbonButton("Column Profile", "📈"))
        preview_group.add_layout(preview_layout)
        layout.addWidget(preview_group)

        # Show group
        show_group = RibbonGroup("Show")
        show_layout = QVBoxLayout()
        show_layout.setSpacing(0)
        show_layout.addWidget(SmallRibbonButton("Formula Bar", "ƒx"))
        show_layout.addWidget(SmallRibbonButton("Always Show More", "⋮"))
        show_group.add_layout(show_layout)
        layout.addWidget(show_group)
    
    def create_tools_tab(self, layout):
        """
        Create Tools tab content - advanced features.

        Groups:
        - Scripts: Python and R script integration
        - Options: Configuration settings
        """
        # Scripts group
        scripts_group = RibbonGroup("Scripts")
        scripts_layout = QVBoxLayout()
        scripts_layout.setSpacing(0)
        scripts_layout.addWidget(SmallRibbonButton("Python Script", "🐍"))
        scripts_layout.addWidget(SmallRibbonButton("R Script", "📊"))
        scripts_group.add_layout(scripts_layout)
        layout.addWidget(scripts_group)

        # Options group
        options_group = RibbonGroup("Options")
        options_layout = QVBoxLayout()
        options_layout.setSpacing(0)
        options_layout.addWidget(SmallRibbonButton("Query Options", "⚙"))
        options_layout.addWidget(SmallRibbonButton("Data Source Settings", "🔧"))
        options_group.add_layout(options_layout)
        layout.addWidget(options_group)


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    """
    Example of how to use the ribbon components in your application.
    """
    from PySide6.QtWidgets import QApplication, QMainWindow
    import sys
    
    class RibbonDemo(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Ribbon Interface Demo")
            self.setGeometry(100, 100, 1200, 600)
            
            # Create main widget
            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            
            # Create layout
            layout = QVBoxLayout(main_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            
            # Add ribbon
            ribbon = RibbonBar()
            layout.addWidget(ribbon)
            
            # Add some content below the ribbon
            content_label = QLabel("Your application content goes here")
            content_label.setAlignment(Qt.AlignCenter)
            content_label.setStyleSheet("QLabel { font-size: 18px; color: #6b7280; }")
            layout.addWidget(content_label, 1)
            
            # Connect ribbon buttons to actions
            self.connect_ribbon_actions()
        
        def connect_ribbon_actions(self):
            """
            Example of how to connect ribbon buttons to your methods.
            
            In a real application, you would:
            1. Store references to specific buttons when creating them
            2. Connect them to your application logic
            
            For example:
                self.save_button = RibbonButton("Save", "💾")
                self.save_button.clicked.connect(self.save_file)
            """
            print("Connect your ribbon buttons to actions here!")
    
    # Run the demo
    app = QApplication(sys.argv)
    demo = RibbonDemo()
    demo.show()
    sys.exit(app.exec())
