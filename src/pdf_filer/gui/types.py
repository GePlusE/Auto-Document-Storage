from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import datetime as dt


@dataclass
class PlanItem:
    input_path: Path
    original_filename: str
    date_prefix: str = ""  # e.g. 2025-12-26 (from metadata/birthtime/mtime)
    naming_template: str = ""  # template used for filename stem (F29)

    sender: str = ""
    conf_final: float = 0.0
    conf_stage1: float = 0.0
    conf_stage2: float = 0.0
    stage_used: int = 0

    document_type: str = "other"
    filename_label: str = "Dokument"

    # LLM routing extras
    llm_target_folder: str = ""
    llm_is_private: bool = False
    llm_folder_reason: str = ""

    # final routing decision
    target_folder: str = ""
    planned_target_path: Optional[Path] = None

    extraction_method: str = ""
    pages_processed: int = 0
    evidence: List[str] = field(default_factory=list)
    notes: str = ""

    # mapping explainability
    mapping_match_type: str = ""  # exact/synonym/contains/regex/none
    mapping_match_value: str = ""

    # UI state
    status: str = "Pending"  # Pending/Accepted/Rejected/Processed/Error
    error: str = ""

    # user edits
    edited_folder: Optional[str] = None
    edited_filename_stem: Optional[str] = None

    created_at: str = field(
        default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds")
    )

    def effective_folder(self) -> str:
        return (self.edited_folder or self.target_folder or "").strip()

    def effective_filename_stem(self) -> str:
        return (self.edited_filename_stem or self.filename_label or "Dokument").strip()
