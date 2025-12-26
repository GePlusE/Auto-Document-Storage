from __future__ import annotations

from pathlib import Path
import re
import unicodedata


INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')
WHITESPACE = re.compile(r"\s+")


def sanitize_filename(name: str, keep_umlauts: bool = True, max_len: int = 120) -> str:
    name = (name or "").strip()
    name = INVALID_CHARS.sub("-", name)
    name = WHITESPACE.sub(" ", name).strip(" .")
    if not keep_umlauts:
        # transliterate-ish: remove diacritics
        name = unicodedata.normalize("NFKD", name)
        name = "".join(ch for ch in name if not unicodedata.combining(ch))
    # prevent empty
    if not name:
        name = "Dokument"
    if len(name) > max_len:
        name = name[:max_len].rstrip(" .")
    return name


def build_base_name(date_prefix: str, original_stem: str, separator: str, keep_umlauts: bool, max_len: int) -> str:
    stem = sanitize_filename(original_stem, keep_umlauts=keep_umlauts, max_len=max_len)
    return f"{date_prefix}{separator}{stem}".strip()


def resolve_collision(target_dir: Path, base_name: str, ext: str, suffix_format: str, max_suffix: int) -> Path:
    candidate = target_dir / f"{base_name}{ext}"
    if not candidate.exists():
        return candidate
    for n in range(1, max_suffix + 1):
        candidate = target_dir / f"{base_name}{suffix_format.format(n=n)}{ext}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many collisions for {base_name}{ext} in {target_dir}")
