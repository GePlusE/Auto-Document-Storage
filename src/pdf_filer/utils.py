from __future__ import annotations

import re

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
