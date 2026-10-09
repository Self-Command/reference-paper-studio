"""Validate the virtual installation tree and capability catalog in Actions."""
from pathlib import Path
import sys
import json
import re
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions, StudioError, write_json
require_actions()
root=Path(__file__).resolve().parents[1]
catalog=yaml.safe_load((root/"catalog/skill-catalog.yaml").read_text(encoding="utf-8"))
ids=set()
for entry in catalog["skills"]:
    if entry["id"] in ids: raise StudioError("DUPLICATE_SKILL_ID")
    ids.add(entry["id"])
    for field in ("inputs","outputs","preconditions"):
        if not isinstance(entry.get(field),list) or not entry[field] or any(not isinstance(value,str) or not value.strip() for value in entry[field]):
            raise StudioError("SKILL_GUIDE_CARD_INCOMPLETE: "+entry["id"]+":"+field)
    if not entry.get("example","").startswith("$"+entry["id"]+" "): raise StudioError("SKILL_USAGE_EXAMPLE_MISMATCH")
    source=root/entry["entrypoint"]
    text=source.read_text(encoding="utf-8")
    header=yaml.safe_load(text.split("---",2)[1])
    if header["name"] != entry["id"] or not header["description"]: raise StudioError("INVALID_SKILL_METADATA")
    for target in re.findall(r"\]\(([^)]+)\)",text):
        if target.startswith("https:"): continue
        virtual=target.removeprefix("../reference-paper-studio/")
        if not (root/virtual).is_file(): raise StudioError("PACKAGE_LINK_MISSING: "+target)
if len(ids)!=10: raise StudioError("SUITE_SKILL_COUNT")
write_json(root/"build/suite-structure.json",{"skills":sorted(ids),"status":"passed","suite_version":catalog["suite_version"]})
