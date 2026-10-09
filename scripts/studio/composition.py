"""Compose registered rules, never merge arbitrary DOCX section definitions."""
from pathlib import Path
from copy import deepcopy
import json
from .contracts import validate, ROOT
from .runtime import require_actions, StudioError, digest
def load_composition(template_id, version):
    require_actions()
    if not template_id.replace("-","").isalnum(): raise StudioError("UNKNOWN_TEMPLATE")
    path=ROOT/"templates"/template_id/"template.json"
    if not path.is_file(): raise StudioError("UNKNOWN_TEMPLATE: "+template_id)
    descriptor=validate(json.loads(path.read_text(encoding="utf-8")),"composition")
    if descriptor["version"] != version: raise StudioError("UNKNOWN_TEMPLATE_VERSION")
    registry=json.loads((ROOT/"components/registry.json").read_text(encoding="utf-8"))
    known={c["id"] for c in registry["components"]}
    if set(descriptor["components"])-known: raise StudioError("UNKNOWN_COMPONENT")
    if "toc" in descriptor["components"] and descriptor["policy"].get("anonymous_no_toc"):
        raise StudioError("COMPONENT_CONFLICT: toc")
    from .components import compile_components
    policy,component_hash=compile_components(descriptor)
    if policy.get("body_columns") not in (1,2): raise StudioError("UNSUPPORTED_REGION_COLUMNS")
    if policy.get("automatic_full_width_objects") is not False: raise StudioError("BODY_SPANNING_FORBIDDEN")
    policy.update(id=template_id,version=version)
    import hashlib
    policy["composition_sha256"]=hashlib.sha256((digest(path)+component_hash).encode()).hexdigest()
    return descriptor,policy

def font_profile(profile_id):
    require_actions()
    profiles=json.loads((ROOT/"catalog/font-profiles.json").read_text(encoding="utf-8"))
    if profile_id not in profiles: raise StudioError("FONT_PROFILE_UNKNOWN")
    # Never silently fall back to another profile.
    return profiles[profile_id]
