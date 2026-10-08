"""Build an installable skill, excluding private fixtures and test outputs."""
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions, write_json, digest
require_actions()
root=Path(__file__).resolve().parents[1]; output=root/"build/reference-paper-studio.zip"
allowed=[root/"SKILL.md",root/"README.md",root/"LICENSE",root/"requirements.lock"]
for folder in ("agents","assets","references","scripts","third_party"):
    allowed += [p for p in (root/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix!=".pyc"]
with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as package:
    for p in sorted(allowed): package.write(p,"reference-paper-studio/"+p.relative_to(root).as_posix())
write_json(root/"build/package-manifest.json",{"file":output.name,"sha256":digest(output),"excluded":"private reference PDFs, model fixtures, task files, tests and build outputs","files":len(allowed)})
