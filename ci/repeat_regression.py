"""Repeat the same bound input and frozen mother; compare actual artifacts."""
from pathlib import Path
import sys,os,json,zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions,digest,write_json,StudioError
require_actions()
from studio.pipeline import export
from studio.qa import visible_docx
from studio.math_layout import tree
from studio.docx_layout import M
from docx import Document

root=Path(__file__).resolve().parents[1]
os.environ["RPS_REGISTRY_ROOT"]=str(root/"build/templates")
os.environ["RPS_CANDIDATE_BUILD"]="true"
work=root/"build/modular-input-front"
request=json.loads((work/"request.json").read_text(encoding="utf-8"))
first=root/"build/modular-model-front";second=root/"build/modular-repeat-front"
result={"status":"running","run_id":os.environ["GITHUB_RUN_ID"],"engine_commit":os.environ["GITHUB_SHA"],
        "input_files":{item["path"]:item["sha256"] for item in request["files"]},"template":request["template"],
        "checks":[],"allowed_binary_differences":["ZIP container timestamps","PDF metadata timestamps and identifiers"],
        "visual_review":"not_asserted","installation_allowed":False}
try:
    export(work,request,second)
    for name in ("document.json","layout-document.json","docx-readback.json","latex-readback.json","reference-map.json","content-report.json","math-layout-ledger.json","inline-math-layout-ledger.json"):
        if json.loads((first/name).read_text())!=json.loads((second/name).read_text()):
            raise StudioError("REPEAT_CONTENT_CHANGED: "+name)
        result["checks"].append(name)
    for name in ("used-master.docx","latex/main.tex","latex/body.tex","latex/layout-body.tex"):
        if digest(first/name)!=digest(second/name):raise StudioError("REPEAT_FROZEN_ASSET_CHANGED: "+name)
        result["checks"].append(name)
    if visible_docx(first/"manuscript.docx")!=visible_docx(second/"manuscript.docx"):
        raise StudioError("REPEAT_WORD_TEXT_CHANGED")
    formulae=lambda path:[tree(node) for node in Document(path)._element.iter(M+"oMath")]
    if formulae(first/"manuscript.docx")!=formulae(second/"manuscript.docx"):
        raise StudioError("REPEAT_WORD_MATH_CHANGED")
    result["checks"].extend(["actual Word text","native OMML trees"])
    for proof in ("word-compat-proof","latex-proof"):
        preview=lambda folder:{p.name:digest(p) for p in (folder/"previews"/proof).glob("*.png")}
        before=preview(first);after=preview(second)
        if not before or before!=after:raise StudioError("REPEAT_RENDER_CHANGED: "+proof)
        result["checks"].append({"proof":proof,"page_count":len(before),"pixel_files":"identical"})
    result["status"]="passed"
except Exception as error:
    result.update(status="failed",error=str(error));raise
finally:
    write_json(root/"build/reproducibility.json",result)
