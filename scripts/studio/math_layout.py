"""Reversible, deterministic OMML row wrapping. No symbol rewriting or font shrink."""
from copy import deepcopy
import re
from lxml import etree
from docx.oxml import OxmlElement
from .docx_layout import M, W, math_width_pt
from .runtime import StudioError, require_actions


def tree(element):
    """Ignore only Word font properties; retain all mathematical properties."""
    return (etree.QName(element).localname, tuple(sorted(element.attrib.items())), element.text or "",
            tuple(tree(c) for c in element if c.tag != W+"rPr"))


def at(root, path):
    for index in path: root = root[index]
    return root


def restore(root, changes):
    result = deepcopy(root)
    for change in reversed(changes):
        current = at(result, change["path"])
        expected = etree.fromstring(change["after"].encode())
        if tree(current) != tree(expected): raise StudioError("MATH_LAYOUT_TRANSFORM_MISMATCH")
        previous = etree.fromstring(change["before"].encode())
        if not change["path"]: result = previous
        else:
            parent = at(result, change["path"][:-1]); parent.replace(current, previous)
    return result


def wrap(root, width_pt):
    require_actions()
    before = deepcopy(root); changes = []
    containers = {"oMath", "e", "num", "den", "lim"}
    def visit(element, path, budget):
        name = etree.QName(element).localname
        # Reserve delimiters, fraction rules and matrix neighbours conservatively.
        children = list(element)
        for index, child in enumerate(children):
            child_budget = budget
            if name in ("d", "borderBox"): child_budget -= 15
            if name in ("mr", "oMath", "e") and child.tag not in (M+"r", M+"rPr", W+"rPr"):
                other = sum(math_width_pt(c, 10) for c in children if c is not child)
                child_budget = max(45, budget-other-8)
            visit(child, path+[index], max(45, child_budget))
        if name not in containers or math_width_pt(element, 10) <= budget: return
        tokens = []
        for child in element:
            if child.tag == M+"r":
                texts = child.findall(M+"t")
                if len(texts) == 1:
                    value = texts[0].text or ""
                    # Ordinary mathematical text may wrap between Chinese characters.
                    pieces = re.split(r"(?=[=<>≤≥+−,;]|[\u3400-\u9fff])", value)
                    for piece in filter(None, pieces):
                        copy = deepcopy(child); copy.find(M+"t").text = piece; tokens.append(copy)
                    continue
            tokens.append(deepcopy(child))
        segments = []; segment = []; depth = 0; previous = ""
        for token in tokens:
            value = token.findtext(M+"t", "") if token.tag == M+"r" else ""
            safe = depth == 0 and (token.tag == M+"r" and bool(re.match(r"^[=<>≤≥+−,;\u3400-\u9fff]", value)) or previous.endswith(")") and value == "1")
            if safe and segment: segments.append(segment); segment=[]
            segment.append(token)
            for character in value:
                if character in "([{": depth += 1
                elif character in ")]}": depth = max(0,depth-1)
            previous = value
        if segment: segments.append(segment)
        rows = []; row = []; used = 0
        for segment in segments:
            size = sum(math_width_pt(t,10) for t in segment)
            if row and used+size > budget:
                rows.append(row); row=[]; used=0
            row.extend(segment); used+=size
        if row: rows.append(row)
        if len(rows) < 2: return
        old = etree.tostring(element, encoding="unicode")
        for child in list(element): element.remove(child)
        array = OxmlElement("m:eqArr")
        props = OxmlElement("m:eqArrPr"); jc = OxmlElement("m:baseJc"); jc.set(M+"val", "top"); props.append(jc); array.append(props)
        for row in rows:
            entry = OxmlElement("m:e")
            first = row[0].findtext(M+"t", "") if row[0].tag == M+"r" else ""
            if re.match(r"^[=<>≤≥]",first):
                # A continuation relation is displayed as a literal operator,
                # avoiding a compatibility parser's missing-operand placeholder.
                props=row[0].find(M+"rPr")
                if props is None: props=OxmlElement("m:rPr"); row[0].insert(0,props)
                normal=OxmlElement("m:nor"); normal.set(M+"val","1"); props.append(normal)
            for child in row: entry.append(child)
            array.append(entry)
        element.append(array)
        changes.append({"path": path, "before": old, "after": etree.tostring(element, encoding="unicode"), "rows": len(rows)})
    visit(root, [], width_pt)
    recovered = restore(root, changes)
    if tree(recovered) != tree(before): raise StudioError("MATH_LAYOUT_NOT_REVERSIBLE")
    return changes
