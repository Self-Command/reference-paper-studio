"""Cloud document task entry. Inputs and implementation are separate checkouts."""
import argparse
import json
from pathlib import Path
import sys
import os
sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio.runtime import require_actions, StudioError, confined, digest, write_json
from studio.pipeline import export
from studio.references import analyze
from studio.review import review


def execute(input_root, request_path, output, artifact_root=None, artifact_run=None):
    require_actions()
    input_root = Path(input_root).resolve()
    request_file = confined(input_root, request_path)
    request = json.loads(request_file.read_text(encoding="utf-8"))
    version2=request.get("schema_version")==2
    if version2:
        from studio.contracts import validate
        from studio.approvals import snapshot
        actual_input=os.environ.get("INPUT_COMMIT")
        if not actual_input: raise StudioError("INPUT_COMMIT_MISSING")
        if request.get("input_commit") and request["input_commit"]!=actual_input: raise StudioError("INPUT_COMMIT_MISMATCH")
        request["input_commit"]=actual_input
        if request.get("engine_commit") and request["engine_commit"]!=os.environ["GITHUB_SHA"]: raise StudioError("ENGINE_COMMIT_MISMATCH")
        validate(request,"request")
        stage=request["operation"]
        if os.environ.get("TASK_ID") and os.environ["TASK_ID"]!=request["task_id"]: raise StudioError("TASK_ID_MISMATCH")
        if os.environ.get("PHASE") and os.environ["PHASE"]!=stage: raise StudioError("TASK_PHASE_MISMATCH")
        declared={f["path"] for f in request["files"]}
        fingerprints={f["path"]:f["sha256"] for f in request["files"]}
        if len(declared)!=len(request["files"]): raise StudioError("DUPLICATE_INPUT_FILE")
    else:
        stage=request["stage"]; declared=set(request["files"]); fingerprints=request["sha256"]
    root = request_file.parent/"files"
    for name in declared:
        path = confined(root, name)
        if not path.is_file() or digest(path) != fingerprints[name]:
            raise StudioError(f"INPUT_FINGERPRINT_MISMATCH: {name}")
    for field in ("manuscript", "metadata", "reference_evidence", "model_evidence", "bibliography", "visual_receipt","approval_file","consistency_registry"):
        if request.get(field) and request[field] not in declared:
            raise StudioError(f"UNDECLARED_INPUT: {field}")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != declared: raise StudioError("INPUT_MANIFEST_MISMATCH")
    if stage == "reference":
        result = analyze(root, request["reference_evidence"], output)
    elif stage in ("review","model-review"):
        result = review(confined(root, request["manuscript"]), output)
    elif stage == "md-review":
        from studio.md_review import inspect
        result=inspect(root,request,output)
    elif stage == "template-build":
        from studio.registry import build
        os.environ["RPS_REGISTRY_ROOT"]=str(Path(output)/"registered")
        choice=request["template"]
        from studio.fonts import install_declared
        fonts=install_declared(root,request,output)
        target=build(choice["id"],choice["version"],choice["font_profile"],fonts)
        result={"assets":str(target),"status":"candidate","registered_for_production":False}
    elif stage == "export":
        if not version2: raise StudioError("APPROVAL_MISSING: migrate legacy document-task export to schema version 2")
        from studio.fonts import install_declared
        install_declared(root,request,output)
        result = export(root, request, output)
    elif stage in ("visual","visual-receipt") and artifact_root and artifact_run:
        from studio.visual_review import verify_receipt
        result = verify_receipt(confined(root,request["visual_receipt"]),artifact_root,artifact_run,output)
    else: raise StudioError("INVALID_STAGE")
    if request.get("consistency_registry"):
        from studio.kdense import check_consistency
        check_consistency(confined(root,request["consistency_registry"]),Path(output)/"scientific-consistency.json")
    write_json(Path(output)/"input-manifest.json", request)
    return result


if __name__ == "__main__":
    require_actions()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", default="build/task")
    parser.add_argument("--artifact-root")
    parser.add_argument("--artifact-run")
    args = parser.parse_args()
    try:
        execute(args.input_root, args.request, args.output, args.artifact_root, args.artifact_run)
    except Exception as error:
        write_json(Path(args.output)/"task-failure.json",{"stage":"failed","error":str(error),"exception_type":type(error).__name__,"run_id":__import__("os").environ["GITHUB_RUN_ID"],"skill_commit":__import__("os").environ.get("GITHUB_SHA"),"request_path":args.request,"diagnostics_retained":True})
        raise
