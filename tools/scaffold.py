#!/usr/bin/env python3
"""scaffold.py — 创建深度研究项目的标准目录树与空索引文件。

用法: uv run python tools/scaffold.py <项目名|路径> [--force]
默认项目名: deep-research-project

依据研究规范第十六节「最终交付目录」。所有索引 CSV 仅写表头，由研究过程逐行填充。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 目录结构: (相对路径, 是否目录)
TREE: list[tuple[str, bool]] = [
    ("report", True),
    ("images", True),
    ("data", True),
    ("evidence", True),
    ("sources", True),
]

# CSV 索引: (相对路径, 表头列表)
INDEXES: list[tuple[str, list[str]]] = [
    ("data/citations.csv", [
        "id", "type", "author_org", "title", "publication_site",
        "publish_date", "doi_or_id", "url", "access_date", "page_or_location", "tier",
    ]),
    ("data/figures.csv", [
        "fig_id", "title", "source_org", "source_doc", "url",
        "publish_date", "access_date", "page_or_location",
        "supports_conclusion", "is_primary_source", "local_path", "status",
    ]),
    ("data/tables.csv", ["table_id", "title", "source", "notes"]),
    ("data/source_data.csv", [
        "data_name", "value", "unit", "stat_time", "region",
        "definition", "source", "source_org", "source_date", "tier", "credibility", "notes",
    ]),
    ("data/company_comparison.csv", [
        "dimension", "company_a", "company_b", "company_c", "company_d", "notes",
    ]),
    ("data/paper_list.csv", [
        "title", "authors", "institution", "publish_date", "venue", "url",
        "doi", "research_question", "method", "dataset", "core_finding",
        "key_data", "limitations", "relevance", "citation_value",
    ]),
    ("data/source_index.csv", [
        "ref_id", "tier", "source_type", "author_org", "title", "url",
        "publish_date", "access_date", "used_for", "notes",
    ]),
    ("data/screenshot_manifest.csv", [
        "fig_id", "url", "capture", "selector", "wait_ms", "local_path",
        "title", "source_org", "source_doc", "publish_date",
        "supports_conclusion", "is_primary_source",
    ]),
    ("evidence/evidence_matrix.csv", [
        "conclusion_id", "core_conclusion", "supporting_evidence",
        "opposing_evidence", "source_tier", "sufficiency", "final_judgment",
    ]),
    ("evidence/controversy_matrix.csv", [
        "controversy_id", "question", "view_a", "supporters_a",
        "view_b", "supporters_b", "evidence_comparison", "research_judgment",
    ]),
]

# Markdown 占位文件: (相对路径, 初始内容)
MD_FILES: list[tuple[str, str]] = [
    ("evidence/research_gaps.md", "# 资料缺口\n\n> 列出尚未获得的数据、无法访问的论文、企业未公开数据、互相矛盾的数据、需访谈确认的问题、需付费数据库的信息、无法验证的传闻。\n\n- \n"),
    ("sources/bibliography.md", "# 参考文献\n\n> 每条尽量含：作者/机构、标题、出版物/网站、发布日期、DOI、原始链接、访问日期、页码。\n\n"),
    ("sources/source_index.md", "# 来源索引\n\n> 主来源清单（与 data/source_index.csv 对应）。\n\n"),
    ("README.md", "# 深度研究报告\n\n> 由 README 生成后填写：研究课题、文件结构、如何阅读、数据截止日期、截图说明、HTML 打开方式、研究限制、资料更新方式。\n"),
]


def write_csv_header(path: Path, header: list[str]) -> None:
    import csv
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(header)


def scaffold(root: Path, force: bool) -> None:
    if root.exists() and any(root.iterdir()) and not force:
        sys.exit(f"✗ 目录已存在且非空: {root}（加 --force 覆盖）")
    root.mkdir(parents=True, exist_ok=True)

    for rel, _ in TREE:
        (root / rel).mkdir(parents=True, exist_ok=True)

    for rel, header in INDEXES:
        write_csv_header(root / rel, header)

    for rel, content in MD_FILES:
        (root / rel).write_text(content, encoding="utf-8")

    # 报告占位
    (root / "report" / "research_report.md").write_text(
        "---\ntitle: \"\"\nsubtitle: \"\"\nauthor: \"深度研究项目组\"\nversion: \"V1.0\"\ncreated_date: \"\"\ndata_cutoff_date: \"\"\nlanguage: \"zh-CN\"\nformat: \"deep-research-report\"\n---\n\n# 研究报告标题\n\n> 待填充。\n",
        encoding="utf-8",
    )

    print(f"✓ 已创建研究项目骨架: {root}")
    for rel, _ in TREE:
        print(f"  - {rel}/")
    print(f"  + {len(INDEXES)} 个索引 CSV + {len(MD_FILES)} 个 Markdown 占位")


def main() -> None:
    ap = argparse.ArgumentParser(description="创建深度研究项目目录树")
    ap.add_argument("project", nargs="?", default="deep-research-project",
                    help="项目目录名或路径（默认 deep-research-project）")
    ap.add_argument("--force", action="store_true", help="目录非空时仍覆盖")
    args = ap.parse_args()
    scaffold(Path(args.project), args.force)


if __name__ == "__main__":
    main()
