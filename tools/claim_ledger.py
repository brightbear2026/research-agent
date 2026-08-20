#!/usr/bin/env python3
"""生成并审计总编辑前后的声明账本。

声明账本不是事实抽取模型；它使用确定性锚点阻止编辑阶段新增引用、数字/日期，
并对同一引用句中删除不确定性限定词的情况给出错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

CITATION_RE = re.compile(r"\[(\d{1,4})\]")
NUMBER_RE = re.compile(
    r"(?<![A-Za-z])(?:19|20)\d{2}(?:[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?)?"
    r"|(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?\s*(?:%|％|万|亿|兆|元|美元|人民币|倍|个|项|家|人|年|月|日)?"
)
QUALIFIERS = (
    "可能", "或许", "大约", "约", "预计", "估计", "推测", "倾向于", "尚不确定",
    "在一定条件下", "在特定条件下", "不一定", "未必", "不能证明", "相关而非因果",
    "截至", "仅限", "取决于", "有待验证", "证据有限", "样本有限",
)


def _without_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _sentences(text: str) -> list[str]:
    text = _without_code(text)
    pieces = re.split(r"(?<=[。！？!?；;])\s*|\n{2,}", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def numeric_anchors(text: str) -> set[str]:
    clean = CITATION_RE.sub("", _without_code(text))
    return {re.sub(r"\s+", "", match.group(0)).replace("，", ",") for match in NUMBER_RE.finditer(clean)}


def citation_ids(text: str) -> set[int]:
    return {int(value) for value in CITATION_RE.findall(_without_code(text))}


def qualifiers(text: str) -> set[str]:
    return {term for term in QUALIFIERS if term in text}


def build_ledger(text: str, source_path: str = "") -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for sentence in _sentences(text):
        citations = sorted(citation_ids(sentence))
        numbers = sorted(numeric_anchors(sentence))
        if not citations and not numbers:
            continue
        entries.append({
            "claim_id": f"AUTO-{len(entries) + 1:04d}",
            "text": sentence,
            "citation_ids": citations,
            "numeric_anchors": numbers,
            "qualifiers": sorted(qualifiers(sentence)),
        })
    return {
        "schema_version": 1,
        "source_path": source_path,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "citation_ids": sorted(citation_ids(text)),
        "numeric_anchors": sorted(numeric_anchors(text)),
        "entries": entries,
    }


def audit_ledger(final_text: str, ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    baseline_citations = {int(value) for value in ledger.get("citation_ids", [])}
    introduced_citations = sorted(citation_ids(final_text) - baseline_citations)
    if introduced_citations:
        errors.append(f"编辑阶段新增引用: {introduced_citations}")
    baseline_numbers = {str(value) for value in ledger.get("numeric_anchors", [])}
    introduced_numbers = sorted(numeric_anchors(final_text) - baseline_numbers)
    if introduced_numbers:
        errors.append(f"编辑阶段新增数字/日期锚点: {introduced_numbers[:20]}")

    by_citations: dict[tuple[int, ...], list[dict[str, Any]]] = {}
    for entry in ledger.get("entries", []):
        key = tuple(int(value) for value in entry.get("citation_ids", []))
        if key:
            by_citations.setdefault(key, []).append(entry)
    for sentence in _sentences(final_text):
        key = tuple(sorted(citation_ids(sentence)))
        candidates = by_citations.get(key, [])
        if len(candidates) != 1:
            continue
        before = set(candidates[0].get("qualifiers", []))
        after = qualifiers(sentence)
        if before and not after:
            errors.append(
                f"同一引用句删除了不确定性限定词/适用条件 {sorted(before)}: {sentence[:120]}"
            )
    return errors


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="生成/审计编辑声明账本")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("baseline")
    create.add_argument("--out", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("final")
    audit.add_argument("--ledger", required=True)
    args = parser.parse_args()
    if args.command == "create":
        baseline = Path(args.baseline).resolve()
        text = baseline.read_text(encoding="utf-8")
        out = Path(args.out).resolve()
        _atomic_json(out, build_ledger(text, str(baseline)))
        print(f"✓ 声明账本已生成: {out}")
        return 0
    final = Path(args.final).resolve().read_text(encoding="utf-8")
    ledger = json.loads(Path(args.ledger).resolve().read_text(encoding="utf-8"))
    errors = audit_ledger(final, ledger)
    if errors:
        for error in errors:
            print(f"✗ {error}", file=sys.stderr)
        return 1
    print("✓ 编辑声明账本审计通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
