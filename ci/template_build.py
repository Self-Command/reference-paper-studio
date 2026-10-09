"""Generate version assets on Actions; local entry refuses execution."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from studio.runtime import require_actions
require_actions()
from studio.locked_template import create_templates
create_templates(Path(__file__).resolve().parents[1]/"build/templates")
