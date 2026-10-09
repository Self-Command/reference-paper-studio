import pytest
from studio.runtime import StudioError,run,digest
from studio.fonts import install_declared
from studio.registry import build,resolve

def test_custom_font_uses_exact_declared_bytes_and_requires_registered_variant(tmp_path,monkeypatch):
    monkeypatch.setenv("RPS_REGISTRY_ROOT",str(tmp_path/"registered"))
    source=run(["fc-match","-f","%{file}","Liberation Serif"]).strip()
    from pathlib import Path
    font=tmp_path/"selected.ttf";font.write_bytes(Path(source).read_bytes())
    request={"files":[{"path":font.name,"sha256":digest(font),"role":"font"}]}
    assets=install_declared(tmp_path,request,tmp_path/"report")
    target=build("general-modeling","1.0.0","open-serif",assets)
    identity={"id":"general-modeling","version":"1.0.0","variant":"front","font_profile":"open-serif","manifest_sha256":digest(target/"manifest.json")}
    monkeypatch.setenv("RPS_CANDIDATE_BUILD","true")
    assert resolve({**request,"template":identity})[0].is_file()
    with pytest.raises(StudioError,match="FONT_ASSET_IDENTITY_MISMATCH"):resolve({"template":identity})

def test_missing_selected_font_never_falls_back(tmp_path,monkeypatch):
    monkeypatch.setenv("RPS_REGISTRY_ROOT",str(tmp_path))
    with pytest.raises(StudioError,match="MISSING_FONT"):build("general-modeling","1.0.0","common-paper")
