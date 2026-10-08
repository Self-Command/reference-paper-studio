"""Format profiles: declarative descriptions of what a finished paper should
look like, so the engine stays generic and the venue rules stay data.

A profile is YAML (or JSON) with three parts:

    page:      geometry and section setup
    defaults:  properties every style inherits unless it overrides them
    styles:    per-role overrides, keyed by canonical role name

Roles are language-neutral (`Heading1`, `FigureCaption`, ...) and map onto
Word's built-in style IDs where one exists, so that Word's navigation pane,
cross-references and generated TOC keep working.
"""

from __future__ import annotations

import json
from pathlib import Path

from .units import CN_SIZES, FONT_HINTS, JUSTIFY, LINE_RULES, PAGE_SIZES, resolve_size

PROFILE_DIR = Path(__file__).resolve().parent.parent.parent / "profiles"

# Canonical role -> (Word styleId, Word style display name, style type).
# Writing into the built-in IDs rather than inventing new ones is what keeps
# the TOC field, the navigation pane and \ref-style cross-references alive.
ROLE_STYLES = {
    "Title":           ("Title", "Title", "paragraph"),
    "Subtitle":        ("Subtitle", "Subtitle", "paragraph"),
    "Author":          ("Author", "Author", "paragraph"),
    "Abstract":        ("Abstract", "Abstract", "paragraph"),
    "AbstractHeading": ("AbstractHeading", "Abstract Heading", "paragraph"),
    "Keywords":        ("Keywords", "Keywords", "paragraph"),
    "Heading1":        ("Heading1", "heading 1", "paragraph"),
    "Heading2":        ("Heading2", "heading 2", "paragraph"),
    "Heading3":        ("Heading3", "heading 3", "paragraph"),
    "Heading4":        ("Heading4", "heading 4", "paragraph"),
    "Body":            ("Normal", "Normal", "paragraph"),
    "BodyFirst":       ("BodyFirst", "Body First", "paragraph"),
    "FigureCaption":   ("FigureCaption", "Figure Caption", "paragraph"),
    "TableCaption":    ("TableCaption", "Table Caption", "paragraph"),
    "Figure":          ("Figure", "Figure", "paragraph"),
    "Equation":        ("Equation", "Equation", "paragraph"),
    "Reference":       ("Reference", "Reference", "paragraph"),
    "Quote":           ("Quote", "Quote", "paragraph"),
    "Code":            ("Code", "Code", "paragraph"),
    "ListBullet":      ("ListBullet", "List Bullet", "paragraph"),
    "ListNumber":      ("ListNumber", "List Number", "paragraph"),
    "TOCHeading":      ("TOCHeading", "TOC Heading", "paragraph"),
    "Header":          ("Header", "header", "paragraph"),
    "Footer":          ("Footer", "footer", "paragraph"),
    "TableText":       ("TableText", "Table Text", "paragraph"),
}

HEADING_ROLES = ["Heading1", "Heading2", "Heading3", "Heading4"]

# Properties a style may declare. Anything else in a profile is a typo, and
# the loader says so rather than silently ignoring it.
STYLE_KEYS = {
    "based_on", "next_style", "latin_font", "cjk_font", "cs_font", "font_hint",
    "size_pt", "bold", "italic", "underline", "all_caps", "small_caps",
    "color", "char_spacing_pt",
    "justify", "first_line_chars", "first_line_pt", "hanging_chars",
    "hanging_pt", "left_chars", "left_pt", "right_pt",
    "space_before_pt", "space_after_pt", "space_before_lines",
    "space_after_lines", "line_rule", "line_pt", "line_multiple",
    "page_break_before", "keep_with_next", "keep_lines", "widow_control",
    "snap_to_grid", "outline_level", "contextual_spacing",
    "border_bottom_pt", "border_top_pt",
}

PAGE_KEYS = {
    "size", "landscape", "margin_cm", "margin_in", "gutter_cm", "mirror",
    "columns", "column_spacing_cm", "header_distance_cm", "footer_distance_cm",
    "different_odd_even", "different_first_page", "doc_grid", "lines_per_page",
    "chars_per_line",
}

# Pairs of page keys that are two spellings of one setting. `extends` merges
# key by key, so a child that switches from margin_cm to margin_in would
# otherwise end up carrying both -- and whichever the engine happens to read
# first wins silently. The child's choice has to displace the inherited one.
PAGE_ALTERNATIVES = [("margin_cm", "margin_in")]

# --- value vocabularies -----------------------------------------------------
#
# The key checks above catch a misspelled *key*. These catch a misspelled
# *value*, which is the likelier mistake when a profile is written by hand from
# a requirements document. Without them `justify: centre-ish` survives loading,
# survives `audit` and `plan`, and finally surfaces during `apply` as a bare
# KeyError naming an internal table -- long after the point where the author
# could see which style caused it.

ENUM_KEYS = {
    "justify": set(JUSTIFY),
    "line_rule": LINE_RULES,
    "font_hint": FONT_HINTS,
}

BOOL_KEYS = {
    "bold", "italic", "underline", "all_caps", "small_caps", "page_break_before",
    "keep_with_next", "keep_lines", "widow_control", "snap_to_grid",
    "contextual_spacing",
}

# size_pt is deliberately absent: it also accepts "小四" and "12pt", so it is
# checked through resolve_size instead.
NUM_KEYS = {
    "char_spacing_pt", "first_line_chars", "first_line_pt", "hanging_chars",
    "hanging_pt", "left_chars", "left_pt", "right_pt", "space_before_pt",
    "space_after_pt", "space_before_lines", "space_after_lines", "line_pt",
    "line_multiple", "border_bottom_pt", "border_top_pt", "outline_level",
}


class ProfileError(ValueError):
    pass


class Profile:
    def __init__(self, data: dict, source: str = "<dict>"):
        self.source = source
        self.name = data.get("name", Path(source).stem)
        self.description = data.get("description", "")
        self.lang = data.get("lang", "en")
        self.page = data.get("page", {}) or {}
        self.defaults = data.get("defaults", {}) or {}
        self.styles = data.get("styles", {}) or {}
        self.tables = data.get("tables", {}) or {}
        self.captions = data.get("captions", {}) or {}
        self.numbering = data.get("numbering", {}) or {}
        self.rules = data.get("rules", {}) or {}
        self.raw = data
        self._validate()

    def _validate(self):
        bad_page = set(self.page) - PAGE_KEYS
        if bad_page:
            raise ProfileError(
                f"{self.source}: unknown page keys {sorted(bad_page)}")
        for role, props in self.styles.items():
            if role not in ROLE_STYLES:
                raise ProfileError(
                    f"{self.source}: unknown style role '{role}'. "
                    f"Known roles: {', '.join(sorted(ROLE_STYLES))}")
            bad = set(props or {}) - STYLE_KEYS
            if bad:
                raise ProfileError(
                    f"{self.source}: style '{role}' has unknown keys "
                    f"{sorted(bad)}")
            self._check_values(props or {}, f"style '{role}'")
        bad_def = set(self.defaults) - STYLE_KEYS
        if bad_def:
            raise ProfileError(
                f"{self.source}: unknown defaults keys {sorted(bad_def)}")
        self._check_values(self.defaults, "defaults")
        self._check_page_values()
        self._check_line_spacing()

    def _check_line_spacing(self):
        """`line_rule: exact` needs `line_pt`, and nothing else supplies it.

        Checked on the *resolved* properties, because the rule may come from a
        style while the measurement comes from defaults -- that combination is
        legal and common. Without this the profile loads, `audit` and `plan`
        both pass, and `apply` dies inside a units helper with a bare TypeError
        that names neither the file nor the style.
        """
        for role in sorted(set(self.styles) | {"Body"}):
            props = self.resolved(role)
            rule = str(props.get("line_rule", "auto")).lower()
            if rule in ("exact", "exactly", "atleast", "at_least") \
                    and props.get("line_pt") is None:
                raise ProfileError(
                    f"{self.source}: style '{role}' has line_rule: {rule}, "
                    f"which measures the line in points, but no line_pt is set "
                    f"on it or on defaults. Add line_pt, or use "
                    f"line_rule: auto with line_multiple.")

    def _check_values(self, props: dict, where: str):
        for key, value in props.items():
            if value is None:
                continue
            if key in ENUM_KEYS:
                if str(value).lower() not in {v.lower() for v in ENUM_KEYS[key]}:
                    raise ProfileError(
                        f"{self.source}: {where} has {key}: {value!r}. "
                        f"Allowed: {', '.join(sorted(ENUM_KEYS[key]))}")
            elif key in BOOL_KEYS:
                if not isinstance(value, bool):
                    raise ProfileError(
                        f"{self.source}: {where} has {key}: {value!r}, "
                        f"which must be true or false")
            elif key in NUM_KEYS:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    unit = ("characters" if key.endswith("_chars")
                            else "points" if key.endswith("_pt")
                            else "lines" if key.endswith("_lines")
                            else "a plain number")
                    raise ProfileError(
                        f"{self.source}: {where} has {key}: {value!r}, "
                        f"which must be a number ({unit})")
            elif key == "size_pt":
                try:
                    resolve_size(value)
                except (TypeError, ValueError) as exc:
                    raise ProfileError(
                        f"{self.source}: {where} has size_pt: {value!r}. "
                        f"Use a number of points (12), a string ('12pt'), or a "
                        f"Chinese size name ({', '.join(list(CN_SIZES)[:4])}, ...)"
                    ) from exc

    def _check_page_values(self):
        size = self.page.get("size")
        if size is not None and str(size).lower() not in PAGE_SIZES:
            raise ProfileError(
                f"{self.source}: page size {size!r} is not known. "
                f"Allowed: {', '.join(sorted(PAGE_SIZES))}")
        for a, b in PAGE_ALTERNATIVES:
            if self.page.get(a) is not None and self.page.get(b) is not None:
                raise ProfileError(
                    f"{self.source}: page declares both {a} and {b}. "
                    f"They set the same thing, so keep one.")
        for key in ("margin_cm", "margin_in"):
            margins = self.page.get(key)
            if margins is None:
                continue
            if not isinstance(margins, dict):
                raise ProfileError(
                    f"{self.source}: page.{key} must be a mapping with "
                    f"top/bottom/left/right, not {margins!r}")
            bad = set(margins) - {"top", "bottom", "left", "right"}
            if bad:
                raise ProfileError(
                    f"{self.source}: page.{key} has unknown edges {sorted(bad)}")

    def resolved(self, role: str) -> dict:
        """Defaults merged with the role's own overrides, sizes normalised."""
        props = dict(self.defaults)
        own = self.styles.get(role, {}) or {}
        props.update(own)
        if "size_pt" in props:
            props["size_pt"] = resolve_size(props["size_pt"])
        _relax_exact_line(role, props, own)
        return props

    def has(self, role: str) -> bool:
        return role in self.styles

    @property
    def active_roles(self):
        return [r for r in ROLE_STYLES if r in self.styles or r == "Body"]


# Roles whose paragraph holds an object taller than a line of text. A CJK
# profile sets 固定行距 20 磅 on the body, which is right for prose and fatal
# here: Word clips the paragraph's line box to exactly that height, the image
# overflows it, and the surrounding text is drawn straight over the picture.
# "atLeast" keeps the same 20pt rhythm for the text case and lets the box grow
# for the tall case. A profile that states line_rule on the role itself is
# taken at its word — this only overrides a value inherited from defaults.
FLOW_ROLES = frozenset({"Figure", "Equation"})


def _relax_exact_line(role: str, props: dict, own: dict = None):
    if role not in FLOW_ROLES:
        return
    if own and ("line_rule" in own or "line_multiple" in own):
        return
    if props.get("line_rule") == "exact":
        props["line_rule"] = "atLeast"


def _load_raw(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml
    except ImportError as exc:
        raise ProfileError(
            "Reading a .yaml profile needs PyYAML (`pip install pyyaml`). "
            "A .json profile works with no extra dependency."
        ) from exc
    return yaml.safe_load(text) or {}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _drop_superseded(page: dict, own_keys: set):
    """Remove inherited spellings the child replaced with the other one."""
    if not page:
        return
    for a, b in PAGE_ALTERNATIVES:
        if a in own_keys and b not in own_keys:
            page.pop(b, None)
        elif b in own_keys and a not in own_keys:
            page.pop(a, None)


def resolve_path(name: str) -> Path:
    p = Path(name)
    if p.exists():
        return p
    for ext in (".yaml", ".yml", ".json"):
        cand = PROFILE_DIR / f"{name}{ext}"
        if cand.exists():
            return cand
    raise ProfileError(
        f"No profile named '{name}'. Available: {', '.join(list_profiles())}")


def load(name: str, _seen=None) -> Profile:
    path = resolve_path(name)
    _seen = _seen or set()
    if path in _seen:
        raise ProfileError(f"circular `extends` involving {path}")
    _seen.add(path)

    data = _load_raw(path)
    parent = data.pop("extends", None)
    if parent:
        own_page = set(data.get("page") or {})
        base = load(parent, _seen).raw
        data = _deep_merge(base, data)
        data.pop("extends", None)
        _drop_superseded(data.get("page"), own_page)
    return Profile(data, str(path))


def list_profiles():
    if not PROFILE_DIR.exists():
        return []
    names = {p.stem for p in PROFILE_DIR.iterdir()
             if p.suffix.lower() in (".yaml", ".yml", ".json")}
    return sorted(names)
