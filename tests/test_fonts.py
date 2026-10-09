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

def test_ttc_collection_uses_actual_sc_face_in_compiled_pdf(tmp_path):
    from studio.fonts import resolve_faces,fontspec_declaration
    from studio.qa import inspect_output_pdf
    fonts={"cjk":"Noto Serif CJK SC","latin":"Liberation Serif","math":"Latin Modern Math"}
    faces=resolve_faces(fonts)
    source=tmp_path/"face.tex"
    source.write_text(r"\documentclass{article}\usepackage{fontspec,xeCJK}"+fontspec_declaration(r"\setCJKmainfont",fonts["cjk"],faces["cjk"])+r"\begin{document}简体中文模型\textbf{字体测试}\end{document}",encoding="utf-8")
    run(["xelatex","-interaction=nonstopmode","-halt-on-error",source.name],cwd=tmp_path)
    observed={name.split("+")[-1] for page in inspect_output_pdf(tmp_path/"face.pdf",tmp_path/"previews")["pages"] for name in page["fonts"]}
    assert faces["cjk"]["upright"]["postscript_name"] in observed, {"faces":faces,"source":source.read_text(),"observed":sorted(observed)}
    assert faces["cjk"]["bold"]["postscript_name"] in observed
    assert not any("CJKjp" in name for name in observed)

def test_exact_family_and_registered_bytes_cannot_be_silently_substituted():
    from studio.qa import check_fonts
    with pytest.raises(StudioError,match="MISSING_FONT"):check_fonts({"fonts":{"cjk":"Serif"}})
    profile={"fonts":{"latin":"Liberation Serif"},"font_faces":{}}
    with pytest.raises(StudioError,match="FONT_FACE_FINGERPRINT_MISMATCH"):check_fonts(profile)
