"""XeLaTeX template generated from the same AST as Word."""
from pathlib import Path
from copy import deepcopy
import json
import re
from .runtime import require_actions, run
from .manuscript import latex_ast, walk


def portable_table_columns(body, ast):
    # Pandoc 3.1's calculated p{(...)*\\real{...}} cannot be read back by its
    # LaTeX reader. Use ordinary p-width columns, retaining the entire table body.
    tables=[n for n in walk(ast) if n.get("t")=="Table"]
    offset=0
    for table in tables:
        match=re.search(r"\\begin\{longtable\}(?:\[[^\]]*\])?",body[offset:])
        if not match: raise ValueError("Missing LaTeX table")
        start=offset+match.end()
        while body[start].isspace(): start+=1
        if body[start]!="{": raise ValueError("Missing LaTeX table column specification")
        depth=1; end=start+1
        while depth:
            if body[end]=="{" and body[end-1]!="\\": depth+=1
            elif body[end]=="}" and body[end-1]!="\\": depth-=1
            end+=1
        count=len(table["c"][2]); spec="{@{}"+"".join("p{"+str(round(.94/count,4))+r"\linewidth}" for _ in range(count))+"@{}}"
        body=body[:start]+spec+body[end:]; offset=start+len(spec)
    return body


def escape(text):
    return "".join({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}.get(c,c) for c in str(text))


def front(meta, english=False, roles=None):
    suffix = "_en" if english else "_zh"
    output=[]
    for key in ("title", "authors", "affiliation", "abstract", "keywords"):
        if roles is not None and key not in roles: continue
        value=meta.get(key+suffix, "")
        if isinstance(value,list):value="; ".join(value)
        if not value:continue
        rendered=meta.get("_meta_tex",{}).get(key+suffix,escape(value))
        if key=="title":output.append(r"\begin{center}\Large\bfseries "+rendered+r"\end{center}")
        elif key in ("authors","affiliation"):output.append(r"\begin{center}"+rendered+r"\end{center}")
        else:
            label=("Abstract: " if english else "摘要：") if key=="abstract" else ("Keywords: " if english else "关键词：")
            # XeTeX accepts Unicode control-word letters. An explicit group
            # terminates \noindent before a Chinese metadata label.
            output.append(r"\noindent{}"+(rendered if key+suffix in meta.get("_meta_tex",{}) else r"\textbf{"+label+"}"+escape(value))+"\n\n")
    return "\n".join(output)


def column_table(table, api, output, caption_position="above"):
    """Independent rows can break between columns, never across the gutter."""
    from .runtime import StudioError
    count = len(table["c"][2])
    rows = list(table["c"][3][1])
    for body in table["c"][4]: rows += body[2]+body[3]
    rows += table["c"][5][1]
    caption = table["c"][1][1]
    pieces = []
    def tex(blocks):
        path = Path(output)/"cell.json"
        path.write_text(json.dumps({"pandoc-api-version":api,"meta":{},"blocks":blocks},ensure_ascii=False),encoding="utf-8")
        return run(["pandoc",path,"-f","json","-t","latex","--wrap=none"]).strip()
    caption_tex=r"\begin{center}"+tex(caption)+r"\end{center}" if caption else ""
    if caption and caption_position=="above": pieces.append(caption_tex)
    spec = "@{}"+"".join("p{\\dimexpr\\linewidth/"+str(count)+"-6pt\\relax}" for _ in range(count))+"@{}"
    for number, row in enumerate(rows):
        cells = row[1]
        if len(cells) != count or any(c[2] != 1 or c[3] != 1 for c in cells):
            raise StudioError("UNSUPPORTED_MERGED_TABLE: use a regular content table")
        values = [tex(cell[4]) for cell in cells]
        rule = r"\toprule" if number == 0 else ""
        end = r"\midrule" if number == len(table["c"][3][1])-1 else r"\bottomrule" if number == len(rows)-1 else ""
        pieces.append("\\noindent\\begin{tabular}{"+spec+"}"+rule+"\n"+" & ".join(values)+r"\\"+end+"\n\\end{tabular}\\par\n")
    if caption and caption_position=="below": pieces.append(caption_tex)
    return "".join(pieces)


def write_latex(ast, equations, metadata, profile, output, layout_ast=None):
    require_actions()
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    data=latex_ast(ast,equations,profile["equation_numbering"])
    ast_path=output/"source.json";ast_path.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    body=run(["pandoc",ast_path,"-f","json","-t","latex","--wrap=none"])
    body=portable_table_columns(body, ast)
    (output/"body.tex").write_text(body, encoding="utf-8")
    # Keep table/figure captions on the agreed sides regardless of Pandoc defaults.
    page=profile["page"]["margin_cm"]
    preamble=r"""\documentclass[10pt,a4paper]{article}
\usepackage{fontspec,xeCJK}
\setmainfont{LATINFONT}
\setCJKmainfont{CJKFONT}
\xeCJKsetup{PunctStyle=plain}
\usepackage[top=TOPcm,bottom=BOTTOMcm,left=LEFTcm,right=RIGHTcm]{geometry}
\usepackage{amsmath,amssymb,mathtools,graphicx,booktabs,longtable,array,multirow}
\usepackage{multicol,caption,hyperref,xurl,xcolor,calc,etoolbox,enumitem,float}
\usepackage{unicode-math}
\setmathfont{Latin Modern Math}
\setkeys{Gin}{keepaspectratio}
\setlength{\LTpre}{0pt}
\setlength{\LTpost}{0pt}
\hypersetup{hidelinks}
\setlength{\columnsep}{0.6cm}
\setlength{\parindent}{2em}
\setlength{\emergencystretch}{1em}
\setlength{\tabcolsep}{3pt}
\setcounter{secnumdepth}{0}
\newcounter{none}
\captionsetup[table]{position=top}
\captionsetup[figure]{position=bottom}
\captionsetup{labelformat=empty}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\newcommand{\passthrough}[1]{#1}
\newcommand{\pandocbounded}[1]{#1}
\newenvironment{CSLReferences}[2]{\begin{list}{}{\setlength{\leftmargin}{1em}\setlength{\itemindent}{-1em}}\item[]}{\end{list}}
\newcommand{\CSLBlock}[1]{#1}
\newcommand{\CSLLeftMargin}[1]{#1}
\newcommand{\CSLRightInline}[1]{#1}
\newcommand{\CSLIndent}[1]{#1}
\begin{document}
"""
    preamble=preamble.replace("LATINFONT",profile["fonts"]["latin"]).replace("CJKFONT",profile["fonts"]["cjk"])
    preamble=preamble.replace(r"\setmathfont{Latin Modern Math}",r"\setmathfont{"+profile["fonts"]["math"]+"}")
    from .fonts import resolve_faces,fontspec_options
    faces=profile.get("font_faces") or resolve_faces(profile["fonts"])
    for role,command in (("latin",r"\setmainfont"),("cjk",r"\setCJKmainfont"),("math",r"\setmathfont")):
        declaration=command+"{"+profile["fonts"][role]+"}"
        preamble=preamble.replace(declaration,declaration+fontspec_options(faces[role]))
    preamble=preamble.replace("[10pt,a4paper]", f"[{profile['body_size_pt']}pt,a4paper]")
    preamble=preamble.replace(r"\columnsep}{0.6cm}",r"\columnsep}{"+str(profile["page"].get("column_spacing_cm",0.6))+"cm}")
    for key,value in page.items():preamble=preamble.replace(key.upper()+"cm",str(value)+"cm")
    # A single body multicols region. Content has no section/column authority.
    layout=latex_ast(layout_ast or ast,equations,profile["equation_numbering"]); blocks=[]
    for block in layout["blocks"]:
        if block.get("t") == "Table":
            blocks.append({"t":"RawBlock","c":["latex",column_table(block,ast["pandoc-api-version"],output,profile.get("captions",{}).get("table","above"))]})
        elif block.get("t")=="Figure":
            fragment={"pandoc-api-version":ast["pandoc-api-version"],"meta":{},"blocks":block["c"][2]}
            image_tex=run(["pandoc","-f","json","-t","latex","--wrap=none"],input_text=json.dumps(fragment))
            caption_fragment={"pandoc-api-version":ast["pandoc-api-version"],"meta":{},"blocks":block["c"][1][1]}
            caption_tex=run(["pandoc","-f","json","-t","latex","--wrap=none"],input_text=json.dumps(caption_fragment))
            ordered=(caption_tex+"\n"+image_tex) if profile.get("captions",{}).get("figure","below")=="above" else (image_tex+"\n"+caption_tex)
            blocks.append({"t":"RawBlock","c":["latex",r"\begin{center}"+ordered+r"\end{center}"]})
        else: blocks.append(block)
    layout["blocks"]=blocks
    layout_path=output/"layout.json";layout_path.write_text(json.dumps(layout,ensure_ascii=False),encoding="utf-8")
    body=run(["pandoc",layout_path,"-f","json","-t","latex","--wrap=none"])
    body=body.replace(r"\begin{figure}",r"\begin{figure}[H]")
    # Fixed width for every illustration, regardless of its source attributes.
    body=re.sub(r"\\includegraphics(?:\[[^\]]*\])?",lambda m:r"\includegraphics[width=\linewidth,keepaspectratio]",body)
    (output/"layout-body.tex").write_text(body,encoding="utf-8")
    header=front(metadata,roles=profile.get("front_roles"))
    if profile["english_abstract_position"]=="front":header+="\n"+front(metadata,True,profile.get("front_roles"))
    end=front(metadata,True,profile.get("front_roles")) if profile["english_abstract_position"]=="end" else ""
    if end:
        # Fixed end-region contract: short title/abstract/keywords stay one
        # unit, instead of stranding the abstract continuation on a new page.
        # Oversized groups fail through the renderer's vertical overflow
        # diagnostics; do not shrink fonts to hide an unfit region.
        end="\n\\par\\noindent\\begin{minipage}{\\textwidth}\n"+end+"\n\\end{minipage}\\par\n"
    if profile.get("front_separate_page"): header+=r"\clearpage"
    columns=profile.get("body_columns",2)
    wrapped=("\n\\begin{multicols}{"+str(columns)+"}\n"+body+"\n\\end{multicols}\n") if columns>1 else "\n"+body+"\n"
    (output/"main.tex").write_text(preamble+header+wrapped+end+"\n\\end{document}\n",encoding="utf-8")
    return output/"main.tex"
