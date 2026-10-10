"""Semantic breakpoints exercised on native Pandoc math in Actions."""
from copy import deepcopy
from docx import Document
from studio.runtime import run
from studio.docx_layout import M
from studio.math_layout import wrap,tree,restore


def test_quantifier_predicate_keeps_a_fitting_scalar_relation_together(tmp_path):
    source=tmp_path/'predicate.md'
    source.write_text(r'$$\exists k\in\{0,\ldots,n-1\},h\in\{0,\ldots,m-1\}:Q(k,h)=1$$',encoding='utf-8')
    native=tmp_path/'predicate.docx';run(['pandoc',source,'-o',native])
    doc=Document(native);formula=next(doc._element.iter(M+'oMath'));original=deepcopy(formula)
    changes=wrap(formula,110)
    assert changes and tree(restore(formula,changes))==tree(original)
    row_texts=[''.join(t.text or '' for t in row.iter(M+'t')) for array in formula.iter(M+'eqArr') for row in array.findall(M+'e')]
    assert not any(text.strip()=='=1' for text in row_texts),row_texts
    assert any('Q(k,h)=1' in text for text in row_texts),row_texts


def test_long_scalar_relation_is_not_forced_into_an_undersized_row(tmp_path):
    source=tmp_path/'wide.md'
    source.write_text(r'$$a_1+a_2+a_3+a_4+a_5+a_6+a_7+a_8=1$$',encoding='utf-8')
    native=tmp_path/'wide.docx';run(['pandoc',source,'-o',native])
    formula=next(Document(native)._element.iter(M+'oMath'));original=deepcopy(formula)
    changes=wrap(formula,65)
    assert tree(restore(formula,changes))==tree(original)
    assert any(len(array.findall(M+'e'))>1 for array in formula.iter(M+'eqArr'))
