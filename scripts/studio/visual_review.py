"""Bind a human/agent visual inspection receipt to existing cloud artifacts."""
from pathlib import Path
import json
import shutil
from .runtime import require_actions, StudioError, confined, digest, write_json


def verify_receipt(receipt_path, artifact_root, run_id, output):
    require_actions()
    root=Path(artifact_root).resolve()
    receipt=json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if receipt.get("schema_version")==2:
        return verify_detailed_receipt(receipt,root,run_id,output)
    if str(receipt.get("run_id")) != str(run_id) or not receipt.get("reviewer") or receipt.get("status") != "passed":
        raise StudioError("INVALID_VISUAL_RECEIPT")
    expected={}
    for report_file in root.rglob("acceptance.json"):
        report=json.loads(report_file.read_text(encoding="utf-8"))
        if report.get("build") != "passed" or report.get("automatic_acceptance") != "passed":
            raise StudioError("VISUAL_REVIEW_REQUIRES_AUTOMATIC_PASS")
        if report.get("execution",{}).get("run_id") and str(report["execution"]["run_id"]) != str(run_id):
            raise StudioError("VISUAL_REPORT_RUN_MISMATCH")
        for name,fingerprint in report.get("editable_outputs",{}).items():
            expected[(report_file.parent/name).relative_to(root).as_posix()]=fingerprint
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
    manifest=root/"package-manifest.json"
    if manifest.is_file():
        package=json.loads(manifest.read_text(encoding="utf-8"))
        archive=confined(root,package["file"])
        if package["automatic_acceptance"] != "passed" or digest(archive) != package["sha256"]:
            raise StudioError("RELEASE_PACKAGE_FINGERPRINT_OR_ACCEPTANCE_FAILED")
        shutil.copy2(archive,Path(output)/archive.name)
        write_json(Path(output)/"release-manifest.json",{**package,"installation_allowed":True,"visual_review":"passed","source_run":str(run_id),"visual_run":__import__("os").environ["GITHUB_RUN_ID"],"meaning":"Exact previously built archive released after bound visual review; no rebuilding or source substitution."})
    return result


def verify_detailed_receipt(receipt,root,run_id,output):
    require_actions()
    if str(receipt.get("run_id"))!=str(run_id) or not receipt.get("reviewer") or receipt.get("visual_status")!="completed":
        raise StudioError("INVALID_VISUAL_RECEIPT")
    if receipt.get("visual_result") not in ("passed","issues_found"): raise StudioError("INVALID_VISUAL_RESULT")
    expected={}; reports=[]
    for report_path in root.rglob("acceptance.json"):
        report=json.loads(report_path.read_text(encoding="utf-8")); reports.append(report)
        if report.get("execution",{}).get("run_id") and str(report["execution"]["run_id"])!=str(run_id): raise StudioError("VISUAL_REPORT_RUN_MISMATCH")
        for name,proof in report.get("pdfs",{}).items():
            path=report_path.parent/name; expected[path.relative_to(root).as_posix()]=proof["sha256"]
            for image in proof["previews"]:
                path=report_path.parent/"previews"/name.removesuffix(".pdf")/image["file"]
                expected[path.relative_to(root).as_posix()]=image["sha256"]
        for name,fingerprint in report.get("editable_outputs",{}).items(): expected[(report_path.parent/name).relative_to(root).as_posix()]=fingerprint
    supplied={item["path"]:item for item in receipt.get("artifacts",[])}
    if not expected or set(supplied)!=set(expected): raise StudioError("VISUAL_COVERAGE_INCOMPLETE")
    for path,fingerprint in expected.items():
        if supplied[path].get("sha256")!=fingerprint or digest(confined(root,path))!=fingerprint or supplied[path].get("reviewed") is not True: raise StudioError("VISUAL_FINGERPRINT_OR_REVIEW_MISMATCH: "+path)
    checks={item["check_id"]:item for item in receipt.get("checks",[])}
    if set(checks)!={"V"+str(i).zfill(2) for i in range(1,22)}: raise StudioError("VISUAL_CHECKLIST_INCOMPLETE")
    if any(item.get("result") not in ("passed","issues_found","not_applicable") for item in checks.values()): raise StudioError("VISUAL_CHECK_RESULT_INVALID")
    issues=receipt.get("findings",[])
    if receipt["visual_result"]=="passed" and (issues or any(item["result"]=="issues_found" for item in checks.values())): raise StudioError("VISUAL_RESULT_CONFLICT")
    automatic=all(r.get("build")=="passed" and r.get("automatic_acceptance")=="passed" for r in reports)
    result={"visual_status":"completed","visual_result":receipt["visual_result"],"automatic_status":"passed" if automatic else "failed","delivery_status":"awaiting_user","installation_allowed":False,"source_run":str(run_id),"receipt":receipt,"meaning":"Identity and reported coverage checked; actual visual judgment belongs to reviewer"}
    write_json(Path(output)/"visual-acceptance.json",result)
    return result
