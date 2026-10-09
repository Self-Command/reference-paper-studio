"""Compose editable MD skeletons from reviewed section blocks with Jinja2."""
from pathlib import Path
import re
from jinja2 import Environment,FileSystemLoader,StrictUndefined
from .contracts import ROOT
from .runtime import require_actions,StudioError,write_json,digest

def compose(template_id,version,output):
    require_actions()
    from .composition import load_composition
    descriptor,_=load_composition(template_id,version)
    source=ROOT/"templates"/template_id/"template.md"
    if not source.is_file(): raise StudioError("MD_TEMPLATE_NOT_AVAILABLE")
    text=source.read_text(encoding="utf-8")
    chunks=re.split(r"(?m)^# ([^\n]+)\n",text)
    sections=[{"title":chunks[i],"content":chunks[i+1].strip()} for i in range(1,len(chunks),2)]
    if not sections:raise StudioError("MD_SECTION_BLOCKS_MISSING")
    env=Environment(loader=FileSystemLoader(ROOT/"components/content"),undefined=StrictUndefined,keep_trailing_newline=True)
    target=Path(output);target.mkdir(parents=True,exist_ok=True)
    (target/"template.md").write_text(env.get_template("frame.md.j2").render(front_matter=chunks[0].strip(),sections=sections),encoding="utf-8")
    write_json(target/"md-composition.json",{"template_id":template_id,"version":version,"source_sha256":digest(source),"shared_frame_sha256":digest(ROOT/"components/content/frame.md.j2"),"sections":sections,"structure_approved":descriptor.get("availability",{}).get("md_ready",False)})
    return sections
