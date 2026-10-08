"""Transport authorization boundaries, evaluated on Actions only."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location("paper",Path(__file__).resolve().parents[1]/"scripts/paper.py")
paper=importlib.util.module_from_spec(spec); spec.loader.exec_module(paper)


def test_transport_confines_explicit_files(tmp_path):
    (tmp_path/"allowed.md").write_text("source")
    assert paper.safe_input(tmp_path,"allowed.md").name=="allowed.md"
    with pytest.raises(ValueError): paper.safe_input(tmp_path,"../outside.md")
    with pytest.raises(ValueError): paper.safe_input(tmp_path,".")
    with pytest.raises(ValueError): paper.safe_input(tmp_path,".secret")


def test_transport_has_no_processing_imports():
    import ast
    tree=ast.parse(Path(paper.__file__).read_text())
    imported=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): imported.extend(n.name for n in node.names)
        elif isinstance(node,ast.ImportFrom): imported.append(node.module or "")
    assert not any(name.startswith(("studio","pytest","docx","pypdf","pdfplumber")) for name in imported)
