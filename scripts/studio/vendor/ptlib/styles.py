"""Write profile roles into the document's styles.xml.

Restyling through *styles* rather than through direct run formatting is the
whole trick. A style edit propagates to every paragraph that uses it, survives
the user's later edits, and keeps the file small. Direct formatting does none
of those things -- and it wins over styles in Word's cascade, so it also has to
be stripped (see apply.strip_direct_formatting).
"""

from __future__ import annotations

from lxml import etree

from .ooxml import (drop_child, get_child, get_or_add, make, onoff, qn,
                    set_border, set_child, set_fonts, set_indent, set_justify,
                    set_size, set_spacing)
from .profile import ROLE_STYLES
from .units import line_spacing


def _styles_root(doc):
    return doc.styles.element


def find_style(doc, style_id: str):
    for st in _styles_root(doc).findall(qn("w:style")):
        if st.get(qn("w:styleId")) == style_id:
            return st
    return None


def ensure_style(doc, style_id: str, name: str, stype: str = "paragraph"):
    """Return the w:style element, creating a minimal one if absent."""
    st = find_style(doc, style_id)
    if st is not None:
        return st
    st = make("w:style", {"w:type": stype, "w:styleId": style_id})
    set_child(st, "name", {"w:val": name})
    set_child(st, "qFormat", {})
    _styles_root(doc).append(st)
    return st


def apply_run_props(st, props: dict):
    """Write the run half of a property dict. Shared with linked char styles,
    which may only carry w:rPr -- a w:pPr inside a character style is invalid."""
    rpr = get_or_add(st, "rPr")
    set_fonts(rpr,
              latin=props.get("latin_font"),
              cjk=props.get("cjk_font"),
              cs=props.get("cs_font") or props.get("latin_font"),
              hint=props.get("font_hint"))
    if props.get("size_pt") is not None:
        set_size(rpr, props["size_pt"])
    for key, tag in (("bold", "b"), ("italic", "i"),
                     ("all_caps", "caps"), ("small_caps", "smallCaps")):
        if key in props:
            onoff(rpr, tag, props[key])
            if key == "bold":
                onoff(rpr, "bCs", props[key])
            if key == "italic":
                onoff(rpr, "iCs", props[key])
    if props.get("underline"):
        set_child(rpr, "u", {"w:val": "single"})
    if props.get("color"):
        set_child(rpr, "color", {"w:val": str(props["color"]).lstrip("#")})
    if props.get("char_spacing_pt") is not None:
        # w:spacing inside rPr is character tracking, in twentieths of a point.
        set_child(rpr, "spacing",
                  {"w:val": str(int(round(props["char_spacing_pt"] * 20)))})
    return rpr


def sync_linked_char_style(doc, st, props: dict):
    """Give a paragraph style's linked character style the same run properties.

    Word's built-in headings ship as a linked pair -- Heading1 plus a hidden
    Heading1Char that still points at the theme font. Restyling only the
    paragraph half leaves any run carrying rStyle="Heading1Char" resolving to
    the theme, which is the same drift the explicit fonts were meant to stop.
    """
    link = get_child(st, "link")
    if link is None:
        return None
    target = find_style(doc, link.get(qn("w:val")) or "")
    if target is None or target.get(qn("w:type")) != "character":
        return None
    apply_run_props(target, props)
    return target


def apply_props(st, props: dict, *, doc=None):
    """Write one resolved property dict onto a w:style element."""
    if props.get("based_on"):
        base_id = ROLE_STYLES.get(props["based_on"], (props["based_on"],))[0]
        set_child(st, "basedOn", {"w:val": base_id})
    if props.get("next_style"):
        nxt = ROLE_STYLES.get(props["next_style"], (props["next_style"],))[0]
        set_child(st, "next", {"w:val": nxt})

    apply_run_props(st, props)
    if doc is not None:
        sync_linked_char_style(doc, st, props)
    # --- paragraph properties ---
    ppr = get_or_add(st, "pPr")

    if props.get("line_rule") or props.get("line_multiple") is not None:
        rule = props.get("line_rule", "auto")
        line, lr = line_spacing(rule,
                                multiple=props.get("line_multiple"),
                                pt=props.get("line_pt"))
        set_spacing(ppr, line=line, line_rule=lr)
        if lr in ("exact", "atLeast"):
            # An exact line height is ignored while the paragraph is snapped to
            # the document grid, so turn the grid off for this style.
            set_spacing(ppr, snap_to_grid=False)

    set_spacing(ppr,
                before_pt=props.get("space_before_pt"),
                after_pt=props.get("space_after_pt"),
                before_lines=props.get("space_before_lines"),
                after_lines=props.get("space_after_lines"))
    if props.get("snap_to_grid") is not None:
        set_spacing(ppr, snap_to_grid=props["snap_to_grid"])

    set_indent(ppr,
               first_line_chars=props.get("first_line_chars"),
               first_line_pt=props.get("first_line_pt"),
               hanging_chars=props.get("hanging_chars"),
               hanging_pt=props.get("hanging_pt"),
               left_chars=props.get("left_chars"),
               left_pt=props.get("left_pt"),
               right_pt=props.get("right_pt"))

    set_justify(ppr, props.get("justify"))

    for key, tag in (("page_break_before", "pageBreakBefore"),
                     ("keep_with_next", "keepNext"),
                     ("keep_lines", "keepLines"),
                     ("widow_control", "widowControl"),
                     ("contextual_spacing", "contextualSpacing")):
        if key in props:
            onoff(ppr, tag, props[key])

    if props.get("outline_level") is not None:
        # Without outlineLvl a heading is invisible to the TOC field and to
        # Word's navigation pane, however large and bold it looks.
        set_child(ppr, "outlineLvl", {"w:val": str(props["outline_level"])})

    if props.get("border_bottom_pt"):
        set_border(ppr, "bottom", size_pt=props["border_bottom_pt"], space=1)
    if props.get("border_top_pt"):
        set_border(ppr, "top", size_pt=props["border_top_pt"], space=1)

    # Drop empty holders so the XML stays clean.
    for holder in ("rPr", "pPr"):
        node = get_child(st, holder)
        if node is not None and len(node) == 0 and not node.attrib:
            st.remove(node)


def install_profile(doc, profile) -> list[str]:
    """Create/overwrite every style the profile declares. Returns role names."""
    written = []
    # Body first: everything else is based on it, and Word resolves basedOn
    # lazily, but writing in dependency order keeps the file readable.
    roles = ["Body"] + [r for r in ROLE_STYLES if r != "Body"]
    for role in roles:
        if role != "Body" and role not in profile.styles:
            continue
        style_id, name, stype = ROLE_STYLES[role]
        st = ensure_style(doc, style_id, name, stype)
        props = profile.resolved(role)
        if role.startswith("Heading") and props.get("outline_level") is None:
            props["outline_level"] = int(role[-1]) - 1
        if role != "Body" and not props.get("based_on"):
            props["based_on"] = "Body"
        apply_props(st, props, doc=doc)
        written.append(role)
    _set_doc_defaults(doc, profile)
    _set_theme_fonts(doc, profile)
    return written


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _set_theme_fonts(doc, profile):
    """Repoint the theme's major/minor faces at the profile's fonts.

    Belt and braces for everything this engine never touches: latent built-in
    styles (Heading 5-9, the table gallery), and anything the user applies
    later. They all reference the theme rather than a concrete typeface, so a
    theme still saying "Calibri" is a standing invitation for the document to
    drift back. Rewriting it once fixes all of them at the source.
    """
    body = profile.resolved("Body")
    heading = profile.resolved("Heading1") if profile.has("Heading1") else body

    part = None
    for p in doc.part.package.iter_parts():
        if str(p.partname).endswith("/theme1.xml"):
            part = p
            break
    if part is None:
        return False

    try:
        root = etree.fromstring(part.blob)
    except etree.XMLSyntaxError:
        return False

    scheme = root.find(f".//{{{A_NS}}}fontScheme")
    if scheme is None:
        return False

    for tag, props in ((f"{{{A_NS}}}majorFont", heading),
                       (f"{{{A_NS}}}minorFont", body)):
        node = scheme.find(tag)
        if node is None:
            continue
        for child, key in ((f"{{{A_NS}}}latin", "latin_font"),
                           (f"{{{A_NS}}}ea", "cjk_font"),
                           (f"{{{A_NS}}}cs", "cs_font")):
            face = props.get(key)
            el = node.find(child)
            if el is not None and face:
                el.set("typeface", face)

    part._blob = etree.tostring(root, xml_declaration=True,
                                encoding="UTF-8", standalone=True)
    return True


def _set_doc_defaults(doc, profile):
    """Also write the profile's body font into w:docDefaults.

    Word falls back to docDefaults (and then to the theme) for anything a style
    leaves unspecified -- including, notably, text inside text boxes, headers
    and newly typed paragraphs. Leaving it at Calibri while every style says
    Times New Roman is why documents drift back to the wrong font.
    """
    props = profile.resolved("Body")
    root = _styles_root(doc)
    dd = get_child(root, "docDefaults")
    if dd is None:
        dd = make("w:docDefaults")
        root.insert(0, dd)
    rpr_default = get_or_add(dd, "rPrDefault")
    rpr = get_or_add(rpr_default, "rPr")
    set_fonts(rpr,
              latin=props.get("latin_font"),
              cjk=props.get("cjk_font"),
              cs=props.get("cs_font") or props.get("latin_font"),
              hint=props.get("font_hint"))
    if props.get("size_pt"):
        set_size(rpr, props["size_pt"])

    # Word's stock pPrDefault carries 1.15 line spacing and 10pt space-after.
    # Every style we write overrides it, but anything we don't touch -- table
    # cells in an untouched table, a text box, the next paragraph the user
    # types -- inherits it and looks nothing like the rest of the document.
    ppr_default = get_child(dd, "pPrDefault")
    if ppr_default is not None:
        ppr = get_child(ppr_default, "pPr")
        if ppr is not None:
            for tag in ("spacing", "ind", "jc"):
                drop_child(ppr, tag)
