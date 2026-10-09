"""Immutable candidate/release template assets and shared font choices."""
from pathlib import Path
import os
import json
import hashlib
from .runtime import require_actions, StudioError, digest, write_json
from .composition import load_composition, font_profile
from .contracts import ROOT
def asset_root():
    return Path(os.environ.get("RPS_REGISTRY_ROOT",ROOT/"assets/registered"))
def build(template_id, version, profile_id="open-serif"):
    require_actions()
    from .locked_template import create_templates
    descriptor,p=load_composition(template_id,version)
    fonts=font_profile(profile_id)
    p["fonts"]=fonts["fonts"]
    target=asset_root()/template_id/version/profile_id
    create_templates(target,p)
    manifest=json.loads((target/"manifest.json").read_text(encoding="utf-8"))
    manifest.update(schema_version=2,composition_sha256=p["composition_sha256"],
        font_profile_id=profile_id,font_profile_sha256=hashlib.sha256(json.dumps(fonts,sort_keys=True).encode()).hexdigest(),
        policy=p,release_state="candidate",automatic_pass=False,visual_review_complete=False)
    write_json(target/"manifest.json",manifest)
    return target

def resolve(request):
    require_actions()
    identity=request["template"]
    descriptor,p=load_composition(identity["id"],identity["version"])
    target=asset_root()/identity["id"]/identity["version"]/identity["font_profile"]
    manifest_path=target/"manifest.json"
    if not manifest_path.is_file(): raise StudioError("TEMPLATE_NOT_READY")
    if digest(manifest_path)!=identity["manifest_sha256"]: raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: manifest")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["composition_sha256"]!=p["composition_sha256"]: raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: composition")
    if manifest.get("release_state")!="released" and os.environ.get("RPS_CANDIDATE_BUILD")!="true":
        raise StudioError("TEMPLATE_NOT_READY: candidate asset")
    variant=identity["variant"]
    if variant not in manifest["variants"]: raise StudioError("UNKNOWN_TEMPLATE_VARIANT")
    path=target/manifest["variants"][variant]["file"]
    if digest(path)!=manifest["variants"][variant]["sha256"]: raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: mother")
    p=manifest["policy"]; p["english_abstract_position"]=variant
    p["equation_numbering"]="preserve" if request.get("document_kind")=="model" else "sequential"
    return path,p,{**identity,"sha256":digest(path),"font_profile_sha256":manifest["font_profile_sha256"],"release_state":manifest["release_state"]}
