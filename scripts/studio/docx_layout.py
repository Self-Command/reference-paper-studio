"""DOCX section routing without applying a body profile to front matter."""
from copy import deepcopy
from pathlib import Path
import re
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm
from lxml import etree
from .runtime import StudioError, require_actions
from .vendor.ptlib.apply import _apply_sectpr, _three_line
from .vendor.ptlib.ooxml import set_child, set_fonts

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def ensure_style(doc, name):
    key = name.replace(" ", "").casefold()
    for style in doc.styles:
        if style.name.replace(" ", "").casefold() == key or style.style_id.casefold() == key:
            return style
    return doc.styles.add_style(name, 1)


def _paragraph(text="", style=None):
    p = OxmlElement("w:p")
    if style:
        ppr = OxmlElement("w:pPr")
        node = OxmlElement("w:pStyle"); node.set(qn("w:val"), style)
        ppr.append(node); p.append(ppr)
    if text:
        r = OxmlElement("w:r"); t = OxmlElement("w:t"); t.text = text
        r.append(t); p.append(r)
    return p


def section_break(columns, profile):
    p = _paragraph()
    ppr = OxmlElement("w:pPr"); sect = OxmlElement("w:sectPr")
    kind = OxmlElement("w:type"); kind.set(qn("w:val"), "continuous"); sect.append(kind)
    _apply_sectpr(sect, {**profile["page"], "columns": columns})
    ppr.append(sect); p.append(ppr)
    return p


def metadata_paragraphs(meta, english=False):
    suffix = "_en" if english else "_zh"
    result = []
    for key, style in [("title", "Title"), ("authors", "Author"), ("affiliation", "Author"), ("abstract", "Abstract"), ("keywords", "Keywords")]:
        value = meta.get(key + suffix, "")
        if isinstance(value, list):
            value = "; ".join(value)
        if value:
            prefix = ("Abstract: " if english else "摘要：") if key == "abstract" else ("Keywords: " if english else "关键词：") if key == "keywords" else ""
            result.append(_paragraph(prefix + value, style))
    return result


def object_math(element):
    return [etree.tostring(m, method="c14n") for m in element.iter(M + "oMath")]


def move_table_captions(doc):
    """Repair only adjacent, identified caption blocks; never infer from all drawings."""
    moved = 0
    for table in doc.tables:
        following = table._tbl.getnext()
        if following is not None and following.tag == qn("w:p"):
            text = "".join(following.itertext())
            # itertext repeats OOXML text in python-docx; use w:t only.
            text = "".join(t.text or "" for t in following.iter(qn("w:t")))
            if re.match(r"^(表\s*\d|Table\s+\d)", text):
                table._tbl.addprevious(following); moved += 1
    return moved


def apply_layout(path, metadata, profile, equations):
    require_actions()
    doc = Document(path)
    before_math = object_math(doc._element)
    body = doc._element.body
    base = doc.sections[0]._sectPr
    _apply_sectpr(base, {**profile["page"], "columns": 2})
    original = [e for e in list(body) if e.tag != qn("w:sectPr")]
    front = metadata_paragraphs(metadata)
    if profile["english_abstract_position"] == "front":
        front += metadata_paragraphs(metadata, True)
    front.append(section_break(1, profile))
    for index, element in enumerate(front):
        body.insert(index, element)
    # Mark the source body for exact XML-based prose and math checks.
    start = OxmlElement("w:bookmarkStart"); start.set(qn("w:id"), "9181"); start.set(qn("w:name"), "RPS_BODY")
    end = OxmlElement("w:bookmarkEnd"); end.set(qn("w:id"), "9181")
    body.insert(len(front), start)
    body.insert(len(front) + 1 + len(original), end)
    if profile["english_abstract_position"] == "end":
        body.insert(len(body)-1, section_break(2, profile))
        for element in metadata_paragraphs(metadata, True):
            body.insert(len(body)-1, element)
        _apply_sectpr(base, {**profile["page"], "columns": 1})
    for name in ("Normal", "Body Text", "First Paragraph", "Abstract", "Keywords", "Author", "Title", "Caption", "Table Caption", "Image Caption"):
        style = ensure_style(doc, name)
        style.font.name = profile["fonts"]["latin"]
        style.font.size = Pt(profile["body_size_pt"] if name != "Title" else 16)
        rpr = style.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None: fonts = OxmlElement("w:rFonts"); rpr.append(fonts)
        fonts.set(qn("w:eastAsia"), profile["fonts"]["cjk"])
        style.paragraph_format.space_after = Pt(3)
        style.paragraph_format.line_spacing = 1.08
    for i in range(1, 5):
        style = ensure_style(doc, f"Heading {i}")
        style.font.name = profile["fonts"]["latin"]
        style.font.size = Pt(12 if i == 1 else 10.5)
        style.font.bold = True
        fonts = style.element.get_or_add_rPr().find(qn("w:rFonts"))
        if fonts is None: fonts = OxmlElement("w:rFonts"); style.element.get_or_add_rPr().append(fonts)
        fonts.set(qn("w:eastAsia"), profile["fonts"]["cjk"])
    displays = []
    for element in original:
        if element.tag == qn("w:p") and list(element.iter(M + "oMathPara")):
            displays.append(element)
    if len(displays) != len(equations):
        raise StudioError(f"FORMULA_CONVERSION_FAILED: expected {len(equations)} OMML displays, got {len(displays)}")
    # Complex model expressions use continuous full-width equation sections.
    # Keep mathematical size/readability; return to the two-column body after each.
    for index, p in enumerate(displays):
        equation = equations[index]
        complex_formula = len(equation["source"]) > 105 or "\\begin" in equation["source"]
        if complex_formula:
            p.addprevious(section_break(2, profile)); p.addnext(section_break(1, profile))
        ppr = p.find(qn("w:pPr"))
        if ppr is None: ppr = OxmlElement("w:pPr"); p.insert(0, ppr)
        tabs = OxmlElement("w:tabs")
        width = 9300 if complex_formula else 4500
        for val, position in [("center", width//2), ("right", width)]:
            tab = OxmlElement("w:tab"); tab.set(qn("w:val"), val); tab.set(qn("w:pos"), str(position)); tabs.append(tab)
        old = ppr.find(qn("w:tabs"))
        if old is not None: ppr.remove(old)
        ordered_tabs = set_child(ppr, "tabs")
        for tab in list(tabs): ordered_tabs.append(tab)
        for math_para in list(p.iter(M + "oMathPara")):
            # Number and equation must share a Word paragraph. Preserve oMath exactly.
            position = p.index(math_para)
            for omath in list(math_para):
                if omath.tag == M + "oMath": p.insert(position, omath); position += 1
            p.remove(math_para)
        leading = OxmlElement("w:r"); leading.append(OxmlElement("w:tab")); p.insert(1, leading)
        number = equation["id"] if profile["equation_numbering"] == "preserve" else str(index+1)
        r = OxmlElement("w:r"); r.append(OxmlElement("w:tab")); t = OxmlElement("w:t"); t.text = f"({number})"; r.append(t); p.append(r)
    moved = move_table_captions(doc)
    for table in doc.tables:
        # Tables are data objects. Wide symbol tables need their own full-width section.
        table._tbl.addprevious(section_break(2, profile))
        table._tbl.addnext(section_break(1, profile))
        _three_line(table, profile["tables"], None)
        # Pandoc can hardcode widths for a full page; recompute for the body column.
        table.autofit = True
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for r in paragraph.runs:
                        r.font.name = profile["fonts"]["latin"]; r.font.size = Pt(9)
                        fonts = r._r.get_or_add_rPr().find(qn("w:rFonts"))
                        if fonts is None: fonts=OxmlElement("w:rFonts"); r._r.get_or_add_rPr().append(fonts)
                        fonts.set(qn("w:eastAsia"), profile["fonts"]["cjk"])
    if before_math != object_math(doc._element):
        raise StudioError("MATH_CHANGED_DURING_LAYOUT")
    doc.save(path)
    return {"table_captions_moved": moved, "native_math_count": len(before_math), "display_count": len(displays)}


def body_only_docx(source, target):
    """Create an audit copy with only the body, excluding generated equation labels."""
    require_actions()
    doc = Document(source)
    body = doc._element.body
    active = False
    for element in list(body):
        if element.tag == qn("w:sectPr"): continue
        if element.tag == qn("w:bookmarkStart") and element.get(qn("w:name")) == "RPS_BODY":
            active=True; body.remove(element); continue
        if element.tag == qn("w:bookmarkEnd") and element.get(qn("w:id")) == "9181":
            active=False; body.remove(element); continue
        if not active:
            body.remove(element); continue
        if list(element.iter(M+"oMath")):
            for r in list(element.findall(qn("w:r"))):
                text="".join(t.text or "" for t in r.iter(qn("w:t")))
                if r.find(qn("w:tab")) is not None and re.fullmatch(r"\([\w.:-]+\)", text): element.remove(r)
    doc.save(target)
