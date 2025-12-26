from __future__ import annotations

from pathlib import Path
from typing import List


def list_pdfs(input_dir: Path, recursive: bool = False) -> List[Path]:
    if not input_dir.exists():
        return []
    pattern = "**/*.pdf" if recursive else "*.pdf"
    files = [p for p in input_dir.glob(pattern) if p.is_file()]
    # Filter common macOS temp/metadata files
    filtered = []
    for p in files:
        name = p.name
        if name.startswith("._") or name.startswith("~") or name.lower() == ".ds_store":
            continue
        filtered.append(p)
    return sorted(filtered)
