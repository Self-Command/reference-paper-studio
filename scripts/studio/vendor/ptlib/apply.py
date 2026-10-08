"""Apply a profile to a document that already has content.

The three jobs here, in the order they have to happen:

1. Install styles (styles.install_profile) -- done by the caller.
2. Point each paragraph at the right style *and remove the direct formatting
   that would otherwise override it*. This second half is what people miss:
   in Word's cascade, direct run formatting beats the style, so a document
   full of hand-set 宋体/小四 runs ignores a perfectly good style definition.
3. Fix the objects styles can't reach: tables, section geometry, captions.
"""

from __future__ import annotations

import re

from .ooxml import (NS, drop_child, get_child, get_or_add, local, make, onoff,
                    qn, set_border, set_child, set_fonts, set_justify,
                    set_size, set_spacing)
from .profile import ROLE_STYLES
from .units import cm_to_twips, inch_to_twips, page_size, pt_to_twips

# Run properties that a style should be allowed to decide. Anything in here is
# stripped from runs so the style actually wins.
CONFLICTING_RPR = {
    "rFonts", "sz", "szCs", "color", "highlight", "spacing", "position",
    "shd", "u", "caps", "smallCaps", "outline", "shadow", "emboss", "imprint",
    "kern", "w", "bdr", "effect",
}
# Emphasis that is genuinely part of the author's meaning, not formatting noise.
MEANINGFUL_RPR = {"b", "bCs", "i", "iCs", "strike", "dstrike", "vertAlign",
                  "rStyle", "lang", "noProof", "em", "rtl", "cs"}

# Paragraph properties a style should decide. sectPr and numPr are load-bearing
# structure, never formatting, so they always survive.
CONFLICTING_PPR = {
    "spacing", "ind", "jc", "keepNext", "keepLines", "pageBreakBefore",
    "widowControl", "outlineLvl", "snapToGrid", "contextualSpacing", "shd",
    "pBdr", "textAlignment", "kinsoku", "wordWrap", "overflowPunct",
    "autoSpaceDE", "autoSpaceDN",
}
PROTECTED_PPR = {"sectPr", "numPr", "rPr", "framePr", "tabs"}


def strip_direct_formatting(para, *, keep_emphasis: bool, drop_para_props=True):
    """Remove formatting that would shadow the paragraph's style."""
    changed = 0
    for run in para._p.findall(qn("w:r")):
        rpr = run.find(qn("w:rPr"))
        if rpr is None:
            continue
        for child in list(rpr):
            name = local(child)
            if name in CONFLICTING_RPR:
                rpr.remove(child)
                changed += 1
            elif not keep_emphasis and name in MEANINGFUL_RPR - {"rStyle", "vertAlign", "lang"}:
                rpr.remove(child)
                changed += 1
        if len(rpr) == 0:
            run.remove(rpr)

    if drop_para_props:
        ppr = para._p.find(qn("w:pPr"))
        if ppr is not None:
            for child in list(ppr):
                name = local(child)
                if name in CONFLICTING_PPR and name not in PROTECTED_PPR:
                    ppr.remove(child)
                    changed += 1
            # Paragraph-mark run properties carry a second copy of the font.
            mark = ppr.find(qn("w:rPr"))
            if mark is not None:
                for child in list(mark):
                    if local(child) in CONFLICTING_RPR:
                        mark.remove(child)
                        changed += 1
                if len(mark) == 0:
                    ppr.remove(mark)
    return changed


def set_paragraph_style(para, role: str):
    set_paragraph_style_el(para._p, role)


def apply_roles(doc, items, profile, *, min_confidence=0.0):
    """Point paragraphs at their styles. Returns a per-role change count."""
    from collections import Counter
    applied = Counter()
    for it in items:
        if it.role == "_empty":
            # Blank spacer paragraphs still carry runs with hard-set fonts and
            # sizes. Normalise them to Body so they can't reintroduce a stray
            # face, and so their height follows the profile's line spacing.
            strip_direct_formatting(it.para, keep_emphasis=False)
            set_paragraph_style(it.para, "Body")
            continue
        if it.confidence < min_confidence and it.role != "Body":
            continue
        role = it.role if profile.has(it.role) or it.role == "Body" else "Body"
        # Headings and captions get a clean slate; body text keeps its
        # bold/italic emphasis because that carries meaning.
        keep = role in ("Body", "BodyFirst", "Abstract", "Quote", "Reference",
                        "TableText", "ListBullet", "ListNumber")
        strip_direct_formatting(it.para, keep_emphasis=keep)
        set_paragraph_style(it.para, role)
        applied[role] += 1
    return dict(applied)


def remove_blank_paragraphs(doc, items) -> int:
    """Delete paragraphs used purely as vertical whitespace.

    Destructive, so it is opt-in. A blank paragraph that carries a section
    break or an anchored drawing is load-bearing and always kept.
    """
    removed = 0
    for it in items:
        if it.role != "_empty":
            continue
        p = it.para._p
        ppr = p.find(qn("w:pPr"))
        if ppr is not None and ppr.find(qn("w:sectPr")) is not None:
            continue
        if p.findall(".//" + qn("w:drawing")) or p.findall(".//" + qn("w:pict")):
            continue
        if p.findall(".//" + qn("w:bookmarkStart")):
            continue
        parent = p.getparent()
        if parent is not None:
            parent.remove(p)
            removed += 1
    return removed


# --- table of contents ------------------------------------------------------

RE_TOC_HEADING = re.compile(r"^\s*(目\s*录|contents|table\s+of\s+contents)\s*$",
                            re.I)


def insert_toc(doc, profile, items, *, levels=3):
    """Insert a TOC *field*, not a rendered list.

    Page numbers are Word's job -- it recomputes them on open (w:dirty) and on
    F9. Writing a literal list of headings and numbers, as template-based tools
    tend to, produces something that is wrong the moment anything reflows.

    Returns "inserted", "existing", or None.
    """
    body = doc.element.body

    # Already has one? Leave it alone; it will refresh itself.
    for instr in body.findall(".//" + qn("w:instrText")):
        if "TOC" in (instr.text or ""):
            return "existing"

    live = [i for i in items if i.role != "_empty"]
    anchor = None      # insert before this element
    heading_p = None   # an existing 目录/Contents heading to reuse

    for it in live:
        if RE_TOC_HEADING.match(it.text):
            heading_p = it.para._p
            break

    if heading_p is not None:
        anchor = heading_p.getnext()
    else:
        # Otherwise: just before the first real chapter heading, which puts it
        # after the title block and abstract without having to model them.
        for it in live:
            if it.is_heading and it.level == 1:
                anchor = it.para._p
                break
    if anchor is None:
        return None

    added = []
    if heading_p is None:
        role = "TOCHeading" if profile.has("TOCHeading") else "Heading1"
        h = make("w:p")
        ppr = make("w:pPr")
        set_child(ppr, "pStyle", {"w:val": ROLE_STYLES[role][0]})
        h.append(ppr)
        r = make("w:r")
        t = make("w:t")
        t.text = (profile.captions or {}).get("toc_title") or (
            "目录" if profile.lang == "zh" else "Contents")
        r.append(t)
        h.append(r)
        added.append(h)
    else:
        set_paragraph_style_el(heading_p,
                               "TOCHeading" if profile.has("TOCHeading")
                               else "Heading1")

    added.append(_toc_field_paragraph(levels, profile))
    for el in added:
        anchor.addprevious(el)
    return "inserted"


def _toc_field_paragraph(levels, profile):
    r"""One paragraph holding a TOC field.

    \o "1-N"  build from outline levels 1..N   (this is why outlineLvl matters)
    \h        make the entries hyperlinks
    \z        hide tab leaders in web layout
    \u        use the outline level, not a TOC-entry field
    """
    p = make("w:p")

    def run(*children):
        r = make("w:r")
        for c in children:
            r.append(c)
        p.append(r)

    run(make("w:fldChar", {"w:fldCharType": "begin", "w:dirty": "1"}))
    instr = make("w:instrText")
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = f' TOC \\o "1-{levels}" \\h \\z \\u '
    run(instr)
    run(make("w:fldChar", {"w:fldCharType": "separate"}))
    placeholder = make("w:t")
    placeholder.text = ("请右键“更新域”生成目录" if profile.lang == "zh"
                        else "Right-click and Update Field to build the TOC")
    run(placeholder)
    run(make("w:fldChar", {"w:fldCharType": "end"}))
    return p


def set_paragraph_style_el(p_el, role: str):
    ppr = p_el.find(qn("w:pPr"))
    if ppr is None:
        ppr = make("w:pPr")
        p_el.insert(0, ppr)
    set_child(ppr, "pStyle", {"w:val": ROLE_STYLES[role][0]})


# --- page setup -------------------------------------------------------------

def setup_page(doc, profile):
    page = profile.page
    if not page:
        return 0
    touched = 0
    for section in doc.sections:
        sect = section._sectPr
        _apply_sectpr(sect, page)
        touched += 1
    return touched


def _apply_sectpr(sect, page):
    if page.get("size"):
        w, h = page_size(page["size"], page.get("landscape", False))
        set_child(sect, "pgSz", {
            "w:w": w, "w:h": h,
            **({"w:orient": "landscape"} if page.get("landscape") else {}),
        })

    margins = page.get("margin_cm") or page.get("margin_in")
    conv = cm_to_twips if page.get("margin_cm") else inch_to_twips
    if margins:
        attrs = {
            "w:top": conv(margins["top"]),
            "w:bottom": conv(margins["bottom"]),
            "w:left": conv(margins["left"]),
            "w:right": conv(margins["right"]),
            "w:header": cm_to_twips(page.get("header_distance_cm", 1.5)),
            "w:footer": cm_to_twips(page.get("footer_distance_cm", 1.75)),
            "w:gutter": cm_to_twips(page.get("gutter_cm", 0)),
        }
        set_child(sect, "pgMar", attrs)

    cols = page.get("columns", 1)
    if cols and cols > 1:
        set_child(sect, "cols", {
            "w:num": cols, "w:space": cm_to_twips(page.get("column_spacing_cm", 0.6)),
            "w:equalWidth": "1",
        })
    elif cols == 1:
        set_child(sect, "cols", {"w:num": "1", "w:space": "425"})

    if page.get("different_odd_even"):
        set_child(sect, "titlePg", {}) if page.get("different_first_page") else None
    if page.get("different_first_page"):
        set_child(sect, "titlePg", {})

    grid = page.get("doc_grid")
    if grid is not None:
        # Chinese templates often ship a "lines per page" grid. Unless the
        # profile asks for one, switch it off: with a grid active Word ignores
        # exact line spacing and re-spaces CJK text to fit the grid.
        if grid in (False, "none", "off"):
            set_child(sect, "docGrid", {"w:type": "default", "w:linePitch": "312"})
        elif grid == "lines":
            lines = page.get("lines_per_page", 44)
            # Whichever margin spelling the profile used -- the loader
            # guarantees only one survives, so `conv` matches `margins`.
            edges = margins or {}
            set_child(sect, "docGrid", {
                "w:type": "lines", "w:linePitch": str(int(round(
                    (page_size(page.get("size", "a4"))[1]
                     - conv(edges.get("top", 2.54 if conv is cm_to_twips else 1))
                     - conv(edges.get("bottom", 2.54 if conv is cm_to_twips else 1)))
                    / lines))),
            })


def set_different_odd_even(doc, enabled: bool):
    """This one lives in settings.xml, not in any section."""
    settings = doc.settings.element
    existing = settings.find(qn("w:evenAndOddHeaders"))
    if enabled and existing is None:
        settings.append(make("w:evenAndOddHeaders"))
        return True
    if not enabled and existing is not None:
        settings.remove(existing)
        return True
    return False


# --- tables -----------------------------------------------------------------

def format_tables(doc, profile):
    spec = profile.tables or {}
    if not spec:
        return 0
    style = spec.get("style", "three-line")
    count = 0
    for table in doc.tables:
        if style in ("three-line", "booktabs", "三线表"):
            _three_line(table, spec, profile)
        elif style == "grid":
            _grid(table, spec)
        _table_common(table, spec, profile)
        count += 1
    return count


def _tbl_pr(table):
    return get_or_add(table._tbl, "tblPr")


def _three_line(table, spec, profile):
    """The academic default: a heavy rule above and below, a light rule under
    the header, and nothing else. No vertical rules at all -- this is the one
    table convention shared by GB/T, booktabs, IEEE and APA."""
    top = spec.get("top_rule_pt", 1.5)
    bottom = spec.get("bottom_rule_pt", 1.5)
    mid = spec.get("header_rule_pt", 0.75)
    header_rows = int(spec.get("header_rows", 1))

    tbl_pr = _tbl_pr(table)
    drop_child(tbl_pr, "tblBorders")
    borders = get_or_add(tbl_pr, "tblBorders")
    for edge, size in (("top", top), ("bottom", bottom)):
        set_child(borders, edge, {"w:val": "single", "w:sz": int(round(size * 8)),
                                  "w:space": "0", "w:color": "000000"})
    for edge in ("left", "right", "insideH", "insideV"):
        set_child(borders, edge, {"w:val": "none", "w:sz": "0",
                                  "w:space": "0", "w:color": "auto"})

    rows = table.rows
    for r_idx, row in enumerate(rows):
        for cell in row.cells:
            tc_pr = get_or_add(cell._tc, "tcPr")
            drop_child(tc_pr, "tcBorders")
            tb = get_or_add(tc_pr, "tcBorders")
            for edge in ("left", "right", "insideH", "insideV"):
                set_child(tb, edge, {"w:val": "none", "w:sz": "0",
                                     "w:space": "0", "w:color": "auto"})
            set_child(tb, "top", {
                "w:val": "single" if r_idx == 0 else "none",
                "w:sz": int(round(top * 8)) if r_idx == 0 else 0,
                "w:space": "0", "w:color": "000000" if r_idx == 0 else "auto"})
            if r_idx == header_rows - 1 and len(rows) > header_rows:
                edge_sz, edge_val = int(round(mid * 8)), "single"
            elif r_idx == len(rows) - 1:
                edge_sz, edge_val = int(round(bottom * 8)), "single"
            else:
                edge_sz, edge_val = 0, "none"
            set_child(tb, "bottom", {"w:val": edge_val, "w:sz": edge_sz,
                                     "w:space": "0",
                                     "w:color": "000000" if edge_val == "single" else "auto"})

    # Repeat the header on every page the table spills onto.
    for r_idx in range(min(header_rows, len(rows))):
        tr_pr = get_or_add(rows[r_idx]._tr, "trPr")
        set_child(tr_pr, "tblHeader", {})
        if spec.get("header_bold"):
            for cell in rows[r_idx].cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.bold = True


def _grid(table, spec):
    size = spec.get("rule_pt", 0.5)
    borders = get_or_add(_tbl_pr(table), "tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        set_child(borders, edge, {"w:val": "single", "w:sz": int(round(size * 8)),
                                  "w:space": "0", "w:color": "000000"})


def _table_common(table, spec, profile):
    tbl_pr = _tbl_pr(table)
    set_child(tbl_pr, "jc", {"w:val": spec.get("align", "center")})
    if spec.get("width_pct"):
        set_child(tbl_pr, "tblW", {"w:w": int(spec["width_pct"] * 50),
                                   "w:type": "pct"})
    if spec.get("autofit") is False:
        set_child(tbl_pr, "tblLayout", {"w:type": "fixed"})

    margins = spec.get("cell_margin_pt")
    if margins:
        cm = get_or_add(tbl_pr, "tblCellMar")
        for edge in ("top", "left", "bottom", "right"):
            set_child(cm, edge, {"w:w": pt_to_twips(margins), "w:type": "dxa"})

    text = spec.get("text") or {}
    role = "TableText" if profile.has("TableText") else None
    for row in table.rows:
        for cell in row.cells:
            valign = spec.get("valign", "center")
            set_child(get_or_add(cell._tc, "tcPr"), "vAlign", {"w:val": valign})
            for para in cell.paragraphs:
                if role:
                    strip_direct_formatting(para, keep_emphasis=True)
                    set_paragraph_style(para, role)
                elif text:
                    ppr = get_or_add(para._p, "pPr")
                    set_justify(ppr, text.get("justify", "center"))
                    drop_child(ppr, "ind")
                    for run in para.runs:
                        rpr = get_or_add(run._r, "rPr")
                        set_fonts(rpr, latin=text.get("latin_font"),
                                  cjk=text.get("cjk_font"))
                        if text.get("size_pt"):
                            set_size(rpr, text["size_pt"])
