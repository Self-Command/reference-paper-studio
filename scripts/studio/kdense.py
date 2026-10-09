"""Bounded adaptation of MIT K-Dense offline evidence checks."""
from pathlib import Path
import os
import sys
import json
from .runtime import require_actions, StudioError, run, write_json
ROOT=Path(__file__).parent/"vendor/kdense"
TOOLS={"consistency":ROOT/"scientific-writing/check_consistency.py",
       "claims":ROOT/"scientific-writing/audit_claims.py",
       "claim_evidence":ROOT/"peer-review/validate_claim_evidence.py",
       "doi":ROOT/"citation-management/doi_to_bibtex.py"}
def check_consistency(registry, output):
    require_actions()
    # Registry is explicitly authored from semantic objects, never every digit in prose.
    import subprocess
    result=subprocess.run([sys.executable,str(TOOLS["consistency"]),str(registry)],text=True,capture_output=True,env={**os.environ,"PYTHONPATH":str(Path(__file__).resolve().parents[1])})
    try: report=json.loads(result.stdout)
    except ValueError: raise StudioError("UPSTREAM_AUDIT_FAILED: "+result.stderr[-2000:])
    write_json(output,report)
    if result.returncode: raise StudioError("EVIDENCE_INCONSISTENT: "+str(output))
    return report
