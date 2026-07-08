"""Project Lineage Dialog - a graphical map of every dataset in the
project and how they relate to each other. Each dataset's source_dataset_ids/source_operation
(already tracked on every Dataset) is laid out as a left-to-right graph:
root datasets (file imports) on the left, derived datasets to the right
of whatever they were built from, connected by labeled arrows."""
from collections import defaultdict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsLineItem, QGraphicsPolygonItem
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPolygonF

from gui.theme import Colors

NODE_W, NODE_H = 190, 64
X_GAP, Y_GAP = 250, 100


class ProjectLineageDialog(QDialog):
    """Read-only graphical map of dataset lineage across the whole
    project - never modifies anything, purely a documentation/navigation
    view."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Project Lineage")
        self.resize(900, 650)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "How every dataset in this project was created and relates to the others. "
            "Root datasets (imported from a file) are on the left; each arrow shows what "
            "operation produced the dataset it points to."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(info)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        layout.addWidget(self.view, 1)

        btn_row = QHBoxLayout()
        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(lambda: self.view.scale(1.2, 1.2))
        btn_row.addWidget(zoom_in_btn)
        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(lambda: self.view.scale(1 / 1.2, 1 / 1.2))
        btn_row.addWidget(zoom_out_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._build_graph()

    def _build_graph(self):
        datasets = self.project.list_datasets() if self.project else []
        by_id = {d.id: d for d in datasets}

        layer: dict = {}

        def compute_layer(ds, visiting):
            if ds.id in layer:
                return layer[ds.id]
            if ds.id in visiting:
                layer[ds.id] = 0  # lineage cycle guard - shouldn't happen, but never hang
                return 0
            visiting = visiting | {ds.id}
            sources = [by_id[sid] for sid in (ds.source_dataset_ids or []) if sid in by_id]
            layer[ds.id] = 0 if not sources else max(compute_layer(s, visiting) for s in sources) + 1
            return layer[ds.id]

        for ds in datasets:
            compute_layer(ds, set())

        layers = defaultdict(list)
        for ds in datasets:
            layers[layer[ds.id]].append(ds)

        positions = {}
        for layer_idx in sorted(layers.keys()):
            for row_idx, ds in enumerate(layers[layer_idx]):
                positions[ds.id] = (layer_idx * X_GAP, row_idx * Y_GAP)

        edge_pen = QPen(QColor(Colors.BORDER_STRONG))
        edge_pen.setWidth(2)
        label_font = QFont()
        label_font.setPointSize(8)

        for ds in datasets:
            if ds.id not in positions:
                continue
            x2, y2 = positions[ds.id]
            for sid in (ds.source_dataset_ids or []):
                if sid not in positions:
                    continue
                x1, y1 = positions[sid]
                start = QPointF(x1 + NODE_W, y1 + NODE_H / 2)
                end = QPointF(x2, y2 + NODE_H / 2)
                line = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
                line.setPen(edge_pen)
                self.scene.addItem(line)
                self._add_arrowhead(end, edge_pen)

                if ds.source_operation:
                    label = QGraphicsTextItem(ds.source_operation)
                    label.setFont(label_font)
                    label.setDefaultTextColor(QColor(Colors.TEXT_SECONDARY))
                    label.setPos((start.x() + end.x()) / 2 - 20, (start.y() + end.y()) / 2 - 18)
                    self.scene.addItem(label)

        for ds in datasets:
            if ds.id not in positions:
                continue
            x, y = positions[ds.id]
            is_root = layer[ds.id] == 0
            rect = QGraphicsRectItem(x, y, NODE_W, NODE_H)
            rect.setBrush(QBrush(QColor(Colors.ACCENT_SOFT if is_root else Colors.SUCCESS_SOFT)))
            rect.setPen(QPen(QColor(Colors.ACCENT if is_root else Colors.SUCCESS), 2))
            self.scene.addItem(rect)

            df = ds.get_current_dataframe()
            row_count = f"{df.height:,} rows" if df is not None else "(no data)"
            subtitle = ds.source_operation.title() if ds.source_operation else (
                "Imported" if ds.source_file_path else "Pasted/Generated"
            )
            text = QGraphicsTextItem(f"{ds.name}\n{row_count}\n{subtitle}")
            text.setPos(x + 8, y + 4)
            self.scene.addItem(text)

        if positions:
            self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def _add_arrowhead(self, tip: QPointF, pen: QPen):
        size = 8
        polygon = QPolygonF([
            tip,
            QPointF(tip.x() - size, tip.y() - size / 2),
            QPointF(tip.x() - size, tip.y() + size / 2),
        ])
        arrow = QGraphicsPolygonItem(polygon)
        arrow.setBrush(QBrush(pen.color()))
        arrow.setPen(pen)
        self.scene.addItem(arrow)
