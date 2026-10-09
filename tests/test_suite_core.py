import json
import pytest
from transitions import MachineError
from studio.approvals import snapshot, require_approval
from studio.state import ProjectFlow
from studio.runtime import StudioError
from studio.kdense import check_consistency
from studio.contracts import validate

def event(kind="md_content", **changes):
    return {"event_id":"a1","event_type":kind,"actor_type":"human","user_instruction":"确认当前稿件","instruction_source":"user-message:fixture","content_snapshot_sha256":"a"*64,**changes}

def test_approval_is_bound_to_content_and_template():
    record=event("export",template_manifest_sha256="b"*64)
    assert require_approval([record],"a1","export","a"*64,"b"*64)==record
    for args in (("c"*64,"b"*64),("a"*64,"c"*64)):
        with pytest.raises(StudioError,match="APPROVAL_STALE"):
            require_approval([record],"a1","export",*args)

def test_approval_cannot_be_invented_or_expand_revision():
    with pytest.raises(StudioError,match="APPROVAL_MISSING"):
        require_approval([event(actor_type="agent")],"a1","md_content","a"*64)
    with pytest.raises(StudioError,match="APPROVAL_STALE"):
        require_approval([event(),event(event_id="a2",supersedes="a1")],"a1","md_content","a"*64)
    with pytest.raises(StudioError,match="REVISION_SCOPE_EXCEEDED"):
        require_approval([event("revision",approved_finding_ids=["F1"])],"a1","revision","a"*64,findings=["F2"])

def test_state_never_auto_approves():
    flow=ProjectFlow("md_reviewed")
    assert not flow.apply("confirm_md") and flow.state=="md_reviewed"
    assert flow.apply("confirm_md",authorized=True) and flow.state=="md_confirmed"
    assert not hasattr(flow,"to_delivered")
    with pytest.raises(MachineError): flow.apply("approve_delivery",authorized=True)

def test_snapshot_order_stable_but_resource_changes_invalidate():
    assert snapshot({"a":"1","b":"2"})==snapshot({"b":"2","a":"1"})
    assert snapshot({"a":"1"})!=snapshot({"a":"2"})

def test_request_rejects_physical_layout_and_incomplete_export():
    value={"schema_version":2,"task_id":"fixture","operation":"md-review","files":[{"path":"manuscript.md","sha256":"a"*64,"role":"manuscript"}]}
    validate(value,"request")
    with pytest.raises(StudioError,match="CONTRACT_INVALID"): validate({**value,"columns":1},"request")
    with pytest.raises(StudioError,match="CONTRACT_INVALID"): validate({**value,"operation":"export"},"request")

def test_upstream_consistency_adapter_runs_and_reports_failure(tmp_path):
    value={"schema_version":"1.0","numeric_facts":[],"methods":[],"results":[]}
    source=tmp_path/"registry.json"; source.write_text(json.dumps(value))
    report=check_consistency(source,tmp_path/"report.json")
    assert report and (tmp_path/"report.json").is_file()
    value["unexpected"]=True; source.write_text(json.dumps(value))
    with pytest.raises(StudioError,match="EVIDENCE_INCONSISTENT"):
        check_consistency(source,tmp_path/"failed.json")
    assert (tmp_path/"failed.json").is_file()
