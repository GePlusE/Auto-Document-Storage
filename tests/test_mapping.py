from pdf_filer.mapping import SenderMapping, SenderMapper

def test_canonicalize_synonym():
    mapping = SenderMapping(
        folders={"Stadtwerke München": "SWM"},
        synonyms={"Stadtwerke Muenchen": "Stadtwerke München"}
    )
    mapper = SenderMapper(mapping)
    assert mapper.canonicalize("Stadtwerke Muenchen") == "Stadtwerke München"
    assert mapper.folder_for("Stadtwerke München") == "SWM"
