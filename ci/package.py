"""Package ten skills and a shared core, excluding all private evidence."""
from pathlib import Path
import sys
import zipfile
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions, write_json, digest, StudioError
require_actions()
root=Path(__file__).resolve().parents[1]
(root/"build").mkdir(exist_ok=True)
catalog=json.loads((root/"catalog/skill-catalog.yaml").read_text(encoding="utf-8"))
output=root/"build/reference-paper-studio-suite-candidate.zip"
included=[]
with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as package:
    for skill in catalog["skills"]:
        source=root/skill["entrypoint"]; name=skill["id"]+"/SKILL.md"
        package.write(source,name); included.append(name)
    for folder in ("assets","references","scripts","catalog","components","schemas","templates","third_party"):
        for source in sorted((root/folder).rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix==".pyc" or source.name.startswith("baseline-"): continue
            name="reference-paper-studio/"+source.relative_to(root).as_posix()
            package.write(source,name); included.append(name)
    for name in ("LICENSE","THIRD_PARTY_NOTICES.md","requirements.lock"):
        if (root/name).is_file(): package.write(root/name,"reference-paper-studio/"+name); included.append("reference-paper-studio/"+name)
with zipfile.ZipFile(output) as package:
    names=package.namelist()
    if any(any(part in ("fixtures","deliveries",".requests","evidence","tests","build") for part in Path(name).parts) for name in names): raise StudioError("PRIVATE_MATERIAL_IN_PACKAGE")
    if len([n for n in names if n.endswith("/SKILL.md")])!=10: raise StudioError("PACKAGE_SKILL_COUNT")
    import re,posixpath
    for name in names:
        if not name.endswith("/SKILL.md"): continue
        text=package.read(name).decode("utf-8")
        for target in re.findall(r"\]\(([^)]+)\)",text):
            if target.startswith("https:"): continue
            resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
            if resolved not in names: raise StudioError("PACKAGE_LINK_MISSING: "+resolved)
write_json(root/"build/package-manifest.json",{"file":output.name,"sha256":digest(output),"suite_version":catalog["suite_version"],"installation_allowed":False,"automatic_acceptance":"candidate_structure_checked","visual_review":"pending","md_templates":"pending_user_review","files":len(included),"excluded":"private source PDFs, model fixtures, approvals, task materials, outputs and tests"})
