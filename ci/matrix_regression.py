"""All nine candidate layouts, using marked synthetic content; no official claims."""
from pathlib import Path
import os,sys,json
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions,digest,write_json
from studio.approvals import snapshot
from studio.pipeline import export
from studio.registry import build
require_actions()
root=Path(__file__).resolve().parents[1]
os.environ["RPS_REGISTRY_ROOT"]=str(root/"build/templates")
os.environ["RPS_CANDIDATE_BUILD"]="true"
results=[]
for template_path in sorted((root/"templates").glob("*/template.json")):
    descriptor=json.loads(template_path.read_text(encoding="utf-8"))
    if descriptor["id"]=="reference-journal-v1": continue
    key=descriptor["id"]; folder=root/"build/matrix-inputs"/key; folder.mkdir(parents=True,exist_ok=True)
    image=Image.new("RGB",(640,220),"white"); draw=ImageDraw.Draw(image);draw.rectangle((25,25,615,195),outline="black",width=3);draw.text((50,90),"SYNTHETIC FORMAT FIXTURE: SOURCE -> TEMPLATE -> CHECK",fill="black");image.save(folder/"flow.png")
    (folder/"manuscript.md").write_text(r'''---
title_zh: "合成排版验收样例"
title_en: "Synthetic formatting acceptance fixture"
abstract_zh: "本材料只测试排版，数字不是实验结果。验证行内公式 $x_i^2/(1+x_i)$。"
abstract_en: "This is a synthetic format test, not research evidence. It preserves inline mathematics $x_i^2/(1+x_i)$."
keywords_zh: ["格式测试"]
keywords_en: ["format test"]
---

# Introduction

This synthetic document checks {{eq:E1}}, {{eq:E2}}, {{eq:E3}}, {{fig:flow}}, and {{tab:T1}}. These values are test fixtures and are not empirical research results.

We keep the original content, editable mathematical structure, and explicit object identities. The layout follows the registered template rather than physical attributes supplied by an author.

# Mathematical objects

$$\sum_{i=1}^{n}\frac{x_i^2}{1+y_i}=\lambda.\tag{E1}$$

$$f(x)=\begin{cases}\frac{x^2}{1+x},&x>0,\\0,&x\le0.\end{cases}\tag{E2}$$

$$\begin{aligned}\min\quad &\sum_{i=1}^{n}c_i x_i\\\text{s.t.}\quad &A x\le b,\\&x_i\ge0.\end{aligned}\tag{E3}$$

# Objects and captions

Table 1 Synthetic parameter values

| Parameter | Value | Unit |
|---|---:|---|
| A | -1.25 | ms |
| B | 3.5 | Hz |

![Figure 1 Synthetic workflow](flow.png){#fig:flow width=200%}

# Conclusion

The manuscript is only a layout fixture. Successful conversion is not mathematical validation, official submission compliance, or authorization to publish research.
''',encoding="utf-8")
    target=build(key,descriptor["version"]); manifest=json.loads((target/"manifest.json").read_text(encoding="utf-8"))
    files=[{"path":name,"sha256":digest(folder/name),"role":"manuscript" if name.endswith(".md") else "image"} for name in ("manuscript.md","flow.png")]
    snap=snapshot({f["path"]:f["sha256"] for f in files})
    outputs=["docx","latex","docx-proof-pdf","latex-pdf","previews"]
    events=[{"event_id":kind,"event_type":kind,"actor_type":"human","user_instruction":"实施批准计划P4，使用标注合成稿件和既有开源字体进行云端工程检查；不代替九类MD结构审定或正式投稿授权","instruction_source":"implementation-request:P4-synthetic-fixtures","content_snapshot_sha256":snap,"template_manifest_sha256":digest(target/"manifest.json"),"font_profile_sha256":manifest["font_profile_sha256"],"approved_outputs":outputs} for kind in ("md_content","presentation","export")]
    write_json(folder/"approvals.json",events);files.append({"path":"approvals.json","sha256":digest(folder/"approvals.json"),"role":"approvals"})
    request={"schema_version":2,"task_id":"matrix-"+key,"operation":"export","engine_commit":os.environ["GITHUB_SHA"],"input_commit":os.environ["GITHUB_SHA"],"template":{"id":key,"version":descriptor["version"],"variant":"front","font_profile":"open-serif","manifest_sha256":digest(target/"manifest.json")},"manuscript":"manuscript.md","files":files,"approval_file":"approvals.json","approvals":{k:k for k in ("md_content","presentation","export")},"outputs":outputs,"document_kind":"format","expected_equations":3}
    write_json(folder/"request.json",request)
    try:
        report=export(folder,request,root/"build/matrix"/key)
        results.append({"id":key,"status":"passed","template_state":"candidate","official_compliance":False,"md_approved":False})
    except Exception as error:
        results.append({"id":key,"status":"failed","error":str(error)})
        print(key+": "+str(error),flush=True)
write_json(root/"build/matrix-summary.json",results)
print(json.dumps(results,ensure_ascii=False),flush=True)
if any(item["status"]=="failed" for item in results): raise RuntimeError("TEMPLATE_MATRIX_FAILED")
