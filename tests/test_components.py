from copy import deepcopy
import pytest
from docx import Document
from studio.components import compile_components,check_content,check_metadata
from studio.composition import load_composition
from studio.md_components import compose
from studio.locked_template import create_templates
from studio.runtime import StudioError

def test_components_control_native_roles_and_supported_objects(tmp_path):
    descriptor=deepcopy(load_composition("general-modeling","1.0.0")[0])
    descriptor["components"].remove("title.bilingual")
    descriptor["components"].remove("figure.inline")
    p,_=compile_components(descriptor)
    p.update(id="component-fixture",version="1")
    create_templates(tmp_path,p)
    assert not any("title_" in par.text for par in Document(tmp_path/"master-front.docx").paragraphs)
    with pytest.raises(StudioError,match="CONTENT_COMPONENT_UNSUPPORTED: figure"):
        check_content({"blocks":[{"t":"Image","c":[["",[],[]],[],["test.png",""]]}]},p)

def test_component_dependencies_and_reusable_md_blocks(tmp_path):
    descriptor=deepcopy(load_composition("general-modeling","1.0.0")[0])
    descriptor["components"].remove("caption")
    with pytest.raises(StudioError,match="COMPONENT_DEPENDENCY_MISSING"):compile_components(descriptor)
    sections=compose("general-modeling","1.0.0",tmp_path)
    assert [section["title"] for section in sections]==["引言","问题描述","模型假设与符号","模型建立","求解方法","模型验证与分析","讨论与局限","结论","参考文献"]
    assert "# 模型建立" in (tmp_path/"template.md").read_text(encoding="utf-8")

def test_metadata_cannot_be_discarded_by_switching_template():
    _,english=load_composition("ieee-access","1.0.0")
    with pytest.raises(StudioError,match="METADATA_LANGUAGE_UNSUPPORTED: abstract_zh"):
        check_metadata({"abstract_en":"Valid English abstract","abstract_zh":"不能默默删除"},english)
    expected={"authors_en":"Synthetic author","affiliation_en":"Synthetic affiliation"}
    assert check_metadata(expected,english)==expected
    _,anonymous=load_composition("cumcm","1.0.0")
    with pytest.raises(StudioError,match="ANONYMOUS_IDENTITY_FORBIDDEN"):
        check_metadata({"authors_zh":"作者"},anonymous)
