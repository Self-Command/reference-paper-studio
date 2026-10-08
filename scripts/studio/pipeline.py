"""Single-source dual export. Runs only on Actions, fails closed on conversion loss."""
from pathlib import Path
import json
import re
import shutil
import os
from .runtime import StudioError, require_actions, run, write_json, digest, confined
from .manuscript import parse, validate_assets, validate_references, model_gate, walk, resolve_crossrefs
from .docx_layout import apply_layout, configure_math_font
from .latex_layout import write_latex
from .qa import check_fonts, check_roundtrips, check_docx, inspect_output_pdf


def strict_pandoc(args, cwd=None):
    # Pandoc exits zero for some unsupported TeX; warnings must still fail the export.
    import subprocess
    require_actions()
    p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if p.returncode or "[WARNING]" in p.stderr or "Could not convert" in p.stderr:
        raise StudioError(f"FORMULA_OR_OBJECT_CONVERSION_FAILED: {p.stderr[-6000:]}")
    return p.stdout


def export(root, request, output, reference_rules=None):
    require_actions()
    try:
        return _export(root, request, output, reference_rules)
    except Exception as error:
        write_json(Path(output)/"acceptance.json", {"build":"failed", "automatic_acceptance":"failed", "visual_review":"not_available", "error":str(error), "exception_type":type(error).__name__})
        raise


def _export(root, request, output, reference_rules=None):
    require_actions()
    root, output = Path(root).resolve(), Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    source = confined(root, request["manuscript"])
    meta = json.loads(confined(root, request["metadata"]).read_text(encoding="utf-8"))
    profile = json.loads(confined(root, request["profile"]).read_text(encoding="utf-8"))
    if request.get("reference_evidence"):
        from .references import analyze
        reference_rules = analyze(root, request["reference_evidence"], output/"reference-analysis")["rules"]
    applied_rules = []
    for rule in reference_rules or []:
        if rule["status"] not in ("reference_consensus", "official_disambiguation"): continue
        if rule["property"] == "body_columns" and rule["value"] != 2: raise StudioError("UNSUPPORTED_BODY_COLUMN_RULE")
        supported={"table_lines":"three_line","table_caption_position":"above","figure_caption_position":"below"}
        if rule["property"] in supported and rule["value"] != supported[rule["property"]]:
            raise StudioError("UNSUPPORTED_REFERENCE_RULE: "+rule["property"])
        if rule["property"] == "english_abstract_position": profile["english_abstract_position"] = rule["value"]
        applied_rules.append(rule)
    write_json(output/"effective-profile.json", {**profile,"adopted_reference_rules":applied_rules})
    if profile.get("english_abstract_position") not in ("front", "end") or profile.get("equation_numbering") not in ("preserve", "sequential"):
        raise StudioError("INVALID_PROFILE")
    check_fonts(profile)
    gate = model_gate(root, request["manuscript"], request.get("model_evidence"), request.get("document_kind") == "paper")
    ast, equations = parse(source, output)
    object_map = resolve_crossrefs(ast, equations, profile["equation_numbering"])
    validate_assets(ast, root); validate_references(ast)
    if request.get("expected_equations") is not None and len(equations) != request["expected_equations"]:
        raise StudioError("EQUATION_COUNT_CHANGED")
    # Resolve citation keys once for both writers; explicit numerical references also work.
    cites = [n for n in walk(ast) if n.get("t") == "Cite"]
    if cites:
        if not request.get("bibliography"): raise StudioError("BIBLIOGRAPHY_REQUIRED")
        citation_args = ["pandoc", output/"document.json", "-f", "json", "-t", "json", "--citeproc", "--bibliography", confined(root, request["bibliography"]), "--csl", Path(__file__).resolve().parents[2]/"assets/numbered.csl"]
        ast = json.loads(strict_pandoc(citation_args))
        write_json(output/"document.json", ast)
    write_json(output/"document.json", ast)
    baseline, final = output/"native.docx", output/"manuscript.docx"
    try:
        strict_pandoc(["pandoc", output/"document.json", "-f", "json", "-o", baseline, "--resource-path", root])
    except StudioError as error:
        bad=[]
        for index, node in enumerate(n for n in walk(ast) if n.get("t") == "Math"):
            probe=output/"formula-probe.md"; probe.write_text("$$"+node["c"][1]+"$$",encoding="utf-8")
            try: strict_pandoc(["pandoc",probe,"-o",output/"formula-probe.docx"])
            except StudioError:
                bad.append({"math_index":index+1,"expression":node["c"][1]})
        raise StudioError(f"{error}\nFORMULA_LOCATIONS: {bad}") from error
    configure_math_font(baseline, profile)
    shutil.copy2(baseline, final)
    layout = apply_layout(final, meta, profile, equations)
    import zipfile
    with zipfile.ZipFile(final) as package:
        for part in ("document","settings"):
            (output/("word-"+part+".xml")).write_bytes(package.read("word/"+part+".xml"))
    texdir = output/"latex"
    main = write_latex(ast, equations, meta, profile, texdir)
    for node in walk(ast):
        if node.get("t") == "Image":
            relative = node["c"][-1][0]; target = confined(texdir, relative); target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(confined(root, relative), target)
    for _ in range(2):
        run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "main.tex"], cwd=texdir, timeout=300)
    log = (texdir/"main.log").read_text(encoding="utf-8", errors="replace")
    if "Missing character:" in log: raise StudioError("MISSING_GLYPH: see latex/main.log")
    overflow = [float(n) for n in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide\)", log)]
    if any(n > 2 for n in overflow): raise StudioError(f"LATEX_OVERFLOW: {overflow}")
    shutil.copy2(texdir/"main.pdf", output/"latex-proof.pdf")
    run(["libreoffice", "-env:UserInstallation=file:///tmp/rps-lo-"+str(os.getpid()), "--headless", "--convert-to", "pdf:writer_pdf_Export", "--outdir", output, final], timeout=300)
    if not (output/"manuscript.pdf").exists(): raise StudioError("DOCX_RENDER_FAILED")
    (output/"manuscript.pdf").rename(output/"word-compat-proof.pdf")
    pdfs = {name: inspect_output_pdf(output/name, output/"previews"/name.removesuffix(".pdf")) for name in ("latex-proof.pdf", "word-compat-proof.pdf")}
    # This catches the editable-but-invisible OMML regression in LibreOffice.
    if equations:
        word_fonts=" ".join(font for page in pdfs["word-compat-proof.pdf"]["pages"] for font in page["fonts"]).replace(" ","").casefold()
        if "latinmodernmath" not in word_fonts: raise StudioError("WORD_PDF_MATH_NOT_VISIBLE: required native math font absent from PDF")
    content = check_roundtrips(ast, baseline, final, texdir/"body.tex", output)
    docx = check_docx(final)
    mapping = {e["id"]: {"ordinal": e["ordinal"], "display": e["id"] if profile["equation_numbering"] == "preserve" else str(e["ordinal"])} for e in equations}
    write_json(output/"reference-map.json", {"equations": mapping, "literature": "shared resolved AST", "objects": object_map})
    report = {"build": "passed", "automatic_acceptance": "passed", "visual_review": "pending", "model_gate": gate,
              "input_sha256": digest(source), "layout": layout, "docx": docx, "content": content, "pdfs": pdfs,
              "font_substitution": {"fonts": profile["fonts"], "exact_reference_match": False, "reason": "Open-source portable proof fonts"},
              "renderer": {"word_pdf": "LibreOffice compatibility rendering, not Microsoft Word native", "latex_pdf": "XeLaTeX"}}
    report["implementation_version"] = __import__("studio").__version__
    report["execution"] = {"run_id":os.environ["GITHUB_RUN_ID"],"skill_commit":os.environ.get("GITHUB_SHA"),"input_files":{p.relative_to(root).as_posix():digest(p) for p in root.rglob("*") if p.is_file()}}
    write_json(output/"acceptance.json", report)
    return report
