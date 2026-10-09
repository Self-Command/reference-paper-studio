"""Mechanical manuscript review with explicit scientific review boundaries."""
from pathlib import Path
import json,re
from .runtime import require_actions,confined,write_json,StudioError,digest
from .manuscript import parse,walk,text_of,validate_assets,validate_references,resolve_crossrefs
from .pipeline import strict_pandoc
from .frontmatter import extract
def inspect(root,request,output):
    require_actions()
    root=Path(root); output=Path(output)
    ast,equations=parse(confined(root,request["manuscript"]),output)
    metadata=extract(ast); ast["meta"]={}
    issues=[]
    if not metadata.get("title_zh") and not metadata.get("title_en") and not any(n.get("t")=="Header" and n["c"][0]==1 for n in ast["blocks"]): issues.append({"id":"MD_TITLE_MISSING","severity":"blocker"})
    if not metadata.get("abstract_zh") and not metadata.get("abstract_en"): issues.append({"id":"MD_ABSTRACT_MISSING","severity":"major"})
    reference_language="en" if any(key.endswith("_en") for key in metadata) and not any(key.endswith("_zh") for key in metadata) else "zh"
    if request.get("template"):
        from .composition import load_composition
        _,policy=load_composition(request["template"]["id"],request["template"]["version"])
        reference_language="en" if policy.get("metadata_languages")==["en"] else "zh"
    mapping=resolve_crossrefs(ast,equations,"preserve",reference_language)
    from .object_audit import inspect as inspect_objects
    object_report=inspect_objects(ast)
    issues.extend({**issue,"severity":"major"} for issue in object_report["issues"])
    validate_assets(ast,root);validate_references(ast)
    prose=text_of(ast["blocks"])
    objects=[]
    for block_index,block in enumerate(ast["blocks"]):
        for node in walk(block):
            if node.get("t") not in ("Table","Figure"): continue
            caption=text_of(node["c"][1][1]).strip()
            if not re.sub(r"^(?:表|图|Fig\.?|Figure|Table)\s*\d+\s*[:：.]?\s*","",caption).strip(): issues.append({"id":"CAPTION_NAME_MISSING","severity":"major","block":block_index+1})
            objects.append({"kind":node["t"],"caption":caption,"block":block_index+1,"source_location_accuracy":"block ordinal; not exact source line"})
    if re.search(r"<[^>]*(?:论文题目|摘要|Title|Abstract)[^>]*>",confined(root,request["manuscript"]).read_text(encoding="utf-8")): issues.append({"id":"UNFINISHED_PLACEHOLDER","severity":"blocker"})
    report={"status":"failed" if issues else "mechanical_checks_passed","issues":issues,"objects":objects,"object_audit":object_report,"formula_ids":[e["id"] for e in equations],"references":mapping,"manuscript_sha256":digest(confined(root,request["manuscript"])),"scientific_review":"Current Codex must assess logic, mathematics and evidence; this program is not a proof or user content approval"}
    write_json(output/"md-review.json",report)
    (output/"MD复检报告.md").write_text("# MD复检报告\n\n程序结果："+report["status"]+"。科学逻辑、数学与证据仍由当前审查和作者确认。\n\n"+"\n".join("- "+str(item) for item in issues),encoding="utf-8")
    return report
