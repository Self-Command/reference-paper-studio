from copy import deepcopy
from docx.oxml import OxmlElement
from studio.composition import load_composition
from studio.math_metrics import configure
from studio.math_layout import wrap,tree,restore
from studio.docx_layout import math_width_pt


def test_registered_glyph_metrics_avoid_breaking_a_narrow_fitting_expression():
    _,profile=load_composition("reference-journal-v1","2.0.0")
    metrics=configure(profile)
    formula=OxmlElement("m:oMath");run=OxmlElement("m:r");text=OxmlElement("m:t")
    text.text="iiii+iiii+iiii";run.append(text);formula.append(run)
    before=deepcopy(formula)
    assert math_width_pt(formula,10,metrics)<70<math_width_pt(formula,10)
    assert wrap(formula,70,metrics=metrics)==[]
    assert tree(formula)==tree(before)
    assert metrics["math"]["W"]>metrics["math"]["i"]


def test_metric_based_layout_remains_reversible():
    _,profile=load_composition("reference-journal-v1","2.0.0")
    metrics=configure(profile)
    formula=OxmlElement("m:oMath");run=OxmlElement("m:r");text=OxmlElement("m:t")
    text.text="WWW+WWW+WWW+WWW";run.append(text);formula.append(run)
    before=deepcopy(formula)
    ledger=wrap(formula,60,metrics=metrics)
    assert ledger and tree(restore(formula,ledger))==tree(before)
