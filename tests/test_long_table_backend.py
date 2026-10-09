"""Cloud feasibility check of upstream CALS, before adopting it in exports."""
import re
import pytest
from studio.runtime import run

def test_upstream_cals_repeats_headers_and_bottom_captions_in_native_columns(tmp_path):
    rows="\n".join(r"\brow\cell{Entry"+str(i)+r"}\cell{Value"+str(i)+r"}\erow" for i in range(160))
    source=r"""\documentclass[twocolumn,a4paper]{article}
\usepackage[margin=2.2cm]{geometry}
\usepackage{multicol,cals}
\makeatletter
\begin{document}
\par\begin{calstable}
\colwidths{{\dimexpr\linewidth/2\relax}{\dimexpr\linewidth/2\relax}}
\def\cals@cs@width{0pt}\def\cals@framecs@width{0pt}
\def\cals@rs@width{0pt}\def\cals@framers@width{1pt}\def\cals@bodyrs@width{0.5pt}
\thead{\brow\cell{Code}\cell{Description}\erow}
\tfoot{\lastrule\par\noindent Table 1 Stress dataset\par}
ROWS
\end{calstable}
\end{document}
""".replace("ROWS",rows)
    (tmp_path/"table.tex").write_text(source,encoding="utf-8")
    run(["xelatex","-interaction=nonstopmode","-halt-on-error","table.tex"],cwd=tmp_path)
    import pdfplumber
    with pdfplumber.open(tmp_path/"table.pdf") as pdf:
        text="\n".join(page.extract_text() or "" for page in pdf.pages)
        assert sorted(int(i) for i in re.findall(r"Entry(\d+)",text))==list(range(160))
        segments=0
        for page in pdf.pages:
            for left,right in ((0,page.width/2),(page.width/2,page.width)):
                words=[word for word in page.extract_words() if left<=word["x0"]<right]
                if not any(word["text"].startswith("Entry") for word in words):continue
                segments+=1
                assert sum(word["text"]=="Code" for word in words)==1
                assert sum(word["text"]=="dataset" for word in words)==1
                assert next(word["top"] for word in words if word["text"]=="dataset")>max(word["top"] for word in words if word["text"].startswith("Entry"))
        assert segments>=4


def table_ast(count=90):
    inline=lambda value:[{"t":"Str","c":value}]
    block=lambda value:[{"t":"Plain","c":inline(value)}]
    cell=lambda value:[["",[],[]],{"t":"AlignDefault"},1,1,block(value)]
    row=lambda values:[["",[],[]],[cell(value) for value in values]]
    table={"t":"Table","c":[["tbl:stress",[],[]],[None,[{"t":"Plain","c":inline("Table 1 Stress dataset")}]],
            [[{"t":"AlignDefault"},{"t":"ColWidthDefault"}] for _ in range(2)],
            [["",[],[]],[row(["Code","Description"])]],
            [[["",[],[]],0,[],[row(["Entry"+str(i),"Value"+str(i)]) for i in range(count)]]],
            [["",[],[]],[]]]}
    return {"pandoc-api-version":[1,23,1],"meta":{},"blocks":[table]}


def test_registered_export_repeats_header_caption_and_preserves_actual_cells(tmp_path):
    from studio.composition import load_composition
    from studio.latex_layout import write_latex
    from studio.latex_tables import reader_copy
    from studio.qa import read_ast,assert_text
    ast=table_ast(160); _,profile=load_composition("reference-journal-v1","2.0.0")
    write_latex(ast,[],{},profile,tmp_path)
    run(["xelatex","-interaction=nonstopmode","-halt-on-error","main.tex"],cwd=tmp_path)
    from pathlib import Path
    import shutil
    proof=Path("build/long-table-probe"); proof.mkdir(parents=True,exist_ok=True)
    for name in ("main.tex","main.pdf","layout-body.tex"):
        shutil.copy2(tmp_path/name,proof/name)
    from studio.qa import inspect_output_pdf
    inspect_output_pdf(proof/"main.pdf",proof/"previews")
    import pdfplumber
    with pdfplumber.open(tmp_path/"main.pdf") as pdf:
        segments=[]; entries=[]
        for page in pdf.pages:
            for left,right in ((0,page.width/2),(page.width/2,page.width)):
                # Fixed 10 pt serif spaces are narrower than pdfplumber's
                # default 3 pt joining tolerance. Do not merge the caption's
                # separate words merely because its font is smaller than the
                # feasibility probe's 12 pt Computer Modern.
                words=[word for word in page.extract_words(x_tolerance=1) if left<=word["x0"]<right]
                data=[word for word in words if re.fullmatch(r"Entry\d+",word["text"])]
                if not data:continue
                entries += [int(word["text"][5:]) for word in data]
                assert sum(word["text"]=="Code" for word in words)==1
                caption=[word for word in words if word["text"]=="dataset"]
                assert len(caption)==1 and caption[0]["top"]>max(word["top"] for word in data)
                assert sum(word["text"]=="(continued)" for word in words)==bool(segments)
                segments.append(words)
        assert len(segments)>=3 and sorted(entries)==list(range(160))
    source=tmp_path/"layout-body.tex"
    actual=read_ast(reader_copy(source,tmp_path),"latex")
    assert_text(ast,actual,"CALS actual source")
    # The audit reads emitted content, so changed data must be detected even
    # though the input AST and portable body.tex are still unchanged.
    source.write_text(source.read_text().replace("Value41","Value999"))
    changed=read_ast(reader_copy(source,tmp_path),"latex")
    from studio.runtime import StudioError
    with pytest.raises(StudioError,match="CONTENT_CHANGED"):assert_text(ast,changed,"CALS changed cell")


def test_cals_reader_rejects_hidden_text_or_unrendered_caption(tmp_path):
    from studio.latex_tables import render,reader_text
    from studio.runtime import StudioError
    ast=table_ast(2)
    source=render(ast["blocks"][0],ast["pandoc-api-version"],tmp_path,"below")
    with pytest.raises(StudioError,match="GENERATED_GRAMMAR_CHANGED"):
        reader_text(source.replace(r"\end{calstable}",r"\end{calstable} Hidden changed content"))
    with pytest.raises(StudioError,match="CAPTION_CALL_CHANGED"):
        reader_text(source.replace(r"\noindent\RPSCaption",r"\noindent Missing title"))


def test_new_table_entrypoints_reject_local_processing(monkeypatch,tmp_path):
    from studio.latex_tables import render,reader_text,reader_copy
    from studio.runtime import StudioError
    monkeypatch.delenv("GITHUB_ACTIONS",raising=False)
    for function in (lambda:render({},[],tmp_path),lambda:reader_text(""),lambda:reader_copy("missing",tmp_path)):
        with pytest.raises(StudioError,match="CLOUD_ONLY"):function()
