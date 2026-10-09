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
def build(template_id, version, profile_id="open-serif", font_assets=None):
    require_actions()
    from .locked_template import create_templates
    descriptor,p=load_composition(template_id,version)
    fonts=font_profile(profile_id)
    p["fonts"]=fonts["fonts"]
    from .qa import check_fonts
    p["font_faces"]=check_fonts(p)
    target=asset_root()/template_id/version/profile_id
    current_font_hash=hashlib.sha256(json.dumps(fonts,sort_keys=True).encode()).hexdigest()
    existing=target/"manifest.json"
    if existing.is_file():
        frozen=json.loads(existing.read_text(encoding="utf-8"))
        if (frozen.get("composition_sha256")!=p["composition_sha256"] or
            frozen.get("font_profile_sha256")!=current_font_hash or
            frozen.get("font_assets",{})!=(font_assets or {}) or frozen.get("policy")!=p):
            changed=[key for key in set(frozen.get("policy",{}))|set(p) if frozen.get("policy",{}).get(key)!=p.get(key)]
            raise StudioError("TEMPLATE_REGISTRY_IDENTITY_CONFLICT: register a new version/font variant; changed policy keys="+str(sorted(changed))+
                              "; composition="+str(frozen.get("composition_sha256")!=p["composition_sha256"])+
                              "; font_profile="+str(frozen.get("font_profile_sha256")!=current_font_hash))
        for asset in frozen.get("variants",{}).values():
            from .runtime import confined
            mother=confined(target,asset["file"])
            if not mother.is_file() or digest(mother)!=asset["sha256"]:
                raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: frozen mother")
        if not frozen.get("variants"):raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: missing frozen variants")
        # Maintenance reuses an identical asset; it must not reset accepted
        # release/review state or regenerate ZIP bytes under the same version.
        return target
    if target.exists() and any(target.iterdir()):
        raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: incomplete registered asset")
    create_templates(target,p)
    manifest=json.loads((target/"manifest.json").read_text(encoding="utf-8"))
    manifest.update(schema_version=2,composition_sha256=p["composition_sha256"],
        font_profile_id=profile_id,font_profile_sha256=current_font_hash,
        policy=p,font_assets=font_assets or {},template_year=descriptor.get("year"),release_state="candidate",automatic_pass=False,visual_review_complete=False)
    write_json(target/"manifest.json",manifest)
    return target

def resolve(request):
    require_actions()
    identity=request["template"]
    descriptor,p=load_composition(identity["id"],identity["version"])
    if "year" in identity and identity["year"]!=descriptor.get("year"):
        raise StudioError("TEMPLATE_YEAR_MISMATCH: "+identity["id"])
    target=asset_root()/identity["id"]/identity["version"]/identity["font_profile"]
    manifest_path=target/"manifest.json"
    if not manifest_path.is_file(): raise StudioError("TEMPLATE_NOT_READY")
    if digest(manifest_path)!=identity["manifest_sha256"]: raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: manifest")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("template_year")!=descriptor.get("year"):
        raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: year")
    if manifest["composition_sha256"]!=p["composition_sha256"]: raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: composition")
    current_fonts=font_profile(identity["font_profile"])
    current_font_hash=hashlib.sha256(json.dumps(current_fonts,sort_keys=True).encode()).hexdigest()
    if manifest.get("font_profile_sha256")!=current_font_hash:
        raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: font profile")
    requested_fonts={f["path"]:f["sha256"] for f in request.get("files",[]) if f.get("role")=="font"}
    if requested_fonts!=manifest.get("font_assets",{}): raise StudioError("FONT_ASSET_IDENTITY_MISMATCH: register this font variant first")
    if manifest.get("release_state")!="released" and os.environ.get("RPS_CANDIDATE_BUILD")!="true":
        raise StudioError("TEMPLATE_NOT_READY: candidate asset")
    variant=identity["variant"]
    if variant not in manifest["variants"]: raise StudioError("UNKNOWN_TEMPLATE_VARIANT")
    path=target/manifest["variants"][variant]["file"]
    if digest(path)!=manifest["variants"][variant]["sha256"]: raise StudioError("TEMPLATE_INTEGRITY_MISMATCH: mother")
    p=manifest["policy"]; p["english_abstract_position"]=variant
    p["equation_numbering"]="preserve" if request.get("document_kind")=="model" else "sequential"
    return path,p,{**identity,"sha256":digest(path),"font_profile_sha256":manifest["font_profile_sha256"],"release_state":manifest["release_state"]}
