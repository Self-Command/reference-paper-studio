"""Read registered font advances in Actions; do not choose or modify fonts."""
from pathlib import Path
from functools import lru_cache
from .runtime import require_actions,run,digest,StudioError


@lru_cache(maxsize=16)
def registered_metrics(family,filename,index,fingerprint):
    require_actions()
    path=run(["fc-match","-f","%{file}",family+":style=Regular"]).strip()
    if Path(path).name!=filename or digest(path)!=fingerprint:
        raise StudioError("FONT_FACE_FINGERPRINT_MISMATCH: math metrics "+family)
    from fontTools.ttLib import TTFont
    with TTFont(path,fontNumber=index) as font:
        units=font["head"].unitsPerEm
        cmap=font.getBestCmap() or {}
        advances=font["hmtx"].metrics
        return {chr(code):advances[glyph][0]/units for code,glyph in cmap.items() if glyph in advances}


def configure(profile):
    require_actions()
    from .fonts import resolve_faces
    faces=profile.get("font_faces") or resolve_faces(profile["fonts"])
    # Font identity comes from the frozen mother policy. The returned advances
    # improve estimates only; actual renderer overflow checks remain decisive.
    result={}
    for role in ("math","cjk"):
        face=faces[role]["upright"]
        result[role]=registered_metrics(profile["fonts"][role],face["file"],face["index"],face["sha256"])
    return result
