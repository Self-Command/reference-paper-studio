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


def test_visual_release_cannot_substitute_word_or_skill_package(tmp_path):
    root=tmp_path/"cloud"; root.mkdir()
    word=root/"manuscript.docx"; word.write_bytes(b"cloud Word bytes")
    pdf=root/"word-proof.pdf"; pdf.write_bytes(b"cloud proof bytes")
    archive=root/"reference-paper-studio.zip"; archive.write_bytes(b"exact built archive")
    report={"build":"passed","automatic_acceptance":"passed","execution":{"run_id":"456"},"editable_outputs":{"manuscript.docx":digest(word)},"pdfs":{"word-proof.pdf":{"sha256":digest(pdf),"previews":[]}}}
    (root/"acceptance.json").write_text(json.dumps(report))
    manifest={"file":archive.name,"sha256":digest(archive),"automatic_acceptance":"passed","installation_allowed":False}
    (root/"package-manifest.json").write_text(json.dumps(manifest))
    receipt={"run_id":"456","reviewer":"reviewer","status":"passed","artifacts":[{"path":p.name,"sha256":digest(p),"reviewed":True} for p in (word,pdf)]}
    path=tmp_path/"receipt.json";path.write_text(json.dumps(receipt));output=tmp_path/"release"
    verify_receipt(path,root,"456",output)
    assert (output/archive.name).read_bytes()==archive.read_bytes()
    assert json.loads((output/"reviewed-package-manifest.json").read_text())["installation_allowed"] is False
    assert not (output/"release-manifest.json").exists()
    word.write_bytes(b"different Word")
    with pytest.raises(StudioError,match="VISUAL_FINGERPRINT"): verify_receipt(path,root,"456",output)
    word.write_bytes(b"cloud Word bytes");archive.write_bytes(b"different archive")
    with pytest.raises(StudioError,match="RELEASE_PACKAGE_FINGERPRINT"): verify_receipt(path,root,"456",output)
