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


def test_piecewise_stacking_preserves_value_condition_order():
    from copy import deepcopy
    from studio.math_layout import wrap, restore, tree
    formula = OxmlElement("m:oMath"); delimiter = OxmlElement("m:d")
    props = OxmlElement("m:dPr")
    for name,value in (("begChr","{"),("endChr","")):
        node = OxmlElement("m:"+name); node.set(qn("m:val"),value); props.append(node)
    delimiter.append(props); argument=OxmlElement("m:e"); delimiter.append(argument)
    matrix=OxmlElement("m:m"); argument.append(matrix); formula.append(delimiter)
    for values in (("expressionexpression","conditioncondition"),("otherexpression","otherwise")):
        row=OxmlElement("m:mr"); matrix.append(row)
        for value in values:
            cell=OxmlElement("m:e"); run=OxmlElement("m:r"); token=OxmlElement("m:t"); token.text=value
            run.append(token); cell.append(run); row.append(cell)
    original=deepcopy(formula); changes=wrap(formula,100)
    assert tree(restore(formula,changes))==tree(original)
    assert [t.text for t in formula.iter(qn("m:t"))]==[t.text for t in original.iter(qn("m:t"))]
    assert all(len(row.findall(qn("m:e")))==1 for row in matrix.findall(qn("m:mr")))


def test_parenthesized_objective_wraps_without_losing_bracket_scope():
    from copy import deepcopy
    from studio.math_layout import wrap,restore,tree
    formula=OxmlElement("m:oMath")
    for text in ("min(","aaaaaaaaaaaa(x)",",","bbbbbbbbbbbb(x)",",","cccccccccccc(x)",")"):
        run=OxmlElement("m:r");token=OxmlElement("m:t");token.text=text;run.append(token);formula.append(run)
    original=deepcopy(formula);ledger=wrap(formula,150)
    assert formula.find(qn("m:eqArr")) is not None
    assert tree(restore(formula,ledger))==tree(original)
    assert "".join(t.text for t in formula.iter(qn("m:t")))=="min(aaaaaaaaaaaa(x),bbbbbbbbbbbb(x),cccccccccccc(x))"

def test_transparent_nested_math_boxes_do_not_consume_column_width():
    from copy import deepcopy
    from studio.math_layout import wrap,tree
    formula=OxmlElement("m:oMath");argument=formula
    for _ in range(12):
        box=OxmlElement("m:box");entry=OxmlElement("m:e");box.append(entry);argument.append(box);argument=entry
    token=OxmlElement("m:r");text=OxmlElement("m:t");text.text="f(aa,bb)";token.append(text);argument.append(token)
    original=deepcopy(formula)
    assert wrap(formula,80)==[]
    assert tree(formula)==tree(original)


def test_nested_math_measurement_visits_each_node_once(monkeypatch):
    import studio.docx_layout as layout
    formula=OxmlElement("m:oMath");argument=formula
    for _ in range(12):
        box=OxmlElement("m:box");entry=OxmlElement("m:e");box.append(entry);argument.append(box);argument=entry
    token=OxmlElement("m:r");text=OxmlElement("m:t");text.text="x";token.append(text);argument.append(token)
    implementation=layout.math_width_pt;calls=[]
    def counted(element,size):
        calls.append(element);return implementation(element,size)
    monkeypatch.setattr(layout,"math_width_pt",counted)
    assert counted(formula,10)==7
    assert len(calls)==len(list(formula.iter()))


def test_inline_formula_reserves_attached_punctuation_but_not_prose():
    from studio.docx_layout import following_punctuation_width
    paragraph=OxmlElement("w:p");formula=OxmlElement("m:oMath");paragraph.append(formula)
    run=OxmlElement("w:r");text=OxmlElement("w:t");text.text="，后续说明";run.append(text);paragraph.append(run)
    assert following_punctuation_width(formula,10)==10
    text.text="。";assert following_punctuation_width(formula,10)==10
    text.text=" suffix";assert following_punctuation_width(formula,10)==0


@pytest.mark.parametrize("expression_right,expected",[(180,False),(202,True)])
def test_rendered_equation_number_region_rejects_collision(expression_right,expected):
    from studio.math_proof import number_region
    number={"text":"(M24)","x0":200,"x1":226,"top":100,"bottom":112}
    expression={"text":"x","x0":170,"x1":expression_right,"top":103,"bottom":112}
    class Page:
        chars=[number,expression]
        def search(self,*args,**kwargs):return [{**number,"chars":[number]}]
    assert bool(number_region(Page(),"(M24)")["violations"])==expected


def test_packaged_image_import_preserves_opaque_bytes_and_drawing_extent(tmp_path):
    from copy import deepcopy
    from io import BytesIO
    from PIL import Image
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from studio.locked_template import import_resources
    source=Document();buffer=BytesIO();Image.new("RGB",(8,5),"white").save(buffer,format="PNG")
    picture=source.add_picture(BytesIO(buffer.getvalue()))
    source_image=next(r.target_part for r in source.part.rels.values() if r.reltype==RT.IMAGE)
    # The importer is a package transfer, not another image decoder. A retained
    # payload must not depend on ImagePart.image/default_cx or be recompressed.
    opaque=b"header-not-supported-by-python-docx"+buffer.getvalue()
    source_image._blob=opaque
    target=Document();elements=[deepcopy(source.paragraphs[-1]._p)]
    original_extent=dict(elements[0].find(".//"+qn("wp:extent")).attrib)
    import_resources(source,target,elements)
    imported=next(r.target_part for r in target.part.rels.values() if r.reltype==RT.IMAGE)
    assert imported is not source_image and imported.blob==opaque
    assert imported.content_type==source_image.content_type
    assert elements[0].find(".//"+qn("wp:extent")).attrib==original_extent
    target._element.body.insert(0,elements[0]);path=tmp_path/"retained.docx";target.save(path)
    reopened=Document(path)
    assert next(r.target_part.blob for r in reopened.part.rels.values() if r.reltype==RT.IMAGE)==opaque
