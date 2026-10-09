"""Locate real display labels; disclose geometry coverage instead of guessing proof."""
from pathlib import Path
import re
import pdfplumber
from .runtime import require_actions,write_json,StudioError

def measure(path,equations,profile):
    require_actions()
    records=[]; failures=[]
    with pdfplumber.open(path) as pdf:
        for equation in equations:
            label=equation["id"] if profile["equation_numbering"]=="preserve" else str(equation["ordinal"])
            matches=[]
            for number,page in enumerate(pdf.pages,1):
                left=profile["page"]["margin_cm"]["left"]*72/2.54
                right=page.width-profile["page"]["margin_cm"]["right"]*72/2.54
                cols=profile.get("body_columns",2); gap=profile["page"]["column_spacing_cm"]*72/2.54
                width=(right-left-(cols-1)*gap)/cols
                for candidate in page.search(re.escape("("+label+")"),regex=True):
                    col=min(cols-1,max(0,int((candidate["x0"]-left)/(width+gap))))
                    col_left=left+col*(width+gap); edge=col_left+width
                    if abs(candidate["x1"]-edge)>14: continue
                    center=(candidate["top"]+candidate["bottom"])/2
                    glyphs=[c for c in page.chars if "math" in c.get("fontname","").lower() and col_left-1<=c["x0"] and c["x1"]<candidate["x0"]-3 and abs((c["top"]+c["bottom"])/2-center)<60]
                    matches.append((number,candidate,glyphs))
            if not matches:
                failures.append(label); records.append({"id":label,"status":"label_not_located_at_column_edge"}); continue
            number,label_box,glyphs=max(matches,key=lambda item:len(item[2]))
            record={"id":label,"page":number,"label_bbox":[label_box[k] for k in ("x0","top","x1","bottom")],"math_glyphs":len(glyphs),"anchor":"center" if re.search(r"\\begin\{(?:cases|aligned|array|matrix)|\\\\",equation["source"]) else "baseline","assessment":"visual_required","reason":"PDF font boxes do not always expose a reliable equation baseline; inspect cloud page against declared anchor"}
            if glyphs:
                record["nearby_math_bbox"]=[min(c["x0"] for c in glyphs),min(c["top"] for c in glyphs),max(c["x1"] for c in glyphs),max(c["bottom"] for c in glyphs)]
            else: failures.append(label); record["status"]="math_not_located"
            records.append(record)
    report={"equations":records,"failed":failures,"automatic_coverage":"label edge and nearby math; actual baseline/center requires visual review","alignment_passed":False}
    write_json(Path(path).parent/"equation-alignment.json",report)
    if failures: raise StudioError("EQUATION_ALIGNMENT_LOCATION_FAILED: "+", ".join(failures))
    return report
