import json
import pytest
from studio.runtime import digest,StudioError
from studio.visual_review import verify_receipt

def fixture(tmp_path):
    root=tmp_path/"proofs";root.mkdir()
    pdf=root/"word-compat-proof.pdf";pdf.write_bytes(b"cloud proof")
    report={"build":"passed","automatic_acceptance":"failed","execution":{"run_id":"71"},"input_sha256":"a"*64,"template":{"manifest_sha256":"b"*64},"pdfs":{pdf.name:{"sha256":digest(pdf),"previews":[]}}}
    report_path=root/"acceptance.json";report_path.write_text(json.dumps(report))
    receipt={"schema_version":2,"run_id":"71","reviewer":"Codex fixture","visual_status":"completed","visual_result":"issues_found","findings":[{"id":"F1","check_id":"V09","page":1,"description":"Equation label drift"}],"checks":[{"check_id":"V"+str(i).zfill(2),"result":"issues_found" if i==9 else "not_applicable"} for i in range(1,22)],"report_bindings":{"acceptance.json":{"sha256":digest(report_path),"input_sha256":"a"*64,"template_manifest_sha256":"b"*64}},"artifacts":[{"path":pdf.name,"sha256":digest(pdf),"reviewed":True}]}
    path=tmp_path/"receipt.json";path.write_text(json.dumps(receipt))
    return root,path,receipt

def test_completed_review_with_issues_does_not_release(tmp_path):
    root,path,receipt=fixture(tmp_path)
    result=verify_receipt(path,root,"71",tmp_path/"out")
    assert result["visual_status"]=="completed" and result["visual_result"]=="issues_found"
    assert result["installation_allowed"] is False

def test_receipt_rejects_wrong_input_template_and_partial_checklist(tmp_path):
    root,path,receipt=fixture(tmp_path)
    receipt["report_bindings"]["acceptance.json"]["input_sha256"]="c"*64
    path.write_text(json.dumps(receipt))
    with pytest.raises(StudioError,match="VISUAL_INPUT_OR_TEMPLATE"):verify_receipt(path,root,"71",tmp_path/"out")
    receipt["report_bindings"]["acceptance.json"]["input_sha256"]="a"*64
    receipt["checks"].pop();path.write_text(json.dumps(receipt))
    with pytest.raises(StudioError,match="VISUAL_CHECKLIST_INCOMPLETE"):verify_receipt(path,root,"71",tmp_path/"out")
