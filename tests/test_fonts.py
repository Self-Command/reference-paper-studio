import pytest
from studio.runtime import StudioError,run,digest
from studio.fonts import install_declared,resolve_faces
from studio.registry import build,resolve

def test_custom_font_uses_exact_declared_bytes_and_requires_registered_variant(tmp_path,monkeypatch):
    monkeypatch.setenv("RPS_REGISTRY_ROOT",str(tmp_path/"registered"))
    source=run(["fc-match","-f","%{file}","Liberation Serif"]).strip()
    from pathlib import Path
    font=tmp_path/"selected.ttf";font.write_bytes(Path(source).read_bytes())
    request={"files":[{"path":font.name,"sha256":digest(font),"role":"font"}]}
    before=resolve_faces({"latin":"Liberation Serif"})
    with monkeypatch.context() as environment:
        environment.setenv("XDG_DATA_HOME",str(tmp_path/"font-inventory"))
        assets=install_declared(tmp_path,request,tmp_path/"report")
        target=build("general-modeling","1.0.0","open-serif",assets)
        identity={"id":"general-modeling","version":"1.0.0","variant":"front","font_profile":"open-serif","manifest_sha256":digest(target/"manifest.json")}
        environment.setenv("RPS_CANDIDATE_BUILD","true")
        assert resolve({**request,"template":identity})[0].is_file()
        with pytest.raises(StudioError,match="FONT_ASSET_IDENTITY_MISMATCH"):resolve({"template":identity})
        assert list((tmp_path/"font-inventory/fonts").rglob("*.ttf"))
    # A duplicate copy of identical bytes must not change fc-match's selected
    # filename in a subsequent frozen-mother build outside this test scope.
    assert resolve_faces({"latin":"Liberation Serif"})==before

def test_missing_selected_font_never_falls_back(tmp_path,monkeypatch):
    monkeypatch.setenv("RPS_REGISTRY_ROOT",str(tmp_path))
    with pytest.raises(StudioError,match="MISSING_FONT"):build("general-modeling","1.0.0","common-paper")

def test_ttc_collection_uses_actual_sc_face_in_compiled_pdf(tmp_path):
    from studio.fonts import resolve_faces,fontspec_declaration
    from studio.qa import inspect_output_pdf
    fonts={"cjk":"Noto Serif CJK SC","latin":"Liberation Serif","math":"Latin Modern Math"}
    faces=resolve_faces(fonts)
    source=tmp_path/"face.tex"
    source.write_text(r"\documentclass{article}\usepackage{fontspec,xeCJK}"+fontspec_declaration(r"\setCJKmainfont",fonts["cjk"],faces["cjk"])+r"\begin{document}骨直令简体中文模型\textbf{字体测试}\end{document}",encoding="utf-8")
    run(["xelatex","-interaction=nonstopmode","-halt-on-error",source.name],cwd=tmp_path)
    observed={name.split("+")[-1] for page in inspect_output_pdf(tmp_path/"face.pdf",tmp_path/"previews")["pages"] for name in page["fonts"]}
    # The shared CFF table in a collection may retain the JP outline name
    # even for an SC face. Validate actual character CIDs against the selected
    # face's cmap, instead of mistaking that name alone for a wrong glyph.
    for shape in ("upright","bold"):
        assert observed & {faces["cjk"][shape]["postscript_name"],*faces["cjk"][shape]["cff_names"]}
    from fontTools.ttLib import TTFont
    from pypdf import PdfReader
    import re
    file=run(["fc-match","-f","%{file}",fonts["cjk"]]).strip()
    with TTFont(file,fontNumber=faces["cjk"]["upright"]["index"]) as font:cmap=font.getBestCmap()
    actual={}
    for entry in PdfReader(tmp_path/"face.pdf").pages[0]["/Resources"]["/Font"].values():
        entry=entry.get_object()
        if "Regular" not in str(entry.get("/BaseFont","")) or "/ToUnicode" not in entry:continue
        text=entry["/ToUnicode"].get_data().decode("ascii")
        for block in re.findall(r"beginbfchar(.*?)endbfchar",text,re.S):
            for code,unicode in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>",block):actual[int(unicode,16)]=int(code,16)
    expected={ord(char):int(cmap[ord(char)][3:]) for char in "骨直令"}
    from studio.runtime import write_json
    write_json("build/font-face-probe.json",{"faces":faces,"observed_pdf_names":sorted(observed),"expected_sc_cids":expected,"actual_pdf_cids":actual,"source":source.read_text()})
    assert {code:actual.get(code) for code in expected}==expected

def test_exact_family_and_registered_bytes_cannot_be_silently_substituted():
    from studio.qa import check_fonts
    with pytest.raises(StudioError,match="MISSING_FONT"):check_fonts({"fonts":{"cjk":"Serif"}})
    profile={"fonts":{"latin":"Liberation Serif"},"font_faces":{}}
    with pytest.raises(StudioError,match="FONT_FACE_FINGERPRINT_MISMATCH"):check_fonts(profile)
