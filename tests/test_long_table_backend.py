"""Cloud feasibility check of upstream CALS, before adopting it in exports."""
import re
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
