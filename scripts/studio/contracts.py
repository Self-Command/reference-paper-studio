"""Shared contracts. Executable validation is Actions-only."""
from pathlib import Path
import json
from jsonschema import Draft202012Validator
from .runtime import require_actions, StudioError
ROOT = Path(__file__).resolve().parents[2]

def validate(value, name):
    require_actions()
    schema = json.loads((ROOT/"schemas"/(name+".schema.json")).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise StudioError("CONTRACT_INVALID: "+name+": "+"; ".join(str(list(e.path))+": "+e.message for e in errors[:12]))
    return value
