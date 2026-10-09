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
        math=Document(path).settings.element.findall(qn("m:mathPr"))
        assert len(math)==1 and math[0].find(qn("m:mathFont")).get(qn("m:val"))=="Latin Modern Math"


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


def test_math_row_wrap_is_reversible():
    from lxml import etree
    from copy import deepcopy
    from studio.math_layout import wrap, restore, tree
    formula = OxmlElement("m:oMath")
    for text in ("a", "+bbbbbbbbbbbb", "+cccccccccccc", "=d"):
        run = OxmlElement("m:r"); token = OxmlElement("m:t"); token.text = text; run.append(token); formula.append(run)
    before = deepcopy(formula)
    ledger = wrap(formula, 80)
    assert ledger and tree(restore(formula,ledger)) == tree(before)
    formula.find(".//"+qn("m:t")).text = "changed"
    with pytest.raises(StudioError, match="MATH_LAYOUT_TRANSFORM_MISMATCH"): restore(formula,ledger)


def test_fill_imports_content_without_source_styles(masters, tmp_path):
    from studio.locked_template import fill
    doc = Document(); doc.add_paragraph("模型正文", style="Heading 1")
    doc.add_paragraph("列表正文")
    source = tmp_path/"source.docx"; doc.save(source)
    master, p, identity = resolve_template(request())
    final = tmp_path/"final.docx"
    report = fill(source,{"title_zh":"题名"},[],master,p,final)
    assert report["section_columns"] == [1,2]
    result = Document(final)
    assert "模型正文" in "".join(par.text for par in result.paragraphs)
    assert result.styles["RPSBody"].font.size.pt == 10


def test_markdown_layout_attributes_are_not_exported():
    from studio.manuscript import strip_layout_attributes
    ast={"blocks":[{"t":"Image","c":[["fig:F1",["custom-style"],[["width","200%"],["font-size","48pt"]]],[],["x.png",""]]}]}
    removed=strip_layout_attributes(ast)
    assert removed and ast["blocks"][0]["c"][0] == ["fig:F1",[],[]]


def test_latex_layout_commands_rejected(tmp_path):
    from studio.manuscript import parse
    source=tmp_path/"override.md"; source.write_text(r"$$\small x+y$$")
    with pytest.raises(StudioError,match="CONTENT_LAYOUT_COMMAND_FORBIDDEN"): parse(source,tmp_path)


def test_unknown_request_field_fails(masters):
    with pytest.raises(StudioError,match="UNKNOWN_REQUEST_FIELDS"):
        resolve_template({**request(),"custom_layout_override": {"columns":1}})


def test_physical_section_tampering_fails(masters,tmp_path):
    master,p,_=resolve_template(request())
    doc=Document(master); doc.sections[1]._sectPr.find(qn("w:cols")).set(qn("w:num"),"1")
    bad=tmp_path/"bad.docx";doc.save(bad)
    with pytest.raises(StudioError,match="TEMPLATE_SECTIONS_CHANGED"):check_contract(bad,p)


def test_glyph_probe_ignores_only_invisible_spacing():
    from studio.math_proof import glyphs
    assert glyphs("x\u200b≤y = z") == glyphs("x≤y=z")
    assert glyphs("x<y") != glyphs("xy")
