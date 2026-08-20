#!/usr/bin/env python3
"""校验 chapter_meta v2，并原子派生数据、证据与争议矩阵。"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.source_identity import canonical_url_key, source_independence_key
except ModuleNotFoundError:
    from source_identity import canonical_url_key, source_independence_key


SD_HEADER = [
    "evidence_id", "claim_id", "data_name", "value", "unit", "stat_time",
    "region", "population_or_scope", "definition", "source_ids", "source",
    "source_org", "source_date", "tier", "credibility", "limitations", "notes",
]
EV_HEADER = [
    "conclusion_id", "core_conclusion", "supporting_evidence",
    "opposing_evidence", "source_tier", "independent_source_count",
    "strong_source_count", "sufficiency", "final_judgment",
    "limitations",
]
CT_HEADER = [
    "controversy_id", "question", "view_a", "supporters_a", "view_b",
    "supporters_b", "evidence_comparison", "research_judgment",
]
BR_HEADER = [
    "source_id", "broker", "authors", "report_type", "title",
    "covered_entity_or_industry", "publish_date", "forecast_horizon",
    "rating", "target_price", "key_assumptions", "primary_data_sources",
    "conflict_disclosure", "url", "access_date", "page_or_location",
    "tier", "independence_group", "used_for", "limitations", "access_notes",
]
DI_HEADER = [
    "fig_id", "source_html", "local_path", "title", "alt_text",
    "visual_type", "size", "detail", "profile", "source_ids",
    "source_orgs", "source_docs", "supports_conclusion",
]
OUTPUTS = (
    ("data/source_data.csv", SD_HEADER),
    ("data/broker_report_list.csv", BR_HEADER),
    ("data/diagram_manifest.csv", DI_HEADER),
    ("evidence/evidence_matrix.csv", EV_HEADER),
    ("evidence/controversy_matrix.csv", CT_HEADER),
)
CONFIDENCES = {"高", "中高", "中", "中低", "低"}
NUMERIC_RE = re.compile(r"(?:^|[^A-Za-z])[-+]?\d+(?:[.,]\d+)?")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value).strip()


def _ids(value: Any) -> list[str]:
    return [str(item).strip() for item in value] if isinstance(value, list) else []


def _is_numeric(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    return bool(NUMERIC_RE.search(value)) if isinstance(value, str) else False


def validate_chapters(document: Any) -> tuple[list[dict[str, Any]], ValidationResult]:
    result = ValidationResult()
    if not isinstance(document, list):
        result.error("$", "合并元数据顶层必须是章节对象数组")
        return [], result
    chapters = [item for item in document if isinstance(item, dict)]
    if len(chapters) != len(document):
        result.error("$", "数组中存在非对象章节")
    seen_chapters: set[str] = set()
    seen_figure_ids: set[str] = set()
    for index, chapter in enumerate(chapters):
        where = f"$[{index}]"
        chapter_id = _string(chapter.get("chapter_id"))
        if chapter.get("schema_version") != 2:
            result.error(where, "schema_version 必须为 2；请先运行 migrate_chapter_meta.py")
        if not re.fullmatch(r"ch\d{2}", chapter_id):
            result.error(where, "chapter_id 必须匹配 chNN")
        if chapter_id in seen_chapters:
            result.error(where, f"chapter_id 重复：{chapter_id}")
        seen_chapters.add(chapter_id)
        for key in ("title", "reader_question", "thesis", "argument_role"):
            if not _string(chapter.get(key)):
                result.error(where, f"缺少非空字段 {key}")

        sources = chapter.get("sources")
        claims = chapter.get("claims")
        evidence = chapter.get("data_points")
        if not isinstance(sources, list):
            result.error(where, "sources 必须是数组")
            sources = []
        if not isinstance(claims, list) or not claims:
            result.error(where, "claims 必须是非空数组")
            claims = []
        if not isinstance(evidence, list):
            result.error(where, "data_points 必须是数组")
            evidence = []
        screenshots = chapter.get("screenshots", [])
        if not isinstance(screenshots, list):
            result.error(where, "screenshots 必须是数组")
            screenshots = []
        diagrams = chapter.get("diagrams", [])
        if not isinstance(diagrams, list):
            result.error(where, "diagrams 必须是数组")
            diagrams = []

        source_ids = {_string(x.get("source_id")) for x in sources if isinstance(x, dict)}
        evidence_ids = {_string(x.get("evidence_id")) for x in evidence if isinstance(x, dict)}
        claim_ids = {_string(x.get("claim_id")) for x in claims if isinstance(x, dict)}
        for label, values in (("source_id", source_ids), ("evidence_id", evidence_ids), ("claim_id", claim_ids)):
            if "" in values:
                result.error(where, f"存在空 {label}")
        if len(source_ids) != len(sources):
            result.error(where, "source_id 缺失或重复")
        if len(evidence_ids) != len(evidence):
            result.error(where, "evidence_id 缺失或重复")
        if len(claim_ids) != len(claims):
            result.error(where, "claim_id 缺失或重复")

        for i, raw in enumerate(screenshots):
            if not isinstance(raw, dict):
                continue
            fig_id = _string(raw.get("fig_id"))
            if not fig_id:
                continue
            item_where = f"{where}.screenshots[{i}]"
            if fig_id in seen_figure_ids:
                result.error(item_where, f"fig_id 全局重复：{fig_id}")
            else:
                seen_figure_ids.add(fig_id)

        for i, raw in enumerate(diagrams):
            item_where = f"{where}.diagrams[{i}]"
            if not isinstance(raw, dict):
                result.error(item_where, "Diagram Design 图必须是对象")
                continue
            fig_id = _string(raw.get("fig_id"))
            if not re.fullmatch(r"FIG-\d{3,}", fig_id):
                result.error(item_where, "fig_id 必须匹配 FIG-NNN")
            elif fig_id in seen_figure_ids:
                result.error(item_where, f"fig_id 全局重复：{fig_id}")
            else:
                seen_figure_ids.add(fig_id)
            if not re.fullmatch(r"diagrams/[^/]+\.html", _string(raw.get("source_html"))):
                result.error(item_where, "source_html 必须是 diagrams/<文件>.html")
            if not re.fullmatch(r"images/[^/]+\.png", _string(raw.get("local_path"))):
                result.error(item_where, "local_path 必须是 images/<文件>.png")
            if raw.get("size") not in {"compact", "standard", "doc-wide", "hero"}:
                result.error(item_where, "size 必须为 compact/standard/doc-wide/hero")
            if raw.get("detail") not in {"minimal", "balanced", "rich"}:
                result.error(item_where, "detail 必须为 minimal/balanced/rich")
            for key in ("title", "visual_type", "profile", "alt_text"):
                if not _string(raw.get(key)):
                    result.error(item_where, f"{key} 不得为空")
            diagram_sources = _ids(raw.get("source_ids"))
            diagram_claims = _ids(raw.get("supports_claim_ids"))
            if not diagram_sources:
                result.error(item_where, "source_ids 不得为空")
            if not diagram_claims:
                result.error(item_where, "supports_claim_ids 不得为空")
            for ref in diagram_sources:
                if ref not in source_ids:
                    result.error(item_where, f"引用不存在的 source_id：{ref}")
            for ref in diagram_claims:
                if ref not in claim_ids:
                    result.error(item_where, f"引用不存在的 claim_id：{ref}")

        for i, raw in enumerate(sources):
            source_where = f"{where}.sources[{i}]"
            if not isinstance(raw, dict):
                result.error(source_where, "来源必须是对象")
                continue
            for key in ("source_id", "title", "url", "tier"):
                if key not in raw:
                    result.error(source_where, f"缺少字段 {key}")
            if not _string(raw.get("title")):
                result.error(source_where, "title 不得为空")
            if raw.get("tier") not in {"A", "B", "C", "D", None}:
                result.error(source_where, "tier 必须为 A/B/C/D/null")
            if _is_broker_report(raw):
                for key in ("organization", "publish_date", "authors", "report_type"):
                    if not raw.get(key):
                        result.warn(source_where, f"券商研报建议补充 {key}")
                if not raw.get("independence_group"):
                    result.warn(source_where, "券商研报建议以券商研究所填写 independence_group")
                if raw.get("tier") != "B":
                    result.warn(source_where, "完整券商研报通常应标 B；摘要/转载应改 source_type 并降为 C/D")

        for i, raw in enumerate(evidence):
            item_where = f"{where}.data_points[{i}]"
            if not isinstance(raw, dict):
                result.error(item_where, "证据必须是对象")
                continue
            for key in ("evidence_id", "claim_id", "source_ids", "value", "unit", "stat_time", "region", "population_or_scope", "definition", "confidence", "limitations"):
                if key not in raw:
                    result.error(item_where, f"缺少字段 {key}")
            if _string(raw.get("claim_id")) not in claim_ids:
                result.error(item_where, f"引用不存在的 claim_id：{raw.get('claim_id')}")
            refs = _ids(raw.get("source_ids"))
            if not refs:
                result.error(item_where, "source_ids 不得为空")
            for ref in refs:
                if ref not in source_ids:
                    result.error(item_where, f"引用不存在的 source_id：{ref}")
            if raw.get("confidence") not in CONFIDENCES:
                result.error(item_where, "confidence 必须为 高/中高/中/中低/低")
            if not isinstance(raw.get("limitations"), list):
                result.error(item_where, "limitations 必须是数组")
            if _is_numeric(raw.get("value")):
                for field_name in ("unit", "stat_time"):
                    if not _string(raw.get(field_name)):
                        result.error(item_where, f"数值证据缺少 {field_name}")
                if not _string(raw.get("region")) and not _string(raw.get("population_or_scope")):
                    result.error(item_where, "数值证据必须填写 region 或 population_or_scope")

        for i, raw in enumerate(claims):
            claim_where = f"{where}.claims[{i}]"
            if not isinstance(raw, dict):
                result.error(claim_where, "声明必须是对象")
                continue
            if not _string(raw.get("text")):
                result.error(claim_where, "text 不得为空")
            for key in ("source_ids", "supporting_evidence_ids", "opposing_evidence_ids", "confidence", "limitations"):
                if key not in raw:
                    result.error(claim_where, f"缺少字段 {key}")
            if raw.get("confidence") not in CONFIDENCES:
                result.error(claim_where, "confidence 必须为 高/中高/中/中低/低")
            if not isinstance(raw.get("limitations"), list):
                result.error(claim_where, "limitations 必须是数组")
            for ref in _ids(raw.get("source_ids")):
                if ref not in source_ids:
                    result.error(claim_where, f"引用不存在的 source_id：{ref}")
            for key in ("supporting_evidence_ids", "opposing_evidence_ids"):
                for ref in _ids(raw.get(key)):
                    if ref not in evidence_ids:
                        result.error(claim_where, f"{key} 引用不存在的 evidence_id：{ref}")

        conclusion = chapter.get("chapter_conclusion")
        cc_where = f"{where}.chapter_conclusion"
        if not isinstance(conclusion, dict):
            result.error(cc_where, "必须是对象")
            continue
        for key in ("claim_id", "judgment", "supporting_evidence_ids", "opposing_evidence_ids", "conditions", "time_range", "confidence", "limitations", "decision_implication"):
            if key not in conclusion:
                result.error(cc_where, f"缺少字段 {key}")
        if not _string(conclusion.get("judgment")):
            result.error(cc_where, "judgment 不得为空")
        if conclusion.get("confidence") not in CONFIDENCES:
            result.error(cc_where, "confidence 必须为 高/中高/中/中低/低")
        if not isinstance(conclusion.get("limitations"), list):
            result.error(cc_where, "limitations 必须是数组")
        cc_claim = _string(conclusion.get("claim_id"))
        if cc_claim not in claim_ids:
            result.error(cc_where, f"引用不存在的 claim_id：{cc_claim}")
        support = _ids(conclusion.get("supporting_evidence_ids"))
        if not support:
            result.error(cc_where, "结论没有真实 supporting_evidence_ids；禁止用结论文本自证")
        for key in ("supporting_evidence_ids", "opposing_evidence_ids"):
            for ref in _ids(conclusion.get(key)):
                if ref not in evidence_ids:
                    result.error(cc_where, f"{key} 引用不存在的 evidence_id：{ref}")
        if _string(conclusion.get("judgment")) in support:
            result.error(cc_where, "结论文本不能作为 evidence_id")
    return chapters, result


def _source_maps(chapter: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    sources = {str(item["source_id"]): item for item in chapter.get("sources", [])}
    evidence = {str(item["evidence_id"]): item for item in chapter.get("data_points", [])}
    return sources, evidence


def emit_source_data(chapters: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for chapter in chapters:
        source_map, _ = _source_maps(chapter)
        claim_map = {str(c["claim_id"]): c for c in chapter.get("claims", [])}
        for item in chapter.get("data_points", []):
            source_ids = _ids(item.get("source_ids"))
            linked = [source_map[sid] for sid in source_ids]
            rows.append({
                "evidence_id": _string(item.get("evidence_id")),
                "claim_id": _string(item.get("claim_id")),
                "data_name": _string(claim_map.get(_string(item.get("claim_id")), {}).get("text")),
                "value": _string(item.get("value")),
                "unit": _string(item.get("unit")),
                "stat_time": _string(item.get("stat_time")),
                "region": _string(item.get("region")),
                "population_or_scope": _string(item.get("population_or_scope")),
                "definition": _string(item.get("definition")),
                "source_ids": "; ".join(source_ids),
                "source": "; ".join(_string(s.get("url")) or _string(s.get("title")) for s in linked),
                "source_org": "; ".join(dict.fromkeys(_string(s.get("organization")) for s in linked if _string(s.get("organization")))),
                "source_date": "; ".join(dict.fromkeys(_string(s.get("publish_date")) for s in linked if _string(s.get("publish_date")))),
                "tier": "; ".join(dict.fromkeys(_string(s.get("tier")) for s in linked if _string(s.get("tier")))),
                "credibility": _string(item.get("confidence")),
                "limitations": "; ".join(_ids(item.get("limitations"))),
                "notes": f"[{chapter.get('chapter_id', '')}]",
            })
    return rows


def _is_broker_report(source: dict[str, Any]) -> bool:
    source_type = _string(source.get("source_type")).lower().replace("-", "_")
    return source_type in {"broker_report", "sell_side_research", "券商研报", "投行研报"}


def emit_broker_reports(chapters: list[dict[str, Any]]) -> list[dict[str, str]]:
    """从章节元数据汇总实际使用的券商研报，并按原始 URL/报告身份去重。"""
    records: dict[str, dict[str, Any]] = {}
    for chapter in chapters:
        chapter_id = _string(chapter.get("chapter_id"))
        claims = [item for item in chapter.get("claims", []) if isinstance(item, dict)]
        for source in chapter.get("sources", []):
            if not isinstance(source, dict) or not _is_broker_report(source):
                continue
            source_id = _string(source.get("source_id"))
            url = _string(source.get("url"))
            report_identity = [
                _string(source.get(key)).lower()
                for key in ("organization", "title", "publish_date")
            ]
            # 同一报告的官网、平台和转载 URL 仍只算一份；元数据不完整时才回退 URL。
            identity = (
                "report:" + "|".join(report_identity)
                if all(report_identity)
                else "url:" + canonical_url_key(url)
            )
            used_claims = [
                _string(claim.get("claim_id"))
                for claim in claims
                if source_id in _ids(claim.get("source_ids"))
            ]
            limitations = _ids(source.get("limitations"))
            row = records.get(identity)
            if row is None:
                row = {
                    "source_id": [],
                    "broker": _string(source.get("organization")),
                    "authors": _first(source, "authors"),
                    "report_type": _string(source.get("report_type")),
                    "title": _string(source.get("title")),
                    "covered_entity_or_industry": _string(source.get("covered_entity_or_industry")),
                    "publish_date": _string(source.get("publish_date")),
                    "forecast_horizon": _string(source.get("forecast_horizon")),
                    "rating": _string(source.get("rating")),
                    "target_price": _string(source.get("target_price")),
                    "key_assumptions": _first(source, "key_assumptions"),
                    "primary_data_sources": _first(source, "primary_data_sources"),
                    "conflict_disclosure": _string(source.get("conflict_disclosure")),
                    "url": url,
                    "access_date": _string(source.get("access_date")),
                    "page_or_location": _string(source.get("page_or_location")),
                    "tier": _string(source.get("tier")),
                    "independence_group": _string(source.get("independence_group")),
                    "used_for": [],
                    "limitations": [],
                    "access_notes": _string(source.get("access_notes")),
                }
                records[identity] = row
            if source_id and source_id not in row["source_id"]:
                row["source_id"].append(source_id)
            usage = f"{chapter_id}:{','.join(used_claims)}" if used_claims else chapter_id
            if usage and usage not in row["used_for"]:
                row["used_for"].append(usage)
            for limitation in limitations:
                if limitation not in row["limitations"]:
                    row["limitations"].append(limitation)

    rows: list[dict[str, str]] = []
    for row in records.values():
        rows.append({
            key: "; ".join(value) if isinstance(value, list) else _string(value)
            for key, value in row.items()
        })
    return rows


def emit_diagrams(chapters: list[dict[str, Any]]) -> list[dict[str, str]]:
    """派生 Diagram Design 导出清单，并保留来源与结论追踪。"""
    rows: list[dict[str, str]] = []
    for chapter in chapters:
        source_map, _ = _source_maps(chapter)
        for diagram in chapter.get("diagrams", []):
            source_ids = _ids(diagram.get("source_ids"))
            linked = [source_map[sid] for sid in source_ids]
            rows.append({
                "fig_id": _string(diagram.get("fig_id")),
                "source_html": _string(diagram.get("source_html")),
                "local_path": _string(diagram.get("local_path")),
                "title": _string(diagram.get("title")),
                "alt_text": _string(diagram.get("alt_text")),
                "visual_type": _string(diagram.get("visual_type")),
                "size": _string(diagram.get("size")),
                "detail": _string(diagram.get("detail")),
                "profile": _string(diagram.get("profile")),
                "source_ids": "; ".join(source_ids),
                "source_orgs": "; ".join(dict.fromkeys(
                    _string(source.get("organization"))
                    for source in linked if _string(source.get("organization"))
                )),
                "source_docs": "; ".join(dict.fromkeys(
                    _string(source.get("title")) for source in linked
                )),
                "supports_conclusion": "; ".join(_ids(diagram.get("supports_claim_ids"))),
            })
    return rows


def _sufficiency(source_records: list[dict[str, Any]], opposing_count: int, limitations: list[str]) -> str:
    independent = {source_independence_key(source) for source in source_records}
    strong = sum(1 for source in source_records if source.get("tier") in {"A", "B"})
    if not independent or strong == 0:
        return "不足"
    if len(independent) < 2:
        return "有限"
    score = min(len(independent), 3) + min(strong, 2)
    if opposing_count:
        score -= 1
    if limitations:
        score -= 1
    if score >= 4:
        return "充分"
    if score >= 3:
        return "较充分"
    return "有限"


def emit_evidence(chapters: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for chapter in chapters:
        source_map, evidence_map = _source_maps(chapter)
        conclusion = chapter["chapter_conclusion"]
        support_ids = _ids(conclusion.get("supporting_evidence_ids"))
        oppose_ids = _ids(conclusion.get("opposing_evidence_ids"))
        support = [evidence_map[item] for item in support_ids]
        oppose = [evidence_map[item] for item in oppose_ids]
        source_ids = list(dict.fromkeys(sid for item in support for sid in _ids(item.get("source_ids"))))
        source_records = [source_map[sid] for sid in source_ids]
        tiers = Counter(_string(item.get("tier")) for item in source_records if _string(item.get("tier")))
        independent = {source_independence_key(source) for source in source_records}
        strong_count = sum(1 for source in source_records if source.get("tier") in {"A", "B"})
        limitations = _ids(conclusion.get("limitations"))
        judgment = _string(conclusion.get("judgment"))
        conditions = _string(conclusion.get("conditions"))
        rows.append({
            "conclusion_id": _string(conclusion.get("claim_id")),
            "core_conclusion": judgment,
            "supporting_evidence": "; ".join(support_ids),
            "opposing_evidence": "; ".join(oppose_ids),
            "source_tier": "; ".join(f"{tier}:{count}" for tier, count in sorted(tiers.items())),
            "independent_source_count": str(len(independent)),
            "strong_source_count": str(strong_count),
            "sufficiency": _sufficiency(source_records, len(oppose), limitations),
            "final_judgment": f"{judgment} 【适用条件】{conditions}" if conditions else judgment,
            "limitations": "; ".join(limitations),
        })
    return rows


def _first(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, list):
            text = "; ".join(_string(x) for x in value if _string(x))
        else:
            text = _string(value)
        if text:
            return text
    return ""


def emit_controversies(chapters: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for chapter in chapters:
        for item in chapter.get("controversies", []):
            if not isinstance(item, dict) or item.get("to_matrix") is False:
                continue
            rows.append({
                "controversy_id": _first(item, "id") or f"{chapter['chapter_id']}-CV-{len(rows)+1:03d}",
                "question": _first(item, "topic", "question"),
                "view_a": _first(item, "side_a", "position_a", "position_A", "pro"),
                "supporters_a": _first(item, "source_a", "side_a_sources", "evidence_a", "pro_sources"),
                "view_b": _first(item, "side_b", "position_b", "position_B", "con"),
                "supporters_b": _first(item, "source_b", "side_b_sources", "evidence_b", "con_sources"),
                "evidence_comparison": _first(item, "caliber_difference", "evidence_tier", "methodological_difference", "root_cause_of_disagreement"),
                "research_judgment": _first(item, "resolution", "conditional_conclusion", "resolution_status"),
            })
    return rows


def _write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in header} for row in rows)


def _backup_outputs(root: Path, paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = root / ".aggregate-backups" / stamp
    for path in existing:
        target = backup / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return backup


def run(root: Path, meta_rel: str, *, dry_run: bool = False, force: bool = False) -> int:
    root = root.resolve()
    meta_path = (root / meta_rel).resolve()
    backup: Path | None = None
    replaced: list[Path] = []
    try:
        meta_path.relative_to(root)
    except ValueError:
        print(f"✗ chapter_meta 路径越界：{meta_path}", file=sys.stderr)
        return 2
    try:
        document = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"✗ 无法读取 chapter_meta：{exc}", file=sys.stderr)
        return 1
    chapters, validation = validate_chapters(document)
    for warning in validation.warnings:
        print(f"! {warning}", file=sys.stderr)
    if validation.errors:
        for error in validation.errors:
            print(f"✗ {error}", file=sys.stderr)
        print(f"✗ 聚合中止：{len(validation.errors)} 个错误；原 CSV 未修改", file=sys.stderr)
        return 1

    rows = (
        emit_source_data(chapters), emit_broker_reports(chapters),
        emit_diagrams(chapters), emit_evidence(chapters), emit_controversies(chapters),
    )
    print(
        f"校验通过：{len(chapters)} 章，{len(rows[0])} 条证据，"
        f"{len(rows[1])} 份券商研报，{len(rows[2])} 张结构图，"
        f"{len(rows[3])} 条结论，{len(rows[4])} 项争议"
    )
    if dry_run:
        print("✓ dry-run 完成；未写入任何文件")
        return 0
    destinations = [root / rel for rel, _ in OUTPUTS]
    existing = [path for path in destinations if path.exists()]
    if existing and not force:
        print("✗ 输出文件已存在；使用 --force 才会在备份后替换：", file=sys.stderr)
        for path in existing:
            print(f"  - {path}", file=sys.stderr)
        return 2

    tmp_dir = Path(tempfile.mkdtemp(prefix="aggregate-meta-", dir=root))
    try:
        staged: list[Path] = []
        for (rel, header), data in zip(OUTPUTS, rows):
            staged_path = tmp_dir / rel
            _write_csv(staged_path, header, data)
            staged.append(staged_path)
        backup = _backup_outputs(root, destinations) if force else None
        for staged_path, destination in zip(staged, destinations):
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_path, destination)
            replaced.append(destination)
        if backup:
            print(f"✓ 原文件备份：{backup}")
    except OSError as exc:
        if backup:
            for destination in replaced:
                saved = backup / destination.relative_to(root)
                if saved.exists():
                    shutil.copy2(saved, destination)
                else:
                    destination.unlink(missing_ok=True)
        else:
            for destination in replaced:
                destination.unlink(missing_ok=True)
        print(f"✗ 写入失败并已回滚：{exc}", file=sys.stderr)
        return 1
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
    print("✓ 五个派生 CSV 已原子替换")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 chapter_meta v2 并派生旁路 CSV")
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--chapter-meta", default="data/chapter_meta.json", help="相对项目根的路径")
    parser.add_argument("--dry-run", action="store_true", help="只校验和统计，不写文件")
    parser.add_argument("--force", action="store_true", help="备份后替换已有输出")
    args = parser.parse_args()
    raise SystemExit(run(Path(args.root).resolve(), args.chapter_meta, dry_run=args.dry_run, force=args.force))


if __name__ == "__main__":
    main()
