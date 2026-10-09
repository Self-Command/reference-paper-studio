import pytest
from studio.runtime import StudioError,digest
from studio.revisions import invalidate,verify

def test_font_change_preserves_content_and_model_approvals():
    events=[{"event_id":k,"event_type":k} for k in ("plan","model","md_content","presentation","export")]
    updated=invalidate(events,{"fonts":True})
    assert {e["event_type"] for e in updated if e.get("validity_status")=="invalidated"}=={"presentation","export"}
    assert all("validity_status" not in e for e in events)
    updated=invalidate(events,{"content":True})
    assert {e["event_type"] for e in updated if e.get("validity_status")=="invalidated"}=={"md_content","presentation","export"}

def test_revision_scope_and_first_version_bytes(tmp_path):
    original=tmp_path/"first.docx"; original.write_bytes(b"exact first version")
    event={"event_id":"r1","event_type":"revision","actor_type":"human","user_instruction":"修复F1","instruction_source":"user:fixture","content_snapshot_sha256":"a"*64,"approved_finding_ids":["F1"],"approved_paths":["layout.py"],"report_sha256":"b"*64}
    first={"first.docx":digest(original)}
    assert verify(tmp_path,{"layout.py":"old"},{"layout.py":"new"},[event],"r1","a"*64,["F1"],first)["first_version_preserved"]
    with pytest.raises(StudioError,match="REVISION_SCOPE_EXCEEDED"):
        verify(tmp_path,{"paper.md":"old"},{"paper.md":"new"},[event],"r1","a"*64,["F1"],first)
    original.write_bytes(b"replacement")
    with pytest.raises(StudioError,match="FIRST_VERSION_CHANGED"):
        verify(tmp_path,{"layout.py":"old"},{"layout.py":"new"},[event],"r1","a"*64,["F1"],first)
