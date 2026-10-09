"""Locate real display labels; disclose geometry coverage instead of guessing proof."""
from pathlib import Path
import re
import pdfplumber
from .runtime import require_actions,write_json,StudioError

def measure(path,equations,profile):
    require_actions()
    import json
    ledger_path=Path(path).parent/"math-layout-ledger.json"
    anchors={item["id"]:item.get("number_anchor") for item in json.loads(ledger_path.read_text(encoding="utf-8"))} if ledger_path.is_file() else {}
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
                    # Cloud diagnostics show display labels within 0.08 pt of
                    # the edge; prose references may be 12 pt away.
                    if abs(candidate["x1"]-edge)>2: continue
                    center=(candidate["top"]+candidate["bottom"])/2
                    # LibreOffice imports native OMML through StarMath and may
                    # emit Liberation/DejaVu/OpenSymbol glyphs. A font-name
                    # substring is not a reliable way to locate mathematics.
                    glyphs=[c for c in page.chars if c["text"].strip() and col_left-1<=c["x0"] and c["x1"]<candidate["x0"]-3 and abs((c["top"]+c["bottom"])/2-center)<60]
                    matches.append((number,candidate,glyphs))
            if not matches:
                failures.append(label); records.append({"id":label,"status":"label_not_located_at_column_edge"}); continue
            number,label_box,glyphs=max(matches,key=lambda item:len(item[2]))
            record={"id":label,"page":number,"label_bbox":[label_box[k] for k in ("x0","top","x1","bottom")],"nearby_visible_glyphs":len(glyphs),"observed_fonts":sorted({c.get("fontname","") for c in glyphs}),"anchor":anchors.get(equation["id"]) or ("center" if re.search(r"\\begin\{(?:cases|aligned|array|matrix)|\\\\",equation["source"]) else "baseline"),"assessment":"visual_required","reason":"Nearby glyphs are geometry evidence, not proof of equation identity or alignment. PDF font boxes do not expose a reliable equation baseline; inspect cloud pages."}
            if glyphs:
                record["nearby_math_bbox"]=[min(c["x0"] for c in glyphs),min(c["top"] for c in glyphs),max(c["x1"] for c in glyphs),max(c["bottom"] for c in glyphs)]
            else: failures.append(label); record["status"]="math_not_located"
            records.append(record)
    report={"equations":records,"failed":failures,"automatic_coverage":"display-label edge and nearby visible content only; equation identity, baseline/center and alignment require separate checks and visual review","alignment_passed":False}
    write_json(Path(path).parent/"equation-alignment.json",report)
    if failures: raise StudioError("EQUATION_ALIGNMENT_LOCATION_FAILED: "+", ".join(failures))
    return report
