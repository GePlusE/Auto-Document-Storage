from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import os
import datetime as dt
import re

import fitz  # PyMuPDF

PDF_DATE_RE = re.compile(r"^D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?")


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    method: str  # textlayer | vision_ocr
    pages_processed: int


def extract_textlayer(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    try:
        chunks = []
        for page in doc:
            chunks.append(page.get_text("text"))
        return "\n".join(chunks).strip()
    finally:
        doc.close()


def render_pages(pdf_path: Path, max_pages: int, dpi: int) -> List[bytes]:
    """Render first N pages to PNG bytes using PyMuPDF."""
    doc = fitz.open(pdf_path)
    try:
        images = []
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(matrix=mat, alpha=False)
            images.append(pix.tobytes("png"))
        return images
    finally:
        doc.close()


def _parse_pdf_date(s: str) -> Optional[dt.date]:
    if not s:
        return None
    m = PDF_DATE_RE.match(s.strip())
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def get_pdf_metadata_date(pdf_path: Path) -> Optional[dt.date]:
    doc = fitz.open(pdf_path)
    try:
        md = doc.metadata or {}
        # Prefer creationDate; fallback to modDate
        for key in ("creationDate", "modDate", "CreationDate", "ModDate"):
            val = md.get(key)
            d = _parse_pdf_date(val) if isinstance(val, str) else None
            if d:
                return d
        return None
    finally:
        doc.close()


def get_file_birthtime_date(path: Path) -> Optional[dt.date]:
    try:
        st = os.stat(path)
        # macOS has st_birthtime
        bt = getattr(st, "st_birthtime", None)
        if bt is None:
            return None
        return dt.datetime.fromtimestamp(bt).date()
    except Exception:
        return None


def get_file_mtime_date(path: Path) -> Optional[dt.date]:
    try:
        st = os.stat(path)
        return dt.datetime.fromtimestamp(st.st_mtime).date()
    except Exception:
        return None


def choose_date_prefix(pdf_path: Path, priority: List[str]) -> Tuple[str, str]:
    """Return (YYYY-MM-DD, source). Source one of: pdf_meta|file_birthtime|mtime|today"""
    today = dt.date.today()
    for src in priority:
        src = str(src).lower()
        if src == "pdf_meta":
            d = get_pdf_metadata_date(pdf_path)
            if d:
                return (d.isoformat(), "pdf_meta")
        elif src == "file_birthtime":
            d = get_file_birthtime_date(pdf_path)
            if d:
                return (d.isoformat(), "file_birthtime")
        elif src == "mtime":
            d = get_file_mtime_date(pdf_path)
            if d:
                return (d.isoformat(), "mtime")
        elif src == "today":
            return (today.isoformat(), "today")
    return (today.isoformat(), "today")
