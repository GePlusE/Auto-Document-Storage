from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List
import yaml


@dataclass(frozen=True)
class PathsConfig:
    input_dir: Path
    documents_dir: Path
    fallback_dir: Path
    db_path: Path
    logs_dir: Path
    mapping_json: Path


@dataclass(frozen=True)
class OCRConfig:
    use_vision: bool = True
    max_pages: int = 5
    dpi: int = 250
    min_text_chars: int = 150
    min_alnum_ratio: float = 0.35


@dataclass(frozen=True)
class ClassificationConfig:
    ollama_host: str
    stage1_model: str
    stage2_model: str
    stage3_model: str = ""
    threshold_accept: float = 0.80
    threshold_safe_to_file: float = 0.70
    temperature: float = 0.0
    max_input_chars: int = 12000
    require_evidence: bool = True
    timeout_seconds: int = 90


@dataclass(frozen=True)
class MappingConfig:
    route_unknown_sender_to_fallback: bool = False


@dataclass(frozen=True)
class RenamingConfig:
    separator: str = " "
    collision_suffix_format: str = "_{n}"
    max_suffix: int = 999
    date_source_priority: List[str] = None
    filename_max_len: int = 120
    keep_umlauts: bool = True


@dataclass(frozen=True)
class AppConfig:
    paths: PathsConfig
    ocr: OCRConfig
    classification: ClassificationConfig
    mapping: MappingConfig
    renaming: RenamingConfig


def _as_path(v: Any) -> Path:
    return Path(str(v)).expanduser()


def load_config(path: Path) -> AppConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")

    p = data.get("paths", {})
    paths = PathsConfig(
        input_dir=_as_path(p["input_dir"]),
        documents_dir=_as_path(p["documents_dir"]),
        fallback_dir=_as_path(p["fallback_dir"]),
        db_path=_as_path(p["db_path"]),
        logs_dir=_as_path(p["logs_dir"]),
        mapping_json=_as_path(p["mapping_json"]),
    )

    o = data.get("ocr", {}) or {}
    ocr = OCRConfig(
        use_vision=bool(o.get("use_vision", True)),
        max_pages=int(o.get("max_pages", 5)),
        dpi=int(o.get("dpi", 250)),
        min_text_chars=int(o.get("min_text_chars", 150)),
        min_alnum_ratio=float(o.get("min_alnum_ratio", 0.35)),
    )

    c = data.get("classification", {})
    clf = ClassificationConfig(
        ollama_host=str(c.get("ollama_host", "http://localhost:11434")),
        stage1_model=str(c.get("stage1_model", "qwen2.5:1.5b-instruct")),
        stage2_model=str(c.get("stage2_model", "qwen2.5:3b-instruct")),
        stage3_model=str(c.get("stage3_model", "")),
        threshold_accept=float(c.get("threshold_accept", 0.80)),
        threshold_safe_to_file=float(c.get("threshold_safe_to_file", 0.70)),
        temperature=float(c.get("temperature", 0.0)),
        max_input_chars=int(c.get("max_input_chars", 12000)),
        require_evidence=bool(c.get("require_evidence", True)),
        timeout_seconds=int(c.get("timeout_seconds", 90)),
    )

    m = data.get("mapping", {}) or {}
    mapping = MappingConfig(route_unknown_sender_to_fallback=bool(m.get("route_unknown_sender_to_fallback", False)))

    r = data.get("renaming", {}) or {}
    date_prio = r.get("date_source_priority", ["pdf_meta", "file_birthtime", "mtime", "today"])
    renaming = RenamingConfig(
        separator=str(r.get("separator", " ")),
        collision_suffix_format=str(r.get("collision_suffix_format", "_{n}")),
        max_suffix=int(r.get("max_suffix", 999)),
        date_source_priority=list(date_prio),
        filename_max_len=int(r.get("filename_max_len", 120)),
        keep_umlauts=bool(r.get("keep_umlauts", True)),
    )

    return AppConfig(paths=paths, ocr=ocr, classification=clf, mapping=mapping, renaming=renaming)
