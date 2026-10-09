"""Cloud-only execution boundary and deterministic process helpers."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


class StudioError(RuntimeError):
    pass


def require_actions():
    if os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("GITHUB_RUN_ID"):
        raise StudioError("CLOUD_ONLY: tests, conversion, compilation, rendering and validation must run in GitHub Actions.")


def run(args, cwd=None, timeout=180, input_text=None, reject_warnings=False):
    require_actions()
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout, input=input_text)
    if result.returncode or (reject_warnings and "[WARNING]" in result.stderr):
        raise StudioError(f"COMMAND_FAILED: {args[0]} ({result.returncode})\n{result.stdout[-5000:]}\n{result.stderr[-5000:]}")
    return result.stdout


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    require_actions()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def confined(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise StudioError(f"PATH_ESCAPE: {relative}")
    return path
