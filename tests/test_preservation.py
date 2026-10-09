import json
import pytest
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from studio.runtime import StudioError
from studio.qa import assert_text
from studio.frontmatter import prepare
from studio.latex_layout import front,write_latex
from studio.composition import load_composition

def test_cjk_metadata_terminates_latex_control_word():
    assert r"\noindent{}摘要：" in front({"abstract_zh":"摘要", "_meta_tex":{"abstract_zh":"摘要：正文"}})

def test_spaces_cannot_mask_latin_word_join():
    with pytest.raises(StudioError,match="word boundaries"):
        assert_text({"blocks":[{"t":"Str","c":"in put"}]},{"blocks":[{"t":"Str","c":"input"}]},"fixture")

def test_graphics_reader_alt_text_is_not_body_prose():
    figure={"t":"Figure","c":[["fig:f",[],[]],[None,[{"t":"Para","c":[{"t":"Str","c":"Figure 1 Example"}]}]],[]]}
    image={"t":"Image","c":[["",[],[]],[{"t":"Str","c":"image"}],["figure.png",""]]}
    assert_text({"blocks":[figure]},{"blocks":[{"t":"Para","c":[{"t":"Str","c":"Figure 1 Example"}]},image]},"fixture")

def test_metadata_inline_math_remains_editable(tmp_path):
    result=prepare({"title_en":"Editable math","abstract_en":"Preserve $x_i^2/(1+x_i)$ and A < B & C."},[1,23,1],tmp_path)
    doc=Document(result["_meta_docx"])
    assert len(list(doc._element.iter(qn("m:oMath"))))==1
    assert result["_meta_math_count"]==1
    assert "A < B & C" in "".join(par.text for par in doc.paragraphs)

def test_end_abstract_uses_one_fixed_unbreakable_region(tmp_path):
    ast={"pandoc-api-version":[1,23,1],"meta":{},"blocks":[{"t":"Para","c":[{"t":"Str","c":"Synthetic body."}]}]}
    _,profile=load_composition("reference-journal-v1","2.0.0")
    profile["english_abstract_position"]="end"
    main=write_latex(ast,[],{"title_en":"Synthetic title","abstract_en":"Synthetic abstract","keywords_en":["fixture"]},profile,tmp_path)
    text=main.read_text()
    assert text.index(r"\twocolumn[")<text.index("Synthetic body.")<text.index(r"\onecolumn")<text.index("Synthetic title")
    assert r"\begin{multicols}" not in text
    end_region=text[text.index(r"\onecolumn"):]
    assert end_region.index(r"\begin{minipage}{\textwidth}")<end_region.index("Synthetic abstract")<end_region.index(r"\end{minipage}")
