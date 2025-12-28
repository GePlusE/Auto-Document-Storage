from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple, Optional

from ..naming import build_base_name, resolve_collision


_INVALID_CHARS_RE = re.compile(
    r"[\/:\*\?\"<>\|]"
)  # Windows-invalid; also good cross-platform


def validate_folder_name(folder: str) -> List[str]:
    errs: List[str] = []
    folder = (folder or "").strip()
    if not folder:
        errs.append("Zielordner darf nicht leer sein.")
        return errs
    if folder in {".", ".."}:
        errs.append("Ungültiger Ordnername.")
    if _INVALID_CHARS_RE.search(folder):
        errs.append('Zielordner enthält ungültige Zeichen (z.B. / : * ? " < > |).')
    if len(folder) > 80:
        errs.append("Zielordner ist sehr lang (>= 80 Zeichen).")
    return errs


def validate_filename_stem(stem: str, max_len: int = 120) -> List[str]:
    errs: List[str] = []
    s = (stem or "").strip()
    if not s:
        errs.append("Dateiname-Label darf nicht leer sein.")
        return errs
    if _INVALID_CHARS_RE.search(s):
        errs.append('Dateiname enthält ungültige Zeichen (z.B. / : * ? " < > |).')
    if s.endswith("."):
        errs.append("Dateiname darf nicht mit Punkt enden.")
    if len(s) > 60:
        errs.append("Label ist sehr lang (empfohlen: <= 60 Zeichen).")
    return errs


def render_template(
    template: str,
    *,
    date_prefix: str,
    sender: str,
    doctype: str,
    folder: str,
    label: str,
) -> str:
    """
    Supported tokens:
      {{date}}, {{sender}}, {{doctype}}, {{folder}}, {{label}}

    We do not enforce the "no digits" rule here because templates are for filenames,
    not for the LLM's label field.
    """
    t = (template or "").strip()
    if not t:
        return ""

    # Safe fallbacks
    sender = (sender or "").strip()
    doctype = (doctype or "").strip()
    folder = (folder or "").strip()
    label = (label or "").strip() or "Dokument"

    out = t
    out = out.replace("{{date}}", date_prefix)
    out = out.replace("{{sender}}", sender)
    out = out.replace("{{doctype}}", doctype)
    out = out.replace("{{folder}}", folder)
    out = out.replace("{{label}}", label)

    # Collapse whitespace (keep underscores etc. as user intended)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def compute_collision_preview(
    *,
    cfg,
    pdf_path: Path,
    date_prefix: str,
    folder: str,
    filename_label: str,
    template: str = "",
    sender: str = "",
    doctype: str = "",
) -> Tuple[Path, str]:
    """
    Returns:
      - planned target path (with collision suffix resolved)
      - human-friendly collision note ("" if none)
    """
    folder = (folder or "").strip()
    filename_label = (filename_label or "Dokument").strip() or "Dokument"
    template = (template or "").strip()

    if folder == cfg.paths.fallback_dir.name:
        target_dir = cfg.paths.fallback_dir
    else:
        target_dir = cfg.paths.documents_dir / folder

    # Default stem behavior (current project logic)
    hint = "Unklar" if folder == cfg.paths.fallback_dir.name else folder
    default_stem = f"{filename_label} {hint}".strip()

    # Render template (F29)
    # If template contains {{date}}, we let the template own the date (no separate date_prefix added).
    used_template = template if template else "{{label}} {{folder}}"
    rendered = render_template(
        used_template,
        date_prefix=date_prefix,
        sender=sender,
        doctype=doctype,
        folder=folder,
        label=filename_label,
    ).strip()

    if not rendered:
        rendered = default_stem

    if "{{date}}" in used_template:
        # Template includes date already
        date_for_builder = ""
        original_stem = rendered
    else:
        date_for_builder = date_prefix
        original_stem = rendered

    base_name = build_base_name(
        date_prefix=date_for_builder,
        original_stem=original_stem,
        separator=cfg.renaming.separator,
        keep_umlauts=cfg.renaming.keep_umlauts,
        max_len=cfg.renaming.filename_max_len,
    )

    ext = pdf_path.suffix if pdf_path.suffix else ".pdf"
    planned = resolve_collision(
        target_dir=target_dir,
        base_name=base_name,
        ext=ext,
        suffix_format=cfg.renaming.collision_suffix_format,
        max_suffix=cfg.renaming.max_suffix,
    )

    expected = f"{base_name}{ext}"
    note = (
        f"Kollision erkannt → umbenannt zu: {planned.name}"
        if planned.name != expected
        else ""
    )
    return planned, note
