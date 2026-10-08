"""Run only in Actions: validate the shipped skill interface and links."""
import os
from pathlib import Path
import re
import sys
import yaml

if os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("GITHUB_RUN_ID"):
    sys.exit("CLOUD_ONLY: skill validation is restricted to GitHub Actions")

root = Path(__file__).resolve().parents[1]
text = (root / "SKILL.md").read_text(encoding="utf-8")
header = yaml.safe_load(text.split("---", 2)[1])
assert header["name"] == "reference-paper-studio"
assert 25 <= len(header["description"]) < 1024
for link in re.findall(r"\]\((references/[^)]+)\)", text):
    assert (root / link).is_file(), link
ui = yaml.safe_load((root / "agents/openai.yaml").read_text(encoding="utf-8"))
assert "$reference-paper-studio" in ui["interface"]["default_prompt"]
assert 25 <= len(ui["interface"]["short_description"]) <= 64
print("Skill metadata and reference links validated")
