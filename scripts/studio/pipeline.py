"""Single-source dual export. Runs only on Actions, fails closed on conversion loss."""
from pathlib import Path
import json
import re
import shutil
import os
from .runtime import StudioError, require_actions, run, write_json, digest, confined
from .manuscript import parse, validate_assets, validate_references, model_gate, walk
from .docx_layout import apply_layout
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


def export(root, request, output):
    require_actions()
    root, output = Path(root).resolve(), Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    source = confined(root, request["manuscript"])
    meta = json.loads(confined(root, request["metadata"]).read_text(encoding="utf-8"))
    profile = json.loads(confined(root, request["profile"]).read_text(encoding="utf-8"))
    if profile.get("english_abstract_position") not in ("front", "end") or profile.get("equation_numbering") not in ("preserve", "sequential"):
        raise StudioError("INVALID_PROFILE")
    check_fonts(profile)
    gate = model_gate(root, request["manuscript"], request.get("model_evidence"), request.get("document_kind") == "paper")
    ast, equations = parse(source, output)
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
    baseline, final = output/"native.docx", output/"manuscript.docx"
    strict_pandoc(["pandoc", output/"document.json", "-f", "json", "-o", baseline, "--resource-path", root])
    shutil.copy2(baseline, final)
    layout = apply_layout(final, meta, profile, equations)
    texdir = output/"latex"
    main = write_latex(ast, equations, meta, profile, texdir)
    for node in walk(ast):
        if node.get("t") == "Image":
            relative = node["c"][-1][0]; target = confined(texdir, relative); target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(confined(root, relative), target)
    content = check_roundtrips(ast, baseline, final, texdir/"body.tex", output)
    docx = check_docx(final)
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
    mapping = {e["id"]: {"ordinal": e["ordinal"], "display": e["id"] if profile["equation_numbering"] == "preserve" else str(e["ordinal"])} for e in equations}
    write_json(output/"reference-map.json", {"equations": mapping, "literature": "shared resolved AST", "figures_tables": "source labels preserved"})
    report = {"build": "passed", "automatic_acceptance": "passed", "visual_review": "pending", "model_gate": gate,
              "input_sha256": digest(source), "layout": layout, "docx": docx, "content": content, "pdfs": pdfs,
              "font_substitution": {"fonts": profile["fonts"], "exact_reference_match": False, "reason": "Open-source portable proof fonts"},
              "renderer": {"word_pdf": "LibreOffice compatibility rendering, not Microsoft Word native", "latex_pdf": "XeLaTeX"}}
    write_json(output/"acceptance.json", report)
    return report
