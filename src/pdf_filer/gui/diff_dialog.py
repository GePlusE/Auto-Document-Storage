from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
)
from PySide6.QtCore import Qt

from .types import PlanItem


class DryRunDiffDialog(QDialog):
    def __init__(self, parent, items: List[PlanItem]):
        super().__init__(parent)
        self.setWindowTitle("Dry-run diff (von → nach)")
        self.resize(1100, 500)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"{len(items)} item(s)"))

        tbl = QTableWidget(self)
        tbl.setColumnCount(5)
        tbl.setHorizontalHeaderLabels(
            ["Original", "Status", "New filename", "Target folder", "Target path"]
        )
        tbl.setRowCount(len(items))
        tbl.horizontalHeader().setStretchLastSection(True)

        for r, it in enumerate(items):
            newname = it.planned_target_path.name if it.planned_target_path else ""
            tgtfolder = it.effective_folder() or it.target_folder
            tgtpath = str(it.planned_target_path) if it.planned_target_path else ""

            tbl.setItem(r, 0, QTableWidgetItem(it.original_filename))
            tbl.setItem(r, 1, QTableWidgetItem(it.status))
            tbl.setItem(r, 2, QTableWidgetItem(newname))
            tbl.setItem(r, 3, QTableWidgetItem(tgtfolder))
            tbl.setItem(r, 4, QTableWidgetItem(tgtpath))

        tbl.resizeColumnsToContents()
        lay.addWidget(tbl, 1)
