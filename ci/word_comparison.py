"""Controlled Word-template comparison, including failures, only on Actions.

Both engines receive the same actual DOCX master and native OOXML body blocks.
The existing output remains the baseline. This experiment does not replace the
production writer or claim mathematical validation.
"""
from copy import deepcopy
from pathlib import Path
import json
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING
from lxml import etree
import pdfplumber
from studio.runtime import require_actions, write_json, digest, run, StudioError
from studio.docx_layout import apply_layout, body_only_docx, W, M
from studio.qa import assert_text, visible_docx, math_list, read_ast, inspect_output_pdf, check_docx, check_equation_visibility
from studio.manuscript import walk

require_actions()
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/word-comparison"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def xml(path):
    with zipfile.ZipFile(path) as z:
        return etree.fromstring(z.read("word/document.xml"))


def math_structure(node):
    # Namespace declarations and prefix choices do not alter the math tree.
    return [node.tag, sorted(node.attrib.items()), node.text or "", [math_structure(c) for c in node]]


def set_child(parent, tag, attrs):
    node = parent.find(qn(tag))
    if node is None:
        node = OxmlElement(tag)
        parent.append(node)
    for key, value in attrs.items():
        node.set(qn(key), str(value))
    return node


def compact_styles(doc):
    for style in doc.styles:
        if style.type != 1:
            continue
        name = style.name.replace(" ", "").lower()
        if name in ("normal", "bodytext", "firstparagraph", "compact", "abstract", "keywords", "author"):
            style.paragraph_format.space_before = Pt(0)
            style.paragraph_format.space_after = Pt(3)
            # Explicit baseline spacing avoids Noto's large default line box.
            style.paragraph_format.line_spacing = Pt(14)
            style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.AT_LEAST
            style.paragraph_format.keep_with_next = False
            style.paragraph_format.keep_together = False
        elif name.startswith("heading"):
            style.paragraph_format.space_before = Pt(7)
            style.paragraph_format.space_after = Pt(3)
            style.paragraph_format.line_spacing = Pt(15)
            style.paragraph_format.keep_with_next = True
        elif name == "title":
            style.paragraph_format.line_spacing = Pt(24)
            style.paragraph_format.line_spacing_rule = WD_LINE_SPACING.AT_LEAST


def prepare(case):
    source = ROOT / "build/baseline" / case
    target = OUT / case
    target.mkdir(parents=True, exist_ok=True)
    acceptance = load(source / "acceptance.json")
    if acceptance.get("automatic_acceptance") != "passed":
        raise StudioError("BASELINE_NOT_ACCEPTED: " + case)
    shutil.copy2(source / "manuscript.docx", target / "baseline.docx")
    shutil.copy2(source / "word-compat-proof.pdf", target / "baseline.pdf")
    ast = load(source / "document.json")
    equations = load(source / "equations.json")
    profile = load(source / "effective-profile.json")
    meta = load(ROOT / "fixtures/model/metadata.json") if case == "model" else {
        "title_zh": "排版能力回归样例", "authors_zh": "测试作者（非论文署名）", "affiliation_zh": "格式测试",
        "abstract_zh": "验证通栏前置信息、双栏正文、原生公式、图下题、表上题。", "keywords_zh": ["格式测试"],
        "title_en": "Formatting regression fixture", "abstract_en": "Synthetic material for formatting checks only.",
        "keywords_en": ["format test"],
    }
    if case == "model" and acceptance["input_sha256"] != digest(ROOT / "fixtures/model/model.md"):
        raise StudioError("BASELINE_SOURCE_MISMATCH")
    candidate = target / "prepared.docx"
    shutil.copy2(source / "native.docx", candidate)
    routing = apply_layout(candidate, meta, profile, equations)
    doc = Document(candidate)
    compact_styles(doc)
    body = doc._element.body
    # Move section properties to the paragraph that actually ends the section.
    # A table still needs an empty following paragraph to carry its section end.
    collapsed = 0
    for element in list(body):
        if element.tag != W + "p" or list(element.iter(W + "t")) or list(element.iter(M + "oMath")):
            continue
        sect = element.find(W + "pPr/" + W + "sectPr")
        previous = element.getprevious()
        if sect is not None and previous is not None and previous.tag == W + "p":
            props = previous.find(W + "pPr")
            if props is None:
                props = OxmlElement("w:pPr"); previous.insert(0, props)
            if props.find(W + "sectPr") is None:
                props.append(deepcopy(sect)); body.remove(element); collapsed += 1
    for table in doc.tables:
        for cell in [c for row in table.rows for c in row.cells]:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.line_spacing = Pt(12)
                paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.AT_LEAST
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.keep_with_next = False
                set_child(paragraph._p.get_or_add_pPr(), "w:ind", {"w:left": 0, "w:right": 0, "w:firstLine": 0, "w:firstLineChars": 0})
    # Display math needs its actual built-up height, never exact prose spacing.
    for paragraph in doc.paragraphs:
        numbered_display = any(r.find(W + "tab") is not None and re.fullmatch(r"\([\w.:-]+\)", "".join(t.text or "" for t in r.iter(W + "t"))) for r in paragraph._p.findall(W + "r"))
        if numbered_display:
            set_child(paragraph._p.get_or_add_pPr(), "w:spacing", {"w:before": 3 * 20, "w:after": 3 * 20, "w:line": 240, "w:lineRule": "auto"})
    doc.save(candidate)
    body = doc._element.body
    start = next(e for e in body if e.tag == W + "bookmarkStart" and e.get(W + "name") == "RPS_BODY")
    end = next(e for e in body if e.tag == W + "bookmarkEnd" and e.get(W + "id") == "9181")
    children = list(body)
    content = children[children.index(start):children.index(end) + 1]
    blocks = [etree.tostring(e, encoding="unicode") for e in content]
    placeholder = OxmlElement("w:p")
    run_node = OxmlElement("w:r"); text = OxmlElement("w:t"); text.text = "{{RPS_BODY}}"
    run_node.append(text); placeholder.append(run_node)
    body.insert(children.index(start), placeholder)
    for element in content:
        body.remove(element)
    doc.save(target / "master.docx")
    fonts = []
    for family in (profile["fonts"]["cjk"], profile["fonts"]["latin"], profile["fonts"].get("math", "Latin Modern Math")):
        filename = run(["fc-match", "-f", "%{file}", family]).strip()
        fonts.append({"name": family, "path": filename})
    write_json(target / "template-input.json", {"blocks": blocks, "equations": equations, "fonts": fonts})
    write_json(target / "experiment-input.json", {"case": case, "profile": profile, "ast": ast, "equations": equations,
        "routing": routing, "collapsed_section_markers": collapsed, "baseline_run": os.environ["BASELINE_RUN"],
        "source_sha256": acceptance["input_sha256"], "master_sha256": digest(target / "master.docx"),
        "changes": ["one shared real DOCX master", "exact 14pt prose baseline", "12pt table baseline", "section ends attached to preceding actual paragraphs"]})
    # Python fills the same master without rewriting other package parts.
    python_doc = Document(target / "master.docx")
    anchor = next(p._p for p in python_doc.paragraphs if p.text == "{{RPS_BODY}}")
    for block in blocks:
        anchor.addprevious(etree.fromstring(block.encode("utf-8")))
    anchor.getparent().remove(anchor)
    python_doc.save(target / "python-template.docx")


def page_metrics(path, profile):
    result = []
    margin = profile["page"]["margin_cm"]
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            top = margin["top"] * 72 / 2.54; bottom = page.height - margin["bottom"] * 72 / 2.54
            left = margin["left"] * 72 / 2.54; right = page.width - margin["right"] * 72 / 2.54
            middle = (left + right) / 2
            chars = [c for c in page.chars if c["text"].strip() and top - 2 <= c["top"] and c["bottom"] <= bottom + 2]
            halves = [[c for c in chars if (c["x0"] + c["x1"]) / 2 < middle], [c for c in chars if (c["x0"] + c["x1"]) / 2 >= middle]]
            spans = [(max(c["bottom"] for c in group) - min(c["top"] for c in group)) / (bottom - top) if group else 0 for group in halves]
            result.append({"page": number, "characters": len(chars), "left_characters": len(halves[0]), "right_characters": len(halves[1]),
                "left_vertical_span": round(spans[0], 3), "right_vertical_span": round(spans[1], 3),
                "column_span_difference": round(abs(spans[0] - spans[1]), 3),
                "needs_visual_review": abs(spans[0] - spans[1]) > .30 and number != len(pdf.pages)})
    return {"pages": len(result), "measurements": result, "interpretation": "Whole-page halves are diagnostics; full-width blocks and a natural last page need visual interpretation."}


def verify(case):
    target = OUT / case
    request = load(target / "experiment-input.json")
    source = ROOT / "build/baseline" / case
    baseline_math = [math_structure(m) for m in xml(source / "native.docx").iter(M + "oMath")]
    baseline_readback = read_ast(source / "native.docx", "docx")
    reports = {}
    for name in ("baseline", "python-template", "node-template"):
        docx = target / (name + ".docx")
        errors = []
        if name != "baseline":
            try:
                body_only_docx(docx, target / (name + "-body.docx"))
                assert_text(request["ast"], visible_docx(target / (name + "-body.docx")), name)
                if baseline_math != [math_structure(m) for m in xml(docx).iter(M + "oMath")]:
                    raise StudioError("OMML_TREE_CHANGED")
                if math_list(baseline_readback) != math_list(read_ast(target / (name + "-body.docx"), "docx")):
                    raise StudioError("MATH_READBACK_CHANGED")
                check_docx(docx)
                if any(etree.QName(node).localname == "undefined" for node in xml(docx).iter()):
                    raise StudioError("INVALID_XML_WRAPPER")
            except Exception as error:
                errors.append(str(error))
            run(["libreoffice", "-env:UserInstallation=file:///tmp/rps-compare-" + name + case, "--headless", "--convert-to", "pdf:writer_pdf_Export", "--outdir", target, docx], timeout=300)
        pdf = target / (name + ".pdf")
        report = inspect_output_pdf(pdf, target / "previews" / name)
        report["page_metrics"] = page_metrics(pdf, request["profile"])
        try:
            report["equation_visibility"] = check_equation_visibility(pdf, [e["id"] for e in request["equations"]])
        except Exception as error:
            errors.append(str(error))
        report.update({"content_preservation": "passed" if not errors else "failed", "errors": errors,
            "native_math_count": len(list(xml(docx).iter(M + "oMath"))), "visual_review": "pending"})
        reports[name] = report
    # The adapters should not change the body or section structure differently.
    left = xml(target / "python-template.docx"); right = xml(target / "node-template.docx")
    equivalence = math_structure(left.find(W + "body")) == math_structure(right.find(W + "body"))
    direct = load(target / "direct-math-probe.json")
    built = [e for e in direct["equations"] if e["conversion"] == "built"]
    converted = math_list(read_ast(target / "direct-math-probe.docx", "docx"))
    source_math = [re.sub(r"\s+", "", e["source"]) for e in request["equations"] if e["id"] in {x["id"] for x in built}]
    # Different TeX spellings may be equivalent; no automatic adoption on that basis.
    direct["literal_readback_equal"] = converted == source_math
    write_json(target / "direct-math-probe.json", direct)
    from PIL import Image, ImageDraw
    for name in reports:
        images = sorted((target / "previews" / name).glob("*.png"))
        tiles = []
        for filename in images:
            picture = Image.open(filename).convert("RGB")
            picture.thumbnail((310, 440))
            tile = Image.new("RGB", (330, 470), "#eeeeee")
            tile.paste(picture, ((330-picture.width)//2, 24))
            ImageDraw.Draw(tile).text((10, 6), name + " / " + filename.stem, fill="black")
            tiles.append(tile)
        sheet = Image.new("RGB", (330*4, 470*((len(tiles)+3)//4)), "white")
        for index, tile in enumerate(tiles):
            sheet.paste(tile, ((index%4)*330, (index//4)*470))
        sheet.save(target / (name + "-contact.png"))
    result = {"case": case, "build": "passed", "automatic_content_checks": "passed" if all(not r["errors"] for r in reports.values()) else "failed",
        "visual_review": "pending", "same_master": True, "adapter_body_trees_equal": equivalence,
        "variants": reports, "node_layout": load(target / "node-layout.json"), "direct_math": direct,
        "source_sha256": request["source_sha256"], "master_sha256": request["master_sha256"],
        "run_id": os.environ["GITHUB_RUN_ID"], "commit": os.environ["GITHUB_SHA"],
        "mathematical_correctness": "not_asserted", "production_writer": "unchanged"}
    write_json(target / "comparison.json", result)
    return result


if __name__ == "__main__":
    stage = sys.argv[1]
    if stage == "prepare":
        for case in ("model", "objects-end"):
            prepare(case)
    elif stage == "verify":
        results = [verify(case) for case in ("model", "objects-end")]
        write_json(OUT / "summary.json", {"cases": results, "build": "passed", "visual_review": "pending"})
        if any(r["automatic_content_checks"] != "passed" for r in results):
            raise StudioError("COMPARISON_CONTENT_FAILURE: see comparison.json")
    else:
        raise StudioError("UNKNOWN_COMPARISON_STAGE")
