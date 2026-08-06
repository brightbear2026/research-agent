#!/usr/bin/env python3
"""evidence.py — 证据库维护与渲染。

把 evidence/evidence_matrix.csv、controversy_matrix.csv、research_gaps.md
汇总渲染成 evidence/summary.md（Markdown 表格），便于粘贴进报告附录；
并对证据充分度做快速统计。

用法: uv run python tools/evidence.py [--root <项目根>]
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

EV_HEADER = ["conclusion_id", "core_conclusion", "supporting_evidence",
             "opposing_evidence", "source_tier", "sufficiency", "final_judgment"]
CT_HEADER = ["controversy_id", "question", "view_a", "supporters_a",
             "view_b", "supporters_b", "evidence_comparison", "research_judgment"]


def ensure_csv(path: Path, header: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def md_table(rows: list[dict]) -> str:
    if not rows:
        return "_(暂无数据)_\n"
    cols = list(rows[0].keys())
    out = ["| " + " | ".join(cols) + " |",
           "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")).replace("\n", " ").replace("|", "/") for c in cols) + " |")
    return "\n".join(out) + "\n"


def run(root: Path) -> int:
    ev_path = root / "evidence" / "evidence_matrix.csv"
    ct_path = root / "evidence" / "controversy_matrix.csv"
    gaps_path = root / "evidence" / "research_gaps.md"
    summary_path = root / "evidence" / "summary.md"

    ensure_csv(ev_path, EV_HEADER)
    ensure_csv(ct_path, CT_HEADER)
    if not gaps_path.exists():
        gaps_path.write_text("# 资料缺口\n\n- \n", encoding="utf-8")

    ev = load(ev_path)
    ct = load(ct_path)
    gaps = gaps_path.read_text(encoding="utf-8")

    parts = ["# 证据库汇总\n"]
    parts.append(f"## 证据矩阵（{len(ev)} 条结论）\n\n{md_table(ev)}")
    parts.append(f"## 争议矩阵（{len(ct)} 项）\n\n{md_table(ct)}")
    parts.append("\n## 资料缺口\n\n" + (gaps.split("\n", 1)[1] if "\n" in gaps else gaps))
    summary_path.write_text("\n".join(parts), encoding="utf-8")

    suff = Counter((r.get("sufficiency", "") or "未填").strip() for r in ev)
    print(f"✓ 证据矩阵 {len(ev)} 条；充分度分布: {dict(suff)}")
    weak = sum(n for k, n in suff.items() if k in ("较弱", "不足"))
    if weak:
        print(f"  ⚠ 有 {weak} 条结论证据较弱/不足，建议补强或标注条件性。")
    print(f"✓ 争议矩阵 {len(ct)} 项")
    print(f"✓ 汇总已写入: {summary_path}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="证据库维护与渲染")
    ap.add_argument("--root", default=".", help="项目根目录")
    args = ap.parse_args()
    sys.exit(run(Path(args.root).resolve()))


if __name__ == "__main__":
    main()
