import json
import pytest
from studio.approvals import snapshot,check_export
from studio.runtime import digest,StudioError

def fixture(root):
    (root/"paper.md").write_text("# Synthetic source\n\nContent must remain bound to authorization.")
    files=[{"path":"paper.md","role":"manuscript","sha256":digest(root/"paper.md")}]
    identity={"manifest_sha256":"b"*64,"font_profile_sha256":"c"*64}
    fingerprint=snapshot({item["path"]:item["sha256"] for item in files})
    events=[{"event_id":kind,"event_type":kind,"actor_type":"human","user_instruction":"Synthetic contract test for approved implementation","instruction_source":"implementation:test-only","content_snapshot_sha256":fingerprint,"template_manifest_sha256":identity["manifest_sha256"],"font_profile_sha256":identity["font_profile_sha256"],"approved_outputs":["docx"]} for kind in ("md_content","presentation","export")]
    (root/"approvals.json").write_text(json.dumps(events))
    files.append({"path":"approvals.json","role":"approvals","sha256":digest(root/"approvals.json")})
    request={"schema_version":2,"manuscript":"paper.md","approval_file":"approvals.json","files":files,"approvals":{kind:kind for kind in ("md_content","presentation","export")},"outputs":["docx"]}
    return request,identity,events

def test_current_export_authorization_reused_but_missing_export_denied(tmp_path):
    request,identity,events=fixture(tmp_path)
    assert check_export(tmp_path,request,identity)["status"]=="bound"
    assert check_export(tmp_path,request,identity)["status"]=="bound"
    request["approvals"]["export"]="no-existing-export-authorization"
    with pytest.raises(StudioError,match="APPROVAL_MISSING: export"):
        check_export(tmp_path,request,identity)

def test_output_scope_and_font_choice_cannot_expand(tmp_path):
    request,identity,events=fixture(tmp_path)
    request["outputs"].append("latex")
    with pytest.raises(StudioError,match="APPROVAL_MISSING: requested outputs"):
        check_export(tmp_path,request,identity)
    request["outputs"]=["docx"]
    with pytest.raises(StudioError,match="APPROVAL_STALE: font choice"):
        check_export(tmp_path,request,{**identity,"font_profile_sha256":"d"*64})

def test_manuscript_cannot_be_excluded_from_snapshot_by_role_masquerade(tmp_path):
    request,identity,events=fixture(tmp_path)
    request["files"][0]["role"]="approvals"
    with pytest.raises(StudioError,match="INPUT_ROLE_MISMATCH: manuscript"):
        check_export(tmp_path,request,identity)

def test_changed_source_invalidates_actual_approval_snapshot(tmp_path):
    request,identity,events=fixture(tmp_path)
    (tmp_path/"paper.md").write_text("Changed source")
    request["files"][0]["sha256"]=digest(tmp_path/"paper.md")
    with pytest.raises(StudioError,match="APPROVAL_STALE: md_content"):
        check_export(tmp_path,request,identity)
