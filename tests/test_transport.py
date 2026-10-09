"""Transport authorization boundaries, evaluated on Actions only."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location("paper",Path(__file__).resolve().parents[1]/"scripts/paper.py")
paper=importlib.util.module_from_spec(spec); spec.loader.exec_module(paper)


def test_transport_confines_explicit_files(tmp_path):
    (tmp_path/"allowed.md").write_text("source")
    assert paper.safe_input(tmp_path,"allowed.md").name=="allowed.md"
    with pytest.raises(ValueError): paper.safe_input(tmp_path,"../outside.md")
    with pytest.raises(ValueError): paper.safe_input(tmp_path,".")
    with pytest.raises(ValueError): paper.safe_input(tmp_path,".secret")


def test_transport_has_no_processing_imports():
    import ast
    tree=ast.parse(Path(paper.__file__).read_text())
    imported=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): imported.extend(n.name for n in node.names)
        elif isinstance(node,ast.ImportFrom): imported.append(node.module or "")
    assert not any(name.startswith(("studio","pytest","docx","pypdf","pdfplumber")) for name in imported)


def test_submission_uses_only_declared_rest_blobs_and_frozen_workflow(tmp_path,monkeypatch):
    import base64,json
    from types import SimpleNamespace
    (tmp_path/"paper.md").write_text("unchanged public source")
    (tmp_path/"private.txt").write_text("must not be transferred")
    spec={"id":"first-use","stage":"review","manuscript":"paper.md","files":["paper.md"]}
    request=tmp_path/"request.json";request.write_text(json.dumps(spec))
    calls=[]
    def command(args,cwd=None,input_text=None):
        calls.append((args,json.loads(input_text) if input_text else None))
        if args[:3]==["gh","repo","view"]:return json.dumps({"isPrivate":True,"defaultBranchRef":{"name":"main"}})
        if args[:2]==["gh","workflow"]:return ""
        path=args[2]
        if path.endswith("git/ref/heads/main"):return '{"object":{"sha":"parent"}}'
        if path.endswith("git/commits/parent"):return '{"tree":{"sha":"base"}}'
        if path.endswith("git/blobs"):return '{"sha":"blob"}'
        if path.endswith("git/trees"):return '{"sha":"tree"}'
        if path.endswith("git/commits"):return '{"sha":"input-commit"}'
        if path.endswith("git/refs"):return '{"ref":"refs/heads/request/first-use"}'
        raise AssertionError(args)
    monkeypatch.setattr(paper,"command",command)
    result=paper.submit(SimpleNamespace(root=tmp_path,request=request,repo="owner/private",workflow_ref="frozen-skill-sha"))
    payloads=[payload for args,payload in calls if args[2].endswith("git/blobs")]
    assert len(payloads)==2
    assert base64.b64decode(payloads[0]["content"])==b"unchanged public source"
    tree=next(payload for args,payload in calls if args[2].endswith("git/trees"))
    assert {item["path"] for item in tree["tree"]}=={".requests/first-use/files/paper.md",".requests/first-use/request.json"}
    dispatch=next(args for args,payload in calls if args[:2]==["gh","workflow"])
    assert dispatch[dispatch.index("--ref")+1]=="frozen-skill-sha"
    assert result["workflow_ref"]=="frozen-skill-sha"
