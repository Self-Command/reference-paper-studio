"""Use explicitly declared font bytes in an isolated Actions font directory."""
from pathlib import Path
import os,shutil
from .runtime import require_actions,confined,digest,run,StudioError,write_json

def install_declared(root,request,output):
    require_actions()
    fonts=[file for file in request.get("files",[]) if file.get("role")=="font"]
    records=[]
    # This is a runner-local font directory; font bytes are not put in build/
    # or redistributed in skill packages.
    directory=Path.home()/".local/share/fonts"/("rps-"+os.environ["GITHUB_RUN_ID"])
    for file in fonts:
        source=confined(root,file["path"])
        if digest(source)!=file["sha256"]: raise StudioError("INPUT_FINGERPRINT_MISMATCH: font "+file["path"])
        if source.suffix.lower() not in (".ttf",".otf",".ttc"): raise StudioError("FONT_FILE_UNSUPPORTED: "+file["path"])
        families=run(["fc-scan","--format","%{family}\n",source]).strip()
        if not families: raise StudioError("INVALID_FONT_FILE: "+file["path"])
        directory.mkdir(parents=True,exist_ok=True)
        target=directory/(file["sha256"]+source.suffix.lower());shutil.copy2(source,target)
        records.append({"input_path":file["path"],"sha256":file["sha256"],"families":families,"redistribution":"not_in_skill_package"})
    if records:run(["fc-cache","-f",directory])
    write_json(Path(output)/"font-assets.json",records)
    return {record["input_path"]:record["sha256"] for record in records}
