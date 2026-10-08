import json
import pytest
from studio.runtime import digest, StudioError
from studio.visual_review import verify_receipt


def test_visual_receipt_bound_to_existing_artifacts(tmp_path):
    folder=tmp_path/"old"; folder.mkdir()
    pdf=folder/"latex-proof.pdf"; pdf.write_bytes(b"existing cloud PDF")
    preview=folder/"previews/latex-proof/page-1.png"; preview.parent.mkdir(parents=True); preview.write_bytes(b"existing preview")
    report={"build":"passed","automatic_acceptance":"passed","pdfs":{"latex-proof.pdf":{"sha256":digest(pdf),"previews":[{"file":preview.name,"sha256":digest(preview)}]}}}
    (folder/"acceptance.json").write_text(json.dumps(report))
    receipt={"run_id":"123","reviewer":"test reviewer","status":"passed","artifacts":[{"path":p.relative_to(folder).as_posix(),"sha256":digest(p),"reviewed":True} for p in (pdf,preview)]}
    path=tmp_path/"receipt.json"; path.write_text(json.dumps(receipt))
    assert verify_receipt(path,folder,"123",tmp_path/"out")["visual_review"]=="passed"
    preview.write_bytes(b"changed")
    with pytest.raises(StudioError,match="VISUAL_FINGERPRINT"): verify_receipt(path,folder,"123",tmp_path/"out")
