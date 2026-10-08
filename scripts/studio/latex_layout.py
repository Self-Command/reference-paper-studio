"""XeLaTeX template generated from the same AST as Word."""
from pathlib import Path
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


def front(meta, english=False):
    suffix = "_en" if english else "_zh"
    output=[]
    for key in ("title", "authors", "affiliation", "abstract", "keywords"):
        value=meta.get(key+suffix, "")
        if isinstance(value,list):value="; ".join(value)
        if not value:continue
        if key=="title":output.append(r"\begin{center}\Large\bfseries "+escape(value)+r"\end{center}")
        elif key in ("authors","affiliation"):output.append(r"\begin{center}"+escape(value)+r"\end{center}")
        else:
            label=("Abstract: " if english else "摘要：") if key=="abstract" else ("Keywords: " if english else "关键词：")
            output.append(r"\noindent\textbf{"+label+"}"+escape(value)+"\n\n")
    return "\n".join(output)


def write_latex(ast, equations, metadata, profile, output):
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
\usepackage[top=TOPcm,bottom=BOTTOMcm,left=LEFTcm,right=RIGHTcm]{geometry}
\usepackage{amsmath,amssymb,mathtools,graphicx,booktabs,longtable,array,multirow}
\usepackage{multicol,caption,hyperref,xurl,xcolor,calc,etoolbox,enumitem}
\usepackage{unicode-math}
\setmathfont{Latin Modern Math}
\setlength{\LTpre}{0pt}
\setlength{\LTpost}{0pt}
\hypersetup{hidelinks}
\setlength{\columnsep}{0.6cm}
\setlength{\parindent}{2em}
\setlength{\emergencystretch}{1em}
\setlength{\tabcolsep}{3pt}
\captionsetup[table]{position=top}
\captionsetup[figure]{position=bottom}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\newcommand{\passthrough}[1]{#1}
\newenvironment{CSLReferences}[2]{\begin{list}{}{\setlength{\leftmargin}{1em}\setlength{\itemindent}{-1em}}\item[]}{\end{list}}
\newcommand{\CSLBlock}[1]{#1}
\newcommand{\CSLLeftMargin}[1]{#1}
\newcommand{\CSLRightInline}[1]{#1}
\newcommand{\CSLIndent}[1]{#1}
\begin{document}
"""
    preamble=preamble.replace("LATINFONT",profile["fonts"]["latin"]).replace("CJKFONT",profile["fonts"]["cjk"])
    preamble=preamble.replace("[10pt,a4paper]", f"[{profile['body_size_pt']}pt,a4paper]")
    preamble=preamble.replace(r"\columnsep}{0.6cm}",r"\columnsep}{"+str(profile["page"].get("column_spacing_cm",0.6))+"cm}")
    for key,value in page.items():preamble=preamble.replace(key.upper()+"cm",str(value)+"cm")
    # Use multicol for prose; displays/tables use full-width breaks for readability.
    pattern=r"(\\\[.*?\\\]|\\begin\{longtable\}.*?\\end\{longtable\}|\\begin\{figure\}.*?\\end\{figure\})"
    body=re.sub(pattern,lambda m:r"\end{multicols}"+"\n"+m.group(0)+"\n"+r"\begin{multicols}{2}",body,flags=re.S)
    header=front(metadata)
    if profile["english_abstract_position"]=="front":header+="\n"+front(metadata,True)
    end=front(metadata,True) if profile["english_abstract_position"]=="end" else ""
    (output/"main.tex").write_text(preamble+header+"\n\\begin{multicols}{2}\n"+body+"\n\\end{multicols}\n"+end+"\n\\end{document}\n",encoding="utf-8")
    return output/"main.tex"
