import json
import pytest
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from studio.runtime import StudioError
from studio.qa import assert_text
from studio.frontmatter import prepare
from studio.latex_layout import front

def test_cjk_metadata_terminates_latex_control_word():
    assert r"\noindent{}摘要：" in front({"abstract_zh":"摘要", "_meta_tex":{"abstract_zh":"摘要：正文"}})

def test_spaces_cannot_mask_latin_word_join():
    with pytest.raises(StudioError,match="word boundaries"):
        assert_text({"blocks":[{"t":"Str","c":"in put"}]},{"blocks":[{"t":"Str","c":"input"}]},"fixture")

def test_metadata_inline_math_remains_editable(tmp_path):
    result=prepare({"title_en":"Editable math","abstract_en":"Preserve $x_i^2/(1+x_i)$ and A < B & C."},[1,23,1],tmp_path)
    doc=Document(result["_meta_docx"])
    assert len(list(doc._element.iter(qn("m:oMath"))))==1
    assert result["_meta_math_count"]==1
    assert "A < B & C" in "".join(par.text for par in doc.paragraphs)
