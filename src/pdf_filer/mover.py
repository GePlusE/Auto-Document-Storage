from __future__ import annotations

from pathlib import Path
import shutil


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def move_file(src: Path, dst: Path):
    ensure_dir(dst.parent)
    # shutil.move is usually atomic on same filesystem.
    shutil.move(str(src), str(dst))
