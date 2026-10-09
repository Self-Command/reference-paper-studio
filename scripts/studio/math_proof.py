"""Render each display in isolation to catch hidden/clipped mathematical glyphs."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import re
import unicodedata
import pdfplumber
from docx import Document
from docx.oxml import OxmlElement
from .runtime import require_actions, run, write_json, StudioError
from .docx_layout import W, M, is_equation_table
from .vendor.ptlib.ooxml import set_child


def glyphs(text):
    # Unicode font alphabets map to their letter identity, never operator deletion.
    return Counter(c for c in unicodedata.normalize("NFKC",text) if not c.isspace() and c not in "\u200b\u200c\u200d\ufeff")


def prove(path, directory):
    require_actions()
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    doc=Document(path); body=doc._element.body
    tables=[deepcopy(t._tbl) for t in doc.tables if is_equation_table(t._tbl)]
    expected=[]
    for table in tables:
        expression="".join(t.text or "" for t in table.iter(M+"t"))
        label="".join(t.text or "" for t in table.iter(W+"t"))
        expected.append({"label":label,"glyphs":glyphs(expression)})
    for element in list(body):
        if element.tag!=W+"sectPr": body.remove(element)
    # Fixed table widths remain identical. One isolation page per display.
    columns=body.find(W+"sectPr").find(W+"cols"); columns.set(W+"num","1")
    for index,table in enumerate(tables):
        if index:
            par=OxmlElement("w:p"); props=OxmlElement("w:pPr")
            set_child(props,"pageBreakBefore"); par.append(props); body.insert(len(body)-1,par)
        body.insert(len(body)-1,table)
    source=directory/"isolated.docx"; doc.save(source)
    run(["libreoffice","-env:UserInstallation=file:///tmp/rps-math-proof","--headless","--convert-to","pdf","--outdir",directory,source],timeout=300)
    report=[]
    with pdfplumber.open(directory/"isolated.pdf") as pdf:
        if len(pdf.pages)!=len(expected): raise StudioError("ISOLATED_EQUATION_PAGINATION_CHANGED")
        for page,item in zip(pdf.pages,expected):
            text=page.extract_text() or ""; observed=glyphs(text.replace(item["label"],""))
            missing=dict(item["glyphs"]-observed)
            report.append({"label":item["label"],"missing":missing,"expected_glyphs":dict(item["glyphs"]),"observed_glyphs":dict(observed)})
    write_json(directory/"glyph-preservation.json",report)
    run(["pdftoppm","-r","100","-png",directory/"isolated.pdf",directory/"equation"],timeout=300)
    return {"equations":len(report),"missing":[r for r in report if r["missing"]],"normalization":"NFKC font alphabets and whitespace only"}
