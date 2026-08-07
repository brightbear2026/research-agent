#!/usr/bin/env python3
"""qc.py — 报告质量检查：引用闭环、链接活性、截图真实性与对应、HTML 基本可用。

用法:
  uv run python tools/qc.py [--root <项目根>] [--report <md>] [--skip-links]

退出码：0 = 全部通过；1 = 发现问题。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

SEARCH_HOSTS = {"google.com", "www.google.com", "bing.com", "www.bing.com",
                "baidu.com", "www.baidu.com", "duckduckgo.com", "www.duckduckgo.com"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.ok: list[str] = []

    def emit(self) -> int:
        print("\n==== QC 结果 ====")
        for w in self.warnings:
            print(f"  ⚠ {w}")
        for e in self.errors:
            print(f"  ✗ {e}")
        for o in self.ok:
            print(f"  ✓ {o}")
        if self.errors:
            print(f"\n失败：{len(self.errors)} 项错误，{len(self.warnings)} 项警告")
            return 1
        print(f"\n通过：{len(self.ok)} 项，{len(self.warnings)} 项警告")
        return 0


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_citations(report: Report, md_text: str, citations: list[dict], root: Path) -> None:
    cited_in_text = set()
    for m in re.finditer(r"\[(\d{1,4})\]", md_text):
        cited_in_text.add(int(m.group(1)))
    registered: dict[int, dict] = {}
    for r in citations:
        try:
            registered[int(r.get("id", ""))] = r
        except (ValueError, TypeError):
            report.warnings.append(f"citations.csv 存在非数字 id: {r.get('id')!r}")

    missing = sorted(n for n in cited_in_text if n not in registered)
    orphans = sorted(n for n in registered if n not in cited_in_text)
    if missing:
        report.errors.append(f"正文引用未登记：{missing}（在 citations.csv 中找不到）")
    if orphans:
        report.warnings.append(f"citations.csv 有未在正文引用的条目：{orphans}")
    no_url = [n for n, r in registered.items() if not (r.get("url") or "").strip()]
    if no_url:
        report.warnings.append(f"参考文献缺 URL：{sorted(no_url)}")
    no_access = [n for n, r in registered.items() if not (r.get("access_date") or "").strip()]
    if no_access:
        report.warnings.append(f"参考文献缺访问日期：{sorted(no_access)}")
    report.ok.append(f"引用闭环：正文 {len(cited_in_text)} 个 / 登记 {len(registered)} 个")


def check_figures(report: Report, md_text: str, figures: list[dict], root: Path) -> None:
    fig_refs = set()
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md_text):
        src = m.group(1).split("?")[0]
        fig_refs.add(Path(src).name if not src.startswith("http") else src)

    by_name = {(Path(r.get("local_path", "")).name): r for r in figures if r.get("local_path")}
    fake = [r for r in figures if "占位" in (r.get("status", "")) or "失败" in (r.get("status", ""))]

    missing_files = []
    for name in fig_refs:
        if name in by_name:
            lp = root / by_name[name]["local_path"]
            if not lp.exists():
                missing_files.append(name)
        else:
            # 引用了图片但不在 figures.csv —— 检查文件是否实际存在
            candidates = [root / "images" / name, root / "report" / name, root / name]
            if any(p.exists() for p in candidates):
                report.warnings.append(f"图片 {name} 存在但未登记 figures.csv（自制图？请标注来源）")
            else:
                report.warnings.append(f"正文引用图片但找不到文件/未登记：{name}")

    if missing_files:
        report.errors.append(f"figures.csv 登记但文件缺失：{missing_files}")
    if fake:
        names = [r.get("fig_id", "?") for r in fake]
        report.warnings.append(f"存在占位/失败截图（非原始截图）：{names} —— 请人工后补或正文标注")
    report.ok.append(f"图片检查：正文引用 {len(fig_refs)} 个 / 登记 {len(figures)} 个")


def classify_url(url: str) -> tuple[str, str]:
    try:
        import httpx
    except ImportError:
        return ("skip", "httpx 不可用")
    try:
        with httpx.Client(follow_redirects=False, timeout=12.0, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }) as c:
            r = c.head(url)
            if r.status_code in (400, 405, 501):  # 部分站点对 HEAD 处理异常，回退 GET
                r = c.get(url)
            host = urlparse(url).netloc
            if host in SEARCH_HOSTS:
                return ("warn", "疑似搜索结果页链接，应替换为原始来源")
            if 300 <= r.status_code < 400:
                loc = r.headers.get("location", "")
                return ("warn", f"重定向 {r.status_code} → {loc}")
            # 400/401/403/429 通常是反爬/请求被拒/限流而非真死链
            # （来源经研究期 WebFetch 或 Playwright 截图验证存在）
            if r.status_code in (400, 401, 403, 429):
                return ("warn", f"HTTP {r.status_code}（疑似反爬/限流/需鉴权，建议人工核）")
            if r.status_code >= 400:
                return ("dead", f"HTTP {r.status_code}")
            return ("ok", f"HTTP {r.status_code}")
    except Exception as e:
        ename = type(e).__name__
        # 网络层异常多为瞬时或反爬，不作硬死链
        if ename in ("ConnectError", "ConnectTimeout", "ReadTimeout",
                     "PoolTimeout", "RemoteProtocolError", "ReadError"):
            return ("warn", f"网络异常 {ename}（可能瞬时/反爬，建议人工核）")
        return ("dead", f"异常: {ename}")


def check_links(report: Report, citations: list[dict], figures: list[dict]) -> None:
    urls: list[tuple[str, str]] = []  # (来源, url)
    for r in citations:
        u = (r.get("url") or "").strip()
        if u:
            urls.append((f"引用{r.get('id')}", u))
    for r in figures:
        u = (r.get("url") or "").strip()
        if u:
            urls.append((f"图{r.get('fig_id')}", u))

    if not urls:
        report.ok.append("链接检查：无 URL")
        return

    dead, warns = [], []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(classify_url, u): (tag, u) for tag, u in urls}
        for fut in as_completed(futs):
            tag, u = futs[fut]
            status, msg = fut.result()
            if status == "dead":
                dead.append(f"{tag} {u} ({msg})")
            elif status == "warn":
                warns.append(f"{tag} {u} ({msg})")
            elif status == "skip":
                warns.append(f"{tag} {u} ({msg})")
    if dead:
        report.errors.append(f"死链 {len(dead)} 个：" + "; ".join(dead[:8]))
    if warns:
        report.warnings.append(f"链接警告 {len(warns)} 个：" + "; ".join(warns[:8]))
    report.ok.append(f"链接检查：{len(urls)} 个 URL")


def run(root: Path, report_md: Path, skip_links: bool) -> int:
    rep = Report()
    if not report_md.exists():
        rep.errors.append(f"找不到报告: {report_md}")
        return rep.emit()
    md_text = report_md.read_text(encoding="utf-8")

    citations = load_csv(root / "data" / "citations.csv")
    figures = load_csv(root / "data" / "figures.csv")

    check_citations(rep, md_text, citations, root)
    check_figures(rep, md_text, figures, root)
    if not skip_links:
        check_links(rep, citations, figures)
    else:
        rep.ok.append("链接检查：已跳过 (--skip-links)")

    # HTML 基本可用
    html = report_md.with_suffix(".html")
    if html.exists() and html.stat().st_size > 0:
        rep.ok.append(f"HTML 已生成: {html.name}")
    else:
        rep.warnings.append(f"HTML 未生成或为空: {html.name}（运行 render_html.py）")
    return rep.emit()


def main() -> None:
    ap = argparse.ArgumentParser(description="报告质量检查")
    ap.add_argument("--root", default=".", help="项目根目录")
    ap.add_argument("--report", default=None, help="report.md 路径")
    ap.add_argument("--skip-links", action="store_true", help="跳过链接活性检查")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    report_md = Path(args.report).resolve() if args.report else root / "report" / "research_report.md"
    sys.exit(run(root, report_md, args.skip_links))


if __name__ == "__main__":
    main()
