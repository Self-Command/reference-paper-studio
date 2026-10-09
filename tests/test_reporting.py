import json
from studio.reporting import publish
from studio.runtime import digest

def test_build_manifest_binds_report_and_preview_index_without_asserting_first_version(tmp_path):
    report={"build":"passed","automatic_acceptance":"passed","execution":{"run_id":"fixture"},"pdfs":{}}
    publish(tmp_path,report)
    manifest=json.loads((tmp_path/"build-manifest.json").read_text())
    for name in ("status.json","preview-index.json","复检报告.md"):
        assert manifest["files"][name]==digest(tmp_path/name)
    assert manifest["status"]["visual_status"]=="not_run"
    assert "是否为稿件首版由项目版本记录确认" in (tmp_path/"复检报告.md").read_text()
