"""Unit conversion for OOXML. Every measurement in WordprocessingML is an
integer in one of a handful of odd units; getting these wrong is the single
most common source of "it looks almost right" bugs."""

# 1 inch = 1440 twips (DXA) = 72 pt; 1 cm = 1440/2.54 = 566.929 twips
TWIPS_PER_INCH = 1440
TWIPS_PER_PT = 20
TWIPS_PER_CM = 1440 / 2.54
EMU_PER_INCH = 914400
EMU_PER_CM = EMU_PER_INCH / 2.54

# Chinese font-size names (号) -> points. Word rounds to half-points, so 五号
# is 10.5pt exactly and 小五 is 9pt.
CN_SIZES = {
    "初号": 42.0, "小初": 36.0,
    "一号": 26.0, "小一": 24.0,
    "二号": 22.0, "小二": 18.0,
    "三号": 16.0, "小三": 15.0,
    "四号": 14.0, "小四": 12.0,
    "五号": 10.5, "小五": 9.0,
    "六号": 7.5, "小六": 6.5,
    "七号": 5.5, "八号": 5.0,
}


def cm_to_twips(cm: float) -> int:
    return int(round(cm * TWIPS_PER_CM))


def inch_to_twips(inch: float) -> int:
    return int(round(inch * TWIPS_PER_INCH))


def pt_to_twips(pt: float) -> int:
    return int(round(pt * TWIPS_PER_PT))


def twips_to_cm(tw: float) -> float:
    return tw / TWIPS_PER_CM


def twips_to_pt(tw: float) -> float:
    return tw / TWIPS_PER_PT


def pt_to_halfpt(pt: float) -> int:
    """w:sz and w:szCs are in half-points. 12pt -> 24."""
    return int(round(pt * 2))


def halfpt_to_pt(hp: float) -> float:
    return hp / 2.0


def cm_to_emu(cm: float) -> int:
    return int(round(cm * EMU_PER_CM))


def resolve_size(value) -> float:
    """Accept 12, "12", "12pt", or a Chinese size name like 小四."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s in CN_SIZES:
        return CN_SIZES[s]
    s = s.removesuffix("pt").removesuffix("磅").strip()
    return float(s)


# Spellings a profile may use for w:jc, mapped to the OOXML value. Kept here
# rather than in ooxml.py so the profile loader can check a spelling without
# pulling in lxml.
JUSTIFY = {"left": "left", "start": "start", "center": "center",
           "centre": "center", "right": "right", "end": "end",
           "both": "both", "justify": "both", "distribute": "distribute"}

# Accepted line_rule spellings. "exact" and "atLeast" measure w:line in twips;
# "auto" measures it in 240ths of a line.
LINE_RULES = {"auto", "exact", "exactly", "atleast", "at_least"}

# w:hint tells Word which face to use for codepoints both fonts claim.
FONT_HINTS = {"default", "eastAsia", "cs"}


def line_spacing(rule: str, *, multiple: float = None, pt: float = None):
    """Return (w:line value, w:lineRule value).

    lineRule="auto" measures w:line in 240ths of a line, so single=240 and
    1.5x=360. lineRule="exact"/"atLeast" measure it in twips, so a fixed 20pt
    line is 400. Chinese thesis specs usually mean the *exact* variant when
    they say 固定值20磅, and the auto variant when they say 1.5倍行距.
    """
    rule = (rule or "auto").lower()
    if rule == "auto":
        if multiple is None:
            multiple = 1.0
        return int(round(multiple * 240)), "auto"
    if rule in ("exact", "exactly"):
        return pt_to_twips(pt), "exact"
    if rule in ("atleast", "at_least"):
        return pt_to_twips(pt), "atLeast"
    raise ValueError(f"unknown line rule: {rule}")


# Page sizes in twips (portrait)
PAGE_SIZES = {
    "a4": (11906, 16838),        # 210 x 297 mm
    "letter": (12240, 15840),    # 8.5 x 11 in
    "a5": (8391, 11906),
    "b5": (9979, 14175),         # 176 x 250 mm, common for Chinese journals
    "legal": (12240, 20160),
}


def page_size(name: str, landscape: bool = False):
    w, h = PAGE_SIZES[str(name).lower()]
    return (h, w) if landscape else (w, h)
