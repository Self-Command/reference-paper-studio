"""Parse and preserve metadata semantics, including editable inline mathematics."""
from pathlib import Path
from copy import deepcopy
import json
from .runtime import require_actions,run,write_json,StudioError
from .manuscript import walk

def extract(ast):
    require_actions()
    metadata={}
    def value(node):
        if node["t"]=="MetaString": return node["c"]
        if node["t"]=="MetaList": return [value(v) for v in node["c"]]
        blocks=[{"t":"Para","c":node["c"]}] if node["t"]=="MetaInlines" else node["c"]
        data={"pandoc-api-version":ast["pandoc-api-version"],"meta":{},"blocks":blocks}
        return run(["pandoc","-f","json","-t","markdown","--wrap=none"],input_text=json.dumps(data)).strip()
    for key,node in ast.get("meta",{}).items():
        if key in {prefix+"_"+lang for prefix in ("title","authors","affiliation","abstract","keywords") for lang in ("zh","en")}:
            metadata[key]=value(node)
    return metadata

def prepare(metadata, api_version, output):
    require_actions()
    output=Path(output); blocks=[]; roles=[]; tex={}; expected_math=[]
    for key,value in metadata.items():
        if key.startswith("_") or not value: continue
        text="; ".join(value) if isinstance(value,list) else str(value)
        prefix=("摘要：" if key.endswith("zh") else "Abstract: ") if key.startswith("abstract_") else ("关键词：" if key.endswith("zh") else "Keywords: ") if key.startswith("keywords_") else ""
        data=json.loads(run(["pandoc","-f","markdown","-t","json"],input_text=prefix+text))
        if len(data["blocks"])!=1 or data["blocks"][0]["t"] not in ("Para","Plain"):
            raise StudioError("METADATA_STRUCTURE_UNSUPPORTED: "+key)
        for node in walk(data["blocks"]):
            if node.get("t") in ("RawBlock","RawInline","Image"): raise StudioError("METADATA_RAW_OBJECT_FORBIDDEN")
            if node.get("t")=="Math":
                if node["c"][0]["t"]!="InlineMath": raise StudioError("METADATA_DISPLAY_MATH_UNSUPPORTED: "+key)
                expected_math.append({"key":key,"expression":node["c"][1]})
        blocks.extend(data["blocks"]); roles.append(key)
        tex[key]=run(["pandoc","-f","json","-t","latex","--wrap=none"],input_text=json.dumps(data)).strip()
    data={"pandoc-api-version":api_version,"meta":{},"blocks":blocks}
    write_json(output/"metadata-source.json",data)
    from .pipeline import strict_pandoc
    strict_pandoc(["pandoc",output/"metadata-source.json","-f","json","-o",output/"metadata-native.docx"])
    write_json(output/"metadata-math.json",expected_math)
    return {**metadata,"_meta_docx":str(output/"metadata-native.docx"),"_meta_roles":roles,"_meta_tex":tex,"_meta_math_count":len(expected_math)}
