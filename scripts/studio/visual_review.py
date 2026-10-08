"""Bind a human/agent visual inspection receipt to existing cloud artifacts."""
from pathlib import Path
import json
from .runtime import require_actions, StudioError, confined, digest, write_json


def verify_receipt(receipt_path, artifact_root, run_id, output):
    require_actions()
    root=Path(artifact_root).resolve()
    receipt=json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if str(receipt.get("run_id")) != str(run_id) or not receipt.get("reviewer") or receipt.get("status") != "passed":
        raise StudioError("INVALID_VISUAL_RECEIPT")
    expected={}
    for report_file in root.rglob("acceptance.json"):
        report=json.loads(report_file.read_text(encoding="utf-8"))
        if report.get("build") != "passed" or report.get("automatic_acceptance") != "passed":
            raise StudioError("VISUAL_REVIEW_REQUIRES_AUTOMATIC_PASS")
        for name, pdf in report["pdfs"].items():
            path=report_file.parent/name
            expected[path.relative_to(root).as_posix()]=pdf["sha256"]
            for preview in pdf["previews"]:
                path=report_file.parent/"previews"/name.removesuffix(".pdf")/preview["file"]
                expected[path.relative_to(root).as_posix()]=preview["sha256"]
    if not expected: raise StudioError("NO_PROOFS_TO_REVIEW")
    supplied={r["path"]:r for r in receipt["artifacts"]}
    if set(expected) != set(supplied): raise StudioError("VISUAL_COVERAGE_INCOMPLETE")
    for path, fingerprint in expected.items():
        item=supplied[path]
        if digest(confined(root,path)) != fingerprint or item.get("sha256") != fingerprint or item.get("reviewed") is not True or item.get("unresolved_findings"):
            raise StudioError("VISUAL_FINGERPRINT_OR_REVIEW_MISMATCH: "+path)
    result={"build":"passed", "automatic_acceptance":"passed", "visual_review":"passed", "source_run":str(run_id), "receipt":receipt,
            "meaning":"Artifact identity and review coverage verified; the reviewer supplies the visual judgment."}
    write_json(Path(output)/"visual-acceptance.json",result)
    return result
