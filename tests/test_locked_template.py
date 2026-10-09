import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from studio.locked_template import create_templates, resolve_template, clean_content, policy, check_contract, paragraph
from studio.runtime import StudioError


def request():
    return {"template_id": "reference-journal-v1", "template_version": 1}


@pytest.fixture
def masters(tmp_path, monkeypatch):
    create_templates(tmp_path)
    monkeypatch.setenv("RPS_TEMPLATE_ROOT", str(tmp_path))
    return tmp_path


def test_master_variants(masters):
    for variant, expected in (("front", [1, 2]), ("end", [1, 2, 1])):
        path, p, identity = resolve_template({**request(), "template_variant": variant})
        assert check_contract(path, p)["section_columns"] == expected
        assert "{{RPS_BODY}}" in "".join(par.text for par in Document(path).paragraphs)
        assert len(identity["sha256"]) == 64


@pytest.mark.parametrize("key", ["profile", "fonts", "columns", "page", "styles", "template_path", "sections"])
def test_content_cannot_override_template(key, masters):
    with pytest.raises(StudioError, match="TEMPLATE_OVERRIDE_FORBIDDEN"):
        resolve_template({**request(), key: "injected"})


def test_master_tampering_fails(masters):
    with (masters/"master-front.docx").open("ab") as stream: stream.write(b"changed")
    with pytest.raises(StudioError, match="TEMPLATE_FINGERPRINT_MISMATCH"): resolve_template(request())


def test_content_format_is_removed():
    par = paragraph("内容", "Body")
    props = par.find(qn("w:pPr")); props.append(OxmlElement("w:sectPr")); props.append(OxmlElement("w:tabs"))
    run = par.find(qn("w:r")); direct = OxmlElement("w:rPr")
    direct.append(OxmlElement("w:sz")); direct.append(OxmlElement("w:rFonts")); direct.append(OxmlElement("w:b")); run.insert(0, direct)
    clean_content(par, policy())
    assert par.find(qn("w:pPr")+"/"+qn("w:sectPr")) is None
    assert par.find(qn("w:pPr")+"/"+qn("w:tabs")) is None
    assert direct.find(qn("w:sz")) is None and direct.find(qn("w:rFonts")) is None
    assert direct.find(qn("w:b")) is not None


def test_unknown_version_rejected(masters):
    with pytest.raises(StudioError, match="UNKNOWN_TEMPLATE_VERSION"): resolve_template({**request(), "template_version": 9})
