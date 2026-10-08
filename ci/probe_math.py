"""Cloud-only controlled OMML renderer diagnosis; no mathematical rewriting."""
from pathlib import Path
import sys
import json
import shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions, run
from studio.manuscript import parse
from studio.docx_layout import configure_math_font, apply_layout, M
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from PIL import Image, ImageDraw

require_actions();root=Path(__file__).resolve().parents[1]
folder=root/"build/probe";folder.mkdir(parents=True,exist_ok=True)
profile=json.loads((root/"fixtures/model/profile.json").read_text())
_, equations=parse(root/"fixtures/model/model.md",folder)
equations=equations[:3]
source=folder/"probe.md"
source.write_text("# Native math renderer probe\n\nInline $x_i + y_i = z_i$.\n\n"+"\n\n".join("$$"+e["source"]+"$$" for e in equations),encoding="utf-8")
native=folder/"base.docx";run(["pandoc",source,"-o",native])
screens=[]
for mode in ("native","settings-only","explicit-runs","final-layout"):
    path=folder/(mode+".docx");shutil.copy2(native,path)
    if mode=="settings-only":
        doc=Document(path); math=doc.settings.element.find(M+"mathPr")
        if math is None: math=OxmlElement("m:mathPr");doc.settings.element.append(math)
        font=math.find(M+"mathFont")
        if font is None: font=OxmlElement("m:mathFont");math.insert(0,font)
        font.set(qn("m:val"),"Latin Modern Math");doc.save(path)
    if mode in ("explicit-runs","final-layout"): configure_math_font(path,profile)
    if mode=="final-layout": apply_layout(path,{},profile,equations)
    run(["libreoffice","-env:UserInstallation=file:///tmp/rps-probe","--headless","--convert-to","pdf","--outdir",folder,path])
    run(["pdftoppm","-f","1","-l","1","-singlefile","-r","75","-png",path.with_suffix(".pdf"),folder/mode])
    picture=Image.open(folder/(mode+".png")).convert("RGB")
    canvas=Image.new("RGB",(picture.width,picture.height+25),"white");canvas.paste(picture,(0,25));ImageDraw.Draw(canvas).text((10,5),mode,fill="black");screens.append(canvas)
montage=Image.new("RGB",(sum(p.width for p in screens),max(p.height for p in screens)),"white")
x=0
for p in screens:montage.paste(p,(x,0));x+=p.width
montage.save(folder/"comparison.png")
