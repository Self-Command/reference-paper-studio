"""Build reproducible candidate mothers; candidates cannot be used as releases."""
from pathlib import Path
import sys, os, json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions,write_json
from studio.registry import build
require_actions()
root=Path(__file__).resolve().parents[1]
os.environ["RPS_REGISTRY_ROOT"]=str(root/"build/templates")
records=[]
for path in sorted((root/"templates").glob("*/template.json")):
    item=json.loads(path.read_text(encoding="utf-8"))
    target=build(item["id"],item["version"])
    records.append({"template_id":item["id"],"version":item["version"],"assets":str(target.relative_to(root)),"state":"candidate"})
write_json(root/"build/template-candidates.json",records)

