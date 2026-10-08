"""Check a document against a profile without modifying it.

Every finding carries a severity, a location, and -- where the engine can fix
it -- the name of the fix that would. `audit` is what runs before `apply` so
the user can see what is about to change, and again after, to confirm it did.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .classify import (RE_FIG_CAPTION, RE_TAB_CAPTION, RE_TERMINAL_PUNCT,
                       classify)
from .ooxml import get_child, local, qn
from .units import twips_to_cm

ERROR, WARN, INFO = "error", "warning", "info"


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    where: str = ""
    fixable: bool = False
    count: int = 1

    def line(self):
        mark = {"error": "✗", "warning": "!", "info": "·"}[self.severity]
        loc = f" [{self.where}]" if self.where else ""
        more = f" (×{self.count})" if self.count > 1 else ""
        fix = " — fixable" if self.fixable else ""
        return f"  {mark} {self.rule}{loc}: {self.message}{more}{fix}"


@dataclass
class Report:
    findings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add(self, *a, **kw):
        self.findings.append(Finding(*a, **kw))

    @property
    def errors(self):
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self):
        return [f for f in self.findings if f.severity == WARN]

    def text(self, verbose=False):
        out = []
        for sev, label in ((ERROR, "Errors"), (WARN, "Warnings"), (INFO, "Notes")):
            group = [f for f in self.findings if f.severity == sev]
            if not group or (sev == INFO and not verbose):
                continue
            out.append(f"{label} ({len(group)}):")
            out.extend(f.line() for f in group)
            out.append("")
        if not out:
            out = ["No issues found."]
        return "\n".join(out).rstrip()


def _para_loc(item):
    text = item.text[:36].replace("\n", " ")
    return f"¶{item.index}“{text}”" if text else f"¶{item.index}"


def audit(doc, profile, *, items=None) -> Report:
    rep = Report()
    items = items if items is not None else classify(doc, profile)
    rep.stats = {
        "paragraphs": len(items),
        "tables": len(doc.tables),
        "sections": len(doc.sections),
        "roles": dict(Counter(i.role for i in items if i.role != "_empty")),
    }
    _check_page(doc, profile, rep)
    _check_fonts(doc, profile, rep)
    _check_headings(items, profile, rep)
    _check_captions(items, profile, rep, doc=doc)
    _check_tables(doc, profile, rep)
    _check_clipped_images(doc, items, rep)
    _check_hygiene(doc, items, rep)
    _check_uncertain(items, rep)
    return rep


def _check_page(doc, profile, rep):
    page = profile.page or {}
    if not page:
        return
    # Profiles may state margins in either unit; compare in cm.
    want = page.get("margin_cm")
    if want is None and page.get("margin_in"):
        want = {k: v * 2.54 for k, v in page["margin_in"].items()}
    for i, section in enumerate(doc.sections):
        sect = section._sectPr
        loc = f"section {i + 1}"
        pg_sz = get_child(sect, "pgSz")
        if page.get("size") and pg_sz is not None:
            from .units import page_size
            w, h = page_size(page["size"], page.get("landscape", False))
            gw, gh = int(pg_sz.get(qn("w:w"), 0)), int(pg_sz.get(qn("w:h"), 0))
            if abs(gw - w) > 20 or abs(gh - h) > 20:
                rep.add("page.size", ERROR,
                        f"page is {twips_to_cm(gw):.1f}×{twips_to_cm(gh):.1f} cm, "
                        f"profile wants {page['size'].upper()}",
                        loc, fixable=True)
        if want:
            mar = get_child(sect, "pgMar")
            if mar is None:
                continue
            for edge in ("top", "bottom", "left", "right"):
                got = twips_to_cm(int(mar.get(qn(f"w:{edge}"), 0)))
                # Twips round to ~0.002 cm, so anything above 0.02 is a real
                # difference, not a rounding artefact.
                if abs(got - want[edge]) > 0.02:
                    rep.add("page.margin", ERROR,
                            f"{edge} margin is {got:.2f} cm, profile wants "
                            f"{want[edge]:.2f} cm", loc, fixable=True)
        cols = get_child(sect, "cols")
        want_cols = page.get("columns", 1)
        got_cols = int(cols.get(qn("w:num"), 1)) if cols is not None else 1
        if got_cols != want_cols:
            rep.add("page.columns", ERROR,
                    f"{got_cols} column(s), profile wants {want_cols}",
                    loc, fixable=True)
        grid = get_child(sect, "docGrid")
        if grid is not None and grid.get(qn("w:type")) in ("lines", "linesAndChars"):
            if page.get("doc_grid") not in ("lines", "linesAndChars"):
                rep.add("page.doc_grid", WARN,
                        "a line grid is active; Word will ignore exact line "
                        "spacing and re-space CJK text to fit it",
                        loc, fixable=True)


def _check_fonts(doc, profile, rep):
    """The classic CJK failure: w:ascii is set but w:eastAsia is not, so Latin
    text obeys the style and Chinese text silently falls back to the theme.

    Walks every w:p in the body rather than doc.paragraphs, because the latter
    skips table cells -- where hand-set fonts are most common.
    """
    body = profile.resolved("Body")
    want_cjk = body.get("cjk_font")
    missing_east = 0
    direct_runs = 0
    seen_latin = Counter()
    seen_cjk = Counter()

    for para in doc.element.body.findall(".//" + qn("w:p")):
        for run in para.findall(qn("w:r")):
            rpr = run.find(qn("w:rPr"))
            if rpr is None:
                continue
            if any(local(c) in ("rFonts", "sz", "szCs") for c in rpr):
                direct_runs += 1
            fonts = rpr.find(qn("w:rFonts"))
            if fonts is None:
                continue
            ascii_f = fonts.get(qn("w:ascii"))
            east = fonts.get(qn("w:eastAsia"))
            if ascii_f:
                seen_latin[ascii_f] += 1
            if east:
                seen_cjk[east] += 1
            text = "".join(t.text or "" for t in run.findall(qn("w:t")))
            if ascii_f and not east and _has_cjk(text):
                missing_east += 1

    if missing_east:
        rep.add("font.eastAsia", ERROR,
                "runs set a Latin face but no w:eastAsia, so Chinese text "
                "falls back to the theme font", fixable=True, count=missing_east)
    if direct_runs:
        rep.add("font.direct", WARN,
                "runs carry hard-coded font/size that overrides any style",
                fixable=True, count=direct_runs)
    if want_cjk and seen_cjk and want_cjk not in seen_cjk:
        rep.add("font.cjk", WARN,
                f"document uses {', '.join(sorted(seen_cjk))} for CJK; "
                f"profile wants {want_cjk}", fixable=True)
    rep.stats["fonts"] = {"latin": dict(seen_latin.most_common(5)),
                          "cjk": dict(seen_cjk.most_common(5))}


CJK_RANGE = re.compile(r"[㐀-鿿豈-﫿぀-ヿ]")


def _has_cjk(s: str) -> bool:
    return bool(CJK_RANGE.search(s or ""))


def _check_headings(items, profile, rep):
    headings = [i for i in items if i.is_heading]
    if not headings:
        rep.add("structure.headings", WARN,
                "no headings detected; the document has no navigable structure")
        return

    no_outline = [h for h in headings if not _has_outline(h.para)]
    if no_outline:
        rep.add("heading.outline_level", ERROR,
                "headings carry no w:outlineLvl, so a generated TOC and the "
                "navigation pane will not see them",
                fixable=True, count=len(no_outline))

    # A jump from H1 straight to H3 breaks list numbering and TOC indentation.
    prev = 0
    for h in headings:
        if prev and h.level > prev + 1:
            rep.add("heading.skipped_level", WARN,
                    f"jumps from level {prev} to level {h.level}",
                    _para_loc(h))
        prev = h.level

    for h in headings:
        if RE_TERMINAL_PUNCT.search(h.text):
            rep.add("heading.punctuation", INFO,
                    "heading ends with sentence punctuation", _para_loc(h))


def _has_outline(para):
    ppr = para._p.find(qn("w:pPr"))
    if ppr is None:
        return False
    if ppr.find(qn("w:outlineLvl")) is not None:
        return True
    try:
        return (para.style.name or "").lower().startswith(("heading", "标题"))
    except Exception:
        return False


def _check_captions(items, profile, rep, doc=None):
    spec = profile.captions or {}
    live = [i for i in items if i.role != "_empty"]
    pos = {i.index: n for n, i in enumerate(live)}

    fig_caps = [i for i in live if i.role == "FigureCaption"]
    tab_caps = [i for i in live if i.role == "TableCaption"]

    want_fig = spec.get("figure_position", "below")
    want_tab = spec.get("table_position", "above")

    for cap in fig_caps:
        n = pos[cap.index]
        prev = live[n - 1] if n else None
        nxt = live[n + 1] if n + 1 < len(live) else None
        actual = ("below" if prev is not None and prev.role == "Figure"
                  else "above" if nxt is not None and nxt.role == "Figure"
                  else None)
        if actual and actual != want_fig:
            rep.add("caption.figure_position", WARN,
                    f"figure caption sits {actual} the figure; "
                    f"profile wants {want_fig}", _para_loc(cap))

    # A table caption's neighbour is a w:tbl, which never appears in
    # doc.paragraphs -- so this one has to be read off the body sequence.
    if doc is not None and tab_caps:
        by_p = {}
        for cap in tab_caps:
            by_p[id(cap.para._p)] = cap
        body = list(doc.element.body)
        for n, node in enumerate(body):
            cap = by_p.get(id(node))
            if cap is None:
                continue
            actual = None
            if _nearest_kind(body, n, -1) == "tbl":
                actual = "below"
            if _nearest_kind(body, n, +1) == "tbl":
                actual = "above"
            if actual and actual != want_tab:
                rep.add("caption.table_position", WARN,
                        f"table caption sits {actual} the table; "
                        f"profile wants {want_tab}", _para_loc(cap))

    _check_caption_sequence(fig_caps, RE_FIG_CAPTION, "figure", rep)
    _check_caption_sequence(tab_caps, RE_TAB_CAPTION, "table", rep)


def _nearest_kind(body, start, step):
    """Walk over blank paragraphs to find the next real block's tag name."""
    i = start + step
    while 0 <= i < len(body):
        node = body[i]
        name = local(node)
        if name == "tbl":
            return "tbl"
        if name == "p":
            if "".join(node.itertext()).strip():
                return "p"
        elif name not in ("bookmarkStart", "bookmarkEnd", "sectPr"):
            return name
        i += step
    return None


def _check_caption_sequence(caps, pattern, kind, rep):
    numbers = []
    for cap in caps:
        m = pattern.match(cap.text)
        if m and m.group(2) and m.group(2)[0].isdigit():
            numbers.append((cap, m.group(2)))
    for idx in range(1, len(numbers)):
        _, prev_n = numbers[idx - 1]
        cap, n = numbers[idx]
        pa, na = _tail_int(prev_n), _tail_int(n)
        if pa is None or na is None:
            continue
        same_chapter = prev_n.rsplit(".", 1)[:-1] == n.rsplit(".", 1)[:-1]
        if same_chapter and na != pa + 1:
            rep.add(f"caption.{kind}_numbering", WARN,
                    f"{kind} numbering jumps from {prev_n} to {n}",
                    _para_loc(cap))


def _tail_int(s):
    tail = re.split(r"[-.–]", s)[-1]
    return int(tail) if tail.isdigit() else None


def _check_tables(doc, profile, rep):
    spec = profile.tables or {}
    if spec.get("style") not in ("three-line", "booktabs", "三线表"):
        return
    for i, table in enumerate(doc.tables):
        loc = f"table {i + 1}"
        borders = table._tbl.find(f"{qn('w:tblPr')}/{qn('w:tblBorders')}")
        verticals = []
        if borders is not None:
            for edge in ("left", "right", "insideV"):
                node = borders.find(qn(f"w:{edge}"))
                if node is not None and node.get(qn("w:val")) not in (None, "none", "nil"):
                    verticals.append(edge)
        else:
            style_id = table._tbl.find(f"{qn('w:tblPr')}/{qn('w:tblStyle')}")
            if style_id is not None and "Grid" in (style_id.get(qn("w:val")) or ""):
                verticals.append("table style has a full grid")
        if verticals:
            rep.add("table.vertical_rules", ERROR,
                    f"has vertical rules ({', '.join(verticals)}); academic "
                    f"tables are three-line", loc, fixable=True)

        if table.rows:
            tr_pr = table.rows[0]._tr.find(qn("w:trPr"))
            repeats = tr_pr is not None and tr_pr.find(qn("w:tblHeader")) is not None
            if not repeats and len(table.rows) > 12:
                rep.add("table.header_repeat", INFO,
                        "long table does not repeat its header row across "
                        "pages", loc, fixable=True)


def _check_clipped_images(doc, items, rep):
    """An inline image inside an exact-height line box gets drawn over.

    Word honours `w:lineRule="exact"` literally: the line box is that tall and
    no taller, so a 230pt figure in a paragraph pinned to 20pt overflows it and
    the following text is painted straight across the picture. This is the one
    formatting error that is invisible in the XML and obvious on the page, so
    it is checked from the geometry rather than from the style name.
    """
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    for it in items:
        exts = it.para._p.findall(f".//{A}ext")
        heights = [int(e.get("cy")) for e in exts if e.get("cy")]
        if not heights:
            continue
        img_pt = max(heights) / 12700.0          # EMU -> pt
        line_pt, rule = _resolved_line(doc, it.para)
        if rule != "exact" or line_pt is None or img_pt <= line_pt:
            continue
        rep.add("figure.clipped", ERROR,
                f"image is {img_pt:.0f}pt tall in a paragraph whose line "
                f"height is fixed at {line_pt:.0f}pt — text will overlap the "
                f"picture; use atLeast spacing on this style",
                f"¶{it.index}", fixable=True)


def _resolved_line(doc, para):
    """(height in pt, rule) for a paragraph, following style inheritance."""
    def read(ppr):
        if ppr is None:
            return None
        sp = ppr.find(qn("w:spacing"))
        if sp is None:
            return None
        rule = sp.get(qn("w:lineRule"))
        line = sp.get(qn("w:line"))
        if rule is None and line is None:
            return None
        return (float(line) / 20.0 if line else None), rule

    direct = read(para._p.find(qn("w:pPr")))
    if direct and direct[1]:
        return direct

    seen = set()
    try:
        st = para.style.element
    except Exception:
        return (None, None)
    while st is not None:
        sid = st.get(qn("w:styleId"))
        if sid in seen:
            break
        seen.add(sid)
        got = read(st.find(qn("w:pPr")))
        if got and got[1]:
            return got
        based = st.find(qn("w:basedOn"))
        if based is None:
            break
        st = _style_by_id(doc, based.get(qn("w:val")))
    return (None, None)


def _style_by_id(doc, style_id):
    if not style_id:
        return None
    for st in doc.styles.element.findall(qn("w:style")):
        if st.get(qn("w:styleId")) == style_id:
            return st
    return None


def _check_hygiene(doc, items, rep):
    blanks = 0
    streak = 0
    manual_breaks = 0
    tab_indent = 0
    space_indent = 0
    double_space = 0

    for it in items:
        if it.role == "_empty":
            streak += 1
            continue
        if streak >= 1:
            blanks += streak
        streak = 0
        raw = it.para.text
        if raw.startswith("\t"):
            tab_indent += 1
        if raw.startswith("    ") or raw.startswith("　　"):
            space_indent += 1
        if "  " in raw.strip():
            double_space += 1
        for br in it.para._p.findall(".//" + qn("w:br")):
            if br.get(qn("w:type")) == "page":
                manual_breaks += 1

    if blanks:
        rep.add("hygiene.blank_paragraphs", WARN,
                "empty paragraphs used as vertical spacing; use style "
                "space-before/after so spacing survives edits",
                fixable=True, count=blanks)
    if tab_indent or space_indent:
        rep.add("hygiene.manual_indent", WARN,
                "paragraphs indented with tabs or literal spaces instead of "
                "w:ind/firstLineChars", fixable=True,
                count=tab_indent + space_indent)
    if double_space:
        rep.add("hygiene.double_space", INFO,
                "runs of consecutive spaces inside paragraphs",
                count=double_space)
    if manual_breaks:
        rep.add("hygiene.manual_page_break", INFO,
                "manual page breaks; prefer page-break-before on the heading "
                "style so breaks move with the content", count=manual_breaks)

    floating = 0
    for anchor in doc.element.body.findall(".//" + qn("w:drawing")):
        if anchor.find("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor") is not None:
            floating += 1
    if floating:
        rep.add("figure.floating", WARN,
                "floating (text-wrapped) images; academic figures should be "
                "inline so they stay with their captions", count=floating)


def _check_uncertain(items, rep):
    low = [i for i in items
           if i.role not in ("Body", "_empty") and i.confidence < 0.6]
    for it in low[:12]:
        rep.add("classify.uncertain", INFO,
                f"guessed {it.role} at {it.confidence:.0%} "
                f"({'; '.join(it.reasons)})", _para_loc(it))
    if len(low) > 12:
        rep.add("classify.uncertain", INFO,
                f"…and {len(low) - 12} more low-confidence guesses")
