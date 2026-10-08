"""Evidence-aware reference inspection. Observations remain human reviewed."""
from collections import defaultdict
from pathlib import Path
import json
import pdfplumber
from pypdf import PdfReader
from .runtime import StudioError, confined, digest, require_actions, write_json, run


def inspect_pdf(path, pages=None):
    require_actions()
    reader = PdfReader(path)
    selected = pages or list(range(1, len(reader.pages) + 1))
    result = {"sha256": digest(path), "page_count": len(reader.pages), "pages": []}
    with pdfplumber.open(path) as pdf:
        for number in selected:
            if not 1 <= number <= len(reader.pages):
                raise StudioError(f"INVALID_REFERENCE_PAGE: {path}:{number}")
            page = pdf.pages[number - 1]
            chars = page.chars
            text = reader.pages[number - 1].extract_text() or ""
            left = sum(c["x0"] < page.width * .45 for c in chars)
            right = sum(c["x0"] > page.width * .52 for c in chars)
            result["pages"].append({
                "page": number, "width_pt": page.width, "height_pt": page.height,
                "text_characters": len(text.strip()),
                "quality": "needs_review" if len(text.strip()) < 60 else "selectable_text",
                "fonts": sorted({c.get("fontname", "") for c in chars}),
                "left_character_count": left, "right_character_count": right,
                "column_observation": "two_regions_possible" if left > 50 and right > 50 else "undetermined",
            })
    return result


def resolve_rules(observations, official=None):
    require_actions()
    grouped = defaultdict(list)
    for item in observations:
        if not item.get("source") or not item.get("pages"):
            raise StudioError("RULE_WITHOUT_PAGE_EVIDENCE")
        grouped[item["property"]].append(item)
    result = []
    for prop, items in sorted(grouped.items()):
        reliable = [i for i in items if i.get("reviewed") is True and i.get("quality", "selectable_text") != "needs_review"]
        values = {json.dumps(i["value"], sort_keys=True, ensure_ascii=False) for i in reliable}
        row = {"property": prop, "observations": items, "status": "unconfirmed", "value": None}
        if len(values) == 1 and len({i["source"] for i in reliable}) >= 2:
            row.update(status="reference_consensus", value=reliable[0]["value"], confidence="reviewed",
                       adopted_reason="Consistent observations in independent published reference papers")
        elif len(values) > 1:
            fallback = (official or {}).get(prop)
            if fallback and fallback.get("reviewed") and fallback.get("source") and fallback.get("pages"):
                row.update(status="official_disambiguation", value=fallback["value"], confidence="reviewed",
                           official_evidence=fallback, adopted_reason="Reference papers disagree on this property")
            else:
                row["status"] = "conflicting"
        result.append(row)
    return result


def analyze(root, evidence_path, output):
    require_actions()
    evidence = json.loads(confined(root, evidence_path).read_text(encoding="utf-8"))
    sources = {}
    for source in evidence["sources"]:
        path = confined(root, source["path"])
        sources[source["id"]] = {**source, "inspection": inspect_pdf(path, source.get("pages"))}
        if evidence.get("render_previews", False):
            folder=Path(output)/"previews"/source["id"]; folder.mkdir(parents=True,exist_ok=True)
            for page in source.get("pages",[]):
                run(["pdftoppm","-f",str(page),"-l",str(page),"-r","85","-png","-singlefile",path.resolve(),folder.resolve()/f"page-{page}"])
    observations = []
    for item in evidence["observations"]:
        if item["source"] not in sources:
            raise StudioError(f"UNKNOWN_REFERENCE_SOURCE: {item['source']}")
        report = sources[item["source"]]["inspection"]
        page_map = {p["page"]: p for p in report["pages"]}
        if any(p not in page_map for p in item["pages"]):
            raise StudioError("UNINSPECTED_REFERENCE_PAGE")
        quality = "needs_review" if any(page_map[p]["quality"] == "needs_review" for p in item["pages"]) else "selectable_text"
        observations.append({**item, "quality": quality, "source_sha256": report["sha256"]})
    official = evidence.get("official", {})
    if official:
        item = evidence.get("official_document")
        if not item: raise StudioError("OFFICIAL_SOURCE_REQUIRED")
        path = confined(root, item["path"])
        if path.suffix.lower() == ".doc":
            folder = Path(output)/"official-conversion"; folder.mkdir(parents=True, exist_ok=True)
            run(["libreoffice", "-env:UserInstallation=file:///tmp/rps-reference-lo", "--headless", "--convert-to", "pdf", "--outdir", folder.resolve(), path.resolve()])
            inspection = inspect_pdf(folder/(path.stem+".pdf"), item["pages"])
            for page in item["pages"]:
                run(["pdftoppm","-f",str(page),"-l",str(page),"-r","85","-png","-singlefile",(folder/(path.stem+".pdf")).resolve(),folder.resolve()/f"page-{page}"])
        else: inspection = inspect_pdf(path, item["pages"])
        sources[item["id"]] = {**item, "original_sha256": digest(path), "inspection": inspection, "role": "official_disambiguation_only"}
        for prop, rule in official.items():
            if rule["source"] != item["id"] or any(p not in item["pages"] for p in rule["pages"]):
                raise StudioError("OFFICIAL_PAGE_NOT_INSPECTED")
            rule["source_sha256"] = digest(path)
    rules = resolve_rules(observations, official)
    report = {"sources": sources, "rules": rules, "unknown_properties": evidence.get("unknown_properties", []),
              "warning": "Text and geometry checks do not establish original Word styles or mathematical correctness."}
    write_json(Path(output) / "reference-report.json", report)
    lines = ["# 参考论文规则档案", "", "| 项目 | 采用值 | 来源状态 |", "|---|---|---|"]
    lines += [f"| {r['property']} | {r['value']} | {r['status']} |" for r in rules]
    for row in rules:
        lines += ["",f"## {row['property']}","",f"采用理由：{row.get('adopted_reason','未确认')}。置信度：{row.get('confidence','未确认')}。"]
        for observation in row["observations"]:
            lines += [f"- {observation['source']}，第 {','.join(map(str,observation['pages']))} 页：{observation.get('observation',observation['value'])} 值：{observation['value']}；范围：{observation.get('scope','未说明')}；质量：{observation['quality']}；SHA-256：{observation['source_sha256']}。"]
        if row.get("official_evidence"):
            official=row["official_evidence"]
            lines += [f"- 差异消歧：{official['source']}，第 {','.join(map(str,official['pages']))} 页；{official.get('observation','')}；SHA-256：{official['source_sha256']}。"]
    lines += ["", "未确认项目："+"、".join(evidence.get("unknown_properties",[])), "", "完整结构化证据见 reference-report.json。"]
    Path(output, "reference-rules.md").write_text("\n".join(lines), encoding="utf-8")
    return report
