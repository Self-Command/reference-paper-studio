"""Semantic LaTeX in Markdown: structure only, never document geometry.

Some public Markdown corpora encode headings/footnotes with LaTeX wrappers.
Read these through Pandoc's LaTeX reader; keep all returned semantic content.
Unknown commands and any raw layout object still fail closed.
"""
from pathlib import Path
import json
import re
from .runtime import require_actions,run,StudioError,write_json


def expand_semantic_tex(ast,output):
    require_actions()
    records=[]
    def expand(node):
        if not isinstance(node,dict):return node
        kind=node.get("t")
        if kind not in ("RawInline","RawBlock"):return node
        format,source=node["c"]
        if format not in ("tex","latex"):raise StudioError("UNSUPPORTED_RAW_OBJECT: "+format)
        rewritten=None;reason=None
        match=re.fullmatch(r"\\(title|author|footnotetext)\s*\{(.*)\}\s*",source,re.S)
        if match:
            command,content=match.groups()
            if command=="title":rewritten=r"\section*{"+content+"}";reason="semantic title as first heading"
            elif command=="author":rewritten=content;reason="author content retained as editable body text"
            else:rewritten=content;reason="unanchored source footnote retained as an explicit source note"
        elif re.fullmatch(r"\\(?:section|subsection|subsubsection|paragraph)\*?\s*\{.*\}\s*",source,re.S):
            rewritten=source;reason="semantic heading"
        elif re.fullmatch(r"\\begin\{abstract\}.*\\end\{abstract\}\s*",source,re.S):
            rewritten=r"\section*{Abstract}"+source.replace(r"\begin{abstract}","").replace(r"\end{abstract}","")
            reason="abstract content retained under its semantic heading"
        elif kind=="RawInline" and re.fullmatch(r"\\[&%$#_{}]",source):
            records.append({"source":source,"kind":kind,"reason":"literal escaped text","replacement":[{"t":"Str","c":source[1:]}]})
            return [{"t":"Str","c":source[1:]}]
        if rewritten is None:raise StudioError("UNSUPPORTED_RAW_OBJECT: "+source[:160])
        # A permitted structural wrapper cannot smuggle formatting through its argument.
        if re.search(r"\\(?:fontsize|fontfamily|fontseries|fontshape|selectfont|tiny|scriptsize|footnotesize|small|large|Large|LARGE|huge|Huge|color|pagebreak|newpage|onecolumn|twocolumn|newgeometry|geometry|includegraphics|vspace|hspace|setlength|input|include|usepackage|documentclass|phantom|hphantom|vphantom|textcolor|resizebox|scalebox|rule|rotatebox)\b",rewritten):
            raise StudioError("CONTENT_LAYOUT_COMMAND_FORBIDDEN: "+source[:160])
        parsed=json.loads(run(["pandoc","-f","latex","-t","json"],input_text=rewritten,reject_warnings=True))
        blocks=parsed["blocks"]
        if match and match[1]=="footnotetext":blocks=[{"t":"BlockQuote","c":blocks}]
        if kind=="RawInline":
            if len(blocks)!=1 or blocks[0]["t"] not in ("Plain","Para"):raise StudioError("UNSUPPORTED_RAW_INLINE_STRUCTURE: "+source[:160])
            replacement=blocks[0]["c"]
        else:replacement=blocks
        if not replacement:raise StudioError("SEMANTIC_IMPORT_EMPTY: "+source[:160])
        records.append({"source":source,"kind":kind,"reason":reason,"replacement":replacement})
        return replacement
    def visit(value):
        if isinstance(value,list):
            result=[]
            for item in value:
                if isinstance(item,dict) and item.get("t") in ("Para","Plain"):
                    content=[n for n in item["c"] if n.get("t") not in ("Space","SoftBreak","LineBreak")]
                    structural=[n for n in content if n.get("t")=="RawInline" and n["c"][0] in ("tex","latex") and re.match(r"\\(?:title|author|footnotetext|section|subsection|subsubsection|paragraph)\b",n["c"][1])]
                    if structural:
                        # Footnotes and headings can be interleaved with source prose.
                        # Lift semantic blocks while retaining every surrounding inline.
                        segment=[]
                        for child in item["c"]:
                            if child in structural:
                                if any(n.get("t") not in ("Space","SoftBreak","LineBreak") for n in segment):result.append(visit({"t":item["t"],"c":segment}))
                                segment=[]
                                result.extend(visit(expand({"t":"RawBlock","c":child["c"]})))
                            else:segment.append(child)
                        if any(n.get("t") not in ("Space","SoftBreak","LineBreak") for n in segment):result.append(visit({"t":item["t"],"c":segment}))
                        continue
                if isinstance(item,dict) and item.get("t") in ("RawInline","RawBlock"):
                    result.extend(visit(expand(item)))
                else:result.append(visit(item))
            return result
        if isinstance(value,dict):return {key:visit(child) for key,child in value.items()}
        return value
    result=visit(ast)
    write_json(Path(output)/"semantic-import-ledger.json",records)
    return result


def normalize_aligned(expression):
    """Discard alignment markers only at the aligned level, not in cases/matrices."""
    tokens=re.split(r"(\\begin\{[^}]+\}|\\end\{[^}]+\}|(?<!\\)&)",expression)
    stack=[];output=[]
    for token in tokens:
        start=re.fullmatch(r"\\begin\{([^}]+)\}",token)
        end=re.fullmatch(r"\\end\{([^}]+)\}",token)
        if start:
            stack.append(start[1]);output.append(r"\begin{array}{l}" if start[1]=="aligned" else token)
        elif end:
            if not stack or stack.pop()!=end[1]:raise StudioError("UNBALANCED_MATH_ENVIRONMENT")
            output.append(r"\end{array}" if end[1]=="aligned" else token)
        elif token=="&" and stack and stack[-1]=="aligned":continue
        else:output.append(token)
    if stack:raise StudioError("UNBALANCED_MATH_ENVIRONMENT")
    return "".join(output)