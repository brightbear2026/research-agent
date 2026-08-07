#!/usr/bin/env python3
"""render_html.py — 把 Markdown 报告渲染为自包含 HTML。

单一事实源：`report.md` 为规范叙事；引用 `[n]`、图片元数据、表格均从
`data/citations.csv` 与 `data/figures.csv` 派生，保证 MD 与 HTML 一致。

用法:
  uv run python tools/render_html.py <report.md> [out.html] [--root <项目根>] [--template <html.j2>]
默认 out = 与 md 同名的 .html（report/ 目录下）。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
import yaml

TEMPLATE_DIR = (Path(__file__).resolve().parent.parent / "templates")


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, m.group(2)


def load_csv_dicts(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def assign_heading_ids(body_html: str) -> tuple[str, list[dict]]:
    """给 h1-h3 加 id 并收集导航项。"""
    nav: list[dict] = []
    counter = 0

    def repl(m: re.Match) -> str:
        nonlocal counter
        counter += 1
        level = int(m.group(1))
        inner = m.group(2)
        hid = f"sec-{counter}"
        text = re.sub(r"<[^>]+>", "", inner).strip()
        if text:
            nav.append({"level": level, "text": text, "id": hid})
        return f'<h{level} id="{hid}">{inner}</h{level}>'

    new_html = re.sub(r"<h([1-3])>(.*?)</h\1>", repl, body_html, flags=re.DOTALL)
    return new_html, nav


TAG_MAP = {  # 行内标签 → HTML span
    "【事实】": '<span class="tag tag-fact">事实</span>',
    "【机构观点": None,  # 特殊：带参数
    "【观点": None,
    "【争议】": '<span class="tag tag-dispute">争议</span>',
    "【研究判断】": '<span class="tag tag-judge">研究判断</span>',
    "【推测】": '<span class="tag tag-guess">推测</span>',
}


def render_inline_tags(html: str) -> str:
    """把行内标签渲染为彩色 chip。支持 【观点·姓名·机构·日期】 / 【机构观点·机构·日期】。"""
    def repl_view(m: re.Match) -> str:
        inner = m.group(1)
        return f'<span class="tag tag-opinion">观点·{inner}</span>'

    def repl_org(m: re.Match) -> str:
        inner = m.group(1)
        return f'<span class="tag tag-org">机构观点·{inner}</span>'

    html = re.sub(r"【观点·([^】]*)】", repl_view, html)
    html = re.sub(r"【机构观点·([^】]*)】", repl_org, html)
    html = re.sub(r"【机构观点】", '<span class="tag tag-org">机构观点</span>', html)
    html = html.replace("【事实】", TAG_MAP["【事实】"])
    html = html.replace("【争议】", TAG_MAP["【争议】"])
    html = html.replace("【研究判断】", TAG_MAP["【研究判断】"])
    html = html.replace("【推测】", TAG_MAP["【推测】"])
    return html


def enhance_figures(body_html: str, figures: list[dict]) -> str:
    """把 <p><img></p> 或 <img> 包成 <figure>，并用 figures.csv 补 figcaption。"""
    by_name = {}
    by_id = {}
    for row in figures:
        lp = (row.get("local_path") or "").strip()
        if lp:
            by_name[Path(lp).name] = row
        fid = (row.get("fig_id") or "").strip()
        if fid:
            by_id[fid] = row

    def fig_for(src: str) -> dict | None:
        name = Path(src.split("?")[0]).name
        if name in by_name:
            return by_name[name]
        # src 可能含 fig_id
        m = re.search(r"(FIG-\d+)", src)
        if m and m.group(1) in by_id:
            return by_id[m.group(1)]
        return None

    def doc_disp(doc: str) -> str:
        doc = (doc or "").strip()
        if not doc:
            return ""
        return doc if doc.startswith("《") else f"《{doc}》"

    def build_figure(img_tag: str) -> str:
        sm = re.search(r'src="([^"]+)"', img_tag)
        am = re.search(r'alt="([^"]*)"', img_tag)
        src = sm.group(1) if sm else ""
        alt = am.group(1) if am else ""
        row = fig_for(src)
        title = (row.get("title") if row else "") or alt or Path(src).name
        cap_parts = [f"<b>{title}</b>"]
        if row and row.get("source_org"):
            seg = f"来源：{row['source_org']}"
            dd = doc_disp(row.get("source_doc", ""))
            if dd:
                seg += f"，{dd}"
            if row.get("publish_date"):
                seg += f"，{row['publish_date']}"
            cap_parts.append(seg)
        elif alt:
            cap_parts.append(f"来源：{alt}")
        caption = "。".join(cap_parts)
        if not caption.endswith("。"):
            caption += "。"
        status = row.get("status", "") if row else ""
        note = ' <span style="color:#b91c1c">（占位图，非原始截图）</span>' if "占位" in status else ""
        # HTML 位于 report/，图片位于项目根 images/，相对路径需上溯一层
        if src and not src.startswith(("http", "//", "/", "../")):
            display_src = "../" + src
        else:
            display_src = src
        return (f'<figure><img src="{display_src}" alt="{alt}">'
                f'<figcaption>{caption}{note}</figcaption></figure>')

    # <p><img ...></p>  →  <figure>（重建干净的 img 标签）
    body_html = re.sub(
        r'<p>\s*(<img[^>]*>)\s*</p>',
        lambda m: build_figure(m.group(1)),
        body_html, flags=re.DOTALL,
    )
    return body_html


def link_citations(body_html: str) -> set[int]:
    """把 [n] 转成锚链接，返回被引用的 id 集合。"""
    cited: set[int] = set()

    def repl(m: re.Match) -> str:
        n = int(m.group(1))
        cited.add(n)
        return f'<a class="cite" href="#ref-{n}">[{n}]</a>'

    body_html = re.sub(r"\[(\d{1,4})\]", repl, body_html)
    return body_html, cited


def build_refs(citations: list[dict], cited: set[int]) -> str:
    if not citations:
        return ""
    rows = {}
    for r in citations:
        rid = r.get("id", "").strip()
        try:
            rows[int(rid)] = r
        except (ValueError, TypeError):
            continue
    # 渲染被引用的（若全无被引用信息，则渲染全部）
    target = sorted(cited) if cited else sorted(rows)
    items = []
    for n in target:
        if n not in rows:
            items.append(f'<li value="{n}"><i>引用 {n}：暂未在 citations.csv 登记</i></li>')
            continue
        r = rows[n]
        seg = []
        author = r.get("author_org", "").strip()
        if author:
            seg.append(author)
        title = r.get("title", "").strip()
        if title:
            seg.append(f"《{title}》" if not title.startswith("《") else title)
        pub = r.get("publication_site", "").strip()
        date = r.get("publish_date", "").strip()
        tail = []
        if pub:
            tail.append(pub)
        if date:
            tail.append(date)
        if tail:
            seg.append(", ".join(tail))
        url = r.get("url", "").strip()
        if url:
            seg.append(f'<a href="{url}" target="_blank" rel="noopener">{url}</a>')
        extra = []
        doi = r.get("doi_or_id", "").strip()
        if doi:
            extra.append(f"DOI/ID: {doi}")
        ad = r.get("access_date", "").strip()
        if ad:
            extra.append(f"访问 {ad}")
        pg = r.get("page_or_location", "").strip()
        if pg:
            extra.append(pg)
        tier = r.get("tier", "").strip()
        if tier:
            extra.append(f"等级 {tier}")
        line = ". ".join(s for s in seg if s)
        if extra:
            line += "（" + "；".join(extra) + "）"
        items.append(f'<li value="{n}">{line}.</li>')
    return "<ol>\n" + "\n".join(items) + "\n</ol>"


def render(md_path: Path, out_path: Path, root: Path, template_path: Path) -> None:
    text = md_path.read_text(encoding="utf-8")
    meta, body_md = split_frontmatter(text)

    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    body_html = md.render(body_md)

    body_html, nav = assign_heading_ids(body_html)
    body_html = render_inline_tags(body_html)
    figures = load_csv_dicts(root / "data" / "figures.csv")
    body_html = enhance_figures(body_html, figures)
    body_html, cited = link_citations(body_html)

    citations = load_csv_dicts(root / "data" / "citations.csv")
    # 若 MD 已含参考文献（由 merge.py 写入），则不重复注入，避免 HTML 出现双份
    refs_html = "" if 'id="ref-1"' in body_html else build_refs(citations, cited)

    env = Environment(loader=FileSystemLoader(str(template_path.parent)),
                      autoescape=select_autoescape(default=False))
    tmpl = env.get_template(template_path.name)
    html = tmpl.render(meta=meta, nav=nav, body_html=body_html, refs_html=refs_html)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"✓ HTML 已生成: {out_path}（导航 {len(nav)} 项，引用 {len(cited)} 个，参考 {len(refs_html.split(chr(10)))} 行）")


def main() -> None:
    ap = argparse.ArgumentParser(description="Markdown 报告 → 自包含 HTML")
    ap.add_argument("md", help="report.md 路径")
    ap.add_argument("out", nargs="?", default=None, help="输出 html 路径（默认同名 .html）")
    ap.add_argument("--root", default=None, help="项目根（默认 md 所在目录上溯到含 data/ 的目录）")
    ap.add_argument("--template", default=str(TEMPLATE_DIR / "report.html.j2"))
    args = ap.parse_args()

    md_path = Path(args.md).resolve()
    if not md_path.exists():
        sys.exit(f"✗ 找不到 markdown: {md_path}")

    out_path = Path(args.out).resolve() if args.out else md_path.with_suffix(".html")

    root = Path(args.root).resolve() if args.root else _infer_root(md_path)
    render(md_path, out_path, root, Path(args.template).resolve())


def _infer_root(md_path: Path) -> Path:
    # md 在 <root>/report/ 下；否则用 md 所在目录
    if md_path.parent.name == "report":
        return md_path.parent.parent
    return md_path.parent


if __name__ == "__main__":
    main()
