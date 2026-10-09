"""Fetch public official assets and extract evidence only inside Actions."""
from pathlib import Path
import sys,json,urllib.request,zipfile,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions,write_json,digest,run
require_actions()
root=Path(__file__).resolve().parents[1]
sources={
 "gmcm-rules-2026":("https://cpipc.acge.org.cn/sysFile/downFile.do?fileId=97a93e3a9e074738aea95eea986508f2","docx"),
 "gmcm-template-2026":("https://cpipc.acge.org.cn/sysFile/downFile.do?fileId=a730b312331e492baad17b248bad6b51","docx"),
 "seet-writing-template":("https://www.sys-ele.com/attached/file/20210316/20210316135031_500.doc","doc"),
 "cjms-writing-rules":("https://www.zgglkx.com/fileup/1003-207x/ITEM/20241015170318.doc","doc"),
 "setp-latex":("https://sysengi.cjoe.ac.cn/CN/item/downloadFile.do?uuid=e4d02914149c49a3afe11dd1acc48f1f","zip"),
 "ieee-access-word":("https://ieeeaccess.ieee.org/wp-content/uploads/2025/08/Access-Template-2024.docx","docx"),
 "ieee-access-latex":("https://ieeeaccess.ieee.org/wp-content/uploads/2026/05/ACCESS_latex_template_20260513-1-1.zip","zip")}
records=[];output=root/"build/official-sources"; output.mkdir(parents=True,exist_ok=True)
for key,(url,extension) in sources.items():
    target=output/(key+"."+extension)
    record={"id":key,"url":url,"status":"pending","redistribution_permission":"not_asserted; excluded from install package"}
    try:
        request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 ReferencePaperStudio source verification"})
        with urllib.request.urlopen(request,timeout=60) as response: content=response.read()
        if extension in ("zip","docx") and not content.startswith(b"PK"): raise ValueError("Downloaded body is not a ZIP/DOCX")
        if extension=="doc" and not content.startswith(bytes.fromhex("d0cf11e0a1b11ae1")): raise ValueError("Downloaded body is not legacy DOC")
        target.write_bytes(content); record["sha256"]=digest(target)
        if extension=="doc":
            run(["libreoffice","-env:UserInstallation=file:///tmp/rps-source-"+key,"--headless","--convert-to","docx","--outdir",output,target],timeout=120)
            target=target.with_suffix("docx")
        if extension in ("docx","doc"):
            run(["pandoc",target,"-t","markdown","-o",output/(key+".md")])
            run(["libreoffice","-env:UserInstallation=file:///tmp/rps-preview-"+key,"--headless","--convert-to","pdf","--outdir",output,target],timeout=120)
            pdf=target.with_suffix("pdf")
            if pdf.is_file(): run(["pdftoppm","-f","1","-l","4","-r","90","-png",pdf,output/(key+"-page")])
        else:
            with zipfile.ZipFile(target) as package:
                record["archive_paths"]=package.namelist()
                # Read template text; do not execute any downloaded code/class.
                texts={name:package.read(name).decode("utf-8",errors="replace") for name in package.namelist() if name.lower().endswith((".tex",".cls",".sty","license",".txt"))}
                write_json(output/(key+"-text.json"),texts)
        record["status"]="extracted_not_yet_reviewed"
    except Exception as error: record.update(status="failed",error=str(error))
    records.append(record)
    print(json.dumps(record,ensure_ascii=False),flush=True)
write_json(output/"source-manifest.json",records)
# A network/source failure is an explicit unready capability, not a false pass.
if any(r["status"]=="failed" for r in records): raise RuntimeError("OFFICIAL_SOURCE_INCOMPLETE: see source-manifest.json")
