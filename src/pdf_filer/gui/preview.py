from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF
from PySide6.QtGui import QImage


class PdfPreview:
    def __init__(self, path: Path):
        self.path = path
        self.doc = fitz.open(str(path))
        self.page_count = self.doc.page_count

    def render_page(self, page_index: int, zoom: float = 1.0) -> QImage:
        page_index = max(0, min(self.page_count - 1, page_index))
        page = self.doc.load_page(page_index)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        fmt = QImage.Format_RGB888
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        return img.copy()  # copy because pix buffer will be freed

    def render_thumbnails(self, zoom: float = 0.2, max_pages: int = 30) -> List[QImage]:
        thumbs: List[QImage] = []
        n = min(self.page_count, max_pages)
        for i in range(n):
            thumbs.append(self.render_page(i, zoom=zoom))
        return thumbs

    def close(self):
        try:
            self.doc.close()
        except Exception:
            pass
