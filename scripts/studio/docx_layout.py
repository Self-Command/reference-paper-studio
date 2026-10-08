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
        if name=="Title": style.font.bold=True
        style.font.color.rgb = RGBColor(0,0,0)
        rpr = style.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None: fonts = OxmlElement("w:rFonts"); rpr.append(fonts)
        fonts.set(qn("w:eastAsia"), profile["fonts"]["cjk"])
        set_fonts(rpr,latin=profile["fonts"]["latin"],cjk=profile["fonts"]["cjk"])
        style.paragraph_format.space_after = Pt(3)
        style.paragraph_format.line_spacing = 1.08
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
    # Complex model expressions use continuous full-width equation sections.
    # Keep mathematical size/readability; return to the two-column body after each.
    for index, p in enumerate(displays):
        equation = equations[index]
        complex_formula = True  # Full-width display region avoids mathematical clipping.
        # Equation tables are explicit layout objects, never data tables.
        table=doc.add_table(rows=1,cols=2)
        props=table._tbl.tblPr
        set_child(props,"tblDescription",{"w:val":"RPS_EQUATION_LAYOUT"})
        set_child(props,"tblLayout",{"w:type":"fixed"})
        margins=profile["page"]["margin_cm"]
        full_width=page_size(profile["page"].get("size","a4"))[0]-cm_to_twips(margins["left"]+margins["right"])
        width=full_width if complex_formula else (full_width-cm_to_twips(profile["page"].get("column_spacing_cm",.6)))//2
        set_child(props,"tblW",{"w:w":str(width),"w:type":"dxa"})
        borders=set_child(props,"tblBorders")
        for edge in ("top","bottom","left","right","insideH","insideV"): set_child(borders,edge,{"w:val":"nil"})
        table.autofit=False
        for cell,column,cell_width in zip(table.rows[0].cells,table.columns,(width-900,900)):
            column.width=Twips(cell_width);cell.width=Twips(cell_width)
            set_child(cell._tc.get_or_add_tcPr(),"vAlign",{"w:val":"center"})
            set_child(cell._tc.get_or_add_tcPr(),"noWrap")
        left=table.cell(0,0)
        for paragraph in list(left._tc.findall(qn("w:p"))): left._tc.remove(paragraph)
        p.addprevious(table._tbl)
        left._tc.append(p)
        # LibreOffice ignores oMathPara inside some table cells. Keep the native
        # oMath unchanged, letting the centered cell paragraph provide layout.
        for wrapper in list(p.findall(M+"oMathPara")):
            position=p.index(wrapper)
            for omath in list(wrapper):
                if omath.tag==M+"oMath": p.insert(position,omath);position+=1
            p.remove(wrapper)
        ppr=p.find(qn("w:pPr"))
        if ppr is None: ppr=OxmlElement("w:pPr");p.insert(0,ppr)
        set_child(ppr,"jc",{"w:val":"center"})
        number = equation["id"] if profile["equation_numbering"] == "preserve" else str(index+1)
        label=table.cell(0,1).paragraphs[0];label.text=f"({number})";label.alignment=2
        label.runs[0].font.size=Pt(profile["body_size_pt"])
        set_fonts(label.runs[0]._r.get_or_add_rPr(),latin=profile["fonts"]["latin"],cjk=profile["fonts"]["cjk"])
        set_child(table.rows[0]._tr.get_or_add_trPr(),"cantSplit")
        if complex_formula:
            table._tbl.addprevious(section_break(2,profile));table._tbl.addnext(section_break(1,profile))
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
        if is_equation_table(element):
            paragraph=element.find(qn("w:tr")).find(qn("w:tc")).find(qn("w:p"))
            element.addprevious(paragraph);body.remove(element);element=paragraph
        if list(element.iter(M+"oMath")):
            for r in list(element.findall(qn("w:r"))):
                text="".join(t.text or "" for t in r.iter(qn("w:t")))
                if r.find(qn("w:tab")) is not None and re.fullmatch(r"\([\w.:-]+\)", text): element.remove(r)
    doc.save(target)


def is_equation_table(element):
    description=element.find(qn("w:tblPr")+"/"+qn("w:tblDescription"))
    return description is not None and description.get(qn("w:val"))=="RPS_EQUATION_LAYOUT"
