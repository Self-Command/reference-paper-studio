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


def wrap(root, width_pt, font_size_pt=10, array_padding_pt=0, metrics=None):
    require_actions()
    before = deepcopy(root); changes = []
    def measure(element):return math_width_pt(element,font_size_pt,metrics)
    # Pandoc represents TeX setminus by ASCII backslash. LibreOffice treats that
    # as a StarMath escape and consumes the following operand. U+2216 carries
    # the same set-difference operator without parser escape semantics.
    slash = [node for node in root.iter(M+"t") if node.text == "\\"]
    if slash:
        old = etree.tostring(root,encoding="unicode")
        for node in slash: node.text = "∖"
        changes.append({"path":[],"before":old,"after":etree.tostring(root,encoding="unicode"),"reason":"setminus operator Unicode spelling"})
    # Subscripts such as Z_{>0} also start with an operator. Guard existing
    # arguments before wrapping, not just newly introduced continuation rows.
    old = etree.tostring(root,encoding="unicode")
    for argument in list(root.iter()):
        if etree.QName(argument).localname not in {"oMath","e","sub","sup","lim","num","den"}: continue
        token = next((c for c in argument if not etree.QName(c).localname.endswith("Pr")),None)
        if token is None or token.tag != M+"r": continue
        value = token.findtext(M+"t","")
        if not re.match(r"^[=<>≤≥+−×∧∨]",value): continue
        symbol=deepcopy(token);symbol.find(M+"t").text=value[0]
        box=OxmlElement("m:box");entry=OxmlElement("m:e");entry.append(symbol);box.append(entry)
        if len(value)>1:
            token.find(M+"t").text=value[1:];token.addprevious(box)
        else: argument.replace(token,box)
    current = etree.tostring(root,encoding="unicode")
    if current != old:
        changes.append({"path":[],"before":old,"after":current,"reason":"editable leading operators in existing math arguments"})
    containers = {"oMath", "e", "num", "den", "lim"}
    def segments_of(element, tail_budget=None):
        tokens=[]
        for child in element:
            if child.tag==M+"r" and len(child.findall(M+"t"))==1:
                value=child.findtext(M+"t","")
                for piece in filter(None,re.split(r"(?=[=<>≤≥+−×∧∨,;:]|[\u3400-\u9fff])",value)):
                    token=deepcopy(child); token.find(M+"t").text=piece; tokens.append(token)
            else: tokens.append(deepcopy(child))
        segments=[]; segment=[]; depth=0; previous=""
        for token in tokens:
            value=token.findtext(M+"t","") if token.tag==M+"r" else ""
            # A quantified condition's colon is a legal break before its
            # predicate. Keeping the range and predicate in one segment was
            # pushing a short trailing '=1' onto a line of its own.
            safe=(depth==0 and (token.tag==M+"r" and bool(re.match(r"^[=<>≤≥+−×∧∨,;:\u3400-\u9fff]",value)) or previous.endswith(")") and value=="1")) or (depth==1 and token.tag==M+"r" and value.startswith(","))
            if safe and segment: segments.append(segment); segment=[]
            segment.append(token)
            for character in value:
                if character in "([{": depth+=1
                elif character in ")]}": depth=max(0,depth-1)
            previous=value
        if segment: segments.append(segment)
        if tail_budget is not None:
            merged=[]
            for item in segments:
                literal="".join(t.text or "" for token in item for t in token.iter(M+"t"))
                if merged and re.fullmatch(r"[=<>≤≥]\s*-?\d+(?:\.\d+)?[.,;]?",literal) and sum(measure(t) for t in merged[-1]+item)<=tail_budget:
                    # Join only a short scalar relation that actually fits.
                    # Never borrow the number region or change the operand.
                    merged[-1].extend(item)
                else: merged.append(item)
            segments=merged
        return segments
    def visit(element, path, budget):
        name = etree.QName(element).localname
        # Only a piecewise delimiter may stack value/condition cells. A general
        # matrix keeps its columns: changing those would change its meaning.
        if name == "m" and measure(element) > budget:
            parent = element.getparent()
            delimiter = parent.getparent() if parent is not None and parent.tag == M+"e" else parent
            props = delimiter.find(M+"dPr") if delimiter is not None and delimiter.tag == M+"d" else None
            if props is not None and props.find(M+"begChr") is not None and props.find(M+"begChr").get(M+"val") == "{" and props.find(M+"endChr") is not None and props.find(M+"endChr").get(M+"val") == "":
                rows = element.findall(M+"mr")
                if rows and all(len(row.findall(M+"e")) == 2 for row in rows):
                    old = etree.tostring(element, encoding="unicode")
                    for row in rows:
                        left, condition = row.findall(M+"e")
                        nested = OxmlElement("m:eqArr")
                        nested.append(deepcopy(left)); nested.append(deepcopy(condition))
                        for child in list(left): left.remove(child)
                        left.append(nested); row.remove(condition)
                    for inherited in list(element.findall(M+"mPr")): element.remove(inherited)
                    changes.append({"path":path,"before":old,"after":etree.tostring(element,encoding="unicode"),"reason":"piecewise value then condition, one column"})
        # Reserve delimiters, fraction rules and matrix neighbours conservatively.
        children = list(element)
        linear_overflow=name in containers and len(segments_of(element))>1 and measure(element)>budget
        for index, child in enumerate(children):
            child_budget = budget
            if name in ("d", "borderBox"): child_budget -= 15
            if name in ("mr", "oMath", "e") and child.tag not in (M+"r", M+"rPr", W+"rPr"):
                other = sum(measure(c) for c in children if c is not child)
                # Only a parent with actual legal split points may move its
                # neighbours to separate lines. Indivisible objects still
                # reserve their neighbours and cannot borrow column width.
                # Reserving ALL unwrapped neighbours here would give a cases
                # condition only 45 pt even after its parent moves to a new row.
                # Transparent single-child argument wrappers add no physical
                # width. Subtracting 8 pt at every nesting level eventually
                # broke short function arguments that already fit the column.
                child_budget = max(45,budget if linear_overflow else budget-other)
            visit(child, path+[index], max(45, child_budget))
        if name not in containers or measure(element) <= budget: return
        # Pandoc renders a newly stacked OMML row as a one-column TeX array.
        # Its two outer arraycolsep spaces occupy real width. Reserve them
        # only when creating that array, never at transparent nesting levels.
        row_budget=max(45,budget-array_padding_pt)
        segments=segments_of(element,row_budget)
        rows = []; row = []; used = 0
        for segment in segments:
            size = sum(measure(t) for t in segment)
            if row and used+size > row_budget:
                rows.append(row); row=[]; used=0
            row.extend(segment); used+=size
        if row: rows.append(row)
        if len(rows) < 2: return
        old = etree.tostring(element, encoding="unicode")
        for child in list(element): element.remove(child)
        array = OxmlElement("m:eqArr")
        # Generated continuation rows form one mathematical object. Its
        # surrounding text baseline must follow the object's centre, rather
        # than the first row. ISO 29500 baseJc defines this relationship;
        # choosing top also offsets numbers when an importer uses that base.
        props = OxmlElement("m:eqArrPr"); jc = OxmlElement("m:baseJc"); jc.set(M+"val", "center"); props.append(jc); array.append(props)
        for row in rows:
            entry = OxmlElement("m:e")
            first = row[0].findtext(M+"t", "") if row[0].tag == M+"r" else ""
            if re.match(r"^[=<>≤≥+−×∧∨]",first):
                # Cloud probe: lit/nor still produce a missing-operand marker
                # in LibreOffice 26.8. A borderless math box groups the single
                # continuation operator while retaining an editable symbol.
                operator = deepcopy(row[0]); operator.find(M+"t").text = first[0]
                box=OxmlElement("m:box"); argument=OxmlElement("m:e")
                argument.append(operator); box.append(argument)
                if len(first)>1:
                    row[0].find(M+"t").text=first[1:]; row.insert(0,box)
                else: row[0]=box
            for child in row: entry.append(child)
            array.append(entry)
        element.append(array)
        changes.append({"path": path, "before": old, "after": etree.tostring(element, encoding="unicode"), "rows": len(rows),"array_padding_pt":array_padding_pt})
    visit(root, [], width_pt)
    recovered = restore(root, changes)
    if tree(recovered) != tree(before): raise StudioError("MATH_LAYOUT_NOT_REVERSIBLE")
    return changes
