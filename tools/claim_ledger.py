#!/usr/bin/env python3
"""生成声明账本，并审计总编辑前后的事实锚点漂移。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


LEDGER_VERSION = 1
NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9])[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:人民币|亿美元|亿元|万元|美元|%|％|万|亿|兆|倍|个|项|家|年|月|日|元|GB|TB|PB|MW|GW)?"
    r"|(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?:人民币|亿美元|亿元|万元|美元|%|％|万|亿|兆|倍|个|项|家|年|月|日|元|GB|TB|PB|MW|GW)"
)
DATE_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?:[-/.年](?:0?[1-9]|1[0-2]))?(?:[-/.月](?:0?[1-9]|[12]\d|3[01]))?日?")
LATIN_ENTITY_RE = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9.+-]*|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")
CHINESE_ENTITY_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9·]{2,24}(?:公司|集团|大学|学院|研究院|协会|委员会|政府|部门|实验室|基金会)")
CITATION_RE = re.compile(r"\[(\d{1,4})\]")

CERTAINTY_TERMS = ("必然", "一定", "确定无疑", "完全证明", "均已", "全部", "所有", "绝不会", "必将")
CAUSAL_TERMS = ("导致", "造成", "源于", "驱动了", "因此证明", "直接决定")
LIMITATION_TERMS = ("限制", "局限", "反证", "争议", "不确定", "仅适用", "适用条件", "可能", "尚未", "无法确认")


def _clean_markdown(text: str) -> str:
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    return text


def _normal_number(token: str) -> str:
    return token.replace(",", "").replace("％", "%")


def extract_anchors(text: str) -> dict[str, list[str] | dict[str, int]]:
    clean = _clean_markdown(text)
    numbers = sorted({_normal_number(match.group(0)) for match in NUMBER_RE.finditer(clean)})
    dates = sorted({match.group(0).replace("/", "-").replace(".", "-") for match in DATE_RE.finditer(clean)})
    entities = {match.group(0).strip() for match in LATIN_ENTITY_RE.finditer(clean)}
    entities.update(match.group(0).strip() for match in CHINESE_ENTITY_RE.finditer(clean))
    certainty = {term: clean.count(term) for term in CERTAINTY_TERMS if term in clean}
    causal = {term: clean.count(term) for term in CAUSAL_TERMS if term in clean}
    limitations = {term: clean.count(term) for term in LIMITATION_TERMS if term in clean}
    return {
        "numbers": numbers,
        "dates": dates,
        "entities": sorted(entities),
        "certainty_terms": certainty,
        "causal_terms": causal,
        "limitation_terms": limitations,
    }


def _citation_contexts(text: str) -> list[dict[str, Any]]:
    clean = _clean_markdown(text)
    sentences = [part.strip() for part in re.split(r"(?<=[。！？!?])|\n+", clean) if part.strip()]
    contexts: list[dict[str, Any]] = []
    for sentence in sentences:
        citations = sorted({int(value) for value in CITATION_RE.findall(sentence)})
        if not citations:
            continue
        contexts.append({
            "citations": citations,
            "text": sentence[:1000],
            "anchors": extract_anchors(sentence),
        })
    return contexts


def _meta_claims(chapters: Any) -> list[dict[str, Any]]:
    if not isinstance(chapters, list):
        return []
    records: list[dict[str, Any]] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        evidence = {str(item.get("evidence_id")): item for item in chapter.get("data_points", []) if isinstance(item, dict)}
        for claim in chapter.get("claims", []):
            if not isinstance(claim, dict):
                continue
            support = [str(item) for item in claim.get("supporting_evidence_ids", [])]
            oppose = [str(item) for item in claim.get("opposing_evidence_ids", [])]
            records.append({
                "chapter_id": chapter.get("chapter_id"),
                "claim_id": claim.get("claim_id"),
                "text": claim.get("text"),
                "source_ids": claim.get("source_ids", []),
                "supporting_evidence_ids": support,
                "opposing_evidence_ids": oppose,
                "confidence": claim.get("confidence"),
                "limitations": claim.get("limitations", []),
                "evidence_anchors": {
                    item_id: extract_anchors(str(evidence[item_id].get("value", "")))
                    for item_id in support + oppose if item_id in evidence
                },
            })
    return records


def build_ledger(baseline_text: str, chapters: Any, baseline_path: str = "") -> dict[str, Any]:
    return {
        "ledger_version": LEDGER_VERSION,
        "baseline_path": baseline_path,
        "baseline_anchors": extract_anchors(baseline_text),
        "citation_contexts": _citation_contexts(baseline_text),
        "claims": _meta_claims(chapters),
    }


def _counter(value: Any) -> Counter[str]:
    return Counter({str(k): int(v) for k, v in value.items()}) if isinstance(value, dict) else Counter()


def audit_text(final_text: str, ledger: dict[str, Any]) -> dict[str, list[str]]:
    baseline = ledger.get("baseline_anchors", {})
    final = extract_anchors(final_text)
    errors: list[str] = []
    warnings: list[str] = []

    for key, label in (("numbers", "数字/数量"), ("dates", "日期"), ("entities", "实体")):
        old = set(baseline.get(key, []))
        new = set(final.get(key, []))
        introduced = sorted(new - old)
        removed = sorted(old - new)
        if introduced:
            errors.append(f"编辑阶段引入组装稿不存在的{label}：{introduced[:20]}")
        if removed:
            warnings.append(f"编辑阶段删除了{label}锚点：{removed[:20]}")

    for key, label in (("certainty_terms", "确定性表述"), ("causal_terms", "因果表述")):
        old = _counter(baseline.get(key, {}))
        new = _counter(final.get(key, {}))
        increased = {term: new[term] - old[term] for term in new if new[term] > old[term]}
        if increased:
            errors.append(f"编辑阶段增强了{label}：{increased}")

    old_limits = _counter(baseline.get("limitation_terms", {}))
    new_limits = _counter(final.get("limitation_terms", {}))
    reduced = {term: old_limits[term] - new_limits[term] for term in old_limits if new_limits[term] < old_limits[term]}
    if reduced:
        warnings.append(f"编辑阶段减少了限制/不确定性表述：{reduced}")
    return {"errors": errors, "warnings": warnings}


def write_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="声明账本生成与编辑漂移审计")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="从组装稿和 chapter_meta 生成账本")
    build.add_argument("--baseline", required=True)
    build.add_argument("--chapter-meta", required=True)
    build.add_argument("--out", required=True)
    audit = sub.add_parser("audit", help="用账本审计终稿")
    audit.add_argument("--ledger", required=True)
    audit.add_argument("--final", required=True)
    args = parser.parse_args()

    try:
        if args.command == "build":
            baseline_path = Path(args.baseline).resolve()
            meta_path = Path(args.chapter_meta).resolve()
            ledger = build_ledger(
                baseline_path.read_text(encoding="utf-8"),
                json.loads(meta_path.read_text(encoding="utf-8")),
                str(baseline_path),
            )
            write_ledger(Path(args.out).resolve(), ledger)
            print(f"✓ 声明账本已生成：{args.out}（{len(ledger['claims'])} 条声明）")
            return 0
        ledger = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
        result = audit_text(Path(args.final).read_text(encoding="utf-8"), ledger)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"✗ 声明账本处理失败：{exc}", file=sys.stderr)
        return 2
    for message in result["warnings"]:
        print(f"! {message}")
    for message in result["errors"]:
        print(f"✗ {message}", file=sys.stderr)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
