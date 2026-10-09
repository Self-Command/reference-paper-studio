"""CALS adapter: native column breaks, repeated headers and actual-source audit."""
from pathlib import Path
import json
import re
from .runtime import require_actions, run, StudioError


BEGIN = "% RPS-CALS-BEGIN "
END = "% RPS-CALS-END"


def render(table, api, output, caption_position="above", rules=None):
    require_actions()
    count = len(table["c"][2])
    if count < 1: raise StudioError("EMPTY_TABLE")
    headers = table["c"][3][1]
    rows = [row for body in table["c"][4] for row in body[2]+body[3]] + table["c"][5][1]
    if not headers: raise StudioError("TABLE_HEADER_REQUIRED: continuation needs a verified header")

    def tex(blocks):
        return run(["pandoc", "-f", "json", "-t", "latex", "--wrap=none"],
                   input_text=json.dumps({"pandoc-api-version":api,"meta":{},"blocks":blocks})).strip()

    def row_tex(row):
        cells = row[1]
        if len(cells)!=count or any(cell[2]!=1 or cell[3]!=1 for cell in cells):
            raise StudioError("UNSUPPORTED_MERGED_TABLE: use a regular content table")
        return r"\brow" + "".join(r"\cell{"+tex(cell[4])+"}" for cell in cells) + r"\erow" + "\n"

    caption = tex(table["c"][1][1])
    if not caption: raise StudioError("TABLE_CAPTION_REQUIRED")
    rules = rules or {"top_rule_pt":1,"header_rule_pt":.5,"bottom_rule_pt":1}
    # CALS uses a shared frame rule; reject unequal top/bottom instead of
    # silently claiming a different registered border policy was applied.
    if rules["top_rule_pt"]!=rules["bottom_rule_pt"]:
        raise StudioError("UNSUPPORTED_TABLE_FRAME_RULE: CALS requires equal top/bottom rules")
    return _compose(caption,"".join(row_tex(row) for row in headers),"".join(row_tex(row) for row in rows),count,caption_position,rules)


def _compose(caption,headers,rows,count,caption_position,rules):
    continued = "（续）" if re.search(r"[\u4e00-\u9fff]",caption) else " (continued)"
    caption_call = r"\par\noindent\RPSCaption\ifnum\value{rpsTableSegment}>1\relax{}"+continued+r"\fi\par"
    head = r"\stepcounter{rpsTableSegment}" + "\n"
    if caption_position=="above": head += caption_call + "\n"
    head += "% RPS-HEADER-BEGIN\n"+headers+"% RPS-HEADER-END\n"
    foot = r"\lastrule" + (caption_call if caption_position=="below" else "")
    widths = "".join(r"{\dimexpr\linewidth/"+str(count)+r"\relax}" for _ in range(count))
    return (BEGIN+str(count)+"\n"+r"\par\begingroup\makeatletter"+"\n"+
            r"\def\RPSCaption{"+caption+"}\n"+r"\setcounter{rpsTableSegment}{0}"+"\n"+
            r"\begin{calstable}\colwidths{"+widths+"}\n"+
            r"\cals@paddingL=3pt\cals@paddingR=3pt\cals@paddingT=2pt\cals@paddingB=2pt"+"\n"+
            r"\def\cals@cs@width{0pt}\def\cals@framecs@width{0pt}\def\cals@rs@width{0pt}"+"\n"+
            r"\def\cals@framers@width{"+str(rules["top_rule_pt"])+"pt}"+
            r"\def\cals@bodyrs@width{"+str(rules["header_rule_pt"])+"pt}\n"+
            r"\thead{"+head+"}\n"+r"\tfoot{"+foot+"}\n"+
            "% RPS-ROWS-BEGIN\n"+rows+"% RPS-ROWS-END\n"+
            r"\end{calstable}\makeatother\endgroup\par"+"\n"+END+"\n")


def _group(text, start):
    """Read generated TeX braces; escapes cannot close a cell or caption."""
    if start>=len(text) or text[start]!="{": raise StudioError("CALS_AUDIT_GROUP_EXPECTED")
    depth=1; index=start+1
    while index<len(text):
        slash_count=0; back=index-1
        while back>=0 and text[back]=="\\": slash_count+=1; back-=1
        if slash_count%2==0:
            if text[index]=="{": depth+=1
            elif text[index]=="}": depth-=1
        if depth==0: return text[start+1:index],index+1
        index+=1
    raise StudioError("CALS_AUDIT_UNBALANCED_GROUP")


def _rows(text, columns):
    rows=[]; index=0
    while index<len(text):
        if text[index].isspace(): index+=1; continue
        if not text.startswith(r"\brow",index): raise StudioError("CALS_AUDIT_UNEXPECTED_ROW_CONTENT")
        index+=len(r"\brow"); cells=[]
        while True:
            while index<len(text) and text[index].isspace(): index+=1
            if not text.startswith(r"\cell",index): break
            index+=len(r"\cell"); value,index=_group(text,index); cells.append(value)
        if len(cells)!=columns or not text.startswith(r"\erow",index):
            raise StudioError("CALS_AUDIT_CELL_COUNT_CHANGED")
        index+=len(r"\erow"); rows.append(cells)
    return rows


def reader_text(text):
    """Normalize actual CALS cells once, never reconstruct them from input AST.

    Only the controlled generated table grammar is accepted. Continuation
    decorators are layout tokens; caption/cells are read from the actual TeX.
    This adapts Pandoc's reader, which has no CALS table handler.
    """
    require_actions()
    pattern=re.compile(r"% RPS-CALS-BEGIN (\d+)\n(.*?)% RPS-CALS-END",re.S)
    def canonical(match):
        columns=int(match.group(1)); source=match.group(2)
        if source.count(r"\begin{calstable}")!=1 or source.count(r"\end{calstable}")!=1:
            raise StudioError("CALS_AUDIT_TABLE_REGION_CHANGED")
        name=r"\def\RPSCaption"
        if source.count(name)!=1: raise StudioError("CALS_AUDIT_CAPTION_DEFINITION_CHANGED")
        caption,_=_group(source,source.index(name)+len(name))
        # Both aliases must still be present; a defined but unrendered caption
        # is not evidence that the visible document retained its title.
        if source.count(r"\RPSCaption")!=2: raise StudioError("CALS_AUDIT_CAPTION_CALL_CHANGED")
        def region(name):
            begin="% RPS-"+name+"-BEGIN\n"; end="% RPS-"+name+"-END"
            if source.count(begin)!=1 or source.count(end)!=1:
                raise StudioError("CALS_AUDIT_REGION_CHANGED: "+name)
            return source.split(begin,1)[1].split(end,1)[0]
        headers=_rows(region("HEADER"),columns); rows=_rows(region("ROWS"),columns)
        if not headers: raise StudioError("CALS_AUDIT_HEADER_LOST")
        header_begin=source.index(r"\thead")+len(r"\thead")
        header,_=_group(source,header_begin)
        position="above" if r"\RPSCaption" in header else "below"
        def rule_value(name):
            matches=re.findall(r"\\def\\cals@"+name+r"@width\{([0-9.]+)pt\}",source)
            if len(matches)!=1: raise StudioError("CALS_AUDIT_RULE_CHANGED")
            return matches[0]
        rules={"top_rule_pt":rule_value("framers"),"header_rule_pt":rule_value("bodyrs")}
        rules["bottom_rule_pt"]=rules["top_rule_pt"]
        # Reject any unexpected text/commands outside the audited content
        # groups, rather than hiding them during reader normalization.
        expected=_compose(caption,region("HEADER"),region("ROWS"),columns,position,rules).rstrip("\n")
        if expected!=match.group(0): raise StudioError("CALS_AUDIT_GENERATED_GRAMMAR_CHANGED")
        spec="".join(r"p{0.1\linewidth}" for _ in range(columns))
        row_lines=lambda values:"\n".join(" & ".join(row)+r"\\" for row in values)
        return (r"\begin{longtable}{"+spec+"}\n"+r"\caption{"+caption+r"}\tabularnewline"+"\n"+
                row_lines(headers)+"\n"+r"\endhead"+"\n"+row_lines(rows)+"\n"+r"\end{longtable}")
    normalized,count=pattern.subn(canonical,text)
    if r"\begin{calstable}" in normalized or BEGIN in normalized or END in normalized:
        raise StudioError("CALS_AUDIT_UNRECOGNIZED_TABLE")
    return normalized


def reader_copy(source, output):
    require_actions()
    target=Path(output)/"latex-layout-reader.tex"
    target.write_text(reader_text(Path(source).read_text(encoding="utf-8")),encoding="utf-8")
    return target
