"""Position identified captions; never confuse equation-layout tables and data."""
import re
from .docx_layout import W,is_equation_table
from .vendor.ptlib.ooxml import set_child
from .runtime import require_actions,StudioError
def text(element): return "".join(n.text or "" for n in element.iter(W+"t"))
def arrange(doc,p):
    require_actions()
    moved=0
    positions=p.get("captions",{"table":"above","figure":"below"})
    for table in doc.tables:
        element=table._tbl
        if is_equation_table(element): continue
        neighbors=[element.getprevious(),element.getnext()]
        caption=next((n for n in neighbors if n is not None and n.tag==W+"p" and re.match(r"^(?:表\s*\d|Table\s+\d)",text(n))),None)
        if caption is None: raise StudioError("TABLE_CAPTION_MISSING")
        if positions["table"]=="below":
            if element.getnext() is not caption: element.addnext(caption); moved+=1
            for par in element.findall(W+"tr")[-1].iter(W+"p"):
                set_child(par.find(W+"pPr"),"keepNext",{"w:val":"1"})
        else:
            if element.getprevious() is not caption: element.addprevious(caption); moved+=1
            set_child(caption.find(W+"pPr"),"keepNext",{"w:val":"1"})
    for image in list(doc._element.body):
        if image.tag!=W+"p" or not list(image.iter(W+"drawing")): continue
        neighbors=[image.getprevious(),image.getnext()]
        caption=next((n for n in neighbors if n is not None and n.tag==W+"p" and re.match(r"^(?:图\s*\d|Fig\.?\s*\d|Figure\s+\d)",text(n))),None)
        # Pandoc may put image and caption text in one paragraph: do not silently assert compliance.
        if caption is None: raise StudioError("FIGURE_CAPTION_MISSING_OR_INLINE")
        if positions["figure"]=="above":
            if image.getprevious() is not caption: image.addprevious(caption); moved+=1
            set_child(caption.find(W+"pPr"),"keepNext",{"w:val":"1"})
        else:
            if image.getnext() is not caption: image.addnext(caption); moved+=1
            set_child(image.find(W+"pPr"),"keepNext",{"w:val":"1"})
    return moved
