"""Common Pandoc representation; loss is an error, not a writer fallback."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re
from .runtime import StudioError, require_actions, run, write_json

MARKDOWN = "markdown+tex_math_single_backslash+tex_math_dollars+pipe_tables+table_captions+citations+raw_attribute"


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def text_of(value):
    if isinstance(value, dict):
        # Short captions and image alt text are aliases, not repeated visible prose.
        if value.get("t") == "Table":
            return text_of(value["c"][1][1])+text_of(value["c"][3:])
        if value.get("t") == "Figure":
            return text_of(value["c"][1][1])
        if value.get("t") == "Str":
            return value["c"]
        if value.get("t") in ("Space", "SoftBreak", "LineBreak"):
            return " "
        if value.get("t") == "Quoted":
            left, right = ("“", "”") if value["c"][0]["t"] == "DoubleQuote" else ("‘", "’")
            return left + text_of(value["c"][1]) + right
        if value.get("t") == "Code": return value["c"][1]
        return "".join(text_of(v) for v in value.values())
    if isinstance(value, list):
        return "".join(text_of(v) for v in value)
    return ""


def parse(source, output):
    require_actions()
    ast = json.loads(run(["pandoc", source, "-f", MARKDOWN, "-t", "json"]))
    equations = []
    for node in walk(ast):
        if node.get("t") == "Math":
            expression = node["c"][1]
            if node["c"][0]["t"] == "DisplayMath":
                tags = re.findall(r"\\tag\{([^}]+)\}", expression)
                if len(tags) > 1:
                    raise StudioError("MULTIPLE_EQUATION_TAGS")
                identifier = tags[0] if tags else f"E{len(equations)+1}"
                if not re.fullmatch(r"[A-Za-z0-9][\w.:-]*", identifier): raise StudioError("INVALID_EQUATION_IDENTIFIER")
                if identifier in {e["id"] for e in equations}:
                    raise StudioError(f"DUPLICATE_EQUATION: {identifier}")
                expression = re.sub(r"\\tag\{[^}]+\}", "", expression).strip()
                equations.append({"id": identifier, "source": expression, "ordinal": len(equations)+1})
                node["c"][1] = expression
    if any(n.get("t") in ("RawInline", "RawBlock") for n in walk(ast)):
        raise StudioError("UNSUPPORTED_RAW_OBJECT: use Markdown objects and math rather than embedded raw commands")
    write_json(Path(output) / "document.json", ast)
    write_json(Path(output) / "equations.json", equations)
    return ast, equations


def validate_assets(ast, root):
    from .runtime import confined
    for node in walk(ast):
        if node.get("t") == "Image":
            image = node["c"][-1][0]
            if "://" in image or not confined(root, image).is_file():
                raise StudioError(f"MISSING_IMAGE: {image}")


def validate_references(ast):
    """Reject unresolved numeric/bibliographic references, ignoring bibliography definitions."""
    text = text_of(ast["blocks"])
    bibliography = text.split("参考文献", 1)[-1] if "参考文献" in text else ""
    body = text.split("参考文献", 1)[0] if bibliography else text
    labels = {int(n) for n in re.findall(r"\[(\d+)\]", bibliography)}
    used = {int(n) for n in re.findall(r"\[(\d+)\]", body)}
    if used - labels:
        raise StudioError(f"BROKEN_REFERENCE: {sorted(used-labels)}")


def resolve_crossrefs(ast, equations, numbering):
    """Shared object identities; explicit markers are identical in both writers."""
    mapping = {"eq:"+e["id"]: "("+(e["id"] if numbering == "preserve" else str(e["ordinal"]))+")" for e in equations}
    blocks = ast["blocks"]
    # Recognize adjacent Chinese/English table captions, including captions below.
    for block in list(blocks):
        if block.get("t") != "Table": continue
        index = blocks.index(block)
        for neighbor in (index-1,index+1):
            if 0 <= neighbor < len(blocks) and blocks[neighbor].get("t") == "Para":
                caption = blocks[neighbor]
                match = re.match(r"^(?:表\s*|Table\s+)(\d+)", text_of(caption))
                if match:
                    block["c"][1] = [None,[caption]]
                    blocks.remove(caption)
                    break
    counters = {"Figure":0,"Table":0}
    for node in walk(ast):
        kind = node.get("t")
        if kind in counters:
            counters[kind] += 1
            prefix, label = ("fig:","图") if kind == "Figure" else ("tab:","表")
            identifier = node["c"][0][0]
            identifier = identifier if identifier.startswith(prefix) else prefix+("F" if kind=="Figure" else "T")+str(counters[kind])
            if identifier in mapping: raise StudioError("DUPLICATE_OBJECT_IDENTIFIER: "+identifier)
            mapping[identifier] = label+str(counters[kind])
    for node in walk(ast):
        if node.get("t") == "Str":
            def substitute(match):
                key=match.group(1)
                if key not in mapping: raise StudioError("BROKEN_CROSS_REFERENCE: "+key)
                return mapping[key]
            node["c"] = re.sub(r"\{\{((?:eq|fig|tab):[\w.:-]+)\}\}",substitute,node["c"])
    return mapping


def latex_ast(ast, equations, numbering):
    result = deepcopy(ast)
    index = 0
    for node in walk(result):
        if node.get("t") == "Math" and node["c"][0]["t"] == "DisplayMath":
            equation = equations[index]
            display = equation["id"] if numbering == "preserve" else str(index + 1)
            node["c"][1] += f"\\tag{{{display}}}"
            index += 1
    return result


def normalized_text(ast):
    """Compare literal visible prose while checking mathematics separately."""
    result = deepcopy(ast)
    def clean(value):
        if isinstance(value, dict):
            if value.get("t") in ("Math", "RawBlock", "RawInline"):
                return {"t": "Str", "c": ""}
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    text = text_of(clean(result["blocks"]))
    return re.sub(r"\s+", "", text)


def model_gate(root, source, evidence, paper=False):
    from .runtime import confined, digest
    require_actions()
    if not paper:
        return {"status": "format_only", "mathematical_validation": "not_asserted"}
    if not evidence:
        raise StudioError("MODEL_NOT_VERIFIED: full paper drafting/export requires current validation and author approval")
    record = json.loads(confined(root, evidence).read_text(encoding="utf-8"))
    model = confined(root, record.get("model", source))
    report = confined(root, record["report"])
    if record.get("status") != "passed" or record.get("author_approved") is not True or record.get("model_sha256") != digest(model) or record.get("report_sha256") != digest(report):
        raise StudioError("MODEL_NOT_VERIFIED: stale or incomplete evidence")
    for claim in record.get("quantitative_claims", []):
        if not claim.get("source") or not claim.get("sha256") or digest(confined(root, claim["source"])) != claim["sha256"]:
            raise StudioError("CLAIM_WITHOUT_EVIDENCE")
    paper_text=confined(root, source).read_text(encoding="utf-8")
    if re.search(r"^#{1,6}\s+.*(?:实验结果|仿真结果|实证结果|结果与分析)",paper_text,re.M) and not record.get("quantitative_claims"):
        raise StudioError("RESULTS_WITHOUT_DATA: empirical results need explicit source-bound claims")
    return {"status": "evidence_bound", "mathematical_validation": "author_supplied_report", "evidence": record}
