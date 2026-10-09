import pytest
from studio.md_review import inspect


@pytest.mark.parametrize("language,expected",[("en","Table 1"),("zh","表1")])
def test_md_review_uses_the_same_generated_reference_language_as_export(tmp_path,language,expected):
    source=tmp_path/"paper.md"
    source.write_text("---\ntitle_"+language+": Review fixture\nabstract_"+language+": Test only.\n---\n\n# Introduction\n\nSee {{tab:T1}}.\n\nTable 1 Data\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",encoding="utf-8")
    request={"manuscript":"paper.md","template":{"id":"ieee-access" if language=="en" else "general-modeling","version":"1.0.0"}}
    report=inspect(tmp_path,request,tmp_path/"review")
    assert report["references"]["tab:T1"]==expected
