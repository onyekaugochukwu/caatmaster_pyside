"""
Modern UI Components for CAATmaster
Inspired by Tailwind CSS + shadcn/ui design system

These components provide modern, styled widgets that follow the design system
defined in modern_dark.qss
"""

from PySide6.QtCore import Qt, QSize, Property, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QIcon, QPixmap, QCursor, QFont, QAction
from PySide6.QtWidgets import (
    QWidget, QPushButton, QLabel, QLineEdit, QFrame, QVBoxLayout,
    QHBoxLayout, QGridLayout, QStackedLayout, QBoxLayout,
    QListWidget, QListWidgetItem, QScrollArea, QSizePolicy,
    QToolButton, QMenu, QSpacerItem, QGraphicsDropShadowEffect
)


# ============================================================================
# MODERN BUTTONS
# ============================================================================

class ModernButton(QPushButton):
    """Modern button with multiple variants (primary, secondary, ghost, danger)"""

    # Button variants
    PRIMARY = "primary"
    SECONDARY = "secondary"
    GHOST = "ghost"
    DANGER = "danger"
    SUCCESS = "success"

    # Signals
    clicked = Signal()

    def __init__(
        self,
        text: str = "",
        variant: str = SECONDARY,
        icon: QIcon = None,
        parent: QWidget = None
    ):
        super().__init__(text, parent)
        self._variant = variant
        self._icon = icon
        self._is_loading = False

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setAttribute(Qt.WA_Hover, True)

        # Set object name for styling
        if variant == self.PRIMARY:
            self.setObjectName("PrimaryButton")
        elif variant == self.DANGER:
            self.setObjectName("DangerButton")
        elif variant == self.SUCCESS:
            self.setObjectName("SuccessButton")
        elif variant == self.GHOST:
            self.setObjectName("GhostButton")
        else:
            self.setObjectName("SecondaryButton")

        # Add icon if provided
        if icon:
            self.setIcon(icon)

    def setLoading(self, loading: bool):
        """Set loading state with spinner"""
        self._is_loading = loading
        if loading:
            self.setEnabled(False)
            self.setText("Loading...")
        else:
            self.setEnabled(True)

    def isLoading(self) -> bool:
        return self._is_loading

    loading = Property(bool, isLoading, setLoading)


class IconButton(QPushButton):
    """Circular icon button"""

    def __init__(
        self,
        icon: QIcon,
        size: int = 32,
        parent: QWidget = None,
        tooltip: str = ""
    ):
        super().__init__(parent=parent)
        self.setIcon(icon)
        self.setFixedSize(size, size)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setObjectName("icon-button")
        if tooltip:
            self.setToolTip(tooltip)

    def sizeHint(self) -> QSize:
        return QSize(32, 32)


class TooltipButton(IconButton):
    """Icon button with tooltip"""

    def __init__(self, icon: QIcon, text: str, parent: QWidget = None):
        super().__init__(icon, 28, parent)
        self.setToolTip(text)
        self._tooltip_text = text


# ============================================================================
# CARDS & CONTAINERS
# ============================================================================

class Card(QFrame):
    """Card container with hover effect and shadow"""

    clicked = Signal()

    def __init__(
        self,
        parent: QWidget = None,
        clickable: bool = False,
        hover_effect: bool = True
    ):
        super().__init__(parent)
        self._clickable = clickable
        self._hover_effect = hover_effect
        self._elevation = 1

        self.setObjectName("Card")
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(QCursor(Qt.PointingHandCursor)) if clickable else None

        # Add shadow effect
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 0, 0, 50))
        self.shadow.setOffset(0, 2)
        self.setGraphicsEffect(self.shadow)

        if clickable:
            self.setAttribute(Qt.WA_Hover, True)
            self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self and self._hover_effect:
            if event.type() == event.Type.Enter:
                self._on_hover(True)
            elif event.type() == event.Type.Leave:
                self._on_hover(False)
        return super().eventFilter(obj, event)

    def _on_hover(self, hovered: bool):
        """Animate elevation on hover"""
        if hovered:
            self.shadow.setBlurRadius(30)
            self.shadow.setOffset(0, 4)
        else:
            self.shadow.setBlurRadius(20)
            self.shadow.setOffset(0, 2)
        self.shadow.update()


class FlatCard(Card):
    """Card without border"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("CardFlat")


class Section(QFrame):
    """Section container with padding"""

    def __init__(self, parent: QWidget = None, title: str = None):
        super().__init__(parent)
        self.setObjectName("Section")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        if title:
            title_label = HeadingLabel(title, level=3)
            layout.addWidget(title_label)


# ============================================================================
# LABELS & TYPOGRAPHY
# ============================================================================

class TitleLabel(QLabel):
    """Large title label (24px, bold)"""

    def __init__(self, text: str = "", parent: QWidget = None):
        super().__init__(text, parent)
        self.setObjectName("TitleLabel")
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)


class HeadingLabel(QLabel):
    """Heading label with configurable level"""

    def __init__(self, text: str = "", level: int = 2, parent: QWidget = None):
        super().__init__(text, parent)

        if level == 1:
            self.setObjectName("HeadingLabel")
            self.setStyleSheet("font-size: 28px; font-weight: 700;")
        elif level == 2:
            self.setObjectName("HeadingLabel")
            self.setStyleSheet("font-size: 20px; font-weight: 600;")
        else:
            self.setObjectName("SubheadingLabel")


class BodyLabel(QLabel):
    """Body text label"""

    def __init__(self, text: str = "", parent: QWidget = None, muted: bool = False):
        super().__init__(text, parent)
        if muted:
            self.setObjectName("MutedLabel")
        else:
            self.setObjectName("BodyLabel")


class CaptionLabel(QLabel):
    """Caption/small text label"""

    def __init__(self, text: str = "", parent: QWidget = None, muted: bool = True):
        super().__init__(text, parent)
        self.setObjectName("CaptionLabel")
        if muted:
            self.setStyleSheet("color: var(--color-text-tertiary);")


class Badge(QLabel):
    """Badge label with color variants"""

    DEFAULT = "default"
    PRIMARY = "primary"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"

    def __init__(
        self,
        text: str = "",
        variant: str = DEFAULT,
        parent: QWidget = None
    ):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)

        if variant == self.PRIMARY:
            self.setObjectName("BadgePrimary")
        elif variant == self.SUCCESS:
            self.setObjectName("BadgeSuccess")
        elif variant == self.WARNING:
            self.setObjectName("BadgeWarning")
        elif variant == self.DANGER:
            self.setObjectName("BadgeDanger")
        else:
            self.setObjectName("Badge")

        self.setMargin(8)


# ============================================================================
# INPUTS
# ============================================================================

class SearchInput(QLineEdit):
    """Search input with icon"""

    def __init__(self, placeholder: str = "Search...", parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("SearchInput")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)


class ModernLineEdit(QLineEdit):
    """Modern line edit with validation support"""

    def __init__(
        self,
        placeholder: str = "",
        parent: QWidget = None,
        validator=None
    ):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        if validator:
            self.setValidator(validator)

    def setError(self, error: bool, message: str = ""):
        """Set error state"""
        if error:
            self.setStyleSheet(
                "QLineEdit { border-color: var(--color-danger); }"
            )
            if message:
                self.setToolTip(message)
        else:
            self.setStyleSheet("")


# ============================================================================
# LAYOUT HELPERS
# ============================================================================

class VBoxLayout(QVBoxLayout):
    """Vertical layout with convenience methods"""

    def __init__(self, parent: QWidget = None, spacing: int = 12):
        super().__init__(parent)
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def add_stretch(self, stretch: int = 0):
        self.addStretch(stretch)

    def add_spacer(self, size: int = 12):
        spacer = QSpacerItem(0, size)
        self.addSpacerItem(spacer)


class HBoxLayout(QHBoxLayout):
    """Horizontal layout with convenience methods"""

    def __init__(self, parent: QWidget = None, spacing: int = 12):
        super().__init__(parent)
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def add_stretch(self, stretch: int = 0):
        self.addStretch(stretch)

    def add_spacer(self, size: int = 12):
        spacer = QSpacerItem(size, 0)
        self.addSpacerItem(spacer)


class GridLayout(QGridLayout):
    """Grid layout with convenience methods"""

    def __init__(self, parent: QWidget = None, spacing: int = 12):
        super().__init__(parent)
        self.setSpacing(spacing)


class CenterLayout(QBoxLayout):
    """Layout that centers its contents"""

    def __init__(self, parent: QWidget = None, orientation: Qt.Orientation = Qt.Horizontal):
        super().__init__(orientation, parent)
        self.setContentsMargins(0, 0, 0, 0)


# ============================================================================
# LIST WIDGETS
# ============================================================================

class ModernListWidget(QListWidget):
    """Modern list widget with card-like items"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("ModernListWidget")
        self.setSpacing(4)
        self.setCursor(QCursor(Qt.PointingHandCursor))


class ListItem(QListWidgetItem):
    """Custom list item"""

    def __init__(self, text: str, parent: QWidget = None):
        super().__init__(text, parent)
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)


# ============================================================================
# SCROLL AREA
# ============================================================================

class ModernScrollArea(QScrollArea):
    """Scroll area with modern styling"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("ModernScrollArea")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.NoFrame)


# ============================================================================
# LOADING INDICATORS
# ============================================================================

class LoadingBar(QFrame):
    """Animated loading bar"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("LoadingBar")
        self.setFixedHeight(4)

        self._progress = 0
        self._animation = None
        self._start_animation()

    def _start_animation(self):
        """Start the loading animation"""
        self._animation = QPropertyAnimation(self, b"progress")
        self._animation.setDuration(1500)
        self._animation.setStartValue(0)
        self._animation.setEndValue(100)
        self._animation.setEasingCurve(QEasingCurve.InOutSine)
        self._animation.setLoopCount(-1)  # Infinite loop
        self._animation.start()

    def getProgress(self) -> int:
        return self._progress

    def setProgress(self, value: int):
        self._progress = value
        self.update()

    progress = Property(int, getProgress, setProgress)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(45, 45, 45))
        painter.drawRoundedRect(self.rect(), 2, 2)

        # Progress
        if self._progress > 0:
            gradient = QLinearGradient(0, 0, self.width(), 0)
            gradient.setColorAt(0, QColor(59, 130, 246))
            gradient.setColorAt(1, QColor(99, 179, 237))
            painter.setBrush(gradient)
            width = int(self.width() * self._progress / 100)
            painter.drawRoundedRect(0, 0, width, self.height(), 2, 2)


class Spinner(QFrame):
    """Animated spinner"""

    def __init__(self, size: int = 32, parent: QWidget = None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(50)

    def _rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() // 2, self.height() // 2)
        painter.rotate(self._angle)

        pen = painter.pen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(QColor(59, 130, 246))
        painter.setPen(pen)

        # Draw arc
        painter.drawArc(-10, -10, 20, 20, 0, 270)


# ============================================================================
# EMPTY STATES
# ============================================================================

class EmptyState(QFrame):
    """Empty state placeholder"""

    def __init__(
        self,
        icon: QIcon = None,
        title: str = "No data",
        description: str = "",
        action_button: QPushButton = None,
        parent: QWidget = None
    ):
        super().__init__(parent)
        self.setObjectName("EmptyState")

        layout = VBoxLayout(self, spacing=16)
        layout.addStretch()

        # Icon
        if icon:
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(64, 64))
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)

        # Title
        title_label = HeadingLabel(title, level=3)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Description
        if description:
            desc_label = BodyLabel(description, muted=True)
            desc_label.setAlignment(Qt.AlignCenter)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        # Action button
        if action_button:
            layout.addWidget(action_button, alignment=Qt.AlignCenter)

        layout.addStretch()


# ============================================================================
# TOAST NOTIFICATIONS
# ============================================================================

class Toast(QFrame):
    """Toast notification widget"""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"

    dismissed = Signal()

    def __init__(
        self,
        message: str,
        variant: str = INFO,
        duration: int = 4000,
        parent: QWidget = None
    ):
        super().__init__(parent)
        self.setObjectName("ToastWidget")
        self.setFixedHeight(60)

        layout = HBoxLayout(self, spacing=12)
        layout.setContentsMargins(16, 12, 16, 12)

        # Icon
        self.icon_label = QLabel()
        layout.addWidget(self.icon_label)

        # Message
        self.message_label = BodyLabel(message)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        layout.addStretch()

        # Dismiss button
        dismiss_btn = IconButton(
            QIcon.fromTheme("dialog-close"),
            20,
            self
        )
        dismiss_btn.clicked.connect(self._dismiss)
        layout.addWidget(dismiss_btn)

        # Set variant styling
        self.setProperty("class", variant)

        # Auto-dismiss
        if duration > 0:
            QTimer.singleShot(duration, self._dismiss)

    def _dismiss(self):
        self.dismissed.emit()
        self.deleteLater()


class ToastManager(QWidget):
    """Manager for toast notifications"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground)

        layout = VBoxLayout(self, spacing=8)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addStretch()

        # Parent should have a layout to contain this
        if parent and parent.layout():
            parent.layout().addWidget(self)

    def show(
        self,
        message: str,
        variant: str = Toast.INFO,
        duration: int = 4000
    ):
        """Show a toast notification"""
        toast = Toast(message, variant, duration, self)
        self.layout().insertWidget(self.layout().count() - 1, toast)

    def success(self, message: str, duration: int = 4000):
        self.show(message, Toast.SUCCESS, duration)

    def warning(self, message: str, duration: int = 4000):
        self.show(message, Toast.WARNING, duration)

    def error(self, message: str, duration: int = 5000):
        self.show(message, Toast.ERROR, duration)

    def info(self, message: str, duration: int = 4000):
        self.show(message, Toast.INFO, duration)


# ============================================================================
# ACCORDION
# ============================================================================

class Accordion(QFrame):
    """Collapsible accordion section"""

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        parent: QWidget = None,
        collapsed: bool = False
    ):
        super().__init__(parent)

        self._collapsed = collapsed
        self._content_height = 0

        layout = VBoxLayout(self, spacing=0)

        # Header
        self.header = QFrame()
        self.header.setCursor(QCursor(Qt.PointingHandCursor))
        header_layout = HBoxLayout(self.header, spacing=8)
        header_layout.setContentsMargins(12, 8, 12, 8)

        # Toggle icon
        self.toggle_icon = QLabel()
        self.toggle_icon.setPixmap(
            QIcon.fromTheme("arrow-right").pixmap(16, 16)
        )
        header_layout.addWidget(self.toggle_icon)

        # Title
        self.title_label = BodyLabel(title, muted=False)
        self.title_label.setStyleSheet("font-weight: 500;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        layout.addWidget(self.header)

        # Content
        self.content = QFrame()
        self.content_layout = VBoxLayout(self.content, spacing=0)
        layout.addWidget(self.content)

        # Connect header click
        self.header.mousePressEvent = self._toggle

        # Initial state
        self._update_state()

    def _toggle(self, event):
        self._collapsed = not self._collapsed
        self._update_state()
        self.toggled.emit(not self._collapsed)

    def _update_state(self):
        """Update visual state based on collapsed state"""
        if self._collapsed:
            self.content.hide()
            self.toggle_icon.setPixmap(
                QIcon.fromTheme("arrow-right").pixmap(16, 16)
            )
        else:
            self.content.show()
            self.toggle_icon.setPixmap(
                QIcon.fromTheme("arrow-down").pixmap(16, 16)
            )

    def addWidget(self, widget: QWidget):
        """Add widget to content area"""
        self.content_layout.addWidget(widget)

    def setTitle(self, title: str):
        """Set accordion title"""
        self.title_label.setText(title)


# ============================================================================
# PROGRESS INDICATORS
# ============================================================================

class ProgressRing(QFrame):
    """Circular progress ring"""

    def __init__(
        self,
        size: int = 48,
        parent: QWidget = None
    ):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._progress = 0
        self._color = QColor(59, 130, 246)

    def getProgress(self) -> int:
        return self._progress

    def setProgress(self, value: int):
        self._progress = max(0, min(100, value))
        self.update()

    progress = Property(int, getProgress, setProgress)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.rect().center()
        radius = min(self.width(), self.height()) // 2 - 4

        # Background ring
        pen = painter.pen()
        pen.setWidth(4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(QColor(45, 45, 45))
        painter.setPen(pen)
        painter.drawEllipse(center, radius, radius)

        # Progress
        if self._progress > 0:
            pen.setColor(self._color)
            painter.setPen(pen)
            span_angle = int(-self._progress * 3.6 * 16)
            painter.drawArc(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
                90 * 16,
                span_angle
            )


# ============================================================================
# DIVIDER
# ============================================================================

class Divider(QFrame):
    """Horizontal or vertical divider"""

    def __init__(
        self,
        parent: QWidget = None,
        vertical: bool = False
    ):
        super().__init__(parent)
        self.setObjectName("Divider")
        if vertical:
            self.setFixedWidth(1)
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        else:
            self.setFixedHeight(1)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


# ============================================================================
# AVATAR
# ============================================================================

class Avatar(QLabel):
    """User avatar with initials or icon"""

    def __init__(
        self,
        text: str = "",
        size: int = 40,
        parent: QWidget = None
    ):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)

        # Background
        self.setStyleSheet(f"""
            background-color: var(--color-accent);
            border-radius: {size // 2}px;
            color: white;
            font-weight: 600;
            font-size: {size // 3}px;
        """)

        if text:
            self.setText(text[:2].upper())


# ============================================================================
# ANIMATED TOGGLE
# ============================================================================

class AnimatedToggle(QFrame):
    """Animated toggle switch"""

    toggled = Signal(bool)

    def __init__(
        self,
        parent: QWidget = None,
        checked: bool = False
    ):
        super().__init__(parent)
        self.setFixedSize(48, 24)

        self._checked = checked
        self._animating = False

        self.setCursor(QCursor(Qt.PointingHandCursor))

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(checked)

    def toggle(self):
        self.setChecked(not self._checked)

    def mousePressEvent(self, event):
        self.toggle()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Track
        track_color = QColor(59, 130, 246) if self._checked else QColor(75, 85, 99)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(0, 0, 48, 24, 12, 12)

        # Knob
        knob_x = 26 if self._checked else 2
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(knob_x, 2, 20, 20)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_spacer(width: int = 0, height: int = 0, horizontal: bool = True) -> QSpacerItem:
    """Create a spacer item"""
    if horizontal:
        return QSpacerItem(width, height, QSizePolicy.Expanding, QSizePolicy.Minimum)
    else:
        return QSpacerItem(width, height, QSizePolicy.Minimum, QSizePolicy.Expanding)


def create_icon_button(
    icon_name: str,
    size: int = 24,
    parent: QWidget = None,
    tooltip: str = ""
) -> IconButton:
    """Create an icon button from theme icon"""
    return IconButton(
        QIcon.fromTheme(icon_name),
        size,
        parent,
        tooltip
    )
