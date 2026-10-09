from studio.object_audit import inspect
from studio.manuscript import parse
from studio.runtime import StudioError
import pytest

def figure(number=1,name="Synthetic figure"):
    return {"t":"Figure","c":[["fig:flow",[],[]],[None,[{"t":"Para","c":[{"t":"Str","c":f"Figure {number} {name}"}]}]],[]]}

def test_caption_itself_is_not_a_body_reference_and_sequences_are_independent():
    ast={"blocks":[figure()]}
    assert inspect(ast)["issues"][0]["id"]=="OBJECT_BODY_REFERENCE_MISSING"
    ast["blocks"].insert(0,{"t":"Para","c":[{"t":"Str","c":"See Figure 1 and Table 1."}]})
    assert inspect(ast)["status"]=="passed"
    ast["blocks"][1]=figure(2)
    assert any(issue["id"]=="CAPTION_SEQUENCE_INVALID" for issue in inspect(ast)["issues"])

def test_empty_object_name_is_rejected_and_stable_reference_is_accepted():
    ast={"blocks":[{"t":"Str","c":"See {{fig:flow}}."},figure(name="")]}
    report=inspect(ast)
    assert [issue["id"] for issue in report["issues"]]==["CAPTION_NAME_MISSING"]
    ast["blocks"][1]=figure()
    assert inspect(ast)["status"]=="passed"

@pytest.mark.parametrize("expression",[r"\hspace{10cm}x",r"\resizebox{10cm}{!}{x}",r"\input{secret}"])
def test_math_cannot_override_geometry_or_execute_raw_tex(tmp_path,expression):
    source=tmp_path/"source.md"; source.write_text("$$"+expression+"$$")
    with pytest.raises(StudioError,match="CONTENT_LAYOUT_COMMAND_FORBIDDEN"):
        parse(source,tmp_path/"review")
