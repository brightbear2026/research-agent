#!/usr/bin/env python3
"""qc.py — 报告质量检查：引用、链接、截图、编辑边界与可读性。

用法:
  uv run python tools/qc.py [--root <项目根>] [--report <md>] [--skip-links]
      [--strict] [--depth 快速|标准|深度] [--citation-baseline <组装稿>]
      [--claim-ledger <声明账本>]

退出码：0 = 全部通过；1 = 发现问题。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

try:
    from tools.claim_ledger import audit_text
except ModuleNotFoundError:  # 兼容直接执行 python tools/qc.py
    from claim_ledger import audit_text

SEARCH_HOSTS = {"google.com", "www.google.com", "bing.com", "www.bing.com",
                "baidu.com", "www.baidu.com", "duckduckgo.com", "www.duckduckgo.com"}

INTERNAL_MARKERS = (
    "供 source_data",
    "供 `data/source_data",
    "供 screenshot_manifest",
    "建议截图项",
    "建议截图登记",
)


@dataclass(frozen=True)
class ReadabilityProfile:
    max_body_chars: int
    max_sentence_chars: int
    p90_sentence_chars: int
    max_paragraph_chars: int
    max_heading_depth: int


READABILITY_PROFILES = {
    "快速": ReadabilityProfile(20_000, 180, 90, 300, 3),
    "标准": ReadabilityProfile(60_000, 220, 110, 400, 3),
    "深度": ReadabilityProfile(100_000, 240, 120, 450, 4),
}


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


def add_issue(report: Report, message: str, strict: bool) -> None:
    """在最终交付模式下把关键警告升级为错误。"""
    (report.errors if strict else report.warnings).append(message)


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def extract_citation_ids(md_text: str) -> set[int]:
    """提取叙事中的数字引用；忽略 fenced code，避免示例代码误报。"""
    without_fences = re.sub(r"```.*?```", "", md_text, flags=re.DOTALL)
    return {int(m.group(1)) for m in re.finditer(r"\[(\d{1,4})\]", without_fences)}


def check_citations(
    report: Report,
    md_text: str,
    citations: list[dict],
    root: Path,
    strict: bool,
) -> None:
    cited_in_text = extract_citation_ids(md_text)
    registered: dict[int, dict] = {}
    duplicate_ids: set[int] = set()
    for r in citations:
        try:
            rid = int(r.get("id", ""))
            if rid in registered:
                duplicate_ids.add(rid)
            registered[rid] = r
        except (ValueError, TypeError):
            add_issue(report, f"citations.csv 存在非数字 id: {r.get('id')!r}", strict)

    if duplicate_ids:
        report.errors.append(f"citations.csv 存在重复 id：{sorted(duplicate_ids)}")

    missing = sorted(n for n in cited_in_text if n not in registered)
    orphans = sorted(n for n in registered if n not in cited_in_text)
    if missing:
        report.errors.append(f"正文引用未登记：{missing}（在 citations.csv 中找不到）")
    if orphans:
        report.warnings.append(f"citations.csv 有未在正文引用的条目：{orphans}")
    no_url = [n for n, r in registered.items() if not (r.get("url") or "").strip()]
    if no_url:
        add_issue(report, f"参考文献缺 URL：{sorted(no_url)}", strict)
    no_access = [n for n, r in registered.items() if not (r.get("access_date") or "").strip()]
    if no_access:
        add_issue(report, f"参考文献缺访问日期：{sorted(no_access)}", strict)
    bad_tier = [n for n, r in registered.items()
                if (r.get("tier") or "").strip().upper() not in {"A", "B", "C", "D"}]
    if bad_tier:
        add_issue(report, f"参考文献缺有效来源等级 A/B/C/D：{sorted(bad_tier)}", strict)
    report.ok.append(f"引用闭环：正文 {len(cited_in_text)} 个 / 登记 {len(registered)} 个")


def check_figures(
    report: Report,
    md_text: str,
    figures: list[dict],
    root: Path,
    strict: bool,
) -> None:
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
                add_issue(report, f"图片 {name} 存在但未登记 figures.csv（自制图？请标注来源）", strict)
            else:
                add_issue(report, f"正文引用图片但找不到文件/未登记：{name}", strict)

    if missing_files:
        report.errors.append(f"figures.csv 登记但文件缺失：{missing_files}")
    if fake:
        names = [r.get("fig_id", "?") for r in fake]
        add_issue(report, f"存在占位/失败截图（非原始截图）：{names} —— 请人工后补或正文标注", strict)
    # 反向校验：真实截图必须内联到正文，不得只留在索引或集中堆末尾
    unplaced = [r.get("fig_id", "?") for r in figures
                if (r.get("status") or "") == "已截图"
                and r.get("local_path")
                and Path(r["local_path"]).name not in fig_refs]
    if unplaced:
        add_issue(report, f"已生成截图未内联到正文（应插入对应章节，勿集中堆附录/末尾）：{unplaced}", strict)
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
            if r.status_code in (400, 405, 412, 501):  # HEAD 可能不支持或缺少前置条件，回退 GET
                r = c.get(url)
            host = urlparse(url).netloc
            if host in SEARCH_HOSTS:
                return ("warn", "疑似搜索结果页链接，应替换为原始来源")
            if 300 <= r.status_code < 400:
                loc = r.headers.get("location", "")
                return ("warn", f"重定向 {r.status_code} → {loc}")
            if r.status_code == 412:
                body = r.text[:4096].lower()
                access_markers = ("captcha", "验证码", "waf", "access denied", "bot challenge")
                if any(marker in body for marker in access_markers):
                    return ("warn", "HTTP 412（响应内容疑似访问控制，建议人工核）")
                return ("warn", "HTTP 412（前置条件失败；原因未确认，不能统一视为反爬）")
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


def _percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * ratio))]


def narrative_text(md_text: str) -> str:
    """提取用于可读性统计的正文，排除元数据、代码、表格和参考文献。"""
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", md_text, flags=re.DOTALL)
    text = re.split(r"(?m)^#{1,3}\s+(?:参考文献|证据与方法附件|附录)\s*$", text, maxsplit=1)[0]
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"(?m)^\s*\|.*\|\s*$", "", text)
    text = re.sub(r"(?m)^\s*(?:[-*_]\s*){3,}$", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    return text


def check_readability(
    report: Report,
    md_text: str,
    depth: str,
    strict: bool,
) -> None:
    profile = READABILITY_PROFILES[depth]
    body = narrative_text(md_text)

    residual_tags = re.findall(r"\[\[SRC(?:\\?\|)", body)
    if residual_tags:
        report.errors.append(f"正文仍存在 {len(residual_tags)} 个未转换的 [[SRC|...]] 源标签")

    markers = [marker for marker in INTERNAL_MARKERS if marker in body]
    if markers:
        add_issue(report, f"正文残留生产过程文字：{markers}", strict)
    internal_headings = re.findall(
        r"(?m)^#{2,6}\s+(?:\d+(?:\.\d+)*\s+)?"
        r"(?:数据小表|建议截图(?:项|登记)?|待补充内容)(?:（[^\n]*）)?\s*$",
        body,
    )
    if internal_headings:
        add_issue(report, f"正文残留 {len(internal_headings)} 个生产过程章节", strict)

    plain = re.sub(r"(?m)^#{1,6}\s+.*$", "", body)
    plain = re.sub(r"<[^>]+>", "", plain)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = re.sub(r"【[^】]+】", "", plain)
    plain = re.sub(r"\[\d+(?:[-,，]\s*\d+)*\]", "", plain)
    body_chars = len(re.sub(r"\s+", "", plain))

    paragraphs = [re.sub(r"\s+", " ", p.strip())
                  for p in re.split(r"\n\s*\n", plain)
                  if p.strip() and not p.lstrip().startswith(("#", "- ", ">"))]
    paragraph_lengths = [len(p) for p in paragraphs]
    sentences = [s.strip() for s in re.split(r"[。！？!?]\s*", "\n".join(paragraphs)) if s.strip()]
    sentence_lengths = [len(s) for s in sentences]

    if body_chars > profile.max_body_chars:
        add_issue(
            report,
            f"正文约 {body_chars} 字符，超过 {depth} 档建议上限 {profile.max_body_chars}",
            strict,
        )
    overly_long = [n for n in sentence_lengths if n > profile.max_sentence_chars]
    if overly_long:
        add_issue(
            report,
            f"存在 {len(overly_long)} 个超长句，最长 {max(overly_long)} 字符（上限 {profile.max_sentence_chars}）",
            strict,
        )
    p90_sentence = _percentile(sentence_lengths, 0.90)
    if p90_sentence > profile.p90_sentence_chars:
        add_issue(
            report,
            f"句长 P90 为 {p90_sentence}，高于 {depth} 档建议值 {profile.p90_sentence_chars}",
            strict,
        )
    long_paragraphs = [n for n in paragraph_lengths if n > profile.max_paragraph_chars]
    if long_paragraphs:
        add_issue(
            report,
            f"存在 {len(long_paragraphs)} 个过长段落，最长 {max(long_paragraphs)} 字符（上限 {profile.max_paragraph_chars}）",
            strict,
        )

    headings = [(len(m.group(1)), m.group(2).strip())
                for m in re.finditer(r"(?m)^(#{1,6})\s+(.+)$", body)]
    too_deep = [title for level, title in headings if level > profile.max_heading_depth]
    if too_deep:
        add_issue(
            report,
            f"标题层级超过 {depth} 档上限 H{profile.max_heading_depth}：{too_deep[:8]}",
            strict,
        )
    jumps = []
    for (prev_level, _), (level, title) in zip(headings, headings[1:]):
        if level > prev_level + 1:
            jumps.append(title)
    if jumps:
        add_issue(report, f"标题层级存在跳跃：{jumps[:8]}", strict)

    # 论证型章节必须先回答问题，再说明对行动的影响；执行摘要、方法和附件不参与。
    chapter_starts = list(re.finditer(r"(?m)^#\s+(第\s*\d+\s*章[^\n]*)$", body))
    missing_answer: list[str] = []
    missing_implication: list[str] = []
    for idx, match in enumerate(chapter_starts):
        end = chapter_starts[idx + 1].start() if idx + 1 < len(chapter_starts) else len(body)
        chapter = body[match.end():end]
        title = match.group(1).strip()
        if not re.search(r"(?m)^##\s+本章结论\s*$", chapter):
            missing_answer.append(title)
        if not re.search(r"(?m)^##\s+对决策的含义\s*$", chapter):
            missing_implication.append(title)
    if missing_answer:
        add_issue(report, f"章节开头缺少「本章结论」：{missing_answer[:8]}", strict)
    if missing_implication:
        add_issue(report, f"章节结尾缺少「对决策的含义」：{missing_implication[:8]}", strict)

    fact_tags = len(re.findall(r"【事实】", body))
    tags_per_10k = fact_tags * 10_000 / max(body_chars, 1)
    if tags_per_10k > 25:
        report.warnings.append(
            f"事实标签密度较高：每万字 {tags_per_10k:.1f} 个，建议普通事实默认不显示标签"
        )

    avg_sentence = statistics.mean(sentence_lengths) if sentence_lengths else 0
    report.ok.append(
        f"可读性：正文约 {body_chars} 字符 / {len(paragraphs)} 段 / "
        f"平均句长 {avg_sentence:.1f} / P90 {p90_sentence}"
    )


def check_editor_baseline(report: Report, md_text: str, baseline_path: Path | None) -> None:
    if baseline_path is None:
        return
    if not baseline_path.exists():
        report.errors.append(f"找不到编辑基线稿: {baseline_path}")
        return
    final_ids = extract_citation_ids(md_text)
    baseline_ids = extract_citation_ids(baseline_path.read_text(encoding="utf-8"))
    introduced = sorted(final_ids - baseline_ids)
    if introduced:
        report.errors.append(f"编辑阶段引入了组装稿中不存在的引用：{introduced}")
    else:
        report.ok.append("编辑审计：未引入组装稿之外的引用")


def check_claim_ledger(
    report: Report,
    md_text: str,
    ledger_path: Path | None,
    strict: bool,
) -> None:
    if ledger_path is None:
        add_issue(report, "未提供声明账本，无法检查数字、日期、实体和确定性漂移", strict)
        return
    if not ledger_path.exists():
        add_issue(report, f"找不到声明账本：{ledger_path}", strict)
        return
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        result = audit_text(md_text, ledger)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        report.errors.append(f"无法读取声明账本：{exc}")
        return
    report.errors.extend(result["errors"])
    for warning in result["warnings"]:
        if "限制/不确定性" in warning:
            add_issue(report, warning, strict)
        else:
            report.warnings.append(warning)
    blocking_warning = strict and any("限制/不确定性" in item for item in result["warnings"])
    if not result["errors"] and not blocking_warning:
        report.ok.append("事实漂移审计：数字、日期、实体、确定性和限制条件未越界")


def run(
    root: Path,
    report_md: Path,
    skip_links: bool,
    strict: bool = False,
    depth: str = "标准",
    skip_readability: bool = False,
    citation_baseline: Path | None = None,
    claim_ledger: Path | None = None,
) -> int:
    rep = Report()
    if not report_md.exists():
        rep.errors.append(f"找不到报告: {report_md}")
        return rep.emit()
    md_text = report_md.read_text(encoding="utf-8")

    citations = load_csv(root / "data" / "citations.csv")
    figures = load_csv(root / "data" / "figures.csv")

    check_citations(rep, md_text, citations, root, strict)
    check_figures(rep, md_text, figures, root, strict)
    if not skip_readability:
        check_readability(rep, md_text, depth, strict)
    else:
        rep.ok.append("可读性检查：已跳过 (--skip-readability)")
    check_editor_baseline(rep, md_text, citation_baseline)
    check_claim_ledger(rep, md_text, claim_ledger, strict)
    if not skip_links:
        check_links(rep, citations, figures)
    else:
        rep.ok.append("链接检查：已跳过 (--skip-links)")

    # HTML 基本可用
    html = report_md.with_suffix(".html")
    if html.exists() and html.stat().st_size > 0:
        rep.ok.append(f"HTML 已生成: {html.name}")
    else:
        add_issue(rep, f"HTML 未生成或为空: {html.name}（运行 render_html.py）", strict)
    return rep.emit()


def main() -> None:
    ap = argparse.ArgumentParser(description="报告质量检查")
    ap.add_argument("--root", default=".", help="项目根目录")
    ap.add_argument("--report", default=None, help="report.md 路径")
    ap.add_argument("--skip-links", action="store_true", help="跳过链接活性检查")
    ap.add_argument("--strict", action="store_true", help="最终交付模式：关键警告升级为错误")
    ap.add_argument("--depth", choices=sorted(READABILITY_PROFILES), default="标准",
                    help="用于可读性阈值的深度档位")
    ap.add_argument("--skip-readability", action="store_true", help="跳过可读性检查")
    ap.add_argument("--citation-baseline", default=None,
                    help="总编辑前的组装稿；校验终稿未创造新引用")
    ap.add_argument("--claim-ledger", default=None,
                    help="编辑前声明账本；默认使用 <root>/data/claim_ledger.json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    report_md = Path(args.report).resolve() if args.report else root / "report" / "research_report.md"
    baseline = Path(args.citation_baseline).resolve() if args.citation_baseline else None
    ledger = Path(args.claim_ledger).resolve() if args.claim_ledger else root / "data" / "claim_ledger.json"
    sys.exit(run(root, report_md, args.skip_links, args.strict, args.depth,
                 args.skip_readability, baseline, ledger))


if __name__ == "__main__":
    main()
