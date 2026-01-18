from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QPlainTextEdit,
    QMessageBox,
)


class MappingEditorDialog(QDialog):
    def __init__(self, parent=None, mapping_path: Path | None = None):
        super().__init__(parent)
        self.setWindowTitle("Sender Mapping Editor")
        self.resize(900, 700)

        self.mapping_path = mapping_path
        self.editor = QPlainTextEdit(self)

        top = QHBoxLayout()
        self.path_label = QLabel(self)
        btn_open = QPushButton("Open JSON…")
        btn_save = QPushButton("Save")
        btn_close = QPushButton("Close")

        btn_open.clicked.connect(self._open)
        btn_save.clicked.connect(self._save)
        btn_close.clicked.connect(self.close)

        top.addWidget(self.path_label, 1)
        top.addWidget(btn_open)
        top.addWidget(btn_save)
        top.addWidget(btn_close)

        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addWidget(self.editor, 1)
        self.setLayout(lay)

        if self.mapping_path:
            self._load(self.mapping_path)

    def _load(self, path: Path):
        self.mapping_path = path
        self.path_label.setText(str(path))
        self.editor.setPlainText(path.read_text(encoding="utf-8"))

    def _open(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Open sender_mapping.json", "", "JSON (*.json)"
        )
        if not p:
            return
        self._load(Path(p))

    def _save(self):
        if not self.mapping_path:
            QMessageBox.warning(self, "No file", "No mapping file loaded.")
            return
        try:
            # Validate JSON
            obj = json.loads(self.editor.toPlainText())
            self.mapping_path.write_text(
                json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            QMessageBox.information(self, "Saved", "Mapping saved.")
        except Exception as e:
            QMessageBox.critical(self, "Invalid JSON", str(e))
