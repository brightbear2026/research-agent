#!/usr/bin/env python3
"""从经过验证的 chapter_meta v2 原子派生全部旁路索引。

本工具只建立引用关系，不从自由文本猜测字段，也绝不把结论本身当作证据。
默认拒绝覆盖已有的非空结果；使用 --force 时先备份，再原子替换。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from tools.meta_schema import validate_chapter_meta
except ModuleNotFoundError:  # 直接执行 tools/aggregate_meta.py
    from meta_schema import validate_chapter_meta

SD_HEADER = [
    "data_id", "chapter_id", "data_name", "value", "unit", "stat_time", "region",
    "definition", "source_ids", "source_urls", "source_orgs", "source_dates", "tiers",
    "independence_groups", "is_key", "notes",
]
EV_HEADER = [
    "conclusion_id", "chapter_id", "core_conclusion", "supporting_evidence_ids",
    "supporting_evidence", "opposing_evidence_ids", "opposing_evidence", "source_ids",
    "source_tier", "independent_source_groups", "sufficiency", "conditions", "confidence",
    "final_judgment",
]
CT_HEADER = [
    "controversy_id", "chapter_id", "question", "view_a", "evidence_ids_a",
    "supporters_a", "view_b", "evidence_ids_b", "supporters_b",
    "evidence_comparison", "research_judgment",
]
SS_HEADER = [
    "fig_id", "url", "capture", "selector", "wait_ms", "local_path", "title",
    "source_org", "source_doc", "publish_date", "supports_conclusion", "is_primary_source",
]
DG_HEADER = [
    "fig_id", "source_html", "local_path", "title", "alt_text", "visual_type",
    "size", "detail", "profile", "source_ids", "source_orgs", "source_docs",
    "supports_conclusion",
]
OUTPUTS = {
    "source_data": Path("data/source_data.csv"),
    "evidence": Path("evidence/evidence_matrix.csv"),
    "controversy": Path("evidence/controversy_matrix.csv"),
    "screenshots": Path("data/screenshot_manifest.csv"),
    "diagrams": Path("data/diagram_manifest.csv"),
    "gaps_json": Path("evidence/research_gaps.json"),
    "gaps_md": Path("evidence/research_gaps.md"),
}


class AggregateError(ValueError):
    pass


def _join(values: list[Any]) -> str:
    return "; ".join(str(value).strip() for value in values if str(value).strip())


def _source_maps(chapter: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    sources = {source["source_id"]: source for source in chapter["sources"]}
    evidence = {item["evidence_id"]: item for item in chapter["evidence_items"]}
    return sources, evidence


def emit_source_data(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chapter in chapters:
        sources, _ = _source_maps(chapter)
        for point in chapter["data_points"]:
            refs = [sources[sid] for sid in point["source_ids"]]
            rows.append({
                "data_id": point["data_id"],
                "chapter_id": chapter["chapter_id"],
                "data_name": point["claim"],
                "value": point["value"],
                "unit": point["unit"],
                "stat_time": point["stat_time"],
                "region": point["region"],
                "definition": point["definition"],
                "source_ids": _join(point["source_ids"]),
                "source_urls": _join([source["url"] for source in refs]),
                "source_orgs": _join([source["organization"] for source in refs]),
                "source_dates": _join([source["publish_date"] for source in refs]),
                "tiers": _join([source["tier"] for source in refs]),
                "independence_groups": _join(sorted({source["independence_group"] for source in refs})),
                "is_key": str(point["is_key"]).lower(),
                "notes": point["notes"],
            })
    return rows


def _sufficiency(source_refs: list[dict[str, Any]]) -> str:
    if not source_refs:
        return "不足"
    groups = {source["independence_group"] for source in source_refs}
    strong = any(source["tier"] in {"A", "B"} for source in source_refs)
    primary = any(source["tier"] == "A" for source in source_refs)
    if len(groups) >= 2 and primary:
        return "充分"
    if len(groups) >= 2 and strong:
        return "较充分"
    if len(groups) >= 2:
        return "中等"
    return "中等" if strong else "较弱"


def emit_evidence(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chapter in chapters:
        sources, evidence = _source_maps(chapter)
        for claim in chapter["claims"]:
            support = [evidence[eid] for eid in claim["supporting_evidence_ids"]]
            oppose = [evidence[eid] for eid in claim["opposing_evidence_ids"]]
            source_ids = sorted({sid for item in support for sid in item["source_ids"]})
            source_refs = [sources[sid] for sid in source_ids]
            rows.append({
                "conclusion_id": claim["claim_id"],
                "chapter_id": chapter["chapter_id"],
                "core_conclusion": claim["statement"],
                "supporting_evidence_ids": _join(claim["supporting_evidence_ids"]),
                "supporting_evidence": _join([item["summary"] for item in support]),
                "opposing_evidence_ids": _join(claim["opposing_evidence_ids"]),
                "opposing_evidence": _join([item["summary"] for item in oppose]),
                "source_ids": _join(source_ids),
                "source_tier": _join(sorted({source["tier"] for source in source_refs})),
                "independent_source_groups": len({source["independence_group"] for source in source_refs}),
                "sufficiency": _sufficiency(source_refs),
                "conditions": claim["conditions"],
                "confidence": claim["confidence"],
                "final_judgment": claim["decision_implication"],
            })
    return rows


def emit_controversies(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chapter in chapters:
        sources, evidence = _source_maps(chapter)
        for item in chapter["controversies"]:
            refs_a = [evidence[eid] for eid in item["evidence_ids_a"]]
            refs_b = [evidence[eid] for eid in item["evidence_ids_b"]]
            source_a = sorted({sid for ev in refs_a for sid in ev["source_ids"]})
            source_b = sorted({sid for ev in refs_b for sid in ev["source_ids"]})
            rows.append({
                "controversy_id": item["controversy_id"],
                "chapter_id": chapter["chapter_id"],
                "question": item["question"],
                "view_a": item["view_a"],
                "evidence_ids_a": _join(item["evidence_ids_a"]),
                "supporters_a": _join([sources[sid]["organization"] for sid in source_a]),
                "view_b": item["view_b"],
                "evidence_ids_b": _join(item["evidence_ids_b"]),
                "supporters_b": _join([sources[sid]["organization"] for sid in source_b]),
                "evidence_comparison": item["evidence_comparison"],
                "research_judgment": item["research_judgment"],
            })
    return rows


def _referenced_images(root: Path) -> set[str] | None:
    candidates = [root / "report/_assembled_report.md", root / "report/research_report.md"]
    report = next((path for path in candidates if path.exists() and path.stat().st_size > 0), None)
    if report is None:
        return None
    text = report.read_text(encoding="utf-8")
    return {Path(match.group(1).split("?", 1)[0]).name for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text)}


def emit_screenshots(chapters: list[dict[str, Any]], root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    referenced = _referenced_images(root)
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    for chapter in chapters:
        sources, _ = _source_maps(chapter)
        for shot in chapter["screenshots"]:
            if referenced is not None and Path(shot["local_path"]).name not in referenced:
                skipped.append(shot["fig_id"])
                continue
            source = sources[shot["source_id"]]
            rows.append({
                "fig_id": shot["fig_id"], "url": shot["url"], "capture": shot["capture"],
                "selector": shot["selector"], "wait_ms": shot["wait_ms"],
                "local_path": shot["local_path"], "title": shot["title"],
                "source_org": source["organization"], "source_doc": source["title"],
                "publish_date": source["publish_date"],
                "supports_conclusion": _join(shot["supports_claim_ids"]),
                "is_primary_source": str(source["tier"] == "A").lower(),
            })
    return rows, skipped


def emit_diagrams(chapters: list[dict[str, Any]], root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """派生 Diagram Design 资产清单；图形本身由 diagram_assets.py 校验和导出。"""
    referenced = _referenced_images(root)
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    for chapter in chapters:
        sources, _ = _source_maps(chapter)
        for diagram in chapter.get("diagrams", []):
            if referenced is not None and Path(diagram["local_path"]).name not in referenced:
                skipped.append(diagram["fig_id"])
                continue
            refs = [sources[source_id] for source_id in diagram["source_ids"]]
            rows.append({
                "fig_id": diagram["fig_id"],
                "source_html": diagram["source_html"],
                "local_path": diagram["local_path"],
                "title": diagram["title"],
                "alt_text": diagram["alt_text"],
                "visual_type": diagram["visual_type"],
                "size": diagram["size"],
                "detail": diagram["detail"],
                "profile": diagram["profile"],
                "source_ids": _join(diagram["source_ids"]),
                "source_orgs": _join([source["organization"] for source in refs]),
                "source_docs": _join([source["title"] for source in refs]),
                "supports_conclusion": _join(diagram["supports_claim_ids"]),
            })
    return rows, skipped


def emit_gaps(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"chapter_id": chapter["chapter_id"], **gap} for chapter in chapters for gap in chapter["gaps"]]


def gaps_markdown(gaps: list[dict[str, Any]]) -> str:
    lines = ["# 资料缺口", "", "> 只有低/中影响、已尝试替代来源且已在报告披露的缺口，才可标记为 accepted。", ""]
    if not gaps:
        return "\n".join(lines + ["暂无已登记资料缺口。", ""])
    for gap in gaps:
        fallbacks = _join(gap.get("fallback_source_ids", [])) or "无"
        lines.extend([
            f"## {gap['gap_id']} · {gap['status']}", "",
            f"- 章节：{gap['chapter_id']}", f"- 描述：{gap['description']}",
            f"- 原因：{gap['reason']}", f"- 影响：{gap['impact']}",
            f"- 原地址：{gap['source_url'] or '无'}", f"- 已尝试替代：{gap['fallback_attempted']}",
            f"- 替代来源：{fallbacks}", f"- 已在报告披露：{gap['disclosed_in_report']}", "",
        ])
    return "\n".join(lines)


def _write_csv(path: Path, header: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in header})


def _meaningful(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    if path.suffix == ".csv":
        return len(path.read_text(encoding="utf-8").splitlines()) > 1
    if path.name == "research_gaps.md":
        body = path.read_text(encoding="utf-8")
        return bool(body.strip()) and body.strip() not in {"# 资料缺口", "# 资料缺口\n\n-"}
    return True


def _commit_batch(root: Path, staged: dict[str, Path], force: bool) -> Path | None:
    existing = {name: root / OUTPUTS[name] for name in staged if _meaningful(root / OUTPUTS[name])}
    if existing and not force:
        raise AggregateError("已有非空聚合结果，拒绝覆盖；确认后使用 --force（会自动备份）: " + ", ".join(str(path) for path in existing.values()))
    backup_dir: Path | None = None
    if existing:
        backup_dir = root / "backups" / f"meta-aggregate-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        for name, original in existing.items():
            target = backup_dir / OUTPUTS[name]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
    replaced: list[tuple[Path, Path | None]] = []
    try:
        for name, temp_path in staged.items():
            destination = root / OUTPUTS[name]
            destination.parent.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / OUTPUTS[name] if backup_dir and (backup_dir / OUTPUTS[name]).exists() else None
            os.replace(temp_path, destination)
            replaced.append((destination, backup))
    except Exception:
        for destination, backup in reversed(replaced):
            if backup and backup.exists():
                shutil.copy2(backup, destination)
            else:
                destination.unlink(missing_ok=True)
        raise
    return backup_dir


def run(root: Path, meta_rel: str, *, dry_run: bool = False, force: bool = False) -> int:
    root = root.resolve()
    meta_path = (root / meta_rel).resolve()
    try:
        meta_path.relative_to(root)
    except ValueError as exc:
        raise AggregateError("chapter_meta 路径必须位于项目目录内") from exc
    if not meta_path.exists():
        raise AggregateError(f"找不到 chapter_meta: {meta_path}")
    chapters = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(chapters, list):
        raise AggregateError("chapter_meta.json 顶层必须是章节数组")
    errors = [f"{chapter.get('chapter_id', '?')}: {error}" for chapter in chapters for error in validate_chapter_meta(chapter)]
    chapter_ids = [chapter.get("chapter_id") for chapter in chapters if isinstance(chapter, dict)]
    duplicates = sorted({chapter_id for chapter_id in chapter_ids if chapter_ids.count(chapter_id) > 1})
    if duplicates:
        errors.append(f"chapter_id 重复: {duplicates}")
    all_figure_ids = [
        item.get("fig_id")
        for chapter in chapters if isinstance(chapter, dict)
        for key in ("screenshots", "diagrams")
        for item in chapter.get(key, []) if isinstance(item, dict)
    ]
    duplicate_figures = sorted({fig_id for fig_id in all_figure_ids if all_figure_ids.count(fig_id) > 1})
    if duplicate_figures:
        errors.append(f"全局 fig_id 重复: {duplicate_figures}")
    if errors:
        raise AggregateError("chapter_meta v2 校验失败:\n  - " + "\n  - ".join(errors))

    source_rows = emit_source_data(chapters)
    evidence_rows = emit_evidence(chapters)
    controversy_rows = emit_controversies(chapters)
    screenshot_rows, skipped = emit_screenshots(chapters, root)
    diagram_rows, skipped_diagrams = emit_diagrams(chapters, root)
    gaps = emit_gaps(chapters)
    stats = {
        "chapters": len(chapters), "data_points": len(source_rows), "claims": len(evidence_rows),
        "controversies": len(controversy_rows), "screenshots": len(screenshot_rows),
        "screenshots_not_referenced": skipped, "diagrams": len(diagram_rows),
        "diagrams_not_referenced": skipped_diagrams, "gaps": len(gaps),
    }
    if dry_run:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    with tempfile.TemporaryDirectory(prefix=".aggregate-meta-", dir=root) as temp_dir:
        temp = Path(temp_dir)
        staged = {
            "source_data": temp / OUTPUTS["source_data"],
            "evidence": temp / OUTPUTS["evidence"],
            "controversy": temp / OUTPUTS["controversy"],
            "screenshots": temp / OUTPUTS["screenshots"],
            "diagrams": temp / OUTPUTS["diagrams"],
            "gaps_json": temp / OUTPUTS["gaps_json"],
            "gaps_md": temp / OUTPUTS["gaps_md"],
        }
        _write_csv(staged["source_data"], SD_HEADER, source_rows)
        _write_csv(staged["evidence"], EV_HEADER, evidence_rows)
        _write_csv(staged["controversy"], CT_HEADER, controversy_rows)
        _write_csv(staged["screenshots"], SS_HEADER, screenshot_rows)
        _write_csv(staged["diagrams"], DG_HEADER, diagram_rows)
        staged["gaps_json"].parent.mkdir(parents=True, exist_ok=True)
        staged["gaps_json"].write_text(json.dumps(gaps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staged["gaps_md"].parent.mkdir(parents=True, exist_ok=True)
        staged["gaps_md"].write_text(gaps_markdown(gaps), encoding="utf-8")
        backup = _commit_batch(root, staged, force)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if backup:
        print(f"✓ 原结果已备份: {backup}")
    print("✓ chapter_meta v2 聚合完成（全部输出已通过校验后替换）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="从 chapter_meta v2 安全派生旁路索引")
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--chapter-meta", default="data/chapter_meta.json", help="相对项目根的路径")
    parser.add_argument("--dry-run", action="store_true", help="只校验和统计，不写文件")
    parser.add_argument("--force", action="store_true", help="备份后覆盖非空聚合结果")
    args = parser.parse_args()
    try:
        return run(Path(args.root).resolve(), args.chapter_meta, dry_run=args.dry_run, force=args.force)
    except (AggregateError, json.JSONDecodeError, OSError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
