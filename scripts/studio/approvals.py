"""Bind explicit user instructions to immutable inputs; no fabricated identity proof."""
from pathlib import Path
import hashlib
import json
from .runtime import require_actions, StudioError, digest, confined
def snapshot(files):
    require_actions()
    return hashlib.sha256(json.dumps(files,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def require_approval(events, event_id, kind, fingerprint, template=None, findings=None):
    require_actions()
    event = next((e for e in events if e.get("event_id")==event_id), None)
    if not event or event.get("event_type") != kind or event.get("actor_type") != "human" or not event.get("user_instruction") or not event.get("instruction_source"):
        raise StudioError("APPROVAL_MISSING: "+kind)
    if event.get("validity_status","valid") != "valid" or event.get("content_snapshot_sha256") != fingerprint:
        raise StudioError("APPROVAL_STALE: "+kind)
    if event.get("invalidated_by") or any(e.get("supersedes")==event_id for e in events):
        raise StudioError("APPROVAL_STALE: superseded "+kind)
    if template and event.get("template_manifest_sha256") != template:
        raise StudioError("APPROVAL_STALE: template "+kind)
    if findings is not None and not set(findings).issubset(event.get("approved_finding_ids",[])):
        raise StudioError("REVISION_SCOPE_EXCEEDED")
    return event

def check_export(root, request, identity):
    require_actions()
    if request.get("schema_version") != 2:
        raise StudioError("APPROVAL_MISSING: legacy export must migrate to version 2")
    root=Path(root)
    declared={f["path"]:f["sha256"] for f in request["files"] if f.get("role") not in ("approvals","request")}
    for name, fingerprint in declared.items():
        if digest(confined(root,name)) != fingerprint: raise StudioError("INPUT_FINGERPRINT_MISMATCH: "+name)
    fingerprint=snapshot(declared)
    events=json.loads(confined(root,request["approval_file"]).read_text(encoding="utf-8"))
    if not isinstance(events,list): raise StudioError("CONTRACT_INVALID: approvals must be an event list")
    from .contracts import validate
    validate(events,"approval")
    ids=[event["event_id"] for event in events]
    if len(ids)!=len(set(ids)): raise StudioError("CONTRACT_INVALID: duplicate approval event IDs")
    for kind,key in (("md_content","md_content"),("presentation","presentation"),("export","export")):
        event=require_approval(events,request["approvals"].get(key),kind,fingerprint,
            identity["manifest_sha256"] if kind in ("presentation","export") else None)
        if kind=="presentation" and event.get("font_profile_sha256") != identity["font_profile_sha256"]:
            raise StudioError("APPROVAL_STALE: font choice")
        if kind=="export" and not set(request.get("outputs",["docx","latex"])).issubset(event.get("approved_outputs",[])):
            raise StudioError("APPROVAL_MISSING: requested outputs")
    return {"status":"bound","snapshot_sha256":fingerprint,"identity_assurance":"Recorded user instruction and scope; not cryptographic human authentication"}
