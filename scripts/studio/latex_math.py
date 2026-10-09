"""Fixed TeX formula/number slots, audited from the actual generated source."""
from pathlib import Path
import re
from .runtime import require_actions,run,StudioError,write_json


MACRO=r"""\newcommand{\RPSdisplay}[3]{%
\begingroup
\setbox0=\hbox{$\displaystyle #1$}%
\setbox1=\hbox{(#2)}%
\ifdim\wd0>\dimexpr\linewidth-33.5bp\relax
\PackageError{reference-paper-studio}{OBJECT_DOES_NOT_FIT: #2}{Formula exceeds the fixed number reservation}%
\fi
\ifdim\wd1>27.5bp
\PackageError{reference-paper-studio}{NUMBER_DOES_NOT_FIT: #2}{Number exceeds the registered area}%
\fi
\par\addvspace{\abovedisplayskip}\noindent
\hbox to\linewidth{\hbox to\dimexpr\linewidth-33.5bp\relax{\hfil
\ifnum#3=1 $\vcenter{\box0}$\else\box0\fi\hfil}%
\hskip6bp\hbox to27.5bp{\hfil\box1}}%
\par\addvspace{\belowdisplayskip}
\endgroup}
"""


def render(expression,label):
    require_actions()
    if not re.fullmatch(r"[A-Za-z0-9.-]+",label):raise StudioError("UNSUPPORTED_FIXED_MATH_LABEL: "+label)
    if r"\tag" in expression:raise StudioError("NESTED_FIXED_MATH_TAG")
    multiline=bool(re.search(r"\\begin\{(?:array|matrix|cases|aligned|alignedat|gathered)\}",expression))
    return r"\RPSdisplay{"+expression+"}{"+label+"}{"+str(int(multiline))+"}"


def replace_displays(text):
    require_actions()
    return re.sub(r"\\\[(.*?)\\tag\{([^{}]+)\}\\\]",lambda match:render(*match.groups()),text,flags=re.S)


def argument(text,start):
    if start>=len(text) or text[start]!="{":raise StudioError("FIXED_MATH_ARGUMENT_MISSING")
    depth=1;position=start+1
    while position<len(text) and depth:
        if text[position]=="\\":position+=2;continue
        if text[position]=="{":depth+=1
        elif text[position]=="}":depth-=1
        position+=1
    if depth:raise StudioError("FIXED_MATH_ARGUMENT_UNCLOSED")
    return text[start+1:position-1],position


def reader_text(text):
    """Decode the actual generated adapter; never rebuild math from source AST."""
    require_actions()
    marker=r"\RPSdisplay";position=0;result=[]
    while True:
        start=text.find(marker,position)
        if start<0:result.append(text[position:]);break
        result.append(text[position:start]);cursor=start+len(marker)
        expression,cursor=argument(text,cursor)
        label,cursor=argument(text,cursor)
        anchor,cursor=argument(text,cursor)
        if anchor not in ("0","1") or render(expression,label)!=text[start:cursor]:
            raise StudioError("FIXED_MATH_ADAPTER_CHANGED")
        result.append(r"\["+expression+r"\tag{"+label+r"}\]")
        position=cursor
    return "".join(result)


def measured_widths(main,output,columns):
    """Native TeX dimensions before acceptance; shared with the cloud diagnosis."""
    require_actions()
    source=Path(main).read_text(encoding="utf-8")
    # Main still uses ordinary displays at this stage; numbers are not shifted
    # or accepted here. Final rendering uses the fixed adapter after fitting.
    displays=re.findall(r"\\\[(.*?)\\tag\{([^{}]+)\}\\\]",source,re.S)
    if not displays:return []
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    preamble=source.split(r"\begin{document}",1)[0]
    body=[r"\begin{document}",r"\setlength{\columnwidth}{\dimexpr(\textwidth-"+str(columns-1)+r"\columnsep)/"+str(columns)+r"\relax}",r"\typeout{RPS-COLUMN=\the\columnwidth}"]
    for expression,label in displays:
        if not re.fullmatch(r"[A-Za-z0-9.-]+",label):raise StudioError("UNSUPPORTED_FIXED_MATH_LABEL")
        body.extend([r"\setbox0=\hbox{$\displaystyle "+expression+r"$}",r"\setbox1=\hbox{("+label+r")}",r"\typeout{RPS-FIT="+label+r"|\the\wd0|\the\wd1}"])
    body.append(r"\end{document}")
    (folder/"measure.tex").write_text(preamble+"\n"+"\n".join(body),encoding="utf-8")
    run(["xelatex","-no-shell-escape","-interaction=nonstopmode","-halt-on-error","measure.tex"],cwd=folder,timeout=180)
    log=(folder/"measure.log").read_text(encoding="utf-8",errors="replace")
    column=re.search(r"RPS-COLUMN=([0-9.]+)pt",log)
    if not column or "Missing character:" in log:raise StudioError("FIXED_MATH_MEASUREMENT_FAILED")
    # OOXML/PDF use 72 points per inch; TeX uses 72.27 points per inch.
    factor=72/72.27;column_bp=float(column.group(1))*factor
    records=[]
    for match in re.finditer(r"RPS-FIT=([^|\s]+)\|\s*([0-9.]+)pt\|\s*([0-9.]+)pt",log):
        label,width,number=match.groups()
        records.append({"label":label,"math_width_bp":float(width)*factor,"number_width_bp":float(number)*factor,
                        "column_width_bp":column_bp,"formula_slot_bp":column_bp-33.5,
                        "fits":float(width)*factor<=column_bp-33.5 and float(number)*factor<=27.5})
    if [r["label"] for r in records]!=[label for _,label in displays]:raise StudioError("FIXED_MATH_MEASUREMENT_COUNT_CHANGED")
    write_json(folder/"widths.json",records)
    return records
