"""Build an installable skill, excluding private fixtures and test outputs."""
from pathlib import Path
import sys
import zipfile
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions, write_json, digest
require_actions()
root=Path(__file__).resolve().parents[1]
summary=root/"build/regression-summary.json"
accepted=summary.is_file() and json.loads(summary.read_text(encoding="utf-8"))["status"]=="passed"
output=root/("build/reference-paper-studio.zip" if accepted else "build/reference-paper-studio-candidate.zip")
allowed=[root/"SKILL.md",root/"README.md",root/"LICENSE",root/"requirements.lock"]
for folder in ("agents","assets","references","scripts","third_party"):
    allowed += [p for p in (root/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix!=".pyc"]
with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as package:
    for p in sorted(allowed): package.write(p,"reference-paper-studio/"+p.relative_to(root).as_posix())
    for name in ("reference-rules.md","reference-report.json"):
        package.write(root/"build/reference-analysis"/name,"reference-paper-studio/references/baseline-"+name)
write_json(root/"build/package-manifest.json",{"file":output.name,"automatic_acceptance":"passed" if accepted else "failed","installation_allowed":False,"visual_review":"pending" if accepted else "blocked","sha256":digest(output),"excluded":"private reference PDFs, model fixtures, task files, tests and build outputs","files":len(allowed)})
