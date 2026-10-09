"""Compile selected components into executable role/object permissions."""
from copy import deepcopy
import hashlib,json
from .contracts import ROOT
from .runtime import require_actions,StudioError,digest

ROLE_COMPONENTS={"title.bilingual":["title"],"authors.affiliations":["authors","affiliation"],"abstract.single":["abstract"],"abstract.bilingual":["abstract"],"summary-sheet":["abstract"],"keywords":["keywords"]}
OBJECT_COMPONENTS={"math.inline":"inline_math","math.display":"display_math","figure.inline":"figure","table.three-line":"table","cross-reference":"cross_reference","bibliography":"bibliography"}
MANDATORY={"page.base","region.front","region.body","check.structure","check.content","check.geometry","check.visual"}

def compile_components(descriptor):
    require_actions()
    registry=json.loads((ROOT/"components/registry.json").read_text(encoding="utf-8"))
    entries={item["id"]:item for item in registry["components"]}
    selected=descriptor["components"]
    if len(selected)!=len(set(selected)): raise StudioError("DUPLICATE_COMPONENT")
    if set(selected)-set(entries): raise StudioError("UNKNOWN_COMPONENT")
    if MANDATORY-set(selected): raise StudioError("REQUIRED_COMPONENT_MISSING: "+str(sorted(MANDATORY-set(selected))))
    for name in selected:
        missing=set(entries[name].get("requires",[]))-set(selected)
        if missing: raise StudioError("COMPONENT_DEPENDENCY_MISSING: "+name+": "+str(sorted(missing)))
    if {"abstract.single","abstract.bilingual"}.issubset(selected): raise StudioError("COMPONENT_CONFLICT: abstract roles")
    if "math.display" in selected and not {"math.number","check.math"}.issubset(selected): raise StudioError("COMPONENT_DEPENDENCY_MISSING: display checks and numbering")
    if "math.multiline" in selected and "math.display" not in selected: raise StudioError("COMPONENT_DEPENDENCY_MISSING: multiline display")
    if {"figure.inline","table.three-line"}&set(selected) and "caption" not in selected: raise StudioError("COMPONENT_DEPENDENCY_MISSING: captions")
    p=deepcopy(descriptor["policy"])
    roles=[role for name in selected for role in ROLE_COMPONENTS.get(name,[])]
    p["front_roles"]=[role for role in ("title","authors","affiliation","abstract","keywords") if role in roles]
    p["enabled_objects"]=[role for name,role in OBJECT_COMPONENTS.items() if name in selected]
    p["component_versions"]={name:entries[name]["version"] for name in selected}
    p["page_numbers"]={"position":"footer-center","start":1,"scope":"all"} if "page-number" in selected else None
    # The registered region/table components own the TeX backend. A task
    # cannot select a different output routine or disable continuation.
    p["latex_body_backend"]="native-columns"
    p["latex_end_backend"]="cuted-strip" if "region.end" in selected else None
    p["latex_table_backend"]="cals" if "table.three-line" in selected else None
    p["paragraph_breaking"]={"emergency_stretch_em":3,"bibliographic_slash_breaks":True}
    p["math_array_padding_pt"]=10
    component_hash=hashlib.sha256(json.dumps({name:entries[name] for name in selected},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return p,component_hash

def check_content(ast,policy):
    require_actions()
    from .manuscript import walk
    allowed=set(policy.get("enabled_objects",[]))
    for index,node in enumerate(walk(ast)):
        kind=node.get("t"); required=None
        if kind=="Math":required="display_math" if node["c"][0]["t"]=="DisplayMath" else "inline_math"
        elif kind in ("Figure","Image"):required="figure"
        elif kind=="Table":required="table"
        elif kind=="Cite":required="bibliography"
        if required and required not in allowed: raise StudioError("CONTENT_COMPONENT_UNSUPPORTED: "+required+" at AST object "+str(index))

def check_metadata(metadata,policy):
    """A template mismatch must not silently discard manuscript fields."""
    require_actions()
    languages=set(policy.get("metadata_languages",["zh","en"]))
    roles=set(policy["front_roles"])
    for key,value in metadata.items():
        if not value: continue
        role,separator,language=key.rpartition("_")
        if not separator or role not in {"title","authors","affiliation","abstract","keywords"}:
            raise StudioError("METADATA_FIELD_UNSUPPORTED: "+key)
        if policy.get("anonymous") and role in {"authors","affiliation"}:
            raise StudioError("ANONYMOUS_IDENTITY_FORBIDDEN: "+key)
        if role not in roles: raise StudioError("METADATA_COMPONENT_UNSUPPORTED: "+key)
        if language not in languages:
            raise StudioError("METADATA_LANGUAGE_UNSUPPORTED: "+key+"; select a registered language variant or confirm a separate manuscript snapshot")
    return {key:value for key,value in metadata.items() if value}
