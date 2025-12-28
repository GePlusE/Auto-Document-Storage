from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import datetime as dt
import subprocess

from ..mover import ensure_dir, move_file
from .types import PlanItem


@dataclass
class HistoryEntry:
    ts: str
    action: str
    file: str
    details: str


@dataclass
class UndoEntry:
    from_path: Path
    to_path: Path


class SessionState:
    def __init__(self, cfg):
        self.cfg = cfg
        self.items: List[PlanItem] = []
        self.history: List[HistoryEntry] = []
        self.undo_stack: List[UndoEntry] = []

    def _now(self) -> str:
        return dt.datetime.now().isoformat(timespec="seconds")

    def set_items(self, items: List[PlanItem]):
        self.items = items
        self.history.append(
            HistoryEntry(self._now(), "DryRun", f"{len(items)} files", "")
        )

    def accept(self, idxs: List[int]):
        for i in idxs:
            it = self.items[i]
            if it.status in {"Processed"}:
                continue
            it.status = "Accepted"
            self.history.append(
                HistoryEntry(self._now(), "Accept", it.original_filename, "")
            )

    def reject(self, idxs: List[int]):
        for i in idxs:
            it = self.items[i]
            if it.status in {"Processed"}:
                continue
            it.status = "Rejected"
            self.history.append(
                HistoryEntry(self._now(), "Reject", it.original_filename, "")
            )

    def move_to_fallback(self, idxs: List[int]):
        for i in idxs:
            it = self.items[i]
            it.edited_folder = self.cfg.paths.fallback_dir.name
            it.target_folder = self.cfg.paths.fallback_dir.name
            it.status = "Accepted"
            self.history.append(
                HistoryEntry(self._now(), "ToFallback", it.original_filename, "")
            )

    def apply_selected(self, idxs: List[int], dry_run: bool = False):
        for i in idxs:
            it = self.items[i]
            if it.status not in {"Accepted"}:
                continue
            if not it.planned_target_path:
                it.status = "Error"
                it.error = "No planned target path"
                continue

            # If user edited folder/name, rebuild the final target path
            target_path = it.planned_target_path

            if dry_run:
                it.status = "Processed"
                self.history.append(
                    HistoryEntry(
                        self._now(), "ApplyDry", it.original_filename, str(target_path)
                    )
                )
                continue

            try:
                ensure_dir(target_path.parent)
                src = it.input_path
                move_file(src, target_path)
                self.undo_stack.append(UndoEntry(from_path=target_path, to_path=src))
                it.status = "Processed"
                self.history.append(
                    HistoryEntry(
                        self._now(), "Apply", it.original_filename, str(target_path)
                    )
                )
            except Exception as e:
                it.status = "Error"
                it.error = str(e)
                self.history.append(
                    HistoryEntry(
                        self._now(), "ApplyError", it.original_filename, str(e)
                    )
                )

    def undo_last(self):
        if not self.undo_stack:
            return
        u = self.undo_stack.pop()
        try:
            ensure_dir(u.to_path.parent)
            move_file(u.from_path, u.to_path)
            self.history.append(
                HistoryEntry(self._now(), "Undo", u.from_path.name, str(u.to_path))
            )
        except Exception as e:
            self.history.append(
                HistoryEntry(self._now(), "UndoError", u.from_path.name, str(e))
            )

    def reveal_in_finder(self, path: Path):
        try:
            subprocess.run(["open", "-R", str(path)], check=False)
        except Exception:
            pass
