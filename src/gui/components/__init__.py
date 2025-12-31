"""
CAATmaster GUI Components
Modern UI components inspired by Tailwind CSS + shadcn/ui design system
"""

from .modern_ui import (
    ModernButton,
    IconButton,
    TooltipButton,
    Card,
    FlatCard,
    Section,
    TitleLabel,
    HeadingLabel,
    BodyLabel,
    CaptionLabel,
    Badge,
    SearchInput,
    ModernLineEdit,
    VBoxLayout,
    HBoxLayout,
    GridLayout,
    CenterLayout,
    ModernListWidget,
    ListItem,
    ModernScrollArea,
    LoadingBar,
    Spinner,
    EmptyState,
    Toast,
    ToastManager,
    Accordion,
    ProgressRing,
    Divider,
    Avatar,
    AnimatedToggle,
    create_spacer,
    create_icon_button,
)

from .sidebar import Sidebar, SidebarButton

from .data_table import ModernDataTable

from .context_menus import (
    ColumnContextMenu,
    CellContextMenu,
    RowContextMenu,
)

from .steps_panel import (
    AppliedStepsPanel,
    TransformationStep,
    StepStatus,
)

from .backstage import BackstageView

from .ribbon import (
    RibbonButton,
    SmallRibbonButton,
    RibbonTab,
    RibbonGroup,
    RibbonBar,
)

__all__ = [
    # Modern UI
    "ModernButton",
    "IconButton",
    "TooltipButton",
    "Card",
    "FlatCard",
    "Section",
    "TitleLabel",
    "HeadingLabel",
    "BodyLabel",
    "CaptionLabel",
    "Badge",
    "SearchInput",
    "ModernLineEdit",
    "VBoxLayout",
    "HBoxLayout",
    "GridLayout",
    "CenterLayout",
    "ModernListWidget",
    "ListItem",
    "ModernScrollArea",
    "LoadingBar",
    "Spinner",
    "EmptyState",
    "Toast",
    "ToastManager",
    "Accordion",
    "ProgressRing",
    "Divider",
    "Avatar",
    "AnimatedToggle",
    "create_spacer",
    "create_icon_button",
    # Sidebar
    "Sidebar",
    "SidebarButton",
    # Data Table
    "ModernDataTable",
    # Context Menus
    "ColumnContextMenu",
    "CellContextMenu",
    "RowContextMenu",
    # Steps Panel
    "AppliedStepsPanel",
    "TransformationStep",
    "StepStatus",
    # Backstage
    "BackstageView",
    # Ribbon
    "RibbonButton",
    "SmallRibbonButton",
    "RibbonTab",
    "RibbonGroup",
    "RibbonBar",
]
