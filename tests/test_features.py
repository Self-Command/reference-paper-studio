import json
from copy import deepcopy
from pathlib import Path
import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from studio.runtime import StudioError, digest
from studio.references import resolve_rules, inspect_pdf
from studio.manuscript import parse, validate_assets, validate_references, model_gate
from studio.docx_layout import move_table_captions, apply_layout
from studio.pipeline import strict_pandoc
from studio.qa import check_fonts, check_docx, assert_text
from studio.vendor.latex_to_omml import latex_to_omml

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT/"assets/profiles/chinese-journal.json").read_text())


def observation(value, source):
    return {"property":"layout", "value":value, "source":source, "pages":[1], "reviewed":True}


def test_reference_consensus_beats_official():
    result = resolve_rules([observation(2,"P1"), observation(2,"P2")], {"layout":{**observation(1,"J1")}})
    assert result[0]["value"] == 2
    assert result[0]["status"] == "reference_consensus"


def test_conflict_uses_official_only_with_evidence():
    assert resolve_rules([observation(2,"P1"),observation(1,"P2")])[0]["status"] == "conflicting"
    assert resolve_rules([observation(2,"P1"),observation(1,"P2")], {"layout":observation(1,"J1")})[0]["status"] == "official_disambiguation"


def test_single_source_and_bad_extraction_unconfirmed():
    assert resolve_rules([observation(2,"P1")])[0]["status"] == "unconfirmed"
    assert resolve_rules([{**observation(2,"P1"),"quality":"needs_review"},observation(2,"P2")])[0]["status"] == "unconfirmed"


def test_scanned_pdf_unreliable(tmp_path):
    from pypdf import PdfWriter
    p = tmp_path/"scan.pdf"; w = PdfWriter(); w.add_blank_page(width=595,height=842); w.write(p)
    assert inspect_pdf(p)["pages"][0]["quality"] == "needs_review"


def test_original_model_has_all_30_equations(tmp_path):
    _, eq = parse(ROOT/"fixtures/model/model.md", tmp_path)
    assert [e["id"] for e in eq] == [f"M{i}" for i in range(1,31)]


def test_duplicate_equation_rejected(tmp_path):
    p=tmp_path/"dup.md"; p.write_text(r"\[x\tag{M1}\]"+"\n\n"+r"\[y\tag{M1}\]")
    with pytest.raises(StudioError, match="DUPLICATE_EQUATION"): parse(p,tmp_path)


def test_missing_asset_rejected():
    with pytest.raises(StudioError, match="MISSING_IMAGE"):
        validate_assets({"t":"Image","c":[[],[],["missing.png",""]]},ROOT)


def test_broken_numeric_reference():
    with pytest.raises(StudioError, match="BROKEN_REFERENCE"):
        validate_references({"blocks":[{"t":"Str","c":"正文[3]参考文献[1]"}]})


def test_unverified_model_blocked():
    with pytest.raises(StudioError, match="MODEL_NOT_VERIFIED"): model_gate(ROOT,"fixtures/model/model.md",None,True)


def test_stale_verification_blocked(tmp_path):
    (tmp_path/"model.md").write_text("model")
    (tmp_path/"report.md").write_text("human verification report")
    (tmp_path/"evidence.json").write_text(json.dumps({"status":"passed","author_approved":True,"model":"model.md","report":"report.md","model_sha256":"old","report_sha256":digest(tmp_path/"report.md")}))
    with pytest.raises(StudioError, match="MODEL_NOT_VERIFIED"): model_gate(tmp_path,"model.md","evidence.json",True)


def test_missing_experiment_source_blocked(tmp_path):
    for name in ("model.md","report.md"): (tmp_path/name).write_text(name)
    evidence={"status":"passed","author_approved":True,"model":"model.md","report":"report.md","model_sha256":digest(tmp_path/"model.md"),"report_sha256":digest(tmp_path/"report.md"),"quantitative_claims":[{"value":"97%"}]}
    (tmp_path/"evidence.json").write_text(json.dumps(evidence))
    with pytest.raises(StudioError, match="CLAIM_WITHOUT_EVIDENCE"): model_gate(tmp_path,"model.md","evidence.json",True)


def test_unknown_formula_command_fails(tmp_path):
    p=tmp_path/"bad.md"; p.write_text(r"$\unsupportedstudio{x}$")
    with pytest.raises(StudioError, match="CONVERSION_FAILED"): strict_pandoc(["pandoc",p,"-o",tmp_path/"bad.docx"])


def test_mit_formula_converter_native():
    result=latex_to_omml(r"\sum_{i=1}^n \frac{x_i^2}{y_i}")
    assert result is not None


def test_caption_repair_does_not_treat_equation_as_table(tmp_path):
    doc=Document(); table=doc.add_table(rows=2,cols=2)
    table.cell(0,0).text="项目"; table.cell(0,1).text="数值"
    doc.add_paragraph("表1 示例表 / Table 1 Example")
    doc.add_paragraph("公式另行处理")
    assert move_table_captions(doc)==1
    assert table._tbl.getprevious().tag == qn("w:p")


@pytest.mark.parametrize("position", ["front","end"])
def test_front_body_sections_preserved(tmp_path,position):
    doc=Document(); doc.add_paragraph("模型正文"); path=tmp_path/"layout.docx"; doc.save(path)
    profile=deepcopy(PROFILE); profile["english_abstract_position"]=position
    apply_layout(path,{"title_zh":"中文题名","abstract_zh":"摘要","abstract_en":"English abstract"},profile,[])
    assert check_docx(path)["section_columns"][0]==1
    assert 2 in check_docx(path)["section_columns"]


def test_missing_font_fails():
    with pytest.raises(StudioError, match="MISSING_FONT"): check_fonts({"fonts":{"cjk":"No Such Studio Font"}})


def test_text_drift_fails():
    with pytest.raises(StudioError, match="CONTENT_CHANGED"):
        assert_text({"blocks":[{"t":"Str","c":"123"}]},{"blocks":[{"t":"Str","c":"124"}]},"test")
