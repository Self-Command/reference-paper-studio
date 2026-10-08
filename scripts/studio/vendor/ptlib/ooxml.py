"""Low-level WordprocessingML helpers.

The one rule that matters here: WordprocessingML is a *sequence* schema, not a
bag of attributes. Children of w:pPr, w:rPr, w:sectPr, w:tblPr and friends must
appear in the exact order the schema declares. Word silently tolerates nothing —
an out-of-order child produces "unreadable content" on open. python-docx models
some of these correctly but not all, so every insertion in this module goes
through `set_child`, which knows the orders.
"""

from lxml import etree

from .units import JUSTIFY as JC

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def qn(tag: str) -> str:
    """'w:rFonts' -> '{...}rFonts'"""
    prefix, _, local = tag.partition(":")
    return f"{{{W}}}{local}" if prefix == "w" else tag


def local(el) -> str:
    return etree.QName(el).localname


def make(tag: str, attrs: dict = None):
    node = etree.Element(qn(tag))
    for k, v in (attrs or {}).items():
        node.set(qn(k), str(v))
    return node


# --- Schema child orders (ECMA-376 Part 1, §17) -----------------------------

ORDER = {
    "pPr": [
        "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
        "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
        "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
        "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
        "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
        "suppressOverlap", "jc", "textDirection", "textAlignment",
        "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
        "pPrChange",
    ],
    "rPr": [
        "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps",
        "strike", "dstrike", "outline", "shadow", "emboss", "imprint",
        "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
        "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
        "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
        "eastAsianLayout", "specVanish", "oMath", "rPrChange",
    ],
    "sectPr": [
        "headerReference", "footerReference", "footnotePr", "endnotePr",
        "type", "pgSz", "pgMar", "paperSrc", "pgBorders", "lnNumType",
        "pgNumType", "cols", "formProt", "vAlign", "noEndnote", "titlePg",
        "textDirection", "bidi", "rtlGutter", "docGrid", "printerSettings",
        "sectPrChange",
    ],
    "style": [
        "name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden",
        "uiPriority", "semiHidden", "unhideWhenUsed", "qFormat", "locked",
        "personal", "personalCompose", "personalReply", "rsid", "pPr", "rPr",
        "tblPr", "trPr", "tcPr", "tblStylePr",
    ],
    "tblPr": [
        "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
        "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd",
        "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
        "tblDescription", "tblPrChange",
    ],
    "tcPr": [
        "cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
        "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark",
        "cellIns", "cellDel", "cellMerge", "tcPrChange",
    ],
    "trPr": [
        "cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter",
        "cantSplit", "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden",
    ],
    "pBdr": ["top", "left", "bottom", "right", "between", "bar"],
    "tblBorders": ["top", "start", "left", "bottom", "end", "right",
                   "insideH", "insideV"],
    "tcBorders": ["top", "start", "left", "bottom", "end", "right",
                  "insideH", "insideV", "tl2br", "tr2bl"],
    "tblCellMar": ["top", "start", "left", "bottom", "end", "right"],
    "numPr": ["ilvl", "numId", "numberingChange", "ins"],
}


def set_child(parent, tag: str, attrs: dict = None, *, replace: bool = True):
    """Insert or update a child, honouring the schema's element order."""
    name = tag.split(":")[-1]
    existing = parent.find(qn(f"w:{name}"))
    if existing is not None:
        if not replace:
            return existing
        parent.remove(existing)

    node = make(f"w:{name}", attrs)
    order = ORDER.get(local(parent))
    if order is None or name not in order:
        parent.append(node)
        return node

    idx = order.index(name)
    for child in parent:
        cname = local(child)
        if cname not in order or order.index(cname) > idx:
            child.addprevious(node)
            return node
    parent.append(node)
    return node


def get_child(parent, tag: str):
    return parent.find(qn(f"w:{tag.split(':')[-1]}"))


def drop_child(parent, tag: str):
    node = get_child(parent, tag)
    if node is not None:
        parent.remove(node)


def get_or_add(parent, tag: str):
    return set_child(parent, tag, replace=False)


def onoff(parent, tag: str, value: bool):
    """w:b, w:i, w:keepNext etc. are on/off toggles. Absent means 'inherit',
    val="0" means 'explicitly off' -- these are different, so an explicit
    False must still emit the element."""
    if value is None:
        drop_child(parent, tag)
    else:
        set_child(parent, tag, {"w:val": "1" if value else "0"})


# --- Fonts ------------------------------------------------------------------

def set_fonts(rpr, *, latin=None, cjk=None, cs=None, hint=None):
    """Set w:rFonts.

    python-docx's `font.name` only writes w:ascii and w:hAnsi, which is why
    Chinese text keeps falling back to the theme font even after you "set the
    font". The East Asian face lives in a separate attribute, w:eastAsia, and
    Word picks between the two per character run. Both must be written.

    The other half of the same trap: if the element already carries theme
    attributes (asciiTheme, eastAsiaTheme, ...), Word resolves those *instead*
    of the explicit names sitting right next to them. A document whose
    docDefaults say eastAsiaTheme="minorEastAsia" will keep rendering in the
    theme font no matter what w:eastAsia says, so the theme attribute for each
    face we set has to go.
    """
    if latin is None and cjk is None and cs is None and hint is None:
        return None
    fonts = get_or_add(rpr, "rFonts")
    if latin:
        fonts.set(qn("w:ascii"), latin)
        fonts.set(qn("w:hAnsi"), latin)
        _drop_theme(fonts, "asciiTheme", "hAnsiTheme")
    if cjk:
        fonts.set(qn("w:eastAsia"), cjk)
        _drop_theme(fonts, "eastAsiaTheme")
    if cs:
        fonts.set(qn("w:cs"), cs)
        _drop_theme(fonts, "cstheme")
    if hint:
        # w:hint tells Word which face to use for ambiguous codepoints
        # (punctuation, digits). "eastAsia" keeps CJK punctuation full-width.
        fonts.set(qn("w:hint"), hint)
    return fonts


def _drop_theme(fonts, *names):
    for name in names:
        for attr in (qn(f"w:{name}"), qn(f"w:{name[0].lower() + name[1:]}")):
            if attr in fonts.attrib:
                del fonts.attrib[attr]


def set_size(rpr, pt: float):
    from .units import pt_to_halfpt
    hp = pt_to_halfpt(pt)
    set_child(rpr, "sz", {"w:val": hp})
    set_child(rpr, "szCs", {"w:val": hp})


# --- Paragraph properties ---------------------------------------------------

def set_spacing(ppr, *, before_pt=None, after_pt=None, line=None,
                line_rule=None, before_lines=None, after_lines=None,
                snap_to_grid=None):
    from .units import pt_to_twips
    attrs = {}
    cur = get_child(ppr, "spacing")
    if cur is not None:
        attrs = dict(cur.attrib)
    if before_pt is not None:
        attrs[qn("w:before")] = str(pt_to_twips(before_pt))
        attrs.pop(qn("w:beforeLines"), None)
    if after_pt is not None:
        attrs[qn("w:after")] = str(pt_to_twips(after_pt))
        attrs.pop(qn("w:afterLines"), None)
    if before_lines is not None:
        attrs[qn("w:beforeLines")] = str(int(before_lines * 100))
    if after_lines is not None:
        attrs[qn("w:afterLines")] = str(int(after_lines * 100))
    if line is not None:
        attrs[qn("w:line")] = str(line)
        attrs[qn("w:lineRule")] = line_rule or "auto"
    if attrs:
        set_child(ppr, "spacing", attrs)
    if snap_to_grid is not None:
        # Chinese templates enable a document grid; a paragraph snapped to it
        # ignores exact line spacing, which is why "固定值20磅" sometimes has
        # no visible effect. Turning snapToGrid off per paragraph fixes it.
        onoff(ppr, "snapToGrid", snap_to_grid)


def set_indent(ppr, *, first_line_chars=None, first_line_pt=None,
               left_chars=None, left_pt=None, right_pt=None, hanging_pt=None,
               hanging_chars=None):
    from .units import pt_to_twips
    attrs = {}
    cur = get_child(ppr, "ind")
    if cur is not None:
        attrs = dict(cur.attrib)

    if first_line_chars is not None:
        # firstLineChars is in 1/100 of a character, so 200 == 2 characters.
        # Prefer it over an absolute twip value: it stays correct when the
        # font size changes, which is exactly what 首行缩进2字符 means.
        attrs[qn("w:firstLineChars")] = str(int(first_line_chars))
        attrs.pop(qn("w:firstLine"), None)
        attrs.pop(qn("w:hanging"), None)
        attrs.pop(qn("w:hangingChars"), None)
    if first_line_pt is not None:
        attrs[qn("w:firstLine")] = str(pt_to_twips(first_line_pt))
        attrs.pop(qn("w:firstLineChars"), None)
    if hanging_pt is not None:
        attrs[qn("w:hanging")] = str(pt_to_twips(hanging_pt))
        attrs.pop(qn("w:firstLine"), None)
        attrs.pop(qn("w:firstLineChars"), None)
    if hanging_chars is not None:
        attrs[qn("w:hangingChars")] = str(int(hanging_chars))
        attrs.pop(qn("w:firstLineChars"), None)
    if left_chars is not None:
        attrs[qn("w:leftChars")] = str(int(left_chars))
    if left_pt is not None:
        attrs[qn("w:left")] = str(pt_to_twips(left_pt))
    if right_pt is not None:
        attrs[qn("w:right")] = str(pt_to_twips(right_pt))
    if attrs:
        set_child(ppr, "ind", attrs)


def set_justify(ppr, value):
    if value is None:
        return
    set_child(ppr, "jc", {"w:val": JC[str(value).lower()]})


def set_border(parent, edge: str, *, size_pt=0.5, style="single",
               color="auto", space=0):
    """Border widths are in eighths of a point, so 1.5pt -> sz="12"."""
    holder = get_or_add(parent, "pBdr" if local(parent) == "pPr" else
                        ("tcBorders" if local(parent) == "tcPr" else "tblBorders"))
    set_child(holder, edge, {
        "w:val": style,
        "w:sz": str(int(round(size_pt * 8))),
        "w:space": str(space),
        "w:color": color,
    })


def clear_borders(parent):
    for holder in ("pBdr", "tcBorders", "tblBorders"):
        drop_child(parent, holder)
