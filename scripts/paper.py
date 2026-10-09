"""Local transport only: copy declared inputs, git push, query/download Actions.

No document processing, test execution, conversion or rendering is imported here.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile

DEFAULT_REPO = "Self-Command/reference-paper-studio"


def command(args, cwd=None, input_text=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", input=input_text)
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
    if spec["stage"] not in ("reference", "review", "export", "visual"): raise ValueError("Invalid stage")
    if not spec.get("files") or len(set(spec["files"])) != len(spec["files"]): raise ValueError("Explicit unique file list required")
    sources = [(name, safe_input(root, name)) for name in spec["files"]]
    info = json.loads(command(["gh", "repo", "view", args.repo, "--json", "isPrivate,defaultBranchRef"]))
    if not info["isPrivate"]: raise ValueError("Task submission requires a private repository")
    # REST transfers exactly the listed blobs; avoids cloning private fixtures or
    # depending on native Git connectivity. It performs no document processing.
    def api(path,payload=None):
        args=["gh","api","repos/"+args_repo+"/"+path]
        if payload is not None:args += ["--method","POST","--input","-"]
        return json.loads(command(args,input_text=json.dumps(payload) if payload is not None else None))
    args_repo=args.repo
    default_ref=info["defaultBranchRef"]["name"]
    parent=api("git/ref/heads/"+default_ref)["object"]["sha"]
    base_tree=api("git/commits/"+parent)["tree"]["sha"]
    tree=[];hashes={};prefix=".requests/"+spec["id"]
    for name,source in sources:
        content=source.read_bytes();hashes[name]=hashlib.sha256(content).hexdigest()
        blob=api("git/blobs",{"content":base64.b64encode(content).decode("ascii"),"encoding":"base64"})
        tree.append({"path":prefix+"/files/"+name,"mode":"100644","type":"blob","sha":blob["sha"]})
    spec["sha256"]=hashes
    blob=api("git/blobs",{"content":json.dumps(spec,ensure_ascii=False,indent=2),"encoding":"utf-8"})
    tree.append({"path":prefix+"/request.json","mode":"100644","type":"blob","sha":blob["sha"]})
    new_tree=api("git/trees",{"base_tree":base_tree,"tree":tree})
    commit=api("git/commits",{"message":"Submit document task "+spec["id"],"tree":new_tree["sha"],"parents":[parent]})["sha"]
    api("git/refs",{"ref":"refs/heads/request/"+spec["id"],"sha":commit})
    workflow_ref=args.workflow_ref or default_ref
    dispatch=["gh", "workflow", "run", "document-task.yml", "--repo", args.repo, "--ref", workflow_ref, "-f", "task_id="+spec["id"], "-f", "input_commit="+commit, "-f", "request_path="+prefix+"/request.json", "-f", "phase="+spec["stage"]]
    if spec["stage"] == "visual":
        dispatch += ["-f","artifact_run="+str(spec["artifact_run"]),"-f","artifact_name="+spec.get("artifact_name","document-task")]
    command(dispatch)
    return {"task_id": spec["id"], "input_commit": commit, "input_files": spec["files"], "workflow_ref": workflow_ref, "status": "dispatched", "runs_url": "https://github.com/"+args.repo+"/actions/workflows/document-task.yml"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    commands = parser.add_subparsers(dest="operation", required=True)
    p = commands.add_parser("submit"); p.add_argument("--root", required=True); p.add_argument("--request", required=True); p.add_argument("--workflow-ref", help="Development workflow ref; defaults to repository default branch")
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
