"""chapter_meta v2 的语义校验与保守迁移函数。"""
from __future__ import annotations

import re
from typing import Any

REQUIRED_TOP_LEVEL = {
    "schema_version", "chapter_id", "title", "reader_question", "thesis",
    "argument_role", "sources", "evidence_items", "claims", "data_points",
    "screenshots", "controversies", "gaps", "chapter_conclusion",
}
NUMERIC_RE = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,.]*(?:\.\d+)?(?:%|％)?")
TIERS = {"A", "B", "C", "D"}
CONFIDENCE = {"高", "中高", "中", "中低", "低"}
DIAGRAM_SIZES = {
    "doc-inline", "doc-wide", "slide-16x9", "slide-4x3", "social-og",
    "social-square", "print-a4-landscape", "print-letter-landscape", "fit",
}
DIAGRAM_DETAILS = {"faithful", "balanced", "simplified"}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unique_ids(items: list[dict[str, Any]], key: str, label: str, errors: list[str]) -> set[str]:
    found: set[str] = set()
    for index, item in enumerate(items):
        value = item.get(key)
        if not _nonempty(value):
            errors.append(f"{label}[{index}] 缺少 {key}")
            continue
        if value in found:
            errors.append(f"{label} 存在重复 {key}: {value}")
        found.add(value)
    return found


def _require_keys(item: dict[str, Any], keys: set[str], label: str, errors: list[str]) -> None:
    missing = sorted(keys - set(item))
    if missing:
        errors.append(f"{label} 缺少字段: {missing}")


def validate_chapter_meta(meta: Any, *, strict: bool = True) -> list[str]:
    """返回错误列表；不猜测或修复字段。"""
    if not isinstance(meta, dict):
        return ["顶层必须是 JSON object"]
    errors: list[str] = []
    missing = sorted(REQUIRED_TOP_LEVEL - set(meta))
    if missing:
        errors.append(f"缺少顶层字段: {missing}")
        return errors
    if meta.get("schema_version") != 2:
        errors.append("schema_version 必须为 2；旧格式请先运行 migrate_meta.py")
    chapter_id = meta.get("chapter_id", "")
    if not re.fullmatch(r"ch\d{2}", str(chapter_id)):
        errors.append("chapter_id 必须形如 ch01")
    for key in ("title", "reader_question", "thesis", "argument_role"):
        if not _nonempty(meta.get(key)):
            errors.append(f"{key} 不能为空")
    list_keys = ("sources", "evidence_items", "claims", "data_points", "screenshots", "controversies", "gaps")
    if "diagrams" in meta:
        list_keys += ("diagrams",)
    for key in list_keys:
        if not isinstance(meta.get(key), list):
            errors.append(f"{key} 必须是数组")
    if errors:
        return errors
    for key in list_keys:
        for index, item in enumerate(meta[key]):
            if not isinstance(item, dict):
                errors.append(f"{key}[{index}] 必须是对象")
    if errors:
        return errors

    sources = meta["sources"]
    evidence = meta["evidence_items"]
    claims = meta["claims"]
    data_points = meta["data_points"]
    source_ids = _unique_ids(sources, "source_id", "sources", errors)
    evidence_ids = _unique_ids(evidence, "evidence_id", "evidence_items", errors)
    claim_ids = _unique_ids(claims, "claim_id", "claims", errors)
    data_ids = _unique_ids(data_points, "data_id", "data_points", errors)
    screenshot_ids = _unique_ids(meta["screenshots"], "fig_id", "screenshots", errors)
    diagram_ids = _unique_ids(meta.get("diagrams", []), "fig_id", "diagrams", errors)
    duplicated_figure_ids = sorted(screenshot_ids & diagram_ids)
    if duplicated_figure_ids:
        errors.append(f"screenshots 与 diagrams 的 fig_id 重复: {duplicated_figure_ids}")
    controversy_ids = _unique_ids(meta["controversies"], "controversy_id", "controversies", errors)
    gap_ids = _unique_ids(meta["gaps"], "gap_id", "gaps", errors)
    id_patterns = (
        (source_ids, rf"{chapter_id}-S\d{{3}}", "source_id"),
        (evidence_ids, rf"{chapter_id}-E\d{{3}}", "evidence_id"),
        (claim_ids, rf"{chapter_id}-C\d{{3}}", "claim_id"),
        (data_ids, rf"{chapter_id}-D\d{{3}}", "data_id"),
        (controversy_ids, rf"{chapter_id}-CV\d{{3}}", "controversy_id"),
        (gap_ids, rf"{chapter_id}-G\d{{3}}", "gap_id"),
        (screenshot_ids | diagram_ids, r"FIG-\d{3,}", "fig_id"),
    )
    for values, pattern, label in id_patterns:
        for value in values:
            if not re.fullmatch(pattern, value):
                errors.append(f"{label} 格式无效: {value}")

    for index, source in enumerate(sources):
        _require_keys(source, {
            "source_id", "type", "organization", "title", "publication", "publish_date",
            "url", "access_date", "tier", "independence_group",
        }, f"sources[{index}]", errors)
    for index, item in enumerate(evidence):
        _require_keys(item, {"evidence_id", "summary", "source_ids", "stance", "limitations"}, f"evidence_items[{index}]", errors)
    for index, claim in enumerate(claims):
        _require_keys(claim, {
            "claim_id", "statement", "supporting_evidence_ids", "opposing_evidence_ids",
            "conditions", "confidence", "decision_implication",
        }, f"claims[{index}]", errors)
    for index, point in enumerate(data_points):
        _require_keys(point, {
            "data_id", "claim", "value", "unit", "stat_time", "region", "definition",
            "source_ids", "is_key", "notes",
        }, f"data_points[{index}]", errors)
    for index, shot in enumerate(meta["screenshots"]):
        _require_keys(shot, {
            "fig_id", "source_id", "url", "capture", "selector", "wait_ms", "local_path",
            "title", "supports_claim_ids",
        }, f"screenshots[{index}]", errors)
    for index, diagram in enumerate(meta.get("diagrams", [])):
        _require_keys(diagram, {
            "fig_id", "title", "visual_type", "source_html", "local_path", "size",
            "detail", "profile", "source_ids", "supports_claim_ids", "alt_text",
        }, f"diagrams[{index}]", errors)
    for index, controversy in enumerate(meta["controversies"]):
        _require_keys(controversy, {
            "controversy_id", "question", "view_a", "evidence_ids_a", "view_b",
            "evidence_ids_b", "evidence_comparison", "research_judgment",
        }, f"controversies[{index}]", errors)
    for index, gap in enumerate(meta["gaps"]):
        _require_keys(gap, {
            "gap_id", "description", "reason", "source_url", "fallback_attempted",
            "fallback_source_ids", "impact", "disclosed_in_report", "status",
        }, f"gaps[{index}]", errors)

    for source in sources:
        sid = source.get("source_id", "?")
        for key in ("type", "organization", "title", "url", "access_date", "independence_group"):
            if not _nonempty(source.get(key)):
                errors.append(f"来源 {sid} 缺少 {key}")
        if not str(source.get("url", "")).startswith(("http://", "https://")):
            errors.append(f"来源 {sid} URL 无效")
        if source.get("tier") not in TIERS:
            errors.append(f"来源 {sid} tier 必须是 A/B/C/D")

    evidence_map = {item.get("evidence_id"): item for item in evidence}
    for item in evidence:
        eid = item.get("evidence_id", "?")
        if not _nonempty(item.get("summary")):
            errors.append(f"证据 {eid} summary 不能为空")
        refs = item.get("source_ids")
        if not isinstance(refs, list) or not refs:
            errors.append(f"证据 {eid} 必须引用至少一个 source_id")
        else:
            unknown = sorted(set(refs) - source_ids)
            if unknown:
                errors.append(f"证据 {eid} 引用了不存在的来源: {unknown}")
        if item.get("stance") not in {"support", "oppose", "context"}:
            errors.append(f"证据 {eid} stance 无效")

    if not claims:
        errors.append("claims 至少需要一条结论")
    for claim in claims:
        cid = claim.get("claim_id", "?")
        statement = claim.get("statement")
        if not _nonempty(statement):
            errors.append(f"结论 {cid} statement 不能为空")
        supporting = claim.get("supporting_evidence_ids")
        opposing = claim.get("opposing_evidence_ids")
        if not isinstance(supporting, list) or not supporting:
            errors.append(f"结论 {cid} 缺少真实 supporting_evidence_ids")
        else:
            unknown = sorted(set(supporting) - evidence_ids)
            if unknown:
                errors.append(f"结论 {cid} 引用了不存在的支撑证据: {unknown}")
            if any(evidence_map.get(eid, {}).get("stance") == "oppose" for eid in supporting):
                errors.append(f"结论 {cid} 把反方证据列为支撑证据")
        if not isinstance(opposing, list):
            errors.append(f"结论 {cid} opposing_evidence_ids 必须是数组")
        else:
            unknown = sorted(set(opposing) - evidence_ids)
            if unknown:
                errors.append(f"结论 {cid} 引用了不存在的反方证据: {unknown}")
        if claim.get("confidence") not in CONFIDENCE:
            errors.append(f"结论 {cid} confidence 无效")
        if _nonempty(statement):
            for eid in supporting or []:
                if str(evidence_map.get(eid, {}).get("summary", "")).strip() == str(statement).strip():
                    errors.append(f"结论 {cid} 与支撑证据 {eid} 文本完全相同，疑似自我支撑")

    for point in data_points:
        did = point.get("data_id", "?")
        if not _nonempty(point.get("claim")):
            errors.append(f"数据点 {did} claim 不能为空")
        if not isinstance(point.get("is_key"), bool):
            errors.append(f"数据点 {did} is_key 必须是布尔值")
        refs = point.get("source_ids")
        if not isinstance(refs, list) or not refs:
            errors.append(f"数据点 {did} 必须引用至少一个 source_id")
            refs = []
        unknown = sorted(set(refs) - source_ids)
        if unknown:
            errors.append(f"数据点 {did} 引用了不存在的来源: {unknown}")
        has_number = isinstance(point.get("value"), (int, float)) or bool(NUMERIC_RE.search(str(point.get("value", ""))))
        if has_number:
            for key in ("unit", "stat_time", "region", "definition"):
                if not _nonempty(point.get(key)):
                    errors.append(f"数值数据点 {did} 缺少 {key}（可明确填写“不适用”，不能留空）")
        if strict and point.get("is_key") is True:
            groups = {s.get("independence_group") for s in sources if s.get("source_id") in refs}
            if len(groups - {None, ""}) < 2:
                errors.append(f"关键数据点 {did} 缺少两个独立来源组")

    for shot in meta["screenshots"]:
        fig_id = shot.get("fig_id", "?")
        if shot.get("source_id") not in source_ids:
            errors.append(f"截图 {fig_id} 引用了不存在的 source_id")
        rel = str(shot.get("local_path", ""))
        if not re.fullmatch(r"images/[^/]+\.png", rel):
            errors.append(f"截图 {fig_id} local_path 必须是 images/<文件>.png")
        if shot.get("capture") not in {"full", "viewport", "element", "pdf"}:
            errors.append(f"截图 {fig_id} capture 无效")
        if not isinstance(shot.get("wait_ms"), int) or not 0 <= shot.get("wait_ms", -1) <= 15000:
            errors.append(f"截图 {fig_id} wait_ms 必须是 0–15000 的整数")
        if not str(shot.get("url", "")).startswith(("http://", "https://")):
            errors.append(f"截图 {fig_id} URL 无效")
        if not _nonempty(shot.get("title")):
            errors.append(f"截图 {fig_id} title 不能为空")
        unknown_claims = sorted(set(shot.get("supports_claim_ids") or []) - claim_ids)
        if unknown_claims:
            errors.append(f"截图 {fig_id} 引用了不存在的结论: {unknown_claims}")

    for diagram in meta.get("diagrams", []):
        fig_id = diagram.get("fig_id", "?")
        if not _nonempty(diagram.get("title")):
            errors.append(f"Diagram Design 图 {fig_id} title 不能为空")
        if not _nonempty(diagram.get("visual_type")):
            errors.append(f"Diagram Design 图 {fig_id} visual_type 不能为空")
        if not re.fullmatch(r"diagrams/[^/]+\.html", str(diagram.get("source_html", ""))):
            errors.append(f"Diagram Design 图 {fig_id} source_html 必须是 diagrams/<文件>.html")
        if not re.fullmatch(r"images/[^/]+\.png", str(diagram.get("local_path", ""))):
            errors.append(f"Diagram Design 图 {fig_id} local_path 必须是 images/<文件>.png")
        if diagram.get("size") not in DIAGRAM_SIZES:
            errors.append(f"Diagram Design 图 {fig_id} size 无效")
        if diagram.get("detail") not in DIAGRAM_DETAILS:
            errors.append(f"Diagram Design 图 {fig_id} detail 无效")
        if not _nonempty(diagram.get("profile")):
            errors.append(f"Diagram Design 图 {fig_id} profile 不能为空")
        if not _nonempty(diagram.get("alt_text")):
            errors.append(f"Diagram Design 图 {fig_id} alt_text 不能为空")
        refs = diagram.get("source_ids")
        if not isinstance(refs, list) or not refs:
            errors.append(f"Diagram Design 图 {fig_id} 必须关联至少一个 source_id")
        else:
            unknown_sources = sorted(set(refs) - source_ids)
            if unknown_sources:
                errors.append(f"Diagram Design 图 {fig_id} 引用了不存在的来源: {unknown_sources}")
        supported = diagram.get("supports_claim_ids")
        if not isinstance(supported, list) or not supported:
            errors.append(f"Diagram Design 图 {fig_id} 必须支持至少一个结论")
        else:
            unknown_claims = sorted(set(supported) - claim_ids)
            if unknown_claims:
                errors.append(f"Diagram Design 图 {fig_id} 引用了不存在的结论: {unknown_claims}")

    for controversy in meta["controversies"]:
        cvid = controversy.get("controversy_id", "?")
        for key in ("question", "view_a", "view_b"):
            if not _nonempty(controversy.get(key)):
                errors.append(f"争议 {cvid} 的 {key} 不能为空")
        for key in ("evidence_ids_a", "evidence_ids_b"):
            refs = controversy.get(key)
            if not isinstance(refs, list):
                errors.append(f"争议 {cvid} 的 {key} 必须是数组")
            else:
                unknown = sorted(set(refs) - evidence_ids)
                if unknown:
                    errors.append(f"争议 {cvid} 引用了不存在的证据: {unknown}")

    for gap in meta["gaps"]:
        gid = gap.get("gap_id", "?")
        if not _nonempty(gap.get("description")):
            errors.append(f"资料缺口 {gid} description 不能为空")
        if gap.get("reason") not in {"not_found", "login", "captcha", "paywall", "blocked", "timeout", "conflict", "not_public", "other"}:
            errors.append(f"资料缺口 {gid} reason 无效")
        if gap.get("impact") not in {"low", "medium", "high", "critical"}:
            errors.append(f"资料缺口 {gid} impact 无效")
        if gap.get("status") not in {"open", "accepted", "resolved"}:
            errors.append(f"资料缺口 {gid} status 无效")
        if gap.get("status") == "accepted":
            if not gap.get("fallback_attempted"):
                errors.append(f"已接受资料缺口 {gid} 未尝试替代来源")
            if gap.get("impact") in {"high", "critical"}:
                errors.append(f"高影响资料缺口 {gid} 不能自动接受")
            if not gap.get("disclosed_in_report"):
                errors.append(f"已接受资料缺口 {gid} 未在报告披露")

    conclusion = meta.get("chapter_conclusion")
    if not isinstance(conclusion, dict):
        errors.append("chapter_conclusion 必须是对象")
    else:
        if conclusion.get("claim_id") not in claim_ids:
            errors.append("chapter_conclusion.claim_id 必须引用 claims 中的结论")
        for key in ("judgment", "decision_implication"):
            if not _nonempty(conclusion.get(key)):
                errors.append(f"chapter_conclusion.{key} 不能为空")
        if conclusion.get("confidence") not in CONFIDENCE:
            errors.append("chapter_conclusion.confidence 无效")
    return errors


def migrate_v1_to_v2(meta: dict[str, Any]) -> dict[str, Any]:
    """保守迁移：保留可确认字段，但绝不自动把结论绑定为证据。"""
    if meta.get("schema_version") == 2:
        return meta
    chapter_id = str(meta.get("chapter_id") or "ch00")
    sources: list[dict[str, Any]] = []
    source_by_url: dict[str, str] = {}
    evidence_items: list[dict[str, Any]] = []
    migrated_points: list[dict[str, Any]] = []

    def add_source(item: dict[str, Any], index: int) -> list[str]:
        candidates: list[str] = []
        for key in ("url", "source_url"):
            value = item.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                candidates.append(value)
        raw_sources = item.get("sources")
        if isinstance(raw_sources, list):
            candidates.extend(str(x) for x in raw_sources if str(x).startswith(("http://", "https://")))
        refs: list[str] = []
        for url in candidates:
            if url not in source_by_url:
                sid = f"{chapter_id}-S{len(sources) + 1:03d}"
                source_by_url[url] = sid
                sources.append({
                    "source_id": sid,
                    "type": str(item.get("source_type") or "待核验"),
                    "organization": str(item.get("source_org") or "待核验"),
                    "title": str(item.get("source_title") or item.get("claim") or item.get("item") or "待核验"),
                    "publication": str(item.get("publication") or ""),
                    "publish_date": str(item.get("source_date") or item.get("publish_date") or ""),
                    "url": url,
                    "access_date": str(item.get("access_date") or "待核验"),
                    "tier": str(item.get("tier") or item.get("source_tier") or "D").strip()[:1].upper() if str(item.get("tier") or item.get("source_tier") or "D").strip()[:1].upper() in TIERS else "D",
                    "independence_group": str(item.get("source_org") or url),
                })
            refs.append(source_by_url[url])
        return refs

    for index, point in enumerate(meta.get("data_points") or [], 1):
        if not isinstance(point, dict):
            continue
        refs = add_source(point, index)
        did = f"{chapter_id}-D{index:03d}"
        migrated_points.append({
            "data_id": did,
            "claim": str(point.get("claim") or point.get("item") or point.get("name") or "待核验数据点"),
            "value": point.get("value", ""),
            "unit": str(point.get("unit") or ""),
            "stat_time": str(point.get("stat_time") or ""),
            "region": str(point.get("region") or ""),
            "definition": str(point.get("definition") or ""),
            "source_ids": refs,
            "is_key": bool(point.get("is_key", False)),
            "notes": "由 v1 迁移；缺失字段必须复核。 " + str(point.get("notes") or point.get("note") or ""),
        })
        if refs:
            evidence_items.append({
                "evidence_id": f"{chapter_id}-E{len(evidence_items) + 1:03d}",
                "summary": migrated_points[-1]["claim"],
                "source_ids": refs,
                "stance": "context",
                "limitations": "由 v1 数据点迁移，尚未确认其与章节结论的支撑关系。",
            })

    claim_id = f"{chapter_id}-C001"
    conclusion = meta.get("chapter_conclusion") if isinstance(meta.get("chapter_conclusion"), dict) else {}
    gaps = []
    for index, old_gap in enumerate(meta.get("gaps") or [], 1):
        description = old_gap if isinstance(old_gap, str) else str(old_gap.get("description") or old_gap)
        gaps.append({
            "gap_id": f"{chapter_id}-G{index:03d}", "description": description,
            "reason": "other", "source_url": "", "fallback_attempted": False,
            "fallback_source_ids": [], "impact": "medium", "disclosed_in_report": False,
            "status": "open",
        })
    gaps.append({
        "gap_id": f"{chapter_id}-G{len(gaps) + 1:03d}",
        "description": "v1 无法可靠表达结论与证据的引用关系；必须人工或由研究代理重新核验后绑定。",
        "reason": "other", "source_url": "", "fallback_attempted": False,
        "fallback_source_ids": [], "impact": "high", "disclosed_in_report": False,
        "status": "open",
    })
    return {
        "schema_version": 2,
        "chapter_id": chapter_id,
        "title": str(meta.get("title") or "待核验章节"),
        "reader_question": str(meta.get("reader_question") or "待核验"),
        "thesis": str(meta.get("thesis") or conclusion.get("judgment") or "待核验"),
        "argument_role": str(meta.get("argument_role") or "待核验"),
        "sources": sources,
        "evidence_items": evidence_items,
        "claims": [{
            "claim_id": claim_id,
            "statement": str(meta.get("thesis") or conclusion.get("judgment") or "待核验"),
            "supporting_evidence_ids": [],
            "opposing_evidence_ids": [],
            "conditions": str(conclusion.get("conditions") or ""),
            "confidence": str(conclusion.get("confidence") or "低") if str(conclusion.get("confidence") or "低") in CONFIDENCE else "低",
            "decision_implication": str(conclusion.get("decision_implication") or "待核验"),
        }],
        "data_points": migrated_points,
        "screenshots": [],
        "diagrams": [],
        "controversies": [],
        "gaps": gaps,
        "chapter_conclusion": {
            "claim_id": claim_id,
            "judgment": str(conclusion.get("judgment") or meta.get("thesis") or "待核验"),
            "counter_evidence": str(conclusion.get("counter_evidence") or ""),
            "conditions": str(conclusion.get("conditions") or ""),
            "time_range": str(conclusion.get("time_range") or ""),
            "confidence": str(conclusion.get("confidence") or "低") if str(conclusion.get("confidence") or "低") in CONFIDENCE else "低",
            "decision_implication": str(conclusion.get("decision_implication") or "待核验"),
        },
    }
