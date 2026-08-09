#!/usr/bin/env python3
"""merge.py — 把章节草稿组装成报告，并生成全局引用索引。

本脚本只负责确定性组装，不承担总编辑工作。默认输出
``report/_assembled_report.md``，随后由 report-editor 将其压缩、去重并写成
``report/research_report.md``。这样可以避免把“章节拼接”误当成最终成稿。

兼容两种源标签：普通正文中的 ``[[SRC|...]]``，以及 Markdown 表格中为避免
列分隔而转义的 ``[[SRC\\|...]]``。旧草稿中的数据小表、截图登记和资料缺口
等生产过程章节会从读者正文移除；新草稿应把这些内容写入同名 ``.meta.json``。

用法:
  uv run python tools/merge.py <项目根> [--title <标题>] [--subtitle <副标题>]
      [--out report/_assembled_report.md]

标签格式（researcher 契约）:
  [[SRC|<类型>|<作者/机构>|<标题>|<出版物/网站>|<发布日期>|<url>|<访问日期>|<等级A/B/C/D>]]
同 url 复用同一 [n]；url 缺失则按整段标签文本去重。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

try:
    from tools.claim_ledger import build_ledger, write_ledger
except ModuleNotFoundError:  # 兼容直接执行 python tools/merge.py
    from claim_ledger import build_ledger, write_ledger

TAG_RE = re.compile(r"\[\[SRC(?:\\?\|)(.*?)\]\]")
URL_RE = re.compile(r"https?://[^\s|]+")
TIER_RE = re.compile(r"\|([ABCD])\]\]\s*$")

# 旧版 researcher 会把下面这些生产过程内容附在章节草稿末尾。它们应进入
# CSV / meta.json，而不应出现在最终面向读者的叙事中。
INTERNAL_SECTION_RE = re.compile(
    r"(?ms)^##+\s+(?:\d+(?:\.\d+)*\s+)?(?:"
    r"数据小表(?:（[^\n]*）)?|"
    r"建议截图(?:项|登记)?(?:（[^\n]*）)?|"
    r"待补充内容(?:（[^\n]*）)?"
    r").*?(?=^##?\s+|\Z)"
)

META_REQUIRED_KEYS = {
    "schema_version", "sources", "claims",
    "chapter_id", "title", "reader_question", "thesis", "argument_role",
    "data_points", "screenshots", "controversies", "gaps", "chapter_conclusion",
}

CITATIONS_COLS = [
    "id", "type", "author_org", "title", "publication_site",
    "publish_date", "doi_or_id", "url", "access_date", "page_or_location", "tier",
]


def normalize_tag_inner(inner: str) -> str:
    """把 Markdown 表格中的 ``\\|`` 恢复成源标签字段分隔符。"""
    return inner.replace(r"\|", "|")


def extract_url(inner: str) -> str:
    inner = normalize_tag_inner(inner)
    m = URL_RE.search(inner)
    return m.group(0) if m else ""


def norm_key(url: str) -> str:
    u = url.strip()
    if not u:
        return ""
    return u.rstrip("/").lower()


def parse_fields(inner: str) -> list[str]:
    inner = normalize_tag_inner(inner)
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


def strip_internal_sections(text: str) -> str:
    """移除旧草稿里不属于读者正文的生产过程章节。"""
    return re.sub(r"\n{3,}", "\n\n", INTERNAL_SECTION_RE.sub("", text)).strip() + "\n"


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
    ap = argparse.ArgumentParser(description="组装章节草稿 → _assembled_report.md + citations.csv")
    ap.add_argument("root", help="项目根目录")
    ap.add_argument("--title", default="深度研究报告")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--topic", default=None, help="研究课题（默认同 title）")
    ap.add_argument("--depth", default="标准", help="快速|标准|深度")
    ap.add_argument("--scope", default="", help="研究范围")
    ap.add_argument("--audience", default="", help="目标读者")
    ap.add_argument(
        "--out",
        default=None,
        help="组装稿路径（默认 <root>/report/_assembled_report.md）",
    )
    ap.add_argument("--require-meta", action="store_true",
                    help="要求每章都有字段完整的同名 .meta.json（新流程推荐）")
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
    chapter_meta: list[dict] = []
    missing_meta: list[str] = []
    for d in drafts:
        text = strip_internal_sections(d.read_text(encoding="utf-8"))
        chapter_texts.append((d.name, text))
        meta_path = d.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if not isinstance(meta, dict):
                    raise ValueError("顶层必须是 JSON object")
                missing_keys = sorted(META_REQUIRED_KEYS - set(meta))
                if missing_keys and args.require_meta:
                    raise ValueError(f"缺少字段: {missing_keys}")
                if args.require_meta and meta.get("schema_version") != 2:
                    raise ValueError("schema_version 必须为 2；旧元数据请先运行 migrate_chapter_meta.py")
                meta["_draft_file"] = d.name
                chapter_meta.append(meta)
            except (json.JSONDecodeError, ValueError) as e:
                sys.exit(f"✗ 无法解析章节元数据 {meta_path}: {e}")
        else:
            missing_meta.append(d.name)
        for m in TAG_RE.finditer(text):
            inner = normalize_tag_inner(m.group(1).strip())
            url = extract_url(inner)
            key = norm_key(url) or inner
            if key not in key_to_num:
                counter += 1
                key_to_num[key] = counter
                num_to_row[counter] = build_row(counter, list(parse_fields(inner)))

    if missing_meta and args.require_meta:
        sys.exit(f"✗ 以下章节缺少同名 .meta.json：{missing_meta}")

    # 第二遍：替换标签为 [n]，组装正文
    def repl(m: re.Match) -> str:
        inner = normalize_tag_inner(m.group(1).strip())
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

    frontmatter_data = {
        "title": args.title,
        "subtitle": args.subtitle,
        "research_topic": topic,
        "version": "1.0",
        "created_date": today,
        "data_cutoff_date": today,
        "depth": args.depth,
        "research_scope": args.scope,
        "target_audience": args.audience,
        "language": "zh-CN",
    }
    frontmatter = "---\n" + yaml.safe_dump(
        frontmatter_data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ) + "---\n\n"

    refs_md = build_refs_md(num_to_row)
    tail = ("\n---\n\n" + refs_md) if refs_md else ""
    report_md = Path(args.out).resolve() if args.out else report_dir / "_assembled_report.md"
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text(frontmatter + toc + body + tail, encoding="utf-8")

    # 写 citations.csv
    citations_path = root / "data" / "citations.csv"
    with citations_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CITATIONS_COLS)
        w.writeheader()
        for n in sorted(num_to_row):
            w.writerow(num_to_row[n])

    chapter_meta_path = root / "data" / "chapter_meta.json"
    chapter_meta_path.write_text(
        json.dumps(chapter_meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    claim_ledger_path = root / "data" / "claim_ledger.json"
    write_ledger(
        claim_ledger_path,
        build_ledger(frontmatter + toc + body + tail, chapter_meta, str(report_md)),
    )

    print(f"✓ 合并 {len(chapter_texts)} 章 → {report_md}")
    print(f"✓ 去重源标签 → {counter} 条引用写入 {citations_path}")
    print(f"✓ 汇总 {len(chapter_meta)} 份章节元数据 → {chapter_meta_path}")
    print(f"✓ 生成编辑前声明账本 → {claim_ledger_path}")
    if missing_meta:
        print(f"  ⚠ 有 {len(missing_meta)} 章缺少同名 .meta.json（旧草稿兼容模式）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
