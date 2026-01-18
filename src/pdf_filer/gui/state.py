from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import datetime as dt
import subprocess

from ..mover import ensure_dir, move_file
from .types import PlanItem
from ..pdf_text import choose_date_prefix


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

    def set_items(self, items: List[PlanItem], action: str = "DryRun"):
        self.items = items
        self.history.append(
            HistoryEntry(self._now(), action, f"{len(items)} files", "")
        )

    def make_placeholder_item(self, path: Path) -> PlanItem:
        """
        Create a PlanItem with minimal defaults (no OCR/LLM run).
        Used for initial GUI list and for cached DB restores.
        """

        try:
            date_prefix, _src = choose_date_prefix(
                path, self.cfg.renaming.date_source_priority
            )
        except Exception:
            date_prefix = ""

        return PlanItem(
            input_path=path,
            original_filename=path.name,
            date_prefix=date_prefix,
            naming_template="",
            sender="",
            conf_final=0.0,
            conf_stage1=0.0,
            conf_stage2=0.0,
            stage_used=0,
            document_type="other",
            filename_label="Dokument",
            llm_target_folder="",
            llm_is_private=False,
            llm_folder_reason="",
            target_folder="",
            planned_target_path=None,
            extraction_method="",
            pages_processed=0,
            evidence=[],
            notes="",
            mapping_match_type="",
            mapping_match_value="",
            status="Pending",
            error="",
            edited_folder=None,
            edited_filename_stem=None,
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

            folder = it.effective_folder()
            stem = it.effective_filename_stem()

            if folder and stem:
                # keep original extension
                ext = it.input_path.suffix if it.input_path.suffix else ".pdf"

                # keep date_prefix if available, otherwise try to read from planned filename
                date_prefix = (it.date_prefix or "").strip()
                if not date_prefix and it.planned_target_path:
                    # Try parse YYYY-MM-DD prefix from planned filename
                    parts = it.planned_target_path.stem.split(" ", 1)
                    if parts and len(parts[0]) == 10:
                        date_prefix = parts[0]

                # Build base name (no collision handling here; apply can collision-check if you want)
                if date_prefix:
                    new_name = f"{date_prefix} {stem}".strip() + ext
                else:
                    new_name = f"{stem}".strip() + ext

                target_dir = self.cfg.paths.documents_dir / folder
                target_path = target_dir / new_name

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
