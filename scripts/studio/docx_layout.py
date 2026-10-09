"""DOCX section routing without applying a body profile to front matter."""
from copy import deepcopy
from pathlib import Path
import re
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, RGBColor, Twips
from lxml import etree
from .runtime import StudioError, require_actions
from .vendor.ptlib.apply import _apply_sectpr, _three_line
from .vendor.ptlib.ooxml import set_child, set_fonts
from .vendor.ptlib.units import page_size, cm_to_twips

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
    _apply_sectpr(sect, {**profile["page"], "columns": columns, "doc_grid": False})
    # A section marker is structure, not a body-text spacer.  Inheriting
    # Normal's line box adds two visible empty lines around every wide object.
    set_child(ppr, "keepNext", {"w:val": "0"})
    set_child(ppr, "keepLines", {"w:val": "0"})
    set_child(ppr, "snapToGrid", {"w:val": "0"})
    set_child(ppr, "spacing", {"w:before": "0", "w:after": "0", "w:line": "20", "w:lineRule": "exact"})
    set_child(ppr, "rPr").append(OxmlElement("w:sz"))
    ppr.find(qn("w:rPr") + "/" + qn("w:sz")).set(qn("w:val"), "2")
    set_child(ppr, "sectPr").extend(list(sect))
    p.append(ppr)
    return p


def math_width_pt(element, size):
    """Conservative OMML width estimate for routing, not mathematical rewriting.

    Fractions stack, matrices/arrays take their widest row and scripts use
    smaller text.  The rendered cloud proof remains the acceptance authority.
    """
    local = etree.QName(element).localname
    if local.endswith("Pr"):
        return 0
    if local == "t":
        return sum(size * (1.15 if ord(c) > 0x2fff else .28 if c.isspace() else .70) for c in element.text or "")
    children = [c for c in element if not etree.QName(c).localname.endswith("Pr")]
    measured = [(etree.QName(c).localname, math_width_pt(c, size)) for c in children]
    widths = dict(measured)
    values = [width for _,width in measured]
    if local == "f":
        return max(widths.get("num", 0), widths.get("den", 0)) + size * .4
    if local in ("sSub", "sSup", "sSubSup"):
        return widths.get("e", 0) + .75 * max(widths.get("sub", 0), widths.get("sup", 0))
    if local in ("eqArr", "m"):
        return max(values, default=0)
    if local == "mr":
        return sum(values) + max(0, len(children) - 1) * size
    if local == "nary":
        return widths.get("e", 0) + max(size * 1.8, .75 * max(widths.get("sub", 0), widths.get("sup", 0)))
    if local in ("limLow", "limUpp"):
        return max(widths.get("e", 0), .75 * widths.get("lim", 0))
    if local in ("d", "borderBox"):
        return sum(values) + size * 1.3
    return sum(values)


def metadata_paragraphs(meta, english=False):
    suffix = "_en" if english else "_zh"
    result = []
    for key, style in [("title", "Title"), ("authors", "Author"), ("affiliation", "Author"), ("abstract", "Abstract"), ("keywords", "Keywords")]:
        value = meta.get(key + suffix, "")
        if isinstance(value, list):
            value = "; ".join(value)
        if value:
            prefix = ("Abstract: " if english else "摘要：") if key == "abstract" else ("Keywords: " if english else "关键词：") if key == "keywords" else ""
            paragraph=_paragraph(prefix + value, style)
            if key in ("title","authors","affiliation"):
                set_child(paragraph.find(qn("w:pPr")),"jc",{"w:val":"center"})
            result.append(paragraph)
    return result


def object_math(element):
    return [etree.tostring(m, method="c14n") for m in element.iter(M + "oMath")]


def configure_math_font(path, profile):
    require_actions()
    doc=Document(path)
    settings=doc.settings.element
    math=settings.find(M+"mathPr")
    if math is None: math=OxmlElement("m:mathPr"); settings.append(math)
    font=math.find(M+"mathFont")
    if font is None: font=OxmlElement("m:mathFont"); math.insert(0,font)
    font.set(qn("m:val"),profile["fonts"].get("math","Latin Modern Math"))
    for run in doc._element.iter(M+"r"):
        props=run.find(qn("w:rPr"))
        if props is None:
            props=OxmlElement("w:rPr")
            position=1 if run.find(M+"rPr") is not None else 0
            run.insert(position,props)
        set_fonts(props,latin=profile["fonts"].get("math","Latin Modern Math"),cjk=profile["fonts"]["cjk"])
        set_child(props,"sz",{"w:val":str(round(profile["body_size_pt"]*2))})
    doc.save(path)


def move_table_captions(doc):
    """Repair only adjacent, identified caption blocks; never infer from all drawings."""
    moved = 0
    for table in doc.tables:
        if is_equation_table(table._tbl): continue
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
    _apply_sectpr(base, {**profile["page"], "columns": 2, "doc_grid": False})
    # The final body-level sectPr also describes a section's start.  Without
    # w:type its default is nextPage, even when all preceding breaks continue.
    set_child(base, "type", {"w:val": "continuous"})
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
        _apply_sectpr(base, {**profile["page"], "columns": 1, "doc_grid": False})
    for name in ("Normal", "Body Text", "First Paragraph", "Abstract", "Keywords", "Author", "Title", "Caption", "Table Caption", "Image Caption"):
        style = ensure_style(doc, name)
        style.font.name = profile["fonts"]["latin"]
        style.font.size = Pt(profile["body_size_pt"] if name != "Title" else 16)
        if name=="Title": style.font.bold=True
        style.font.color.rgb = RGBColor(0,0,0)
        rpr = style.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None: fonts = OxmlElement("w:rFonts"); rpr.append(fonts)
        fonts.set(qn("w:eastAsia"), profile["fonts"]["cjk"])
        set_fonts(rpr,latin=profile["fonts"]["latin"],cjk=profile["fonts"]["cjk"])
        style.paragraph_format.space_after = Pt(3)
        style.paragraph_format.line_spacing = 1.08
        set_child(style.element.get_or_add_pPr(), "snapToGrid", {"w:val": "0"})
    for i in range(1, 5):
        style = ensure_style(doc, f"Heading {i}")
        style.font.name = profile["fonts"]["latin"]
        style.font.size = Pt(12 if i == 1 else 10.5)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0,0,0)
        fonts = style.element.get_or_add_rPr().find(qn("w:rFonts"))
        if fonts is None: fonts = OxmlElement("w:rFonts"); style.element.get_or_add_rPr().append(fonts)
        fonts.set(qn("w:eastAsia"), profile["fonts"]["cjk"])
        set_fonts(style.element.get_or_add_rPr(),latin=profile["fonts"]["latin"],cjk=profile["fonts"]["cjk"])
    displays = []
    for element in original:
        if element.tag == qn("w:p") and list(element.iter(M + "oMathPara")):
            displays.append(element)
    if len(displays) != len(equations):
        raise StudioError(f"FORMULA_CONVERSION_FAILED: expected {len(equations)} OMML displays, got {len(displays)}")
    # Only expressions that exceed a body column need full-width sections.
    # Short expressions stay with their prose instead of balancing both columns
    # and inserting section markers for every equation.
    equation_columns = []
    for index, p in enumerate(displays):
        equation = equations[index]
        margins=profile["page"]["margin_cm"]
        full_width=page_size(profile["page"].get("size","a4"))[0]-cm_to_twips(margins["left"]+margins["right"])
        column_width=(full_width-cm_to_twips(profile["page"].get("column_spacing_cm", .6)))//2
        estimate=sum(math_width_pt(m, profile["body_size_pt"]) for m in p.iter(M+"oMath"))
        number = equation["id"] if profile["equation_numbering"] == "preserve" else str(index+1)
        label_width=(len(number)+2)*profile["body_size_pt"]*.58+8
        wide=estimate+2*label_width > column_width/20
        width=full_width if wide else column_width
        equation_columns.append({"id":equation["id"], "columns_spanned":2 if wide else 1, "estimated_math_width_pt":round(estimate, 2)})
        if wide:
            p.addprevious(section_break(2,profile));p.addnext(section_break(1,profile))
        # Native inline OMML in a tabbed full-width paragraph avoids the table
        # importer regression. Only the display wrapper changes, never oMath.
        for wrapper in list(p.findall(M+"oMathPara")):
            position=p.index(wrapper)
            for omath in list(wrapper):
                if omath.tag==M+"oMath": p.insert(position,omath);position+=1
            p.remove(wrapper)
        ppr=p.find(qn("w:pPr"))
        if ppr is None: ppr=OxmlElement("w:pPr");p.insert(0,ppr)
        set_child(ppr,"jc",{"w:val":"left"})
        set_child(ppr,"ind",{"w:left":"0","w:right":"0","w:firstLine":"0"})
        tabs=set_child(ppr,"tabs")
        for val,pos in (("center",width//2),("right",width)):
            tab=OxmlElement("w:tab");tab.set(qn("w:val"),val);tab.set(qn("w:pos"),str(pos));tabs.append(tab)
        leading=OxmlElement("w:r");leading.append(OxmlElement("w:tab"));p.insert(1,leading)
        label=OxmlElement("w:r");label.append(OxmlElement("w:tab"));text=OxmlElement("w:t");text.text=f"({number})";label.append(text);p.append(label)
    moved = move_table_captions(doc)
    for table in doc.tables:
        if is_equation_table(table._tbl): continue
        # Tables are data objects. Wide symbol tables need their own full-width section.
        before=table._tbl.getprevious()
        if before is not None and before.tag==qn("w:p") and re.match(r"^(表\s*\d|Table\s+\d)","".join(t.text or "" for t in before.iter(qn("w:t")))):
            before.addprevious(section_break(2, profile))
        else: table._tbl.addprevious(section_break(2, profile))
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
                        set_fonts(r._r.get_or_add_rPr(),latin=profile["fonts"]["latin"],cjk=profile["fonts"]["cjk"])
    for element in original:
        if element.tag==qn("w:p") and list(element.iter(qn("w:drawing"))):
            element.addprevious(section_break(2, profile))
            after=element.getnext()
            if after is not None and after.tag==qn("w:p") and re.match(r"^(图\s*\d|Fig(?:ure)?\.?\s*\d)","".join(t.text or "" for t in after.iter(qn("w:t")))):
                after.addnext(section_break(1, profile))
            else: element.addnext(section_break(1, profile))
    if before_math != object_math(doc._element):
        raise StudioError("MATH_CHANGED_DURING_LAYOUT")
    doc.save(path)
    return {"table_captions_moved": moved, "native_math_count": len(before_math), "display_count": len(displays), "equation_columns":equation_columns}


def body_only_docx(source, target):
    """Create an audit copy with only the body, excluding generated equation labels."""
    require_actions()
    doc = Document(source)
    body = doc._element.body
    active = False
    body_bookmark_id = None
    for element in list(body):
        if element.tag == qn("w:sectPr"): continue
        if element.tag == qn("w:bookmarkStart") and element.get(qn("w:name")) == "RPS_BODY":
            body_bookmark_id = element.get(qn("w:id"))
            active=True; body.remove(element); continue
        if element.tag == qn("w:bookmarkEnd") and body_bookmark_id is not None and element.get(qn("w:id")) == body_bookmark_id:
            active=False; body.remove(element); continue
        if not active:
            body.remove(element); continue
        if is_equation_table(element):
            paragraph=element.find(qn("w:tr")).find(qn("w:tc")).find(qn("w:p"))
            # The single-line generator uses inline OMML and the label in one
            # paragraph to share a baseline. Normalize ONLY this audit copy to
            # the source display wrapper; the mathematical tree stays exact.
            if paragraph.find(M+"oMathPara") is None:
                for math in list(paragraph.findall(M+"oMath")):
                    wrapper=OxmlElement("m:oMathPara");math.addprevious(wrapper);wrapper.append(math)
            element.addprevious(paragraph);body.remove(element);element=paragraph
        if list(element.iter(M+"oMath")):
            for r in list(element.findall(qn("w:r"))):
                text="".join(t.text or "" for t in r.iter(qn("w:t")))
                if r.find(qn("w:tab")) is not None and re.fullmatch(r"\([\w.:-]+\)", text): element.remove(r)
    doc.save(target)


def is_equation_table(element):
    description=element.find(qn("w:tblPr")+"/"+qn("w:tblDescription"))
    return description is not None and description.get(qn("w:val"))=="RPS_EQUATION_LAYOUT"
