from pdf_filer.utils import alnum_ratio

def test_alnum_ratio():
    assert alnum_ratio("abc 123") > 0.5
    assert alnum_ratio("!!!") == 0.0
