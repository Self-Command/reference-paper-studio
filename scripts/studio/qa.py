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
                glyphs=[c for c in page.chars if c["text"].strip() and 45 < c["x0"] and c["x1"] < word["x0"]-5 and abs((c["top"]+c["bottom"])/2-center)<6]
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
    final_ast = read_ast(Path(output)/"body-audit.docx", "docx")
    assert_text(ast, visible_docx(Path(output)/"body-audit.docx"), "formatted DOCX XML text")
    if math_list(baseline_ast) != math_list(final_ast):
        raise StudioError("MATH_CHANGED: formatted DOCX readback")
    latex_ast = read_ast(latex_reader_copy(latex_body, output), "latex")
    write_json(Path(output)/"latex-readback.json",latex_ast)
    assert_text(ast, latex_ast, "LaTeX readback")
    if math_list(ast) != math_list(latex_ast):
        raise StudioError("MATH_CHANGED: LaTeX readback")
    # Check original conversion retained all inline and display equations as editable OMML.
    with zipfile.ZipFile(final) as package:
        xml = etree.fromstring(package.read("word/document.xml"))
    expected = sum(n.get("t") == "Math" for n in walk(ast))
    if len(list(xml.iter(M+"oMath"))) != expected:
        raise StudioError("FORMULA_CONVERSION_FAILED: native equation count")
    result = {"prose_numbers_tables_references": "exact_visible_text", "latex_math": "source_expression_preserved",
              "docx_math": "native_OMML_unchanged_and_readback_equal", "math_count": expected,
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
