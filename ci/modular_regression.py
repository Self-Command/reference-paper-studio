"""Candidate regression authorized by the implementation request, not fabricated paper approval."""
from pathlib import Path
import os,sys,json,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions,digest,write_json,StudioError
from studio.registry import build
from studio.approvals import snapshot
from studio.pipeline import export
require_actions()
root=Path(__file__).resolve().parents[1]
os.environ["RPS_REGISTRY_ROOT"]=str(root/"build/templates")
os.environ["RPS_CANDIDATE_BUILD"]="true"
results=[]
for variant in ("front","end"):
    work=root/"build"/("modular-input-"+variant); work.mkdir(parents=True,exist_ok=True)
    for name in ("model.md","metadata.json"):
        shutil.copy2(root/"fixtures/model"/name,work/name)
    # Original has an unnamed parameter table. It correctly failed the first
    # run (37926336985). Use an explicitly labelled, separate format fixture;
    # do not mutate the approved/private original or call this formal approval.
    source_text=(work/"model.md").read_text(encoding="utf-8")
    source_text=source_text.replace("| 符号 | 含义与条件 |","表1 输入参数（格式回归新增题注，待作者确认）\n\n| 符号 | 含义与条件 |",1)
    (work/"model.md").write_text(source_text,encoding="utf-8")
    write_json(work/"fixture-changes.json",{"original_sha256":digest(root/"fixtures/model/model.md"),"changes":["Add explicit test-only caption to unnamed parameter table"],"original_modified":False,"formal_user_paper":False})
    master=build("reference-journal-v1","2.0.0")
    manifest=json.loads((master/"manifest.json").read_text(encoding="utf-8"))
    files=[{"path":name,"sha256":digest(work/name),"role":"manuscript" if name=="model.md" else "metadata"} for name in ("model.md","metadata.json")]
    fingerprint=snapshot({f["path"]:f["sha256"] for f in files})
    events=[]
    for kind in ("md_content","presentation","export"):
        events.append({"event_id":kind,"event_type":kind,"actor_type":"human","user_instruction":"执行批准计划P2，使用现有模型和既有开源字体进行云端格式回归；不宣称模型数学验证或正式论文批准","instruction_source":"implementation-request:P2-format-regression","content_snapshot_sha256":fingerprint,"template_manifest_sha256":digest(master/"manifest.json"),"font_profile_sha256":manifest["font_profile_sha256"],"approved_outputs":["docx","latex","docx-proof-pdf","latex-pdf","previews"]})
    write_json(work/"approvals.json",events)
    files.append({"path":"approvals.json","sha256":digest(work/"approvals.json"),"role":"approvals"})
    request={"schema_version":2,"task_id":"model-"+variant,"operation":"export","engine_commit":os.environ["GITHUB_SHA"],"input_commit":os.environ["GITHUB_SHA"],"manuscript":"model.md","metadata":"metadata.json","files":files,"approval_file":"approvals.json","approvals":{k:k for k in ("md_content","presentation","export")},"template":{"id":"reference-journal-v1","version":"2.0.0","variant":variant,"font_profile":"open-serif","manifest_sha256":digest(master/"manifest.json")},"document_kind":"model","expected_equations":30,"outputs":["docx","latex","docx-proof-pdf","latex-pdf","previews"]}
    write_json(work/"request.json",request)
    try:
        report=export(work,request,root/"build"/("modular-model-"+variant))
        results.append({"case":variant,"status":"passed"})
    except Exception as error:
        results.append({"case":variant,"status":"failed","error":str(error)})
write_json(root/"build/modular-regression.json",results)
if any(r["status"]=="failed" for r in results): raise StudioError("MODULAR_REGRESSION_FAILED")
