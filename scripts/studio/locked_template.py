"""Versioned mother documents and a content-only Word writer. Actions only."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import json
import os
import re
from lxml import etree
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Twips, RGBColor
from docx.enum.text import WD_LINE_SPACING
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from .runtime import require_actions, StudioError, digest, write_json
from .docx_layout import W, M, section_break, is_equation_table
from .vendor.ptlib.apply import _apply_sectpr, _three_line
from .vendor.ptlib.ooxml import set_child, set_fonts

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "assets/templates/reference-journal-v1.json"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
ROLES = ("Body", "Title", "Author", "Abstract", "Keywords", "Caption", "TableText", "Equation", "Marker", "Heading1", "Heading2", "Heading3", "Heading4", "List")


def policy():
    require_actions()
    return json.loads(POLICY.read_text(encoding="utf-8"))


def resolve_template(request):
    require_actions()
    forbidden = {"profile", "fonts", "font", "font_size", "body_size_pt", "page", "margins", "columns", "sections", "template_path", "styles", "layout"}
    extra = forbidden.intersection(request)
    if extra: raise StudioError("TEMPLATE_OVERRIDE_FORBIDDEN: " + ", ".join(sorted(extra)))
    p = policy()
    if request.get("template_id") != p["id"] or request.get("template_version") != p["version"]:
        raise StudioError("UNKNOWN_TEMPLATE_VERSION: require reference-journal-v1 version 1")
    variant = request.get("template_variant", "front")
    if variant not in ("front", "end"): raise StudioError("UNKNOWN_TEMPLATE_VARIANT")
    directory = Path(os.environ.get("RPS_TEMPLATE_ROOT", ROOT/"assets/templates/v1"))
    manifest = json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    if manifest["policy_sha256"] != digest(POLICY): raise StudioError("TEMPLATE_POLICY_FINGERPRINT_MISMATCH")
    path = directory/manifest["variants"][variant]["file"]
    if digest(path) != manifest["variants"][variant]["sha256"]: raise StudioError("TEMPLATE_FINGERPRINT_MISMATCH")
    p["english_abstract_position"] = variant
    p["equation_numbering"] = "sequential" if request.get("document_kind") == "paper" else "preserve"
    return path, p, {"id": p["id"], "version": p["version"], "variant": variant, "sha256": digest(path), "policy_sha256": digest(POLICY)}


def column_width(p):
    margins = p["page"]["margin_cm"]
    return round((21-margins["left"]-margins["right"]-p["page"]["column_spacing_cm"])/2*1440/2.54)


def pstyle(element, role):
    old = element.find(W+"pPr")
    numbering = deepcopy(old.find(W+"numPr")) if old is not None and old.find(W+"numPr") is not None else None
    if old is not None: element.remove(old)
    props = OxmlElement("w:pPr"); element.insert(0, props)
    set_child(props, "pStyle", {"w:val": "RPS"+role})
    if numbering is not None: props.append(numbering)


def paragraph(text, role):
    element = OxmlElement("w:p"); pstyle(element, role)
    run = OxmlElement("w:r"); node = OxmlElement("w:t"); node.text = text
    run.append(node); element.append(run)
    return element


def create_templates(directory):
    """Create release assets once; never build a mother from a manuscript."""
    require_actions()
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    p = policy(); variants = {}
    for variant in ("front", "end"):
        doc = Document(); body = doc._element.body
        for item in list(body):
            if item.tag != W+"sectPr": body.remove(item)
        for role in ROLES:
            style = doc.styles.add_style("RPS"+role, 1); style.base_style = doc.styles["Normal"]
            style.font.name = p["fonts"]["latin"]
            style.font.size = Pt(16 if role == "Title" else 12 if role == "Heading1" else 1 if role == "Marker" else 10)
            style.font.bold = role == "Title" or role.startswith("Heading")
            style.font.color.rgb = RGBColor(0, 0, 0)
            set_fonts(style.element.get_or_add_rPr(), latin=p["fonts"]["latin"], cjk=p["fonts"]["cjk"])
            fmt = style.paragraph_format
            fmt.space_before = Pt(6 if role.startswith("Heading") else 0)
            fmt.space_after = Pt(0 if role == "Marker" else 2 if role == "TableText" else 3)
            fmt.line_spacing = Pt(1 if role == "Marker" else 24 if role == "Title" else 12 if role == "TableText" else 14)
            fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY if role == "Marker" else WD_LINE_SPACING.AT_LEAST
            fmt.keep_with_next = role.startswith("Heading"); fmt.keep_together = False
            fmt.widow_control = True; fmt.page_break_before = False
            fmt.first_line_indent = Pt(20 if role == "Body" else 0)
            fmt.left_indent = Pt(0); fmt.right_indent = Pt(0)
            fmt.alignment = 1 if role in ("Title", "Author", "Caption") else 3 if role in ("Body", "Abstract") else 0
        normal = doc.styles["Normal"]; normal.font.name = p["fonts"]["latin"]; normal.font.size = Pt(10)
        set_fonts(normal.element.get_or_add_rPr(), latin=p["fonts"]["latin"], cjk=p["fonts"]["cjk"])
        settings = doc.settings.element
        math = OxmlElement("m:mathPr"); font = OxmlElement("m:mathFont"); font.set(qn("m:val"), p["fonts"]["math"]); math.append(font); settings.append(math)
        def metadata(suffix):
            for key, role in (("title", "Title"), ("authors", "Author"), ("affiliation", "Author"), ("abstract", "Abstract"), ("keywords", "Keywords")):
                body.insert(len(body)-1, paragraph("{{"+key+"_"+suffix+"}}", role))
        metadata("zh")
        if variant == "front": metadata("en")
        body.insert(len(body)-1, section_break(1, p))
        body.insert(len(body)-1, paragraph("{{RPS_BODY}}", "Body"))
        if variant == "end": body.insert(len(body)-1, section_break(2, p)); metadata("en")
        final = body.find(W+"sectPr")
        _apply_sectpr(final, {**p["page"], "columns": 2 if variant == "front" else 1, "doc_grid": False})
        set_child(final, "type", {"w:val": "continuous"})
        path = directory/("master-"+variant+".docx"); doc.save(path)
        variants[variant] = {"file": path.name, "sha256": digest(path)}
    write_json(directory/"manifest.json", {"id": p["id"], "version": p["version"], "policy_sha256": digest(POLICY), "variants": variants})


def clean_content(element, p):
    """Input cannot carry paragraph geometry or Word style definitions."""
    mapping = {"Title": "Heading1", "BodyText": "Body", "FirstParagraph": "Body", "Compact": "Body", "Caption": "Caption", "ImageCaption": "Caption", "TableCaption": "Caption"}
    for par in element.iter(W+"p"):
        old = par.find(W+"pPr/"+W+"pStyle")
        identifier = old.get(W+"val", "BodyText") if old is not None else "BodyText"
        role = identifier if identifier in {"Heading1", "Heading2", "Heading3", "Heading4"} else mapping.get(identifier, "Body")
        pstyle(par, role)
    for run in element.iter(W+"r"):
        props = run.find(W+"rPr")
        if props is not None:
            for child in list(props):
                if child.tag not in {W+"b", W+"i", W+"vertAlign"}: props.remove(child)
    for br in list(element.iter(W+"br")):
        if br.get(W+"type") in ("page", "column"): br.getparent().remove(br)
    for run in element.iter(M+"r"):
        props = run.find(W+"rPr")
        if props is not None: run.remove(props)
        props = OxmlElement("w:rPr"); run.append(props)
        set_fonts(props, latin=p["fonts"]["math"], cjk=p["fonts"]["cjk"])
        set_child(props, "sz", {"w:val": "20"})
    return element


def check_contract(path, p):
    require_actions()
    doc = Document(path)
    columns = [int(s._sectPr.find(W+"cols").get(W+"num", "1")) for s in doc.sections]
    expected = [1, 2] if p["english_abstract_position"] == "front" else [1, 2, 1]
    if columns != expected: raise StudioError("TEMPLATE_SECTIONS_CHANGED: "+str(columns))
    active = False; bookmark = None
    for item in doc._element.body:
        if item.tag == W+"bookmarkStart" and item.get(W+"name") == "RPS_BODY":
            active = True; bookmark = item.get(W+"id"); continue
        if item.tag == W+"bookmarkEnd" and item.get(W+"id") == bookmark: active = False
        if active and list(item.iter(W+"sectPr")): raise StudioError("BODY_SECTION_FORBIDDEN")
    return {"section_columns": columns, "body_columns": 2, "body_section_changes": 0, "content_layout_overrides": False}
