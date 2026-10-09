"""Separate build, automated checks, actual review completion and user decision."""
from pathlib import Path
import json
from .runtime import require_actions,write_json,digest
def publish(output,report):
    require_actions()
    output=Path(output)
    status={"build_status":"succeeded" if report.get("build")=="passed" else "failed","automatic_status":"passed" if report.get("automatic_acceptance")=="passed" else "failed","visual_status":"not_run","visual_result":"not_assessed","delivery_status":"awaiting_user" if report.get("automatic_acceptance")=="passed" else "diagnostic_only"}
    write_json(output/"status.json",status)
    previews=[]
    for name,pdf in report.get("pdfs",{}).items():
        for page,item in enumerate(pdf.get("previews",[]),1): previews.append({"output":name,"page":page,"path":"previews/"+name.removesuffix(".pdf")+"/"+item["file"],"sha256":item["sha256"]})
    write_json(output/"preview-index.json",previews)
    text="# 云端构建检查报告\n\n本文件是自动报告，逐页视觉复检尚未执行。是否为稿件首版由项目版本记录确认。\n\n"+"\n".join("- "+key+": "+value for key,value in status.items())+"\n\nWord校样由LibreOffice生成，LaTeX校样由XeLaTeX生成。分页可以不同，内容必须保留。\n\n"+"\n".join("- "+str(error) for error in report.get("errors",[report.get("error")] ) if error)+"\n\n未经批准不自动修复。本运行产物独立保留，不覆盖首版或其他运行。\n"
    (output/"复检报告.md").write_text(text,encoding="utf-8")
    # Write last so the index and human-readable report are fingerprinted too.
    files={p.relative_to(output).as_posix():digest(p) for p in output.rglob("*") if p.is_file() and p.name!="build-manifest.json"}
    write_json(output/"build-manifest.json",{"schema_version":1,"execution":report.get("execution"),"template":report.get("template"),"status":status,"files":files})
