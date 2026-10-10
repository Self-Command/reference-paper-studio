"""Registered role styles, checked against actual mothers and cloud renderers."""
from copy import deepcopy
import pytest
import pdfplumber
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING
from studio.composition import load_composition
from studio.components import compile_components
from studio.locked_template import create_templates,check_contract
from studio.runtime import StudioError,run


def test_style_component_requires_valid_registered_role_geometry():
    descriptor=deepcopy(load_composition("gmcm","1.1.0")[0])
    descriptor["components"].remove("style.roles")
    with pytest.raises(StudioError,match="STYLE_COMPONENT_REQUIRED"): compile_components(descriptor)
    descriptor["components"].append("style.roles")
    descriptor["policy"]["role_styles"]["Heading1"]["size_pt"]=2
    with pytest.raises(StudioError,match="ROLE_STYLE_INVALID"): compile_components(descriptor)


def test_gmcm_registered_mother_and_actual_word_style_geometry(tmp_path):
    _,policy=load_composition("gmcm","1.1.0")
    policy["english_abstract_position"]="front"
    create_templates(tmp_path,policy)
    target=tmp_path/"master-front.docx"
    doc=Document(target)
    assert doc.styles["RPSBody"].font.size==Pt(12)
    assert doc.styles["RPSTitle"].font.size==Pt(16)
    assert doc.styles["RPSHeading1"].font.size==Pt(14)
    assert doc.styles["RPSHeading1"].paragraph_format.alignment==1
    assert doc.styles["RPSBody"].paragraph_format.line_spacing_rule==WD_LINE_SPACING.SINGLE
    check_contract(target,policy)
    doc.add_paragraph("Registered heading",style="RPSHeading1")
    doc.save(target)
    run(["libreoffice","-env:UserInstallation=file:///tmp/rps-role-styles","--headless","--convert-to","pdf","--outdir",tmp_path,target])
    with pdfplumber.open(tmp_path/"master-front.pdf") as pdf:
        heading=next(w for page in pdf.pages for w in page.extract_words(extra_attrs=["size"]) if w["text"]=="Registered")
        assert abs(heading["size"]-14)<.2
    doc.styles["RPSHeading1"].font.size=Pt(10);doc.save(target)
    with pytest.raises(StudioError,match="TEMPLATE_ROLE_STYLE_CHANGED"): check_contract(target,policy)


def test_gmcm_native_tex_heading_size_and_continuous_footer(tmp_path):
    from studio.latex_layout import write_latex
    _,policy=load_composition("gmcm","1.1.0")
    policy["english_abstract_position"]="front"
    ast={"pandoc-api-version":[1,23,1],"meta":{},"blocks":[{"t":"Header","c":[1,["",[],[]],[{"t":"Str","c":"RegisteredHeading"}]]},{"t":"Para","c":[{"t":"Str","c":"Body"}]}]}
    main=write_latex(ast,[],{"title_zh":"中文题目","abstract_zh":"摘要内容"},policy,tmp_path)
    run(["xelatex","-interaction=nonstopmode","-halt-on-error",main.name],cwd=tmp_path)
    with pdfplumber.open(tmp_path/"main.pdf") as pdf:
        assert len(pdf.pages)==2
        for index,page in enumerate(pdf.pages,1):
            assert [w["text"] for w in page.extract_words() if w["top"]>page.height-60]==[str(index)]
        heading=next(w for w in pdf.pages[1].extract_words(extra_attrs=["size"]) if w["text"]=="RegisteredHeading")
        assert abs(heading["size"]-14)<.2
        assert abs((heading["x0"]+heading["x1"])/2-pdf.pages[1].width/2)<2
