import importlib.util
from pathlib import Path
import pytest
from studio.runtime import StudioError


def module():
    path=Path(__file__).resolve().parents[1]/"ci/measure_display_artifacts.py"
    spec=importlib.util.spec_from_file_location("display_measurement_diagnostic",path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def test_extract_preserves_complete_generated_display_expression():
    expression=r"\begin{array}{r}x_1 \\ = \left\{\begin{matrix}0\\\frac{a}{b}\end{matrix}\right.\end{array}"
    source=r"\begin{document}\["+expression+r"\tag{M6}\] prose \[y^2\tag{M7}\]"
    records=module().extract_displays(source)
    assert [r["id"] for r in records]==["M6","M7"]
    assert records[0]["expression"]==expression
    assert source[records[0]["source_start"]:records[0]["source_end"]]==r"\["+expression+r"\tag{M6}\]"


@pytest.mark.parametrize("source,error",[
    (r"\[x\]","NO_GENERATED_DISPLAYS"),
    (r"\[x\tag{M1}\]\[y\tag{M1}\]","DUPLICATE_MEASUREMENT_LABEL"),
    (r"\[x\tag{unsafe/name}\]","UNSUPPORTED_MEASUREMENT_LABEL")])
def test_measurement_input_fails_explicitly(source,error):
    with pytest.raises(StudioError,match=error):module().extract_displays(source)
