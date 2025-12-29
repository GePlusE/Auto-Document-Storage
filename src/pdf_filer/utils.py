from __future__ import annotations

import hashlib
import re

from pathlib import Path

IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def redact_sensitive(text: str) -> str:
    # Very lightweight redaction: IBANs and emails.
    text = IBAN_RE.sub("[REDACTED_IBAN]", text)
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    return text


def alnum_ratio(text: str) -> float:
    if not text:
        return 0.0
    alnum = sum(1 for ch in text if ch.isalnum())
    return alnum / max(1, len(text))


def file_fingerprint_sha256(path: Path, max_bytes: int = 5_000_000) -> str:
    """
    Stable fingerprint: sha256 over first max_bytes + file size.
    Good tradeoff: stable across renames/moves, fast enough for typical PDFs.
    """
    h = hashlib.sha256()
    p = Path(path)

    size = p.stat().st_size
    h.update(str(size).encode("utf-8"))
    h.update(b"|")

    with p.open("rb") as f:
        remaining = max_bytes
        while remaining > 0:
            chunk = f.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)

    return h.hexdigest()
