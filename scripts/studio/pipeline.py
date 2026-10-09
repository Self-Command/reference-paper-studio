"""Single-source dual export. Runs only on Actions, fails closed on conversion loss."""
from pathlib import Path
import json
import re
import shutil
import os
from .runtime import StudioError, require_actions, run, write_json, digest, confined
from .manuscript import parse, validate_assets, validate_references, model_gate, walk, resolve_crossrefs, text_of, strip_layout_attributes
from .docx_layout import configure_math_font
from .locked_template import resolve_template, fill, check_contract
from .latex_layout import write_latex
from .qa import check_fonts, check_roundtrips, check_docx, inspect_output_pdf, check_equation_visibility, check_page_flow, check_column_geometry


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
        directory=Path(output)
        existing=directory/"acceptance.json"
        if existing.is_file() and json.loads(existing.read_text(encoding="utf-8")).get("pdfs"): raise
        complete=all((directory/n).is_file() for n in ("manuscript.docx","word-compat-proof.pdf","latex-proof.pdf"))
        binding_file=directory/"execution-binding.json"
        binding=json.loads(binding_file.read_text(encoding="utf-8")) if binding_file.is_file() else {}
        proofs={}
        for name in ("word-compat-proof.pdf","latex-proof.pdf"):
            record=directory/(name+".json")
            if record.is_file(): proofs[name]=json.loads(record.read_text(encoding="utf-8"))
        editable={name:digest(directory/name) for name in ("manuscript.docx","latex/main.tex") if (directory/name).is_file()}
        write_json(directory/"acceptance.json", {**binding,"build":"passed" if complete else "failed", "automatic_acceptance":"failed", "visual_review":"pending" if proofs else "unavailable", "error":str(error), "exception_type":type(error).__name__, "execution":binding.get("execution",{"run_id":os.environ["GITHUB_RUN_ID"],"skill_commit":os.environ.get("GITHUB_SHA")}),"template_request":request.get("template",{k:request.get(k) for k in ("template_id","template_version","template_variant")}),"pdfs":proofs,"editable_outputs":editable,"diagnostic_artifacts_retained":True})
        from .reporting import publish
        publish(directory,json.loads((directory/"acceptance.json").read_text(encoding="utf-8")))
        raise


def _export(root, request, output, reference_rules=None):
    require_actions()
    root, output = Path(root).resolve(), Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    source = confined(root, request["manuscript"])
    ast, equations = parse(source, output)
    from .frontmatter import extract,prepare
    meta=extract(ast)
    if request.get("metadata"):
        legacy_meta=json.loads(confined(root,request["metadata"]).read_text(encoding="utf-8"))
        if any(key in meta and meta[key]!=value for key,value in legacy_meta.items()): raise StudioError("METADATA_CONFLICT")
        meta.update(legacy_meta)
    ast["meta"]={}
    master, profile, template_identity = resolve_template(request)
    write_json(output/"execution-binding.json",{"input_sha256":digest(source),"template":template_identity,"execution":{"run_id":os.environ["GITHUB_RUN_ID"],"skill_commit":os.environ.get("GITHUB_SHA"),"input_commit":request.get("input_commit"),"input_files":{p.relative_to(root).as_posix():digest(p) for p in root.rglob("*") if p.is_file()}}})
    if request.get("schema_version")==2:
        from .approvals import check_export
        approval=check_export(root,request,template_identity)
        write_json(output/"approval-binding.json",approval)
    if request.get("reference_evidence"):
        from .references import analyze
        reference_rules = analyze(root, request["reference_evidence"], output/"reference-analysis")["rules"]
    applied_rules = []
    for rule in reference_rules or []:
        if rule["status"] not in ("reference_consensus", "official_disambiguation"): continue
        if rule["property"] == "body_columns" and rule["value"] != profile.get("body_columns",2): raise StudioError("TEMPLATE_REFERENCE_CONFLICT: body columns")
        supported={"table_lines":"three_line","table_caption_position":profile.get("captions",{}).get("table","above"),"figure_caption_position":profile.get("captions",{}).get("figure","below")}
        if rule["property"] in supported and rule["value"] != supported[rule["property"]]:
            raise StudioError("UNSUPPORTED_REFERENCE_RULE: "+rule["property"])
        if rule["property"] == "english_abstract_position" and profile["english_abstract_position"] != rule["value"]:
            raise StudioError("TEMPLATE_REFERENCE_CONFLICT: English abstract position")
        applied_rules.append(rule)
    write_json(output/"effective-profile.json", {**profile,"adopted_reference_rules":applied_rules})
    if profile.get("english_abstract_position") not in ("front", "end") or profile.get("equation_numbering") not in ("preserve", "sequential"):
        raise StudioError("INVALID_PROFILE")
    check_fonts(profile)
    gate = model_gate(root, request["manuscript"], request.get("model_evidence"), request.get("document_kind") == "paper")
    if profile.get("anonymous") and any(value for key,value in meta.items() if key.startswith(("authors_","affiliation_"))):
        raise StudioError("ANONYMOUS_IDENTITY_FORBIDDEN")
    meta={key:value for key,value in meta.items() if key[-2:] in profile.get("metadata_languages",["zh","en"])}
    meta=prepare(meta,ast["pandoc-api-version"],output)
    removed_attributes = strip_layout_attributes(ast)
    promoted_title=None
    if ast["blocks"] and ast["blocks"][0].get("t")=="Header" and ast["blocks"][0]["c"][0]==1 and text_of(ast["blocks"][0])==meta.get("title_zh"):
        promoted_title=text_of(ast["blocks"].pop(0))
    object_map = resolve_crossrefs(ast, equations, profile["equation_numbering"])
    if request.get("document_kind")=="paper" and any(r["property"]=="bilingual_captions" and r["value"] is True for r in applied_rules):
        for node in walk(ast):
            if node.get("t") in ("Table","Figure"):
                caption=text_of(node["c"][1][1])
                if not re.search(r"\b(?:Table|Fig\.?|Figure)\s*\d",caption):
                    raise StudioError("BILINGUAL_CAPTION_REQUIRED: "+node["t"]+"; provide and verify the English caption")
    validate_assets(ast, root); validate_references(ast)
    if request.get("expected_equations") is not None and len(equations) != request["expected_equations"]:
        raise StudioError("EQUATION_COUNT_CHANGED")
    # Resolve citation keys once for both writers; explicit numerical references also work.
    write_json(output/"document.json", ast)
    cites = [n for n in walk(ast) if n.get("t") == "Cite"]
    if cites:
        if not request.get("bibliography"): raise StudioError("BIBLIOGRAPHY_REQUIRED")
        citation_args = ["pandoc", output/"document.json", "-f", "json", "-t", "json", "--citeproc", "--bibliography", confined(root, request["bibliography"]), "--csl", Path(__file__).resolve().parents[2]/"assets/numbered.csl"]
        ast = json.loads(strict_pandoc(citation_args))
        write_json(output/"document.json", ast)
    write_json(output/"document.json", ast)
    baseline, final = output/"native.docx", output/"manuscript.docx"
    # Pandoc's aligned→OMML writer emits literal '&' in eqArr rows. Translate
    # alignment-only syntax to a one-column array; author source stays unchanged.
    from copy import deepcopy
    word_ast=deepcopy(ast); converter_normalizations=[]
    for index,node in enumerate(n for n in walk(word_ast) if n.get("t")=="Math"):
        expression=node["c"][1]
        if r"\begin{aligned}" in expression:
            from .semantic_import import normalize_aligned
            normalized=normalize_aligned(expression)
            converter_normalizations.append({"math_index":index,"source":expression,"word_input":normalized,"reason":"alignment separators, not literal math symbols"})
            node["c"][1]=normalized
    write_json(output/"word-input.json",word_ast)
    write_json(output/"converter-normalizations.json",converter_normalizations)
    try:
        strict_pandoc(["pandoc", output/"word-input.json", "-f", "json", "-o", baseline, "--resource-path", root])
    except StudioError as error:
        bad=[]
        for index, node in enumerate(n for n in walk(ast) if n.get("t") == "Math"):
            probe=output/"formula-probe.md"; probe.write_text("$$"+node["c"][1]+"$$",encoding="utf-8")
            try: strict_pandoc(["pandoc",probe,"-o",output/"formula-probe.docx"])
            except StudioError:
                bad.append({"math_index":index+1,"expression":node["c"][1]})
        raise StudioError(f"{error}\nFORMULA_LOCATIONS: {bad}") from error
    configure_math_font(baseline, profile)
    shutil.copy2(master, output/"used-master.docx")
    layout = fill(baseline, meta, equations, master, profile, final)
    import zipfile
    with zipfile.ZipFile(final) as package:
        for part in ("document","settings"):
            (output/("word-"+part+".xml")).write_bytes(package.read("word/"+part+".xml"))
    texdir = output/"latex"
    # Both writers use the same reversible native layout decisions for displays.
    from copy import deepcopy
    from .docx_layout import body_only_docx
    from .qa import read_ast
    body_only_docx(final, output/"layout-bridge.docx")
    bridge = read_ast(output/"layout-bridge.docx", "docx")
    bridge_math = [n for n in walk(bridge) if n.get("t") == "Math"]
    layout_ast = deepcopy(ast)
    all_math = [n for n in walk(layout_ast) if n.get("t") == "Math"]
    if len(bridge_math) != len(all_math): raise StudioError("LAYOUT_BRIDGE_MATH_COUNT_CHANGED")
    ledger = json.loads((output/"math-layout-ledger.json").read_text(encoding="utf-8"))
    inline_ledger = json.loads((output/"inline-math-layout-ledger.json").read_text(encoding="utf-8"))
    display_index = 0; inline_index = 0; bridge_map = []
    for index, (node, rendered) in enumerate(zip(all_math, bridge_math)):
        if node["c"][0]["t"] == "DisplayMath":
            if ledger[display_index]["changes"]:
                bridge_map.append({"math_index":index,"id":equations[display_index]["id"],"original":node["c"][1],"layout":rendered["c"][1]})
                node["c"][1] = rendered["c"][1]
            display_index += 1
        else:
            if inline_ledger[inline_index]:
                bridge_map.append({"math_index":index,"id":"inline-"+str(inline_index),"original":node["c"][1],"layout":rendered["c"][1]})
                node["c"][1] = rendered["c"][1]
            inline_index += 1
    write_json(output/"shared-layout-map.json",bridge_map)
    main = write_latex(ast, equations, meta, profile, texdir, layout_ast)
    write_json(output/"layout-document.json",layout_ast)
    for node in walk(ast):
        if node.get("t") == "Image":
            relative = node["c"][-1][0]; target = confined(texdir, relative); target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(confined(root, relative), target)
    run(["libreoffice", "-env:UserInstallation=file:///tmp/rps-lo-"+str(os.getpid()), "--headless", "--convert-to", "pdf:writer_pdf_Export", "--outdir", output, final], timeout=300)
    if not (output/"manuscript.pdf").exists(): raise StudioError("DOCX_RENDER_FAILED")
    (output/"manuscript.pdf").rename(output/"word-compat-proof.pdf")
    word_pdf=inspect_output_pdf(output/"word-compat-proof.pdf",output/"previews/word-compat-proof")
    write_json(output/"word-compat-proof.pdf.json",word_pdf)
    word_pdf["page_flow"]=check_page_flow(output/"word-compat-proof.pdf",profile)
    word_geometry=check_column_geometry(output/"word-compat-proof.pdf",profile,ast,meta)
    write_json(output/"word-column-geometry.json",word_geometry)
    acceptance_errors=[]
    from .math_proof import prove
    if equations:
        isolated_math=prove(final,output/"isolated-math-proof")
        write_json(output/"isolated-math-summary.json",isolated_math)
        if isolated_math["missing"]: acceptance_errors.append("WORD_MATH_GLYPHS_MISSING: "+", ".join(r["label"] for r in isolated_math["missing"]))
    if equations:
        labels=[e["id"] if profile["equation_numbering"]=="preserve" else str(e["ordinal"]) for e in equations]
        try: word_pdf["equation_visibility"]=check_equation_visibility(output/"word-compat-proof.pdf",labels)
        except StudioError as error: acceptance_errors.append(str(error))
        from .equation_alignment import measure
        try: word_pdf["equation_alignment"]=measure(output/"word-compat-proof.pdf",equations,profile)
        except StudioError as error: acceptance_errors.append(str(error))
    for _ in range(2):
        run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "main.tex"], cwd=texdir, timeout=300)
    log = (texdir/"main.log").read_text(encoding="utf-8", errors="replace")
    if "Missing character:" in log: raise StudioError("MISSING_GLYPH: see latex/main.log")
    overflow = [float(n) for n in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide\)", log)]
    if any(n > 2 for n in overflow): acceptance_errors.append(f"LATEX_OVERFLOW: {overflow}")
    shutil.copy2(texdir/"main.pdf", output/"latex-proof.pdf")
    pdfs = {"word-compat-proof.pdf":word_pdf,"latex-proof.pdf":inspect_output_pdf(output/"latex-proof.pdf",output/"previews/latex-proof")}
    write_json(output/"latex-proof.pdf.json",pdfs["latex-proof.pdf"])
    latex_geometry=check_column_geometry(output/"latex-proof.pdf",profile,ast,meta)
    write_json(output/"latex-column-geometry.json",latex_geometry)
    if word_geometry["violations"] or latex_geometry["violations"]:
        acceptance_errors.append("BODY_COLUMN_OVERFLOW: see *-column-geometry.json")
    try: content = check_roundtrips(ast, baseline, final, texdir/"body.tex", output)
    except StudioError as error:
        content={"status":"failed","error":str(error)}; acceptance_errors.append(str(error))
    docx = check_docx(final,profile)
    mapping = {e["id"]: {"ordinal": e["ordinal"], "display": e["id"] if profile["equation_numbering"] == "preserve" else str(e["ordinal"])} for e in equations}
    write_json(output/"reference-map.json", {"equations": mapping, "literature": "shared resolved AST", "objects": object_map})
    report = {"build": "passed", "automatic_acceptance": "failed" if acceptance_errors else "passed", "visual_review": "blocked" if acceptance_errors else "pending", "model_gate": gate,
              "input_sha256": digest(source), "layout": layout, "docx": docx, "content": content, "pdfs": pdfs,
              "font_substitution": {"fonts": profile["fonts"], "exact_reference_match": False, "reason": "Open-source portable proof fonts"},
              "renderer": {"word_pdf": "LibreOffice compatibility rendering, not Microsoft Word native", "latex_pdf": "XeLaTeX"}}
    report["source_title_promoted_to_front_matter"]=promoted_title
    report["font_substitution"]["observed_word_fonts"]=sorted({font for page in word_pdf["pages"] for font in page["fonts"]})
    report["font_substitution"]["word_compatibility_note"]="LibreOffice may substitute StarMath fonts when importing OMML; observed PDF fonts are reported separately from fonts encoded in the editable Word mother."
    report["template"] = template_identity
    report["content_layout_attributes_removed"] = removed_attributes
    report["implementation_version"] = __import__("studio").__version__
    report["execution"] = {"run_id":os.environ["GITHUB_RUN_ID"],"skill_commit":os.environ.get("GITHUB_SHA"),"input_commit":request.get("input_commit"),"input_files":{p.relative_to(root).as_posix():digest(p) for p in root.rglob("*") if p.is_file()}}
    report["editable_outputs"] = {"manuscript.docx":digest(final),"latex/main.tex":digest(main)}
    write_json(output/"acceptance.json", report)
    report["errors"]=acceptance_errors
    write_json(output/"acceptance.json", report)
    from .reporting import publish
    publish(output,report)
    if acceptance_errors: raise StudioError("AUTOMATIC_ACCEPTANCE_FAILED: "+"; ".join(acceptance_errors))
    return report
