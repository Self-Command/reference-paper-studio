"""Cloud document task entry. Inputs and implementation are separate checkouts."""
import argparse
import json
from pathlib import Path
import sys
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
    root = request_file.parent/"files"
    declared = set(request["files"])
    for name in declared:
        path = confined(root, name)
        if not path.is_file() or digest(path) != request["sha256"][name]:
            raise StudioError(f"INPUT_FINGERPRINT_MISMATCH: {name}")
    for field in ("manuscript", "metadata", "profile", "reference_evidence", "model_evidence", "bibliography", "visual_receipt"):
        if request.get(field) and request[field] not in declared:
            raise StudioError(f"UNDECLARED_INPUT: {field}")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != declared: raise StudioError("INPUT_MANIFEST_MISMATCH")
    if request["stage"] == "reference":
        result = analyze(root, request["reference_evidence"], output)
    elif request["stage"] == "review":
        result = review(confined(root, request["manuscript"]), output)
    elif request["stage"] == "export":
        result = export(root, request, output)
    elif request["stage"] == "visual" and artifact_root and artifact_run:
        from studio.visual_review import verify_receipt
        result = verify_receipt(confined(root,request["visual_receipt"]),artifact_root,artifact_run,output)
    else: raise StudioError("INVALID_STAGE")
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
    execute(args.input_root, args.request, args.output, args.artifact_root, args.artifact_run)
