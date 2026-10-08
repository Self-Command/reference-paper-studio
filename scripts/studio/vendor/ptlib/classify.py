"""Decide what role each existing paragraph plays.

Reformatting a document someone else wrote is mostly a classification problem:
the content is fine, but a heading might be a Normal paragraph that was bolded
by hand, and a caption might be indistinguishable from body text except that it
starts with "图 3-1". This module guesses, records *why* it guessed, and
reports a confidence so the caller can show a plan before touching anything.

Order matters: explicit signals (a real Heading style, an outline level) always
beat textual patterns, which in turn beat visual heuristics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ooxml import NS, get_child, local, qn

# --- textual patterns -------------------------------------------------------

CN_NUM = "零一二三四五六七八九十百千两"

RE_DECIMAL_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s*[.、]?\s+?\S")
RE_DECIMAL_BARE = re.compile(r"^(\d+(?:\.\d+)+)\s*[.、]?\s*\S")
RE_CN_CHAPTER = re.compile(rf"^第\s*[{CN_NUM}\d]+\s*[章篇]")
RE_CN_SECTION = re.compile(rf"^第\s*[{CN_NUM}\d]+\s*[节部分]")
RE_CN_ENUM = re.compile(rf"^[{CN_NUM}]+\s*[、.]")
RE_PAREN_ENUM = re.compile(rf"^[(（]\s*[{CN_NUM}\d]+\s*[)）]")
RE_APPENDIX = re.compile(r"^(附\s*录|appendix)\s*[A-Za-z\d]?", re.I)

RE_FIG_CAPTION = re.compile(
    rf"^\s*(图|圖|Fig\.?|Figure)\s*[-–—]?\s*"
    rf"(\d+(?:[-.–]\d+)*|[{CN_NUM}]+)\s*[:：.、]?\s*",
    re.I)
RE_TAB_CAPTION = re.compile(
    rf"^\s*(表|Tab\.?|Table)\s*[-–—]?\s*"
    rf"(\d+(?:[-.–]\d+)*|[{CN_NUM}]+)\s*[:：.、]?\s*",
    re.I)

# "图 2 展示了 GSL 的计算流程。" starts exactly like a caption and is a body
# sentence citing the figure. The tell is what follows the number: a caption
# continues with the figure's *name*, a cross-reference continues with a verb
# or a locative. Without this the sentence is restyled as a caption, the real
# caption below it becomes a duplicate, and the numbering check reports a
# nonsensical "jumps from 2 to 2".
RE_XREF_LEAD = re.compile(
    r"^\s*(?:"
    r"展示|显示|给出|描述|说明|呈现|列出|列举|总结|概述|对比|比较|绘制|"
    r"表明|反映|报告|所示|示意|以及|中|里|的|和|与|及|至|到"
    r"|(?:shows?|illustrates?|presents?|depicts?|summari[sz]es?|compares?"
    r"|lists?|reports?|gives?|and|to|through)\b"
    r")",
    re.I)

# A caption is a label, so it contains no full stop. Deliberately CJK-only: an
# English caption may legitimately read "Figure 3 Overall architecture." and a
# period is too ambiguous to judge on. English cross-references are caught by
# the verb list above, and "Figure 3. …" by the separator branch below.
RE_SENTENCE_PUNCT = re.compile(r"[。；！？]")


def _is_caption(text, pattern):
    """True when `text` is a caption rather than a sentence citing the float.

    Three tells, in order of reliability. A separator after the number settles
    it — "图 2：…" and "Table 2. …" are never prose. Failing that, a caption is
    a label, so it does not end in sentence punctuation, and it does not
    continue with a verb the way "图 2 展示了…" does. Enumerating verbs alone is
    a losing game; the punctuation test is what actually generalises.
    """
    m = pattern.match(text)
    if not m:
        return False
    if re.search(r"[:：.、]\s*$", m.group(0)):
        return True
    rest = text[m.end():]
    if not rest.strip():
        return True                       # bare "图 2" — a caption with no title
    if RE_SENTENCE_PUNCT.search(rest):
        return False
    return not RE_XREF_LEAD.match(rest)

RE_ABSTRACT_HEAD = re.compile(r"^\s*(摘\s*要|内容摘要|abstract)\s*$", re.I)
RE_KEYWORDS = re.compile(r"^\s*(关\s*键\s*词|关键字|key\s*words?)\s*[:：]", re.I)
RE_REF_HEAD = re.compile(
    r"^\s*(参\s*考\s*文\s*献|references?|bibliography|works\s+cited)\s*$", re.I)
RE_ACK_HEAD = re.compile(r"^\s*(致\s*谢|acknowledge?ments?)\s*$", re.I)
RE_TOC_HEAD = re.compile(r"^\s*(目\s*录|contents|table\s+of\s+contents)\s*$", re.I)
RE_REF_ENTRY = re.compile(r"^\s*[\[［【]\s*\d+\s*[\]］】]")

# A heading almost never ends in sentence punctuation.
RE_TERMINAL_PUNCT = re.compile(r"[。．.；;：:，,、!！?？]$")

UNNUMBERED_HEADINGS = {
    "摘要", "abstract", "关键词", "keywords", "目录", "contents",
    "参考文献", "references", "bibliography", "致谢", "acknowledgments",
    "acknowledgements", "附录", "appendix", "引言", "绪论", "前言",
    "introduction", "conclusion", "结论", "结语", "abstract in chinese",
}

BODY_ROLE = "Body"


@dataclass
class Item:
    index: int
    para: object                  # docx.text.paragraph.Paragraph
    text: str
    role: str = BODY_ROLE
    confidence: float = 0.0
    reasons: list = field(default_factory=list)
    level: int = 0                # heading depth, 1-based; 0 if not a heading
    numbered_text: str = ""       # the "1.2.1" prefix, if any

    @property
    def is_heading(self):
        return self.role.startswith("Heading")


# --- signal extraction ------------------------------------------------------

def _style_name(para) -> str:
    try:
        return (para.style.name or "").strip()
    except Exception:
        return ""


def _outline_level(para):
    ppr = para._p.find(qn("w:pPr"))
    if ppr is None:
        return None
    lvl = ppr.find(qn("w:outlineLvl"))
    if lvl is None:
        return None
    try:
        return int(lvl.get(qn("w:val")))
    except (TypeError, ValueError):
        return None


def _has_drawing(para) -> bool:
    return bool(para._p.findall(".//" + qn("w:drawing"))
                or para._p.findall(".//" + qn("w:pict")))


def _has_math(para) -> bool:
    m = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    return bool(para._p.findall(f".//{{{m}}}oMath")
                or para._p.findall(f".//{{{m}}}oMathPara"))


def _max_size_pt(para, fallback):
    sizes = []
    for sz in para._p.findall(".//" + qn("w:sz")):
        try:
            sizes.append(int(sz.get(qn("w:val"))) / 2.0)
        except (TypeError, ValueError):
            pass
    return max(sizes) if sizes else fallback


def _mostly_bold(para) -> bool:
    runs = [r for r in para.runs if r.text.strip()]
    if not runs:
        return False
    bold = sum(1 for r in runs if r.bold)
    return bold >= max(1, len(runs) * 0.8)


def _alignment(para):
    ppr = para._p.find(qn("w:pPr"))
    if ppr is None:
        return None
    jc = ppr.find(qn("w:jc"))
    return jc.get(qn("w:val")) if jc is not None else None


_STYLE_ROLE_MAP = [
    (re.compile(r"^(heading|标题)\s*([1-9])", re.I), lambda m: f"Heading{min(int(m.group(2)), 4)}"),
    (re.compile(r"^(title|题目|论文标题)$", re.I), lambda m: "Title"),
    (re.compile(r"^(subtitle|副标题)$", re.I), lambda m: "Subtitle"),
    (re.compile(r"^(caption|题注)$", re.I), lambda m: None),  # ambiguous: fig or tab
    (re.compile(r"^(quote|引用|intense\s*quote)$", re.I), lambda m: "Quote"),
    (re.compile(r"^(list\s*paragraph|列出段落)$", re.I), lambda m: None),
]


def _role_from_style(name: str):
    for pattern, fn in _STYLE_ROLE_MAP:
        m = pattern.match(name)
        if m:
            return fn(m)
    return None


# --- main pass --------------------------------------------------------------

def classify(doc, profile=None, *, body_size_pt=None) -> list[Item]:
    paras = doc.paragraphs
    body_size = body_size_pt or _guess_body_size(paras)

    items = []
    for i, p in enumerate(paras):
        text = p.text.strip()
        items.append(Item(index=i, para=p, text=text))

    _pass_explicit(items)
    _pass_textual(items)
    _pass_visual(items, body_size)
    _pass_context(items)
    _pass_defaults(items, profile)
    return items


def _guess_body_size(paras) -> float:
    """The most common run size is the body size, whatever the style says."""
    from collections import Counter
    counter = Counter()
    for p in paras:
        n = len(p.text.strip())
        if n < 40:
            continue
        for sz in p._p.findall(".//" + qn("w:sz")):
            try:
                counter[int(sz.get(qn("w:val"))) / 2.0] += n
            except (TypeError, ValueError):
                pass
    return counter.most_common(1)[0][0] if counter else 12.0


def _pass_explicit(items):
    """Trust real styles and outline levels above everything else."""
    for it in items:
        if not it.text and not _has_drawing(it.para):
            it.role = "_empty"
            it.confidence = 1.0
            it.reasons.append("empty paragraph")
            continue

        name = _style_name(it.para)
        role = _role_from_style(name)
        if role and role.startswith("Heading"):
            it.role, it.level = role, int(role[-1])
            it.confidence = 0.95
            it.reasons.append(f"style '{name}'")
            continue
        if role:
            it.role = role
            it.confidence = 0.9
            it.reasons.append(f"style '{name}'")
            continue

        lvl = _outline_level(it.para)
        if lvl is not None and lvl < 9:
            it.role, it.level = f"Heading{min(lvl + 1, 4)}", min(lvl + 1, 4)
            it.confidence = 0.85
            it.reasons.append(f"outlineLvl={lvl}")


def _pass_textual(items):
    for it in items:
        if it.confidence >= 0.85 or it.role == "_empty":
            continue
        t = it.text

        if _is_caption(t, RE_FIG_CAPTION):
            it.role, it.confidence = "FigureCaption", 0.9
            it.reasons.append("starts with a figure label")
            continue
        if _is_caption(t, RE_TAB_CAPTION):
            it.role, it.confidence = "TableCaption", 0.9
            it.reasons.append("starts with a table label")
            continue
        if RE_KEYWORDS.match(t):
            it.role, it.confidence = "Keywords", 0.95
            it.reasons.append("keywords marker")
            continue
        if RE_ABSTRACT_HEAD.match(t):
            it.role, it.confidence = "AbstractHeading", 0.95
            it.reasons.append("abstract heading")
            continue
        if RE_TOC_HEAD.match(t):
            it.role, it.confidence = "TOCHeading", 0.9
            it.reasons.append("table-of-contents heading")
            continue
        if RE_REF_HEAD.match(t) or RE_ACK_HEAD.match(t) or RE_APPENDIX.match(t):
            it.role, it.level, it.confidence = "Heading1", 1, 0.9
            it.reasons.append("front/back-matter heading")
            continue

        if len(t) <= 80 and not RE_TERMINAL_PUNCT.search(t):
            m = RE_DECIMAL_HEADING.match(t)
            if m:
                depth = m.group(1).count(".") + 1
                it.role = f"Heading{min(depth, 4)}"
                it.level = min(depth, 4)
                it.numbered_text = m.group(1)
                it.confidence = 0.8 if depth > 1 else 0.65
                it.reasons.append(f"decimal number '{m.group(1)}'")
                continue
            if RE_CN_CHAPTER.match(t):
                it.role, it.level, it.confidence = "Heading1", 1, 0.85
                it.reasons.append("第N章")
                continue
            if RE_CN_SECTION.match(t):
                it.role, it.level, it.confidence = "Heading2", 2, 0.75
                it.reasons.append("第N节")
                continue
            if RE_CN_ENUM.match(t):
                it.role, it.level, it.confidence = "Heading2", 2, 0.6
                it.reasons.append("一、enumeration")
                continue
            if RE_PAREN_ENUM.match(t):
                it.role, it.level, it.confidence = "Heading3", 3, 0.55
                it.reasons.append("（一）enumeration")
                continue
            if t.lower().rstrip(":：") in UNNUMBERED_HEADINGS:
                it.role, it.level, it.confidence = "Heading1", 1, 0.7
                it.reasons.append("well-known section name")
                continue


def _pass_visual(items, body_size):
    """Bold, oversized, short, unpunctuated lines that nothing else claimed."""
    for it in items:
        if it.confidence >= 0.6 or it.role == "_empty":
            continue
        if _has_drawing(it.para):
            it.role, it.confidence = "Figure", 0.85
            it.reasons.append("contains an image")
            continue
        if _has_math(it.para) and len(it.text) < 200:
            it.role, it.confidence = "Equation", 0.8
            it.reasons.append("contains an equation object")
            continue

        t = it.text
        if not t or len(t) > 60 or RE_TERMINAL_PUNCT.search(t):
            continue
        size = _max_size_pt(it.para, body_size)
        bold = _mostly_bold(it.para)
        bigger = size >= body_size + 1
        if bigger and bold:
            it.role, it.level, it.confidence = "Heading2", 2, 0.5
            it.reasons.append(f"bold and {size:g}pt vs {body_size:g}pt body")
        elif bigger:
            it.role, it.level, it.confidence = "Heading2", 2, 0.4
            it.reasons.append(f"{size:g}pt vs {body_size:g}pt body")
        elif bold and len(t) <= 30:
            it.role, it.level, it.confidence = "Heading3", 3, 0.35
            it.reasons.append("short bold line")


def _pass_context(items):
    """Fix up roles that only make sense relative to their neighbours."""
    # Everything after a References heading, until the next heading, is an entry.
    in_refs = False
    for it in items:
        if it.role == "_empty":
            continue
        if it.is_heading:
            in_refs = bool(RE_REF_HEAD.match(it.text))
            continue
        if in_refs and it.confidence < 0.9:
            it.role, it.confidence = "Reference", 0.85
            it.reasons.append("inside the references section")
        elif RE_REF_ENTRY.match(it.text) and it.confidence < 0.6:
            it.role, it.confidence = "Reference", 0.6
            it.reasons.append("looks like a numbered reference entry")

    # Abstract body: paragraphs between an abstract heading and the keywords.
    in_abstract = False
    for it in items:
        if it.role == "AbstractHeading":
            in_abstract = True
            continue
        if it.role in ("Keywords", "_empty"):
            if it.role == "Keywords":
                in_abstract = False
            continue
        if in_abstract:
            if it.is_heading:
                in_abstract = False
            elif it.confidence < 0.8:
                it.role, it.confidence = "Abstract", 0.75
                it.reasons.append("between abstract heading and keywords")

    # The document title: the first substantial paragraph, if nothing before it
    # was a heading and it isn't already spoken for.
    for it in items:
        if it.role == "_empty":
            continue
        if it.role in ("Title", "AbstractHeading", "TOCHeading"):
            break
        if it.is_heading and it.confidence >= 0.8:
            break
        if it.text and len(it.text) <= 100 and it.confidence < 0.7:
            it.role, it.level, it.confidence = "Title", 0, 0.6
            it.reasons.append("first substantial line of the document")
        break

    # A caption directly above a table, or below a figure, is more certain.
    for i, it in enumerate(items):
        if it.role != "FigureCaption":
            continue
        prev = next((x for x in reversed(items[:i]) if x.role != "_empty"), None)
        if prev is not None and prev.role == "Figure":
            it.confidence = max(it.confidence, 0.95)
            it.reasons.append("directly below a figure")


def _pass_defaults(items, profile):
    """Demote roles the profile doesn't define, and headings deeper than it
    supports, so we never apply a style that was never installed."""
    for it in items:
        if it.role == "_empty":
            continue
        if profile is None:
            continue
        if it.role == BODY_ROLE:
            continue
        if it.role in ("Figure",) and not profile.has("Figure"):
            it.role = BODY_ROLE
            it.reasons.append("profile defines no Figure style")
            continue
        if not profile.has(it.role) and it.role != BODY_ROLE:
            # Fall back up the heading chain, else to Body.
            if it.is_heading:
                for lvl in range(it.level, 0, -1):
                    if profile.has(f"Heading{lvl}"):
                        it.role, it.level = f"Heading{lvl}", lvl
                        break
                else:
                    it.role = BODY_ROLE
            else:
                it.role = BODY_ROLE
                it.reasons.append("profile defines no such style")


def summarize(items) -> dict:
    from collections import Counter
    counts = Counter(it.role for it in items if it.role != "_empty")
    low = [it for it in items
           if it.role not in (BODY_ROLE, "_empty") and it.confidence < 0.6]
    return {"counts": dict(counts), "uncertain": low}
