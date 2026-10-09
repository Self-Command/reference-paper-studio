"""Measure immutable generated TeX displays on Actions; no source-run repair."""
from pathlib import Path
import json,re,sys,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions,run,write_json,digest,StudioError
require_actions()


def extract_displays(source):
    require_actions()
    records=[]
    for match in re.finditer(r"\\\[(.*?)\\tag\{([^{}]+)\}\\\]",source,re.S):
        expression,label=match.groups()
        if not re.fullmatch(r"[A-Za-z0-9.-]+",label):
            raise StudioError("UNSUPPORTED_MEASUREMENT_LABEL: "+label)
        records.append({"id":label,"expression":expression,"source_start":match.start(),"source_end":match.end()})
    if not records:raise StudioError("NO_GENERATED_DISPLAYS_TO_MEASURE")
    if len({r["id"] for r in records})!=len(records):raise StudioError("DUPLICATE_MEASUREMENT_LABEL")
    return records


def column_setup(columns):
    require_actions()
    if columns not in (1,2):raise StudioError("UNSUPPORTED_MEASUREMENT_COLUMNS")
    # e-TeX dimexpr accepts a literal multiplier, not a parenthesized integer
    # expression followed by a dimension. Resolve that integer in Python.
    return r"\setlength{\columnwidth}{\dimexpr(\textwidth-"+str(columns-1)+r"\columnsep)/"+str(columns)+r"\relax}"


def main():
    require_actions()
    artifact_root=Path("diagnostic-artifacts")
    output=Path("build/display-measurements")
    reports=[]
    for source in sorted(artifact_root.rglob("main.tex")):
        if source.parent.name!="latex" or not (source.parent.parent/"acceptance.json").is_file():continue
        accepted=json.loads((source.parent.parent/"acceptance.json").read_text(encoding="utf-8"))
        text=source.read_text(encoding="utf-8")
        preamble,separator,_=text.partition(r"\begin{document}")
        if not separator:raise StudioError("GENERATED_TEX_PREAMBLE_MISSING")
        displays=extract_displays(text)
        case=source.parent.parent.name
        folder=output/case;folder.mkdir(parents=True,exist_ok=True)
        columns=accepted.get("layout",{}).get("body_columns",2)
        body=[r"\begin{document}\pagestyle{empty}",
              column_setup(columns),
              r"\typeout{RPS-COLUMN=\the\columnwidth}"]
        for index,display in enumerate(displays):
            if index:body.append(r"\clearpage")
            label=display["id"];expression=display["expression"]
            body.extend([
                r"\setbox0=\hbox{$\displaystyle "+expression+r"$}",
                r"\setbox1=\hbox{("+label+r")}",
                r"\typeout{RPS-METRIC="+label+r"|\the\wd0|\the\ht0|\the\dp0|\the\wd1}",
                r"\noindent\begin{minipage}{\columnwidth}Formula\par",
                r"\["+expression+r"\tag{"+label+r"}\]\end{minipage}"])
        body.append(r"\end{document}")
        probe=folder/"measure.tex"
        probe.write_text(preamble+"\n"+"\n".join(body),encoding="utf-8")
        run(["xelatex","-no-shell-escape","-interaction=nonstopmode","-halt-on-error","measure.tex"],cwd=folder,timeout=180)
        log=(folder/"measure.log").read_text(encoding="utf-8",errors="replace")
        column=re.search(r"RPS-COLUMN=([0-9.]+)pt",log)
        if not column:raise StudioError("MEASUREMENT_COLUMN_MISSING")
        column_pt=float(column.group(1))
        metrics=[]
        for match in re.finditer(r"RPS-METRIC=([^|\s]+)\|\s*([0-9.]+)pt\|\s*([0-9.]+)pt\|\s*([0-9.]+)pt\|\s*([0-9.]+)pt",log):
            label,width,height,depth,number=match.groups()
            width,height,depth,number=map(float,(width,height,depth,number))
            metrics.append({"id":label,"width_tex_pt":width,"height_tex_pt":height,"depth_tex_pt":depth,
                            "number_width_tex_pt":number,"column_width_tex_pt":column_pt,
                            "centered_ams_required_tex_pt":width+2*(number+10),
                            "separate_number_region_required_tex_pt":width+number+6})
        if [r["id"] for r in metrics]!=[r["id"] for r in displays]:raise StudioError("MEASUREMENT_COUNT_CHANGED")
        import pdfplumber
        with pdfplumber.open(folder/"measure.pdf") as pdf:
            if len(pdf.pages)!=len(displays):raise StudioError("DISPLAY_DIAGNOSTIC_PAGINATION_CHANGED")
            from studio.math_proof import isolated_number_center
            for page,metric in zip(pdf.pages,metrics):
                metric["actual_isolated_number_center"]=isolated_number_center(page,"("+metric["id"]+")")
        # Preserve previews only for the objects identified by the actual review.
        selected=[]
        for index,display in enumerate(displays,1):
            if display["id"] not in ("M2","M6","M8","M10"):continue
            run(["pdftoppm","-f",str(index),"-l",str(index),"-singlefile","-r","100","-png",folder/"measure.pdf",folder/display["id"]])
            selected.append({"id":display["id"],"file":display["id"]+".png","sha256":digest(folder/(display["id"]+".png"))})
        record={"source_run":os.environ.get("SOURCE_RUN"),"source":source.as_posix(),"source_sha256":digest(source),
                "diagnostic_run":os.environ["GITHUB_RUN_ID"],"engine_commit":os.environ.get("GITHUB_SHA"),
                "measurements":metrics,"selected_previews":selected,
                "status":"measured_not_accepted","limitation":"TeX box dimensions and isolated baseline evidence; original artifacts are unchanged. No font shrink, tag raising or automatic acceptance."}
        write_json(folder/"measurements.json",record);reports.append(record)
    if not reports:raise StudioError("DISPLAY_DIAGNOSTIC_SOURCE_MISSING")
    write_json(output/"summary.json",reports)


if __name__=="__main__":main()
