from pathlib import Path
import tempfile

from pdf_filer.naming import sanitize_filename, resolve_collision

def test_sanitize_filename_basic():
    assert sanitize_filename("  Rechnung: Telekom/DSL  ") == "Rechnung- Telekom-DSL"
    assert sanitize_filename("") == "Dokument"

def test_resolve_collision_suffix():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        (p / "2025-11-11 Rechnung.pdf").write_text("x")
        out = resolve_collision(p, "2025-11-11 Rechnung", ".pdf", "_{n}", 999)
        assert out.name == "2025-11-11 Rechnung_1.pdf"
