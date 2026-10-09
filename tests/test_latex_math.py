import re
from pathlib import Path
import pytest
import pdfplumber
from studio.latex_math import MACRO,render,reader_text,replace_displays,measured_widths
from studio.runtime import run,StudioError
from studio.math_proof import isolated_number_center


def test_actual_adapter_readback_preserves_nested_expression_and_label():
    expression=r"\begin{array}{r}x_1 \\ = \left\{\begin{matrix}0\\\frac{a}{b}\end{matrix}\right.\end{array}"
    actual=render(expression,"M10")
    assert reader_text(actual)==r"\["+expression+r"\tag{M10}\]"
    changed=actual.replace(r"\frac{a}{b}",r"\frac{a}{c}")
    assert reader_text(changed)!=reader_text(actual)
    with pytest.raises(StudioError,match="ADAPTER_CHANGED"):reader_text(actual[:-2]+"0}")
    with pytest.raises(StudioError,match="UNCLOSED"):reader_text(actual[:-1])


def test_fixed_number_slots_have_real_centered_rendering(tmp_path):
    expr=r"\begin{array}{r}x_1+x_2+x_3+x_4\\=y_1+y_2+y_3+y_4\\\geq 0\end{array}"
    source=r"\documentclass{article}\usepackage{amsmath}\usepackage{unicode-math}\usepackage[margin=2.2cm]{geometry}\setmathfont{Latin Modern Math}"+MACRO+r"\begin{document}\pagestyle{empty}\noindent\begin{minipage}{225bp}Formula\par"+render(expr,"M10")+r"\end{minipage}\end{document}"
    (tmp_path/"test.tex").write_text(source,encoding="utf-8")
    run(["xelatex","-no-shell-escape","-interaction=nonstopmode","-halt-on-error","test.tex"],cwd=tmp_path)
    with pdfplumber.open(tmp_path/"test.pdf") as pdf:
        assert len(pdf.pages)==1
        center=isolated_number_center(pdf.pages[0],"(M10)")
        assert center["status"]=="measured" and abs(center["center_delta_pt"])<5
        label=pdf.pages[0].search(r"\(M10\)",regex=True)[0]
        assert abs(label["x1"]-(2.2*72/2.54+225))<1


def test_unfit_math_explicitly_fails_in_the_actual_tex_renderer(tmp_path):
    source=r"\documentclass{article}\usepackage{amsmath}"+MACRO+r"\begin{document}\begin{minipage}{100bp}"+render("W"*40,"M1")+r"\end{minipage}\end{document}"
    (tmp_path/"test.tex").write_text(source,encoding="utf-8")
    with pytest.raises(StudioError,match="OBJECT_DOES_NOT_FIT"):
        run(["xelatex","-no-shell-escape","-interaction=nonstopmode","-halt-on-error","test.tex"],cwd=tmp_path)


def test_measured_widths_record_actual_fixed_region_fit(tmp_path):
    main=tmp_path/"main.tex"
    main.write_text(r"\documentclass{article}\usepackage{amsmath}\begin{document}\[x^2\tag{M1}\]\["+"W"*40+r"\tag{M2}\]\end{document}",encoding="utf-8")
    widths=measured_widths(main,tmp_path/"measure",2)
    assert widths[0]["fits"] and not widths[1]["fits"]
    assert widths[1]["math_width_bp"]>widths[1]["formula_slot_bp"]
