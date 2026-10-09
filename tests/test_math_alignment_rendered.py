from pathlib import Path
import json
import pdfplumber
from studio.composition import load_composition
from studio.registry import build
from studio.locked_template import fill
from studio.pipeline import strict_pandoc
from studio.math_proof import prove,isolated_number_center


def test_generated_multiline_number_uses_actual_cloud_math_center(tmp_path,monkeypatch):
    monkeypatch.setenv("RPS_REGISTRY_ROOT",str(tmp_path/"registry"))
    target=build("reference-journal-v1","2.0.0")
    _,profile=load_composition("reference-journal-v1","2.0.0")
    source=tmp_path/"formula.md"
    expression=r"a_1+a_2+a_3+a_4+a_5+a_6+a_7+a_8+a_9+a_{10}+a_{11}+a_{12}=0"
    source.write_text("$$"+expression+"$$",encoding="utf-8")
    native=tmp_path/"native.docx"
    strict_pandoc(["pandoc",source,"-o",native])
    final=tmp_path/"manuscript.docx"
    fill(native,{},[{"id":"M1","ordinal":1,"source":expression}],target/"master-front.docx",profile,final)
    layout=json.loads((tmp_path/"math-layout-ledger.json").read_text())
    assert layout[0]["number_anchor"]=="center"
    proof=prove(final,tmp_path/"proof")
    assert proof["missing"]==[]
    with pdfplumber.open(tmp_path/"proof/isolated.pdf") as pdf:
        measurement=isolated_number_center(pdf.pages[0],"(M1)")
    assert measurement["status"]=="measured"
    assert abs(measurement["center_delta_pt"])<=6,measurement
