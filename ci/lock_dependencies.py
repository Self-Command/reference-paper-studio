"""Record full resolved Python dependencies and wheel hashes in cloud."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions,run,digest,write_json
require_actions()
root=Path(__file__).resolve().parents[1]; output=root/"build/dependency-provenance"; output.mkdir(parents=True,exist_ok=True)
freeze=run([sys.executable,"-m","pip","freeze"])
(output/"resolved.lock").write_text(freeze,encoding="utf-8")
run([sys.executable,"-m","pip","download","--no-deps","-r",output/"resolved.lock","--dest",output/"packages"],timeout=180)
records=[{"file":p.name,"sha256":digest(p)} for p in (output/"packages").iterdir() if p.is_file()]
write_json(output/"hashes.json",records)
# Downloaded distributions are not needed in user artifacts.
import shutil
shutil.rmtree(output/"packages")
