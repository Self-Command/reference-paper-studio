"""Audit object names, independent sequences and visible body references."""
from copy import deepcopy
import re
from .runtime import require_actions
from .manuscript import walk,text_of

PATTERNS={"Figure":r"^(?:图|Figure|Fig\.?)\s*(\d+)\s*[:：.]?\s*(.*)$","Table":r"^(?:表|Table)\s*(\d+)\s*[:：.]?\s*(.*)$"}

def inspect(ast,require_references=True):
    require_actions()
    body=deepcopy(ast)
    for node in walk(body):
        if node.get("t") in ("Figure","Table"): node["c"][1]=[None,[]]
    prose=text_of(body.get("blocks",[]))
    counters={"Figure":0,"Table":0}; records=[]; issues=[]
    for node in walk(ast):
        kind=node.get("t")
        if kind not in counters: continue
        counters[kind]+=1
        caption=text_of(node["c"][1][1]).strip()
        object_id=node["c"][0][0] or ("fig:F" if kind=="Figure" else "tab:T")+str(counters[kind])
        match=re.fullmatch(PATTERNS[kind],caption,re.S)
        record={"id":object_id,"kind":kind,"ordinal":counters[kind],"caption":caption}
        if not match: issues.append({"id":"CAPTION_NUMBER_OR_NAME_MISSING","object":object_id})
        else:
            if int(match[1])!=counters[kind]: issues.append({"id":"CAPTION_SEQUENCE_INVALID","object":object_id,"expected":counters[kind],"actual":int(match[1])})
            if not match[2].strip(): issues.append({"id":"CAPTION_NAME_MISSING","object":object_id})
        number=str(counters[kind])
        pattern=(r"(?:图\s*|(?:Figure|Fig\.?)\s*)" if kind=="Figure" else r"(?:表\s*|Table\s*)")+number+r"(?!\d)"
        referenced=bool(re.search(pattern,prose,re.I) or "{{"+object_id+"}}" in prose)
        record["body_referenced"]=referenced
        if require_references and not referenced: issues.append({"id":"OBJECT_BODY_REFERENCE_MISSING","object":object_id})
        records.append(record)
    return {"status":"failed" if issues else "passed","objects":records,"issues":issues,"reference_scope":"caption text excluded; accepts stable markers or printed object numbers"}
