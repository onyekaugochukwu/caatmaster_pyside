"""
AI Activity Log dialog — surfaces the two things a critical review of the
AI features found were completely invisible before: what did every real
LLM call actually see and say (the audit log), and what has it cost so far
(usage stats). For a tool whose whole purpose is auditability, "trust the
AI silently" isn't good enough — this makes both reviewable.
"""
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QSplitter, QHeaderView, QGroupBox, QGridLayout
)
from PySide6.QtCore import Qt


class AIActivityLogDialog(QDialog):
    def __init__(self, ai_manager, parent=None):
        super().__init__(parent)
        self.ai_manager = ai_manager
        self.setWindowTitle("AI Activity Log")
        self.resize(1000, 650)

        layout = QVBoxLayout(self)

        # --- Usage summary ---
        stats = ai_manager.get_usage_stats() if ai_manager else {
            "total_requests": 0, "total_tokens": 0, "estimated_cost": 0.0, "by_provider": {}
        }

        summary_box = QGroupBox("Usage Summary")
        summary_layout = QGridLayout(summary_box)
        summary_layout.addWidget(QLabel("<b>Total Requests:</b>"), 0, 0)
        summary_layout.addWidget(QLabel(str(stats["total_requests"])), 0, 1)
        summary_layout.addWidget(QLabel("<b>Total Tokens:</b>"), 0, 2)
        summary_layout.addWidget(QLabel(f"{stats['total_tokens']:,}"), 0, 3)
        summary_layout.addWidget(QLabel("<b>Estimated Cost:</b>"), 0, 4)
        summary_layout.addWidget(QLabel(f"${stats['estimated_cost']:.4f}"), 0, 5)

        by_provider = stats.get("by_provider", {})
        if by_provider:
            row = 1
            summary_layout.addWidget(QLabel("<b>By Provider:</b>"), row, 0)
            detail = ", ".join(
                f"{prov} ({b['requests']} req, {b['tokens']:,} tok, ${b['estimated_cost']:.4f})"
                for prov, b in by_provider.items()
            )
            provider_label = QLabel(detail)
            provider_label.setWordWrap(True)
            summary_layout.addWidget(provider_label, row, 1, 1, 5)

        layout.addWidget(summary_box)

        # --- Audit log table + detail pane ---
        entries = ai_manager.get_audit_log(limit=500) if ai_manager else []
        entries = list(reversed(entries))  # newest first

        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget(len(entries), 6)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Task Type", "Provider", "Model", "Tokens", "Latency (ms)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._entries = entries
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(str(entry.get("timestamp", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(entry.get("task_type", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(entry.get("provider", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(str(entry.get("model", ""))))
            tokens = entry.get("tokens") or {}
            self.table.setItem(row, 4, QTableWidgetItem(str(tokens.get("total_tokens", "")) if isinstance(tokens, dict) else ""))
            self.table.setItem(row, 5, QTableWidgetItem(f"{entry.get('latency_ms', 0):.0f}" if entry.get("latency_ms") else ""))
        self.table.currentCellChanged.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setPlaceholderText("Select a row above to see the full prompt and response.")
        splitter.addWidget(self.detail_view)
        splitter.setSizes([300, 300])

        layout.addWidget(splitter)

        if not entries:
            empty_label = QLabel("No AI calls have been logged yet.")
            empty_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def _on_row_selected(self, current_row, *_):
        if current_row < 0 or current_row >= len(self._entries):
            return
        entry = self._entries[current_row]
        prompt = entry.get("prompt", [])
        prompt_text = "\n\n".join(
            f"[{m.get('role', '?')}]\n{m.get('content', '')}" for m in prompt
        ) if isinstance(prompt, list) else str(prompt)

        parts = [
            f"Timestamp: {entry.get('timestamp', '')}",
            f"Task type: {entry.get('task_type', '')}",
            f"Provider: {entry.get('provider', '')}  Model: {entry.get('model', '')}",
        ]
        if entry.get("error"):
            parts.append(f"Error: {entry['error']}")
        parts.append("\n--- PROMPT ---\n" + prompt_text)
        parts.append("\n--- RESPONSE ---\n" + str(entry.get("response", "")))

        self.detail_view.setPlainText("\n".join(parts))
