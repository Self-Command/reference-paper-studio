import subprocess
import os
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("entry",["scripts/ci_run.py","ci/template_build.py","ci/validate_skill.py","ci/regression.py","ci/package.py","ci/template_matrix.py","ci/modular_regression.py","ci/repeat_regression.py","ci/matrix_regression.py","ci/official_sources.py","ci/diagnose_artifacts.py","ci/measure_display_artifacts.py","ci/suite_check.py","ci/lock_dependencies.py","scripts/studio/vendor/latex_to_omml.py"])
def test_processing_entry_rejects_local_environment(entry):
    environment={k:v for k,v in os.environ.items() if k not in ("GITHUB_ACTIONS","GITHUB_RUN_ID")}
    result=subprocess.run(["python",str(ROOT/entry)],env=environment,capture_output=True,text=True)
    assert result.returncode != 0
    assert "CLOUD_ONLY" in result.stderr+result.stdout


def test_new_latex_math_execution_is_blocked_before_processing(monkeypatch,tmp_path):
    from studio.latex_math import measured_widths,replace_displays
    from studio.runtime import StudioError
    monkeypatch.delenv("GITHUB_ACTIONS",raising=False)
    with pytest.raises(StudioError,match="CLOUD_ONLY"):measured_widths(tmp_path/"missing.tex",tmp_path,2)
    with pytest.raises(StudioError,match="CLOUD_ONLY"):replace_displays(r"\[x\tag{M1}\]")
