"""Approve a specific difference while retaining the exact first delivery."""
from copy import deepcopy
from .runtime import require_actions,StudioError,digest,confined
from .approvals import require_approval

def invalidate(events,changes):
    require_actions()
    result=deepcopy(events)
    kinds=set()
    if changes.get("content"):
        kinds.update(("md_content","presentation","export","revision","delivery"))
    if changes.get("model"):
        kinds.update(("model","md_content","presentation","export","revision","delivery"))
    if changes.get("template") or changes.get("fonts"):
        kinds.update(("presentation","export","revision","delivery"))
    if changes.get("md_structure"):
        kinds.update(("md_content","presentation","export","revision","delivery"))
    for event in result:
        if event.get("event_type") in kinds and event.get("validity_status","valid")=="valid":
            event["validity_status"]="invalidated"
            event["invalidation_reason"]={k:v for k,v in changes.items() if v}
    return result

def verify(root,before,after,events,event_id,snapshot_sha256,findings,first_artifacts):
    require_actions()
    event=require_approval(events,event_id,"revision",snapshot_sha256,findings=findings)
    if not event.get("report_sha256") or not event.get("approved_paths"):
        raise StudioError("REVISION_SCOPE_MISSING: report and paths required")
    changed=sorted(name for name in set(before)|set(after) if before.get(name)!=after.get(name))
    if set(changed)-set(event["approved_paths"]): raise StudioError("REVISION_SCOPE_EXCEEDED: "+str(changed))
    for name,fingerprint in first_artifacts.items():
        if not confined(root,name).is_file() or digest(confined(root,name))!=fingerprint:
            raise StudioError("FIRST_VERSION_CHANGED: "+name)
    return {"status":"within_scope","changed_paths":changed,"approved_findings":findings,"report_sha256":event["report_sha256"],"first_version_preserved":True}
