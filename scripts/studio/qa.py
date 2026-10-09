"""Cloud checks for content preservation and observable output properties."""
from pathlib import Path
import json
import re
import zipfile
from lxml import etree
from docx import Document
import pdfplumber
from .runtime import StudioError, require_actions, run, digest, write_json
from .manuscript import normalized_text, walk
from .docx_layout import body_only_docx, is_equation_table, M, W


def read_ast(path, fmt):
    return json.loads(run(["pandoc", path, "-f", fmt, "-t", "json"]))


def math_list(ast):
    return [re.sub(r"\\tag\{[^}]+\}|\s+", "", n["c"][1]) for n in walk(ast) if n.get("t") == "Math"]


def assert_text(left, right, label):
    a, b = normalized_text(left), normalized_text(right)
    if a != b:
        index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        raise StudioError(f"CONTENT_CHANGED {label} at {index}: {a[max(0,index-30):index+70]!r} != {b[max(0,index-30):index+70]!r}")


def visible_docx(path):
    # Read actual WordprocessingML text once. Pandoc's reader can repeat the
    # caption as both a short/long alias; those aliases are not extra Word text.
    with zipfile.ZipFile(path) as package:
        xml=etree.fromstring(package.read("word/document.xml"))
    return {"blocks":[{"t":"Str","c":"".join(t.text or "" for t in xml.iter(W+"t"))}]}


def latex_reader_copy(source, output):
    require_actions()
    text=Path(source).read_text(encoding="utf-8")
    pattern=r"(\\toprule.*?)(\\endfirsthead)(.*?)(\\endhead)"
    def remove_repeated_header(match):
        first, second=match.group(1).strip(),match.group(3).strip()
        if first != second: raise StudioError("UNEXPECTED_REPEATED_TABLE_HEADER")
        return first+"\n"+match.group(4)
    text=re.sub(r"\\begin\{longtable\}.*?\\end\{longtable\}",lambda m:re.sub(pattern,remove_repeated_header,m.group(0),flags=re.S),text,flags=re.S)
    path=Path(output)/"latex-reader-input.tex";path.write_text(text,encoding="utf-8")
    return path


def check_equation_visibility(path, identifiers):
    require_actions()
    found={}
    with pdfplumber.open(path) as pdf:
        for number,page in enumerate(pdf.pages,1):
            for word in page.extract_words():
                identifier=word["text"].strip("()")
                if word["text"] != f"({identifier})" or identifier not in identifiers: continue
                center=(word["top"]+word["bottom"])/2
                # A native OMML cases/aligned expression can occupy several
                # baselines while its right-side number is emitted on only
                # one baseline.  Keep the horizontal relationship strict,
                # but allow the expression's measured line span.  The
                # number itself is excluded from candidates, so a missing
                # formula still produces no evidence.
                nearby=[c for c in page.chars if c["text"].strip() and 45 < c["x0"] and c["x1"] < word["x0"]-5 and abs((c["top"]+c["bottom"])/2-center)<18]
                glyphs=nearby
                # Body references such as '(M4)' must not replace stronger
                # evidence from the actual numbered display.
                if len(glyphs) > found.get(identifier, {}).get("formula_line_glyphs", -1):
                    found[identifier]={"page":number,"formula_line_glyphs":len(glyphs)}
    missing=[label for label in identifiers if label not in found or found[label]["formula_line_glyphs"]==0]
    write_json(Path(path).parent/"equation-visibility.json",{"equations":found,"missing":missing})
    if missing: raise StudioError("WORD_PDF_MATH_NOT_VISIBLE: "+", ".join(missing))
    return found


def check_roundtrips(ast, baseline, final, latex_body, output):
    require_actions()
    baseline_ast = read_ast(baseline, "docx")
    write_json(Path(output)/"docx-readback.json",baseline_ast)
    assert_text(ast, visible_docx(baseline), "source -> native DOCX XML text")
    body_only_docx(final, Path(output)/"body-audit.docx")
    # Reverse only recorded layout transforms and verify their exact forward trees.
    from .math_layout import restore, tree
    audit_path = Path(output)/"body-audit.docx"
    audit = Document(audit_path)
    ledger = json.loads((Path(output)/"math-layout-ledger.json").read_text(encoding="utf-8"))
    displays = list(audit._element.iter(M+"oMathPara"))
    if len(displays) != len(ledger): raise StudioError("DISPLAY_LEDGER_COUNT_CHANGED")
    for wrapper, record in zip(displays, ledger):
        formula = wrapper.find(M+"oMath")
        wrapper.replace(formula, restore(formula, record["changes"]))
    base_math = list(Document(baseline)._element.iter(M+"oMath"))
    audit_math = list(audit._element.iter(M+"oMath"))
    if [tree(m) for m in base_math] != [tree(m) for m in audit_math]: raise StudioError("MATH_STRUCTURE_CHANGED")
    audit.save(audit_path)
    final_ast = read_ast(Path(output)/"body-audit.docx", "docx")
    assert_text(ast, visible_docx(Path(output)/"body-audit.docx"), "formatted DOCX XML text")
    if math_list(baseline_ast) != math_list(final_ast):
        raise StudioError("MATH_CHANGED: formatted DOCX readback")
    latex_ast = read_ast(latex_reader_copy(latex_body, output), "latex")
    write_json(Path(output)/"latex-readback.json",latex_ast)
    assert_text(ast, latex_ast, "LaTeX readback")
    if math_list(ast) != math_list(latex_ast):
        raise StudioError("MATH_CHANGED: LaTeX readback")
    rendered_ast = read_ast(Path(latex_body).parent/"layout-body.tex", "latex")
    expected_layout = json.loads((Path(output)/"layout-document.json").read_text(encoding="utf-8"))
    assert_text(expected_layout, rendered_ast, "actual LaTeX layout body")
    if math_list(expected_layout) != math_list(rendered_ast): raise StudioError("MATH_CHANGED: actual LaTeX layout body")
    # Check original conversion retained all inline and display equations as editable OMML.
    with zipfile.ZipFile(final) as package:
        xml = etree.fromstring(package.read("word/document.xml"))
    expected = sum(n.get("t") == "Math" for n in walk(ast))
    if len(list(xml.iter(M+"oMath"))) != expected:
        raise StudioError("FORMULA_CONVERSION_FAILED: native equation count")
    result = {"prose_numbers_tables_references": "exact_visible_text", "latex_math": "source_expression_preserved",
              "docx_math": "recorded_layout_reversed_exact_math_tree_and_readback_equal", "math_count": expected,
              "reader_normalization":"Identical longtable repeated-page headers are read once; actual Word XML text is used instead of duplicated reader caption aliases.",
              "limitation": "Preservation checks do not prove mathematical correctness."}
    write_json(Path(output)/"content-report.json", result)
    return result


def check_docx(path):
    require_actions()
    doc = Document(path)
    columns = [int(s._sectPr.find(W+"cols").get(W+"num", "1")) for s in doc.sections]
    if 1 not in columns or 2 not in columns:
        raise StudioError("MIXED_COLUMNS_LOST")
    for table in doc.tables:
        if is_equation_table(table._tbl): continue
        for edge in table._tbl.iter():
            if etree.QName(edge).localname in ("left", "right", "insideV", "start", "end") and edge.get(W+"val") not in (None, "nil", "none", "0"):
                raise StudioError("TABLE_VERTICAL_BORDER")
        after = table._tbl.getnext()
        if after is not None and re.match(r"^(表\s*\d|Table\s+\d)", "".join(t.text or "" for t in after.iter(W+"t"))):
            raise StudioError("TABLE_CAPTION_BELOW")
    return {"section_columns": columns, "data_tables": sum(not is_equation_table(t._tbl) for t in doc.tables), "equation_layouts":sum(is_equation_table(t._tbl) for t in doc.tables), "three_line_tables": "checked"}


def check_fonts(profile):
    require_actions()
    available = run(["fc-list", ":", "family"])
    for font in profile["fonts"].values():
        if font.casefold() not in available.casefold():
            raise StudioError(f"MISSING_FONT: {font}")


def inspect_output_pdf(path, preview_dir):
    require_actions()
    path = Path(path); preview_dir = Path(preview_dir); preview_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    with pdfplumber.open(path) as pdf:
        if not pdf.pages: raise StudioError("EMPTY_PDF")
        for index, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if "\ufffd" in text: raise StudioError(f"REPLACEMENT_CHARACTER {path.name}:{index}")
            outside = [c for c in page.chars if c["x0"] < -1 or c["x1"] > page.width+1 or c["top"] < -1 or c["bottom"] > page.height+1]
            if outside: raise StudioError(f"PAGE_CLIPPING {path.name}:{index}: {len(outside)} glyphs")
            if any(i["x0"] < -1 or i["x1"] > page.width+1 or i["top"] < -1 or i["bottom"] > page.height+1 for i in page.images):
                raise StudioError(f"IMAGE_CLIPPING {path.name}:{index}")
            pages.append({"page": index, "characters": len(text), "fonts": sorted({c.get("fontname", "") for c in page.chars})})
    run(["pdftoppm", "-r", "100", "-png", path, preview_dir/"page"], timeout=300)
    return {"sha256": digest(path), "pages": pages, "previews": [{"file": p.name, "sha256": digest(p)} for p in sorted(preview_dir.glob("*.png"))]}


def check_page_flow(path, profile, maximum_pages=None):
    """Catch sparse interior pages; the final page can legitimately be short."""
    require_actions()
    measurements=[]
    with pdfplumber.open(path) as pdf:
        if maximum_pages is not None and len(pdf.pages)>maximum_pages:
            raise StudioError(f"EXCESSIVE_PAGINATION: {len(pdf.pages)} pages, regression limit {maximum_pages}")
        for number,page in enumerate(pdf.pages,1):
            top=profile["page"]["margin_cm"]["top"]*72/2.54
            bottom=page.height-profile["page"]["margin_cm"]["bottom"]*72/2.54
            objects=[c for c in page.chars if c["text"].strip() and top-2 <= c["top"] and c["bottom"] <= bottom+2]
            objects+=page.images
            span=(max(o["bottom"] for o in objects)-min(o["top"] for o in objects))/(bottom-top) if objects else 0
            measurements.append({"page":number,"occupied_vertical_span":round(span,3),"final_page":number==len(pdf.pages)})
            if number<len(pdf.pages) and span<.35:
                raise StudioError(f"SPARSE_INTERIOR_PAGE: {Path(path).name}:{number}: occupied span {span:.1%}")
    return {"pages":len(measurements),"measurements":measurements}


def check_column_geometry(path, profile, ast, metadata):
    """Measure the actual rendered body, excluding the template's metadata zones."""
    require_actions()
    from .manuscript import text_of
    first = next((text_of(b) for b in ast["blocks"] if text_of(b).strip()), "")
    prefix = re.sub(r"\s+", "", first)[:12]
    end_title = re.sub(r"\s+", "", metadata.get("title_en", ""))[:12]
    def find_line(page, fragment):
        if not fragment: return None
        lines = {}
        for char in page.chars:
            key = round((char["top"]+char["bottom"])/2/3)*3
            lines.setdefault(key, []).append(char)
        for values in lines.values():
            text = re.sub(r"\s+", "", "".join(c["text"] for c in sorted(values,key=lambda c:c["x0"])))
            if fragment in text: return min(c["top"] for c in values)
        return None
    violations=[]; regions=[]; started=False
    with pdfplumber.open(path) as pdf:
        left=profile["page"]["margin_cm"]["left"]*72/2.54
        right=pdf.pages[0].width-profile["page"]["margin_cm"]["right"]*72/2.54
        gap=profile["page"]["column_spacing_cm"]*72/2.54
        midpoint=(left+right)/2; gutter=(midpoint-gap/2,midpoint+gap/2)
        for number,page in enumerate(pdf.pages,1):
            start=find_line(page,prefix) if not started else None
            if not started and start is None: continue
            top=start-1 if start is not None else profile["page"]["margin_cm"]["top"]*72/2.54
            started=True
            end=find_line(page,end_title) if profile["english_abstract_position"]=="end" else None
            bottom=end-1 if end is not None else page.height-profile["page"]["margin_cm"]["bottom"]*72/2.54
            chars=[c for c in page.chars if c["text"].strip() and c["top"]>=top and c["bottom"]<=bottom+1]
            bad=[c for c in chars if c["x0"]<left-1 or c["x1"]>right+1 or c["x0"]<midpoint and c["x1"]>gutter[0]+1 or c["x0"]>=midpoint and c["x0"]<gutter[1]-1]
            for char in bad[:50]: violations.append({"page":number,"text":char["text"],"x0":round(char["x0"],2),"x1":round(char["x1"],2),"top":round(char["top"],2)})
            regions.append({"page":number,"body_top":round(top,2),"body_bottom":round(bottom,2),"characters":len(chars),"overflow_glyphs":len(bad)})
            if end is not None: break
    if not started: raise StudioError("BODY_REGION_NOT_LOCATED: "+prefix)
    return {"gutter":gutter,"regions":regions,"violations":violations,"authority":"Actual compatibility/PDF geometry, not a pagination estimate"}
