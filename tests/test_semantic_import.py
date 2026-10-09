"""Generic mixed Markdown/semantic LaTeX support; all parser tests are cloud-only."""
import pytest
from studio.manuscript import parse,walk,text_of
from studio.runtime import StudioError
from studio.semantic_import import normalize_aligned


def test_structural_wrappers_preserve_author_abstract_and_unanchored_notes(tmp_path):
    source=tmp_path/"source.md"
    source.write_text(r"""\title{Generic mathematical paper}

\author{A. Author ${}^{1}$}

\begin{abstract}
A preserved abstract with $x^2$.
\end{abstract}

\section*{1. Problem}

Body with $x_i$ and escaped \& text.

\footnotetext{Source note with $z_j$.}

\[\sum_{i=1}^{n}x_i=\frac{1}{2}\tag{F1}\]
""",encoding="utf-8")
    ast,equations=parse(source,tmp_path/"out")
    assert "Generic mathematical paper" in text_of(ast["blocks"])
    assert "A. Author" in text_of(ast["blocks"]) and "Source note" in text_of(ast["blocks"])
    assert len([n for n in walk(ast) if n.get("t")=="Math"])==5
    assert equations[0]["id"]=="F1"
    assert not any(n.get("t") in ("RawBlock","RawInline") for n in walk(ast))


@pytest.mark.parametrize("source",[r"\section*{\fontsize{22}{24}\selectfont Injected}",r"\author{\onecolumn Injection}",r"\begin{table}content\end{table}","<div>raw html</div>"])
def test_semantic_wrappers_cannot_override_template(source,tmp_path):
    path=tmp_path/"source.md";path.write_text(source,encoding="utf-8")
    with pytest.raises(StudioError,match="CONTENT_LAYOUT_COMMAND_FORBIDDEN|UNSUPPORTED_RAW_OBJECT"):
        parse(path,tmp_path/"out")


def test_nested_alignment_preserves_cases_and_matrix_columns():
    source=r"\begin{aligned}f(x)&=\begin{cases}a&x>0\\b&x\le0\end{cases}\\G&=\begin{matrix}a&b\\c&d\end{matrix}\end{aligned}"
    result=normalize_aligned(source)
    assert result.count("&")==4
    assert r"\begin{cases}a&x>0" in result and r"\begin{matrix}a&b" in result
    assert result.startswith(r"\begin{array}{l}f(x)=")


def test_unbalanced_alignment_is_an_explicit_failure():
    with pytest.raises(StudioError,match="UNBALANCED_MATH_ENVIRONMENT"):
        normalize_aligned(r"\begin{aligned}x&=1\end{matrix}")