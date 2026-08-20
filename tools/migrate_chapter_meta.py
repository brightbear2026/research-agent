#!/usr/bin/env python3
"""将 chapter_meta v1 无损迁移到 v2，不覆盖原文件。

迁移只做结构转换，不猜测单位、统计时间、地区或证据关系。无法可靠推断的
字段写为 null/空列表，并在 limitations 中明确记录，留给人工补录。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONFIDENCES = {"高", "中高", "中", "中低", "低"}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _confidence(value: Any, default: str = "中") -> str:
    return value if value in CONFIDENCES else default


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _stable_id(chapter_id: str, kind: str, index: int) -> str:
    return f"{chapter_id}-{kind}-{index:03d}"


def _tier(dp: dict[str, Any]) -> str | None:
    for key in ("tier", "level", "grade", "source_tier", "source_grade"):
        value = _text(dp.get(key)).upper()
        match = re.search(r"(?:^|[^A-Z])([ABCD])(?:级|$|[^A-Z])", value)
        if match:
            return match.group(1)
    return None


def migrate_chapter(chapter: dict[str, Any]) -> dict[str, Any]:
    """返回新的 v2 章节对象；输入对象不被修改。"""
    if chapter.get("schema_version") == 2:
        return json.loads(json.dumps(chapter, ensure_ascii=False))

    out = json.loads(json.dumps(chapter, ensure_ascii=False))
    chapter_id = _text(out.get("chapter_id")) or "ch00"
    old_points = out.get("data_points") if isinstance(out.get("data_points"), list) else []
    sources: list[dict[str, Any]] = []
    source_by_key: dict[str, str] = {}
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for index, raw in enumerate(old_points, 1):
        dp = raw if isinstance(raw, dict) else {"value": raw}
        evidence_id = _text(dp.get("evidence_id")) or _text(dp.get("id")) or _stable_id(chapter_id, "EV", index)
        claim_id = _text(dp.get("claim_id")) or _stable_id(chapter_id, "CL", index)
        claim_text = next((_text(dp.get(k)) for k in ("claim", "item", "name", "point") if _text(dp.get(k))), "")
        source_title = next((_text(dp.get(k)) for k in ("source", "source_label", "source_citation") if _text(dp.get(k))), "未命名来源")
        source_url = next((_text(dp.get(k)) for k in ("url", "source_url", "source_tag_url") if _text(dp.get(k))), "")
        source_key = source_url.rstrip("/").lower() or source_title
        source_id = source_by_key.get(source_key)
        if source_id is None:
            source_id = _stable_id(chapter_id, "SRC", len(sources) + 1)
            source_by_key[source_key] = source_id
            sources.append({
                "source_id": source_id,
                "title": source_title,
                "url": source_url or None,
                "organization": _text(dp.get("source_org")) or None,
                "publish_date": _text(dp.get("source_date")) or _text(dp.get("publish_date")) or None,
                "tier": _tier(dp),
                "independence_group": None,
            })

        limitations = _list(dp.get("limitations"))
        field_map = {
            "unit": dp.get("unit"),
            "stat_time": dp.get("stat_time"),
            "region": dp.get("region"),
            "population_or_scope": dp.get("population_or_scope"),
            "definition": dp.get("definition"),
        }
        for field, value in field_map.items():
            if value in (None, ""):
                limitations.append(f"v1 未提供 {field}；迁移器未推断")
        evidence.append({
            **dp,
            "evidence_id": evidence_id,
            "claim_id": claim_id,
            "source_ids": [source_id],
            "value": dp.get("value"),
            "unit": _text(dp.get("unit")) or None,
            "stat_time": _text(dp.get("stat_time")) or None,
            "region": _text(dp.get("region")) or None,
            "population_or_scope": _text(dp.get("population_or_scope")) or None,
            "definition": _text(dp.get("definition")) or None,
            "confidence": _confidence(dp.get("confidence")),
            "limitations": list(dict.fromkeys(limitations)),
        })
        claims.append({
            "claim_id": claim_id,
            "text": claim_text or f"待补录声明（来自 {evidence_id}）",
            "source_ids": [source_id],
            "supporting_evidence_ids": [evidence_id],
            "opposing_evidence_ids": [],
            "confidence": _confidence(dp.get("confidence")),
            "limitations": [] if claim_text else ["v1 数据点缺少明确声明文本"],
        })

    old_conclusion = out.get("chapter_conclusion")
    cc = old_conclusion if isinstance(old_conclusion, dict) else {}
    conclusion_claim_id = _text(cc.get("claim_id")) or f"{chapter_id}-CONCLUSION"
    conclusion_limitations = _list(cc.get("limitations"))
    conclusion_limitations.append("v1 未记录结论与证据的显式关系；supporting_evidence_ids 需人工补录")
    conclusion_claim = {
        "claim_id": conclusion_claim_id,
        "text": _text(cc.get("judgment")) or _text(out.get("thesis")) or "待补录章节结论",
        "source_ids": [],
        "supporting_evidence_ids": [],
        "opposing_evidence_ids": [],
        "confidence": _confidence(cc.get("confidence")),
        "limitations": list(dict.fromkeys(conclusion_limitations)),
    }
    claims.append(conclusion_claim)

    out.update({
        "schema_version": 2,
        "sources": sources,
        "claims": claims,
        "data_points": evidence,
        "screenshots": out.get("screenshots") if isinstance(out.get("screenshots"), list) else [],
        "controversies": out.get("controversies") if isinstance(out.get("controversies"), list) else [],
        "gaps": out.get("gaps") if isinstance(out.get("gaps"), list) else [],
        "chapter_conclusion": {
            **cc,
            "claim_id": conclusion_claim_id,
            "judgment": _text(cc.get("judgment")) or _text(out.get("thesis")),
            "supporting_evidence_ids": [],
            "opposing_evidence_ids": [],
            "conditions": _text(cc.get("conditions")),
            "time_range": _text(cc.get("time_range")),
            "confidence": _confidence(cc.get("confidence")),
            "limitations": list(dict.fromkeys(conclusion_limitations)),
            "decision_implication": _text(cc.get("decision_implication")),
        },
    })
    return out


def migrate_document(document: Any) -> Any:
    if isinstance(document, list):
        return [migrate_chapter(ch) if isinstance(ch, dict) else ch for ch in document]
    if isinstance(document, dict):
        return migrate_chapter(document)
    raise ValueError("chapter_meta 顶层必须是 object 或 object 数组")


def main() -> int:
    parser = argparse.ArgumentParser(description="chapter_meta v1 → v2 无损迁移")
    parser.add_argument("input", help="v1 JSON 文件")
    parser.add_argument("--output", help="输出路径；默认在文件名后追加 .v2.json")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的输出文件")
    args = parser.parse_args()
    source = Path(args.input).resolve()
    output = Path(args.output).resolve() if args.output else source.with_name(f"{source.stem}.v2.json")
    if source == output:
        print("✗ 输出路径不能与输入路径相同；迁移工具禁止原地覆盖", file=sys.stderr)
        return 2
    if output.exists() and not args.force:
        print(f"✗ 输出已存在：{output}（使用 --force 才可覆盖输出文件）", file=sys.stderr)
        return 2
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
        migrated = migrate_document(document)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"✗ 迁移失败：{exc}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    count = len(migrated) if isinstance(migrated, list) else 1
    print(f"✓ 已迁移 {count} 章：{output}")
    print("! 未推断的字段和结论证据关系已写入 limitations，请人工补录后再聚合")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
