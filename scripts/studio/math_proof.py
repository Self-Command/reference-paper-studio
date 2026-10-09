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
    tables=[]; inline_index=0; active=False
    for element in body:
        if element.tag==W+"bookmarkStart" and element.get(W+"name")=="RPS_BODY":active=True;continue
        if element.tag==W+"bookmarkEnd" and element.get(W+"id")=="9181":active=False
        if not active:continue
        if is_equation_table(element):tables.append(deepcopy(element));continue
        for math in element.iter(M+"oMath"):
            inline_index+=1
            table=doc.add_table(rows=1,cols=2);table._tbl.getparent().remove(table._tbl)
            # Diagnostic isolation keeps the actual editable expression intact.
            table.cell(0,0).paragraphs[0]._p.append(deepcopy(math))
            table.cell(0,1).text="(inline-"+str(inline_index)+")"
            tables.append(table._tbl)
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
        from .locked_template import paragraph
        body.insert(len(body)-1,paragraph("Formula", "Equation"))
        body.insert(len(body)-1,table)
    source=directory/"isolated.docx"; doc.save(source)
    run(["libreoffice","-env:UserInstallation=file:///tmp/rps-math-proof","--headless","--convert-to","pdf","--outdir",directory,source],timeout=300)
    report=[]
    with pdfplumber.open(directory/"isolated.pdf") as pdf:
        if len(pdf.pages)!=len(expected): raise StudioError("ISOLATED_EQUATION_PAGINATION_CHANGED")
        for page,item in zip(pdf.pages,expected):
            text=page.extract_text() or ""; observed=glyphs(text.replace(item["label"],"").replace("Formula",""))
            missing=dict(item["glyphs"]-observed)
            report.append({"label":item["label"],"missing":missing,"expected_glyphs":dict(item["glyphs"]),"observed_glyphs":dict(observed)})
    write_json(directory/"glyph-preservation.json",report)
    run(["pdftoppm","-r","100","-png",directory/"isolated.pdf",directory/"equation"],timeout=300)
    return {"equations":len(report),"display_equations":len(report)-inline_index,"inline_equations":inline_index,"missing":[r for r in report if r["missing"]],"normalization":"NFKC font alphabets and whitespace only"}
