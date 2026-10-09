"""Read already-built cloud proofs; never mutate or rebuild the source run."""
from pathlib import Path
import json,re,sys
import pdfplumber
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions,write_json
require_actions()
root=Path("diagnostic-artifacts")
records=[]
for path in sorted(root.rglob("latex-column-geometry.json")):
    geometry=json.loads(path.read_text(encoding="utf-8"))
    item={"file":path.as_posix(),"violations":geometry.get("violations",[])}
    print(json.dumps(item,ensure_ascii=False),flush=True)
    records.append(item)
for path in sorted(root.rglob("main.log")):
    log=path.read_text(encoding="utf-8",errors="replace")
    source=path.with_suffix(".tex").read_text(encoding="utf-8").splitlines()
    for match in re.finditer(r"Overfull \\hbox.*?(?:at lines|in paragraph at lines) (\d+)--(\d+)",log,re.S):
        first,last=map(int,match.groups())
        item={"file":path.as_posix(),"first_line":first,"last_line":last,"source":"\n".join(source[max(0,first-2):min(len(source),last+2)])}
        print(json.dumps(item,ensure_ascii=False),flush=True)
        records.append(item)
for path in sorted(root.rglob("manuscript.docx")):
    profile_path=path.parent/"effective-profile.json"
    if not profile_path.is_file():continue
    from docx import Document
    from studio.docx_layout import M,W,math_width_pt,following_punctuation_width,is_equation_table
    from studio.locked_template import column_width
    from lxml import etree
    p=json.loads(profile_path.read_text(encoding="utf-8"))
    for table_index,table in enumerate(Document(path).tables):
        if is_equation_table(table._tbl):continue
        for row_index,row in enumerate(table.rows):
            for cell_index,cell in enumerate(row.cells):
                formulae=list(cell._tc.iter(M+"oMath"))
                if not formulae:continue
                item={"file":path.as_posix(),"table":table_index,"row":row_index,"cell":cell_index,
                      "text":cell.text,"formulas":[]}
                for formula in formulae:
                    punctuation=following_punctuation_width(formula,p["body_size_pt"])
                    item["formulas"].append({"xml":etree.tostring(formula,encoding="unicode"),
                        "estimated_width_pt":math_width_pt(formula,p["body_size_pt"]),
                        "punctuation_reserve_pt":punctuation,
                        "cell_budget_pt":column_width(p)/20/len(row.cells)-12-punctuation})
                print(json.dumps(item,ensure_ascii=False),flush=True);records.append(item)
for path in sorted(root.rglob("*-summary.json"))+sorted(root.glob("*regression.json")):
    print(path.as_posix()+": "+path.read_text(encoding="utf-8"),flush=True)
for path in sorted(root.rglob("word-compat-proof.pdf")):
    item={"file":path.as_posix(),"pages":[]}
    profile_path=path.parent/"effective-profile.json"
    if not profile_path.is_file(): continue
    p=json.loads(profile_path.read_text(encoding="utf-8"))
    with pdfplumber.open(path) as pdf:
        for number,page in enumerate(pdf.pages,1):
            left=p["page"]["margin_cm"]["left"]*72/2.54
            right=page.width-p["page"]["margin_cm"]["right"]*72/2.54
            cols=p.get("body_columns",2);gap=p["page"]["column_spacing_cm"]*72/2.54
            width=(right-left-(cols-1)*gap)/cols
            labels=[]
            for label in page.search(r"\((?:M|E)?\d+\)",regex=True):
                col=min(cols-1,max(0,int((label["x0"]-left)/(width+gap))))
                labels.append({"text":label["text"],"bbox":[label[k] for k in ("x0","top","x1","bottom")],"edge_delta_pt":label["x1"]-(left+col*(width+gap)+width)})
            item["pages"].append({"page":number,"fonts":sorted({c.get("fontname","") for c in page.chars}),"labels":labels})
    records.append(item)
    print(json.dumps(item,ensure_ascii=False),flush=True)
for path in sorted(root.rglob("latex-proof.pdf")):
    with pdfplumber.open(path) as pdf:
        item={"file":path.as_posix(),"last_pages":[{"page":index+1,"text":page.extract_text() or ""} for index,page in enumerate(pdf.pages) if index>=len(pdf.pages)-2]}
    records.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
write_json("build/proof-diagnostics.json",records)
