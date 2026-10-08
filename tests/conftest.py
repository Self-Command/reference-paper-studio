import os
import sys
from pathlib import Path

if os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("GITHUB_RUN_ID"):
    raise RuntimeError("CLOUD_ONLY: pytest must run in GitHub Actions")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
