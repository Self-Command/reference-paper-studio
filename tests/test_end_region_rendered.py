import re
import pdfplumber
from studio.composition import load_composition
from studio.manuscript import parse
from studio.latex_layout import write_latex
from studio.runtime import run
from studio.qa import check_column_geometry


def test_diagnostic_cuted_short_probe_can_share_page_without_proving_real_model(tmp_path):
    _,profile=load_composition("reference-journal-v1","2.0.0")
    profile["english_abstract_position"]="end"
    profile["latex_end_backend"]="cuted-strip"
    source=tmp_path/"short.md"
    source.write_text("# Registered body\n\n"+"Short body paragraphs retain native column layout and original content. "*18,encoding="utf-8")
    ast,equations=parse(source,tmp_path)
    metadata={"title_zh":"登记摘要区域","abstract_zh":"本例仅测试固定区域。",
              "keywords_zh":["测试"],"title_en":"Registered end abstract",
              "abstract_en":"The final abstract uses a full width region on the same page when sufficient space is available. "*3,
              "keywords_en":["end region","fixed template"]}
    texdir=tmp_path/"latex"
    write_latex(ast,equations,metadata,profile,texdir)
    run(["xelatex","-interaction=nonstopmode","-halt-on-error","main.tex"],cwd=texdir)
    proof=texdir/"main.pdf"
    with pdfplumber.open(proof) as pdf:
        assert len(pdf.pages)==1
        text=pdf.pages[0].extract_text()
        compact=re.sub(r"\s+","",text)
        assert "Registeredendabstract" in compact and "endregion" in compact
        assert text.index("Registered body") < text.index("Registered end abstract")
    assert check_column_geometry(proof,profile,ast,metadata)["violations"]==[]
