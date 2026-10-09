"""Use explicitly declared font bytes in an isolated Actions font directory."""
from pathlib import Path
import os,shutil
from .runtime import require_actions,confined,digest,run,StudioError,write_json

def resolve_faces(fonts):
    """Resolve exact families and TTC faces, without accepting fontconfig fallback."""
    require_actions()
    records={}
    for role,family in fonts.items():
        records[role]={}
        for shape,style in (("upright","Regular"),("bold","Bold"),("italic","Italic"),("bolditalic","Bold Italic")):
            fields=run(["fc-match","-f","%{file}\n%{index}\n%{family}\n%{postscriptname}\n",family+":style="+style]).splitlines()
            if len(fields)!=4 or family.casefold() not in {part.strip().casefold() for part in fields[2].split(",")}:
                raise StudioError("MISSING_FONT: exact family "+family+" ("+shape+")")
            file,index,names,postscript=fields
            if not index.isdecimal() or not Path(file).is_file():raise StudioError("FONT_FACE_UNRESOLVED: "+family)
            from fontTools.ttLib import TTFont
            with TTFont(file,fontNumber=int(index)) as font:
                cff_names=font["CFF "].cff.fontNames if "CFF " in font else []
            records[role][shape]={"family":family,"families":names,"file":Path(file).name,"index":int(index),"postscript_name":postscript,"cff_names":cff_names,"sha256":digest(file),"collection":Path(file).suffix.lower() in (".ttc",".otc")}
    return records

def fontspec_options(faces):
    """Collection indices are fixed from actual fontconfig matches, not guessed."""
    require_actions()
    keys={"upright":"UprightFeatures","bold":"BoldFeatures","italic":"ItalicFeatures","bolditalic":"BoldItalicFeatures"}
    options=["FontIndex="+str(faces["upright"]["index"])] if faces["upright"]["collection"] else []
    options += [keys[shape]+"={FontIndex="+str(face["index"])+"}" for shape,face in faces.items() if face["collection"]]
    return "["+",".join(options)+"]" if options else ""

def fontspec_declaration(command,family,faces):
    """TTC FontIndex applies to files; a family-name lookup may discard it."""
    require_actions()
    if not any(face["collection"] for face in faces.values()):return command+"{"+family+"}"
    paths={}
    styles={"upright":"Regular","bold":"Bold","italic":"Italic","bolditalic":"Bold Italic"}
    for shape,face in faces.items():
        path=run(["fc-match","-f","%{file}",family+":style="+styles[shape]]).strip()
        if Path(path).name!=face["file"] or digest(path)!=face["sha256"]:raise StudioError("FONT_FACE_FINGERPRINT_MISMATCH: "+family)
        if any(char in path for char in ("{","}","%","#","\\")):raise StudioError("FONT_PATH_UNSAFE: "+family)
        paths[shape]=path
    options=fontspec_options(faces)[1:-1]
    directories={str(Path(path).parent) for path in paths.values()}
    if len(directories)!=1:raise StudioError("FONT_COLLECTION_DIRECTORY_MISMATCH: "+family)
    options="Path={"+str(Path(paths["upright"]).parent)+"/},"+options
    for shape,key in (("bold","BoldFont"),("italic","ItalicFont"),("bolditalic","BoldItalicFont")):
        options+=","+key+"={"+Path(paths[shape]).name+"}"
    return command+"{"+Path(paths["upright"]).name+"}["+options+"]"

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
