#!/usr/bin/env python3
"""merge.py — 把 report/_draft_chNN_*.md 合并成 report/research_report.md，并把内联源标签 [[SRC|...]] 去重为全局 [n] 引用，写出 data/citations.csv。

单一事实源：草稿为 canonical 片段；本脚本做**确定性合并**——按 url 去重标签、依首次出现分配 [n]、统一替换、组装正文 + frontmatter。HTML 由 render_html.py 从 MD + citations.csv 派生。

用法:
  uv run python tools/merge.py <项目根> [--title <标题>] [--subtitle <副标题>]

标签格式（researcher 契约）:
  [[SRC|<类型>|<作者/机构>|<标题>|<出版物/网站>|<发布日期>|<url>|<访问日期>|<等级A/B/C/D>]]
同 url 复用同一 [n]；url 缺失则按整段标签文本去重。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

TAG_RE = re.compile(r"\[\[SRC\|(.*?)\]\]")
URL_RE = re.compile(r"https?://[^\s|]+")
TIER_RE = re.compile(r"\|([ABCD])\]\]\s*$")

CITATIONS_COLS = [
    "id", "type", "author_org", "title", "publication_site",
    "publish_date", "doi_or_id", "url", "access_date", "page_or_location", "tier",
]


def extract_url(inner: str) -> str:
    m = URL_RE.search(inner)
    return m.group(0) if m else ""


def norm_key(url: str) -> str:
    u = url.strip()
    if not u:
        return ""
    return u.rstrip("/").lower()


def parse_fields(inner: str) -> list[str]:
    parts = inner.split("|")
    # 期望 8 段：type|author|title|pub|date|url|access|tier
    if len(parts) == 8:
        return parts
    # 容错：title 含 | 等导致段数异常——用 url/tier 正则兜底，前几段尽力取
    url = extract_url(inner)
    tier = ""
    m = re.search(r"([ABCD])\s*$", inner.strip())
    if m:
        tier = m.group(1)
    # 去掉末尾 url|access|tier，前面按 | 切前三段
    head = inner
    if url:
        head = inner.split(url)[0].rstrip("|")
    head_parts = [p.strip() for p in head.split("|")]
    while len(head_parts) < 4:
        head_parts.append("")
    access = ""
    if url:
        tail = inner.split(url, 1)[1].lstrip("|")
        # tail 形如 access|tier
        tail_parts = [t.strip() for t in tail.split("|")]
        if tail_parts:
            access = tail_parts[0]
    return head_parts[0], head_parts[1], head_parts[2], head_parts[3], "", url, access, tier  # type: ignore[return-value]


def build_row(n: int, parts: list[str]) -> dict:
    # parts: type, author_org, title, publication_site, publish_date, url, access_date, tier
    p = (parts + [""] * 8)[:8]
    return {
        "id": n,
        "type": p[0].strip(),
        "author_org": p[1].strip(),
        "title": p[2].strip(),
        "publication_site": p[3].strip(),
        "publish_date": p[4].strip(),
        "doi_or_id": "",
        "url": p[5].strip(),
        "access_date": p[6].strip(),
        "page_or_location": "",
        "tier": p[7].strip(),
    }


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").strip()


def build_refs_md(num_to_row: dict[int, dict]) -> str:
    """从 citations 数据生成 Markdown 参考文献 <ol>（带 id="ref-N" 锚点），写入 MD 使其自包含。"""
    if not num_to_row:
        return ""
    items = []
    for n in sorted(num_to_row):
        r = num_to_row[n]
        seg = []
        a = _esc(r.get("author_org", ""))
        if a:
            seg.append(a)
        t = _esc(r.get("title", ""))
        if t:
            seg.append(f"《{t}》" if not t.startswith("《") else t)
        pub = _esc(r.get("publication_site", ""))
        d = _esc(r.get("publish_date", ""))
        tail = [x for x in (pub, d) if x]
        if tail:
            seg.append("，".join(tail))
        url = (r.get("url", "") or "").strip()
        if url:
            seg.append(f'<a href="{url}">{url}</a>')
        extra = []
        ad = _esc(r.get("access_date", ""))
        if ad:
            extra.append(f"访问 {ad}")
        tier = _esc(r.get("tier", ""))
        if tier:
            extra.append(f"等级 {tier}")
        line = ". ".join(s for s in seg if s)
        if extra:
            line += "（" + "；".join(extra) + "）"
        items.append(f'<li value="{n}" id="ref-{n}">{line}.</li>')
    return "## 参考文献\n\n<ol>\n" + "\n".join(items) + "\n</ol>\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="合并章节草稿 → research_report.md + citations.csv")
    ap.add_argument("root", help="项目根目录")
    ap.add_argument("--title", default="深度研究报告")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--topic", default=None, help="研究课题（默认同 title）")
    ap.add_argument("--depth", default="标准", help="快速|标准|深度")
    ap.add_argument("--scope", default="", help="研究范围")
    ap.add_argument("--audience", default="", help="目标读者")
    args = ap.parse_args()
    topic = args.topic or args.title
    today = date.today().isoformat()

    root = Path(args.root).resolve()
    report_dir = root / "report"
    drafts = sorted(report_dir.glob("_draft_ch*.md"))
    if not drafts:
        sys.exit(f"✗ 在 {report_dir} 找不到 _draft_ch*.md 草稿")

    # 第一遍：按出现顺序收集标签、去重、分配 [n]
    key_to_num: dict[str, int] = {}
    num_to_row: dict[int, dict] = {}
    counter = 0
    chapter_texts: list[tuple[str, str]] = []
    for d in drafts:
        text = d.read_text(encoding="utf-8")
        chapter_texts.append((d.name, text))
        for m in TAG_RE.finditer(text):
            inner = m.group(1).strip()
            url = extract_url(inner)
            key = norm_key(url) or inner
            if key not in key_to_num:
                counter += 1
                key_to_num[key] = counter
                num_to_row[counter] = build_row(counter, list(parse_fields(inner)))

    # 第二遍：替换标签为 [n]，组装正文
    def repl(m: re.Match) -> str:
        inner = m.group(1).strip()
        url = extract_url(inner)
        key = norm_key(url) or inner
        return f"[{key_to_num[key]}]"

    body_chunks: list[str] = []
    toc_lines: list[str] = []
    for name, text in chapter_texts:
        new_text = TAG_RE.sub(repl, text)
        # 取首个一级标题作为目录项
        hm = re.search(r"^#\s+(.+)$", new_text, re.MULTILINE)
        if hm:
            toc_lines.append(f"- {hm.group(1).strip()}")
        body_chunks.append(new_text.rstrip())

    toc = "## 目录\n\n" + "\n".join(toc_lines) + "\n\n---\n\n" if toc_lines else ""
    body = ("\n\n---\n\n".join(body_chunks)) + "\n"

    frontmatter = f"""---
title: "{args.title}"
subtitle: "{args.subtitle}"
research_topic: "{topic}"
version: "1.0"
created_date: "{today}"
data_cutoff_date: "{today}"
depth: "{args.depth}"
research_scope: "{args.scope}"
target_audience: "{args.audience}"
language: "zh-CN"
---

"""

    refs_md = build_refs_md(num_to_row)
    tail = ("\n---\n\n" + refs_md) if refs_md else ""
    report_md = report_dir / "research_report.md"
    report_md.write_text(frontmatter + toc + body + tail, encoding="utf-8")

    # 写 citations.csv
    citations_path = root / "data" / "citations.csv"
    with citations_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CITATIONS_COLS)
        w.writeheader()
        for n in sorted(num_to_row):
            w.writerow(num_to_row[n])

    print(f"✓ 合并 {len(chapter_texts)} 章 → {report_md}")
    print(f"✓ 去重源标签 → {counter} 条引用写入 {citations_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
