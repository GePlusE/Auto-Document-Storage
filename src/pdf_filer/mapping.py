from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import json


@dataclass
class SenderMapping:
    folders: Dict[str, str]
    synonyms: Dict[str, str]


def load_sender_mapping(path: Path) -> SenderMapping:
    data = json.loads(path.read_text(encoding="utf-8"))
    folders = data.get("folders", {}) or {}
    synonyms = data.get("synonyms", {}) or {}
    return SenderMapping(folders=dict(folders), synonyms=dict(synonyms))


def normalize_sender(s: str) -> str:
    return " ".join((s or "").strip().split())


class SenderMapper:
    def __init__(self, mapping: SenderMapping):
        self.mapping = mapping

    def canonicalize(self, sender: str) -> str:
        sender_n = normalize_sender(sender)
        # Direct synonym mapping (exact)
        return normalize_sender(self.mapping.synonyms.get(sender_n, sender_n))

    def folder_for(self, sender_canonical: str) -> Optional[str]:
        sender_canonical = normalize_sender(sender_canonical)
        return self.mapping.folders.get(sender_canonical)
