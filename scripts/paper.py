"""Local transport only: copy declared inputs, git push, query/download Actions.

No document processing, test execution, conversion or rendering is imported here.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile

DEFAULT_REPO = "Self-Command/reference-paper-studio"


def command(args, cwd=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode: raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


def safe_input(root, name):
    path = (root/name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Input must be an existing file beneath --root: {name}")
    if "\\" in name or ".." in PurePosixPath(name).parts or name.startswith("."):
        raise ValueError(f"Use plain slash-separated relative input paths: {name}")
    return path


def submit(args):
    root = Path(args.root).resolve()
    spec = json.loads(Path(args.request).read_text(encoding="utf-8-sig"))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", spec["id"]): raise ValueError("Invalid task id")
    if spec["stage"] not in ("reference", "review", "export"): raise ValueError("Invalid stage")
    if not spec.get("files") or len(set(spec["files"])) != len(spec["files"]): raise ValueError("Explicit unique file list required")
    sources = [(name, safe_input(root, name)) for name in spec["files"]]
    info = json.loads(command(["gh", "repo", "view", args.repo, "--json", "isPrivate,defaultBranchRef"]))
    if not info["isPrivate"]: raise ValueError("Task submission requires a private repository")
    with tempfile.TemporaryDirectory(prefix="rps-submit-") as temp:
        checkout = Path(temp)/"checkout"
        command(["gh", "repo", "clone", args.repo, checkout, "--", "--depth", "1"])
        branch = "request/"+spec["id"]
        command(["git", "checkout", "-b", branch], checkout)
        task = checkout/".requests"/spec["id"]
        hashes = {}
        for name, source in sources:
            target = task/"files"/name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
        spec["sha256"] = hashes
        (task/"request.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        command(["git", "add", "-f", "--", str(task.relative_to(checkout))], checkout)
        command(["git", "-c", "user.name=reference-paper-studio", "-c", "user.email=studio@users.noreply.github.com", "commit", "-m", "Submit document task "+spec["id"]], checkout)
        commit = command(["git", "rev-parse", "HEAD"], checkout)
        command(["git", "push", "origin", "HEAD"], checkout)
    command(["gh", "workflow", "run", "document-task.yml", "--repo", args.repo, "--ref", info["defaultBranchRef"]["name"], "-f", "task_id="+spec["id"], "-f", "input_commit="+commit, "-f", "request_path=.requests/"+spec["id"]+"/request.json"])
    return {"task_id": spec["id"], "input_commit": commit, "input_files": spec["files"], "status": "dispatched", "runs_url": "https://github.com/"+args.repo+"/actions/workflows/document-task.yml"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    commands = parser.add_subparsers(dest="operation", required=True)
    p = commands.add_parser("submit"); p.add_argument("--root", required=True); p.add_argument("--request", required=True)
    p = commands.add_parser("status"); p.add_argument("--run"); p.add_argument("--task")
    p = commands.add_parser("fetch"); p.add_argument("--run", required=True); p.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.operation == "submit": result = submit(args)
    elif args.operation == "status":
        if args.run: result = json.loads(command(["gh", "run", "view", args.run, "--repo", args.repo, "--json", "databaseId,status,conclusion,url,jobs,headSha"]))
        else:
            result = json.loads(command(["gh", "run", "list", "--repo", args.repo, "--workflow", "document-task.yml", "--limit", "50", "--json", "databaseId,status,conclusion,displayTitle,url,headSha"]))
            if args.task: result = [r for r in result if r["displayTitle"] == "Document task: "+args.task]
    else:
        command(["gh", "run", "download", args.run, "--repo", args.repo, "--dir", Path(args.output).resolve()])
        result = {"run": args.run, "output": str(Path(args.output).resolve())}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
