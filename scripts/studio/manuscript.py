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
        if value.get("t") == "Str":
            return value["c"]
        if value.get("t") in ("Space", "SoftBreak", "LineBreak"):
            return " "
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
                if identifier in {e["id"] for e in equations}:
                    raise StudioError(f"DUPLICATE_EQUATION: {identifier}")
                expression = re.sub(r"\\tag\{[^}]+\}", "", expression).strip()
                equations.append({"id": identifier, "source": expression, "ordinal": len(equations)+1})
                node["c"][1] = expression
    if any(n.get("t") in ("RawInline", "RawBlock") and n.get("c", [""])[0] not in ("tex", "latex") for n in walk(ast)):
        raise StudioError("UNSUPPORTED_RAW_OBJECT: use Markdown objects rather than embedded HTML/Word")
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
    return {"status": "evidence_bound", "mathematical_validation": "author_supplied_report", "evidence": record}
