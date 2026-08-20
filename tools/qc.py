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
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

try:
    from tools.claim_ledger import audit_text
    from tools.source_identity import source_independence_key
except ModuleNotFoundError:  # 兼容直接执行 python tools/qc.py
    from claim_ledger import audit_text
    from source_identity import source_independence_key

SEARCH_HOSTS = {"google.com", "www.google.com", "bing.com", "www.bing.com",
                "baidu.com", "www.baidu.com", "duckduckgo.com", "www.duckduckgo.com"}

INTERNAL_MARKERS = (
    "供 source_data",
    "供 `data/source_data",
    "供 screenshot_manifest",
    "建议截图项",
    "建议截图登记",
)

BANNED_PHRASES = (
    "众所周知",
    "毫无疑问",
    "必将",
    "彻底改变",
    "颠覆一切",
    "市场前景无限",
    "具有重大意义",
)
BOX_DRAWING_RE = re.compile(r"[┌┐└┘├┤┬┴┼─│╔╗╚╝╠╣╦╩╬═║▼▲▶◀]{3,}")
ENGLISH_QUOTE_WORD_LIMIT = 25

# 快变领域来源域名（小写子串匹配）：光通信 / AI 硬件 / 半导体月度迭代，
# 其 A/B 级来源若距今超 FRESHNESS_MONTHS 则提示核对最新数据，避免报告逼近保鲜期。
FAST_MOVING_DOMAINS = (
    "yolegroup.com", "lightcounting.com", "delloro.com", "lightwaveonline.net",
    "semianalysis.com", "cignal.ai", "lightreading.com",
)
FRESHNESS_MONTHS = 18

# 段落级数值声明触发词：保守模式——只在这些量纲出现时才视为“数值声明”。
NUMERIC_CLUE_RE = re.compile(
    r"\d[\d.,]*\s*(?:亿|万|美元|%|Gbps?|Tbps?|Gb/?s|Tb/?s|nm|CAGR|"
    r"市场份额|市场规模|出货|排名)"
)


@dataclass(frozen=True)
class ReadabilityProfile:
    min_body_chars: int
    max_body_chars: int
    max_sentence_chars: int
    p90_sentence_chars: int
    max_paragraph_chars: int
    max_heading_depth: int


READABILITY_PROFILES = {
    "快速": ReadabilityProfile(4_000, 20_000, 180, 90, 300, 3),
    "标准": ReadabilityProfile(10_000, 60_000, 220, 110, 400, 3),
    "深度": ReadabilityProfile(18_000, 100_000, 240, 120, 450, 4),
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


def _without_code(md_text: str, *, keep_non_mermaid_fences: bool = False) -> str:
    """移除代码块；检查框线图时只移除 Mermaid，以捕获 fenced ASCII 图。"""
    if keep_non_mermaid_fences:
        return re.sub(r"```mermaid\s*\n.*?```", "", md_text, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"```.*?```", "", md_text, flags=re.DOTALL)


def check_fact_citation_locality(report: Report, md_text: str, strict: bool) -> None:
    """每个带【事实】的正文段落必须在同一段内给出数字引用。"""
    body = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", md_text, flags=re.DOTALL)
    body = re.split(
        r"(?m)^#{1,3}\s+(?:参考文献|证据与方法附件|附录)\s*$",
        body,
        maxsplit=1,
    )[0]
    body = _without_code(body)
    missing: list[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        if "【事实】" not in paragraph:
            continue
        units = [line for line in paragraph.splitlines() if "【事实】" in line and line.lstrip().startswith("|")]
        if not units:
            units = [paragraph]
        for unit in units:
            if not re.search(r"\[\d{1,4}\]", unit):
                snippet = re.sub(r"\s+", " ", unit).strip()[:80]
                missing.append(snippet)
    if missing:
        add_issue(
            report,
            f"{len(missing)} 个【事实】段落没有同段引用 [n]：{missing[:5]}",
            strict,
        )
    else:
        report.ok.append("事实就近引用：所有【事实】段落均有同段引用")


def _english_word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", text))


def check_prohibited_content(report: Report, md_text: str, strict: bool) -> None:
    """拦截写作禁忌、手画框线图和过长英文直接引语。"""
    prose = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", md_text, flags=re.DOTALL)
    prose = re.split(
        r"(?m)^#{1,3}\s+(?:参考文献|证据与方法附件|附录)\s*$",
        prose,
        maxsplit=1,
    )[0]
    prose = _without_code(prose)
    phrases = [phrase for phrase in BANNED_PHRASES if phrase in prose]
    if phrases:
        add_issue(report, f"正文含禁用无证据套话：{phrases}", strict)

    ascii_candidate = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", md_text, flags=re.DOTALL)
    ascii_candidate = re.split(
        r"(?m)^#{1,3}\s+(?:参考文献|证据与方法附件|附录)\s*$",
        ascii_candidate,
        maxsplit=1,
    )[0]
    ascii_candidate = _without_code(ascii_candidate, keep_non_mermaid_fences=True)
    frames = BOX_DRAWING_RE.findall(ascii_candidate)
    if frames:
        add_issue(report, f"正文含 {len(frames)} 处手画 ASCII/Unicode 框线图；请改用 Mermaid 或表格", strict)

    quote_candidates: list[str] = []
    for pattern in (r'"([^"\n]+)"', r"“([^”]+)”", r"「([^」]+)」"):
        quote_candidates.extend(m.group(1) for m in re.finditer(pattern, prose, flags=re.DOTALL))
    quote_candidates.extend(
        re.sub(r"^>\s?", "", line)
        for line in prose.splitlines()
        if line.lstrip().startswith(">")
    )
    too_long = sorted(
        {_english_word_count(quote) for quote in quote_candidates
         if _english_word_count(quote) > ENGLISH_QUOTE_WORD_LIMIT},
        reverse=True,
    )
    if too_long:
        add_issue(
            report,
            f"英文直接引语超过 {ENGLISH_QUOTE_WORD_LIMIT} 词：最长 {too_long[0]} 词；请缩短并改为转述",
            strict,
        )
    if not phrases and not frames and not too_long:
        report.ok.append("内容禁忌：无禁用套话、框线图或过长英文直引")


def check_evidence_independence(report: Report, root: Path, depth: str, strict: bool) -> None:
    """从 chapter_meta 追踪结论到证据与来源，防止“有 ID 但无交叉验证”。"""
    path = root / "data" / "chapter_meta.json"
    if not path.exists():
        add_issue(report, f"找不到章节元数据，无法检查独立来源：{path}", strict)
        return
    try:
        chapters = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(f"无法读取章节元数据并检查独立来源：{exc}")
        return
    if not isinstance(chapters, list):
        report.errors.append("chapter_meta.json 顶层必须是数组")
        return

    minimum = 1 if depth == "快速" else 2
    failures: list[str] = []
    numeric_failures: list[str] = []
    weak_tier_failures: list[str] = []
    checked = 0
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("chapter_id") or "?")
        sources = {
            str(item.get("source_id")): item
            for item in chapter.get("sources", [])
            if isinstance(item, dict) and item.get("source_id")
        }
        evidence = {
            str(item.get("evidence_id")): item
            for item in chapter.get("data_points", [])
            if isinstance(item, dict) and item.get("evidence_id")
        }

        def source_ids_for(evidence_ids: list[str], direct_ids: list[str] | None = None) -> list[str]:
            source_ids = list(direct_ids or [])
            for evidence_id in evidence_ids:
                item = evidence.get(str(evidence_id), {})
                source_ids.extend(str(x) for x in item.get("source_ids", []) if x)
            return list(dict.fromkeys(source_ids))

        def groups_for(evidence_ids: list[str], direct_ids: list[str] | None = None) -> set[str]:
            return {
                source_independence_key(sources[sid])
                for sid in source_ids_for(evidence_ids, direct_ids)
                if sid in sources
            }

        conclusion = chapter.get("chapter_conclusion") or {}
        conclusion_groups = groups_for(conclusion.get("supporting_evidence_ids", []))
        checked += 1
        if len(conclusion_groups) < minimum:
            failures.append(f"{chapter_id}:{conclusion.get('claim_id', '?')}={len(conclusion_groups)}/{minimum}")
        conclusion_sources = source_ids_for(conclusion.get("supporting_evidence_ids", []))
        if not any(sources[sid].get("tier") in {"A", "B"} for sid in conclusion_sources if sid in sources):
            weak_tier_failures.append(f"{chapter_id}:{conclusion.get('claim_id', '?')}")

        for claim in chapter.get("claims", []):
            if not isinstance(claim, dict):
                continue
            linked = [evidence.get(str(eid), {}) for eid in claim.get("supporting_evidence_ids", [])]
            is_numeric = bool(re.search(r"\d", str(claim.get("text") or ""))) or any(
                isinstance(item.get("value"), (int, float))
                or bool(re.search(r"\d", str(item.get("value") or "")))
                for item in linked
            )
            if not is_numeric:
                continue
            groups = groups_for(
                claim.get("supporting_evidence_ids", []),
                [str(x) for x in claim.get("source_ids", [])],
            )
            if len(groups) < 2:
                numeric_failures.append(f"{chapter_id}:{claim.get('claim_id', '?')}={len(groups)}/2")
            numeric_sources = source_ids_for(
                claim.get("supporting_evidence_ids", []),
                [str(x) for x in claim.get("source_ids", [])],
            )
            if not any(sources[sid].get("tier") in {"A", "B"} for sid in numeric_sources if sid in sources):
                weak_tier_failures.append(f"{chapter_id}:{claim.get('claim_id', '?')}")

    if failures:
        add_issue(report, f"章节重要结论独立来源不足：{failures}", strict)
    if numeric_failures:
        add_issue(report, f"数值声明未达到 2 个独立来源：{numeric_failures}", strict)
    if weak_tier_failures:
        add_issue(report, f"重要/数值声明仅由 C/D 级或未知来源支撑：{sorted(set(weak_tier_failures))}", strict)
    if not failures and not numeric_failures and not weak_tier_failures:
        report.ok.append(f"证据独立性：{checked} 个章节结论通过（最低 {minimum} 个独立来源）")


def _parse_year_month(value: str | None) -> tuple[int, int] | None:
    """从 publish_date 文本提取 (year, month)；只认首个 YYYY 或 YYYY-MM，月缺省取 1。

    跳过「未注明」「访问日期…」与空值等无法解析的口径。
    """
    if not value:
        return None
    m = re.search(r"(\d{4})(?:[-/](\d{1,2}))?", str(value))
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2)) if m.group(2) else 1
    if not (1900 <= year <= 2100 and 1 <= month <= 12):
        return None
    return (year, month)


def check_source_freshness(
    report: Report,
    citations: list[dict],
    strict: bool,
    *,
    reference_date: datetime | None = None,
) -> None:
    """对快变领域的 A/B 级来源检查时效：距今超阈值给 advisory（建议核对最新数据）。

    reference_date 可注入以便测试；默认取当前时间。
    """
    # advisory-only：时效是新鲜度提示而非正确性缺陷，始终进 warnings。strict 形参预留，
    # 未来若要在 --strict 下升级为阻断，可把 report.warnings.append(...) 改为 add_issue(..., strict)。
    ref = reference_date or datetime.now()
    ref_total = ref.year * 12 + ref.month
    threshold = FRESHNESS_MONTHS
    stale: list[str] = []
    checked = 0
    for r in citations:
        if (r.get("tier") or "").strip().upper() not in {"A", "B"}:
            continue
        url = (r.get("url") or "").lower()
        if not any(dom in url for dom in FAST_MOVING_DOMAINS):
            continue
        ym = _parse_year_month(r.get("publish_date"))
        if not ym:
            continue
        checked += 1
        age_months = ref_total - (ym[0] * 12 + ym[1])
        if age_months > threshold:
            title = (r.get("title") or "").strip()[:40]
            stale.append(
                f"引用{r.get('id')}《{title}》发表于 {ym[0]:04d}-{ym[1]:02d}，"
                f"距今 {age_months} 个月"
            )
    if stale:
        report.warnings.append(
            f"时效性：{len(stale)} 个快变领域来源距今超 {threshold} 个月，建议核对最新数据："
            + "；".join(stale[:6])
        )
    elif checked:
        report.ok.append(f"来源时效性：{checked} 个快变领域 A/B 级来源均在 {threshold} 个月内")
    else:
        report.ok.append("来源时效性：无可解析日期的快变领域 A/B 级来源")


def check_numeric_claim_sourcing(
    report: Report,
    md_text: str,
    citations: list[dict],
    strict: bool,
) -> None:
    """段落级数值声明不得仅由单一 C/D 级来源支撑。

    针对「单源 C/D 级（营销/自媒体）数值以【事实】进正文」的盲区——「≥2 独立来源」
    规则只在 chapter_meta 结论/claim 粒度校验，正文段落只要 ≥1 引用即放行。本检查补上
    段落粒度：复用事实就近引用的正文分段与【事实】检测，保守触发（仅【事实】段 +
    命中数值量纲 + 段内去重引用恰 1 个且其等级 ∈ {C, D}）。advisory，不阻断。
    """
    # advisory-only：始终进 warnings。strict 形参预留，未来若要在 --strict 下升级为阻断，
    # 可把 report.warnings.append(...) 改为 add_issue(report, ..., strict)。
    tier_by_id: dict[int, str] = {}
    for r in citations:
        try:
            tier_by_id[int(r.get("id", ""))] = (r.get("tier") or "").strip().upper()
        except (ValueError, TypeError):
            continue
    body = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", md_text, flags=re.DOTALL)
    body = re.split(
        r"(?m)^#{1,3}\s+(?:参考文献|证据与方法附件|附录)\s*$",
        body, maxsplit=1,
    )[0]
    body = _without_code(body)
    weak: list[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        if "【事实】" not in paragraph:
            continue
        if not NUMERIC_CLUE_RE.search(paragraph):
            continue
        units = [line for line in paragraph.splitlines()
                 if "【事实】" in line and line.lstrip().startswith("|")]
        if not units:
            units = [paragraph]
        for unit in units:
            if not NUMERIC_CLUE_RE.search(unit):
                continue
            ids = {int(m) for m in re.findall(r"\[(\d{1,4})\]", unit)}
            if len(ids) != 1:
                continue
            nid = next(iter(ids))
            if tier_by_id.get(nid, "") in {"C", "D"}:
                snippet = re.sub(r"\s+", " ", unit).strip()[:60]
                weak.append(f"[{nid}]({tier_by_id.get(nid)}) {snippet}")
    if weak:
        report.warnings.append(
            "段落级数值声明仅依赖单一 C/D 级来源，建议补独立第二来源或改标【推测】："
            + "；".join(weak[:6])
        )
    else:
        report.ok.append("段落级数值声明：未发现单一 C/D 级来源支撑的数值")


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


def check_diagrams(
    report: Report,
    md_text: str,
    diagrams: list[dict],
    figures: list[dict],
    root: Path,
    strict: bool,
) -> None:
    """检查 Diagram Design 静态源、PNG、正文位置和来源追踪。"""
    if not diagrams:
        report.ok.append("Diagram Design：无登记图")
        return
    try:
        from tools.diagram_assets import resolve_input_path, validate_diagram_html
        from tools.screenshot import resolve_image_output
    except ModuleNotFoundError:
        from diagram_assets import resolve_input_path, validate_diagram_html
        from screenshot import resolve_image_output

    body_images = {
        Path(match.group(1).split("?")[0]).name
        for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md_text)
        if not match.group(1).startswith("http")
    }
    figures_by_id = {
        (row.get("fig_id") or "").strip(): row
        for row in figures if (row.get("fig_id") or "").strip()
    }
    seen: set[str] = set()
    valid = 0
    for row in diagrams:
        fig_id = (row.get("fig_id") or "").strip()
        if not re.fullmatch(r"FIG-\d{3,}", fig_id):
            report.errors.append(f"diagram_manifest.csv fig_id 无效：{fig_id!r}")
            continue
        if fig_id in seen:
            report.errors.append(f"diagram_manifest.csv fig_id 重复：{fig_id}")
            continue
        seen.add(fig_id)
        if not (row.get("source_ids") or "").strip():
            report.errors.append(f"Diagram Design {fig_id} 缺少 source_ids")
        if not (row.get("supports_conclusion") or "").strip():
            report.errors.append(f"Diagram Design {fig_id} 缺少 supports_conclusion")
        try:
            source = resolve_input_path(root, (row.get("source_html") or "").strip())
            output, normalized = resolve_image_output(
                root, (row.get("local_path") or "").strip(), fig_id,
            )
        except ValueError as exc:
            report.errors.append(f"Diagram Design {fig_id} 路径无效：{exc}")
            continue
        html_errors = validate_diagram_html(source)
        if html_errors:
            report.errors.append(f"Diagram Design {fig_id} 静态源无效：{'；'.join(html_errors)}")
        figure = figures_by_id.get(fig_id)
        if figure is None:
            add_issue(report, f"Diagram Design {fig_id} 未登记 figures.csv", strict)
        else:
            if (figure.get("local_path") or "").strip() != normalized:
                report.errors.append(f"Diagram Design {fig_id} 与 figures.csv 的 local_path 不一致")
            if "Diagram Design" not in (figure.get("status") or ""):
                add_issue(report, f"Diagram Design {fig_id} 的 figures.csv 状态不是生成图状态", strict)
        if not output.exists():
            add_issue(report, f"Diagram Design {fig_id} 尚未导出 PNG：{normalized}", strict)
        if Path(normalized).name not in body_images:
            add_issue(report, f"Diagram Design {fig_id} 未内联到正文对应论断附近", strict)
        if not html_errors:
            valid += 1
    report.ok.append(f"Diagram Design：登记 {len(diagrams)} 张 / 静态源通过 {valid} 张")


def wayback_snapshot(url: str, timeout: float = 6.0) -> str | None:
    """查询 Wayback Availability API；有归档返回快照 URL，否则 None。

    任意异常/超时/格式异常都优雅降级为 None（绝不拖垮链接检查）。仅对已判定的
    死链调用，量小。
    """
    try:
        import httpx
    except ImportError:
        return None
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as c:
            r = c.get("https://archive.org/available", params={"url": url})
            if r.status_code != 200:
                return None
            data = r.json()
            snap = (data.get("archived_snapshots") or {}).get("closest") or {}
            if snap.get("available") and snap.get("url"):
                return str(snap["url"])
            return None
    except Exception:
        return None


def _dead_or_archived(status_msg: str, url: str) -> tuple[str, str]:
    """死链判定前查 Wayback：有归档则降为 archived（保留死因 + 存档链接），否则保持 dead。

    这样伪造 URL（无归档）在 qc_debt.json 中显眼标红，而真实但反爬/失效的来源能被
    Wayback 佐证其曾存在——守护「不编造 URL」红线的同时不再惩罚好来源。
    """
    snap = wayback_snapshot(url)
    if snap:
        return ("archived", f"{status_msg}；Wayback 已归档：{snap}")
    return ("dead", status_msg)


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
                return _dead_or_archived(f"HTTP {r.status_code}", url)
            return ("ok", f"HTTP {r.status_code}")
    except Exception as e:
        ename = type(e).__name__
        # 网络层异常多为瞬时或反爬，不作硬死链
        if ename in ("ConnectError", "ConnectTimeout", "ReadTimeout",
                     "PoolTimeout", "RemoteProtocolError", "ReadError"):
            return ("warn", f"网络异常 {ename}（可能瞬时/反爬，建议人工核）")
        return _dead_or_archived(f"异常: {ename}", url)


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

    dead, archived, warns = [], [], []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(classify_url, u): (tag, u) for tag, u in urls}
        for fut in as_completed(futs):
            tag, u = futs[fut]
            status, msg = fut.result()
            if status == "dead":
                dead.append(f"{tag} {u} ({msg})")
            elif status == "archived":
                archived.append(f"{tag} {u} ({msg})")
            elif status in ("warn", "skip"):
                warns.append(f"{tag} {u} ({msg})")
    # 死链永不阻断 exit：链接活性与来源质量负相关（反爬越严的站点越是 A/B 级好来源），
    # 故降为建议 + Wayback 标注。死链/归档/警告全部进 warnings 与 qc_debt.json，
    # 由人工异步收尾，不再阻塞核心交付。
    if dead:
        report.warnings.append(
            f"死链 {len(dead)} 个（建议人工核 / 补来源，不阻断交付）："
            + "; ".join(dead[:8])
        )
    if archived:
        report.warnings.append(
            f"已归档死链 {len(archived)} 个（HTTP 失败但 Wayback 有存档✓）："
            + "; ".join(archived[:8])
        )
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

    if body_chars < profile.min_body_chars:
        add_issue(
            report,
            f"正文约 {body_chars} 字符，低于 {depth} 档最低完整度 {profile.min_body_chars}；"
            "请补齐核心论证、证据解释、反证和限制，不得用重复文字凑数",
            strict,
        )
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


def _categorize_warning(msg: str) -> str:
    """按既定前缀把 advisory warning 归类（供 qc_debt.json by_category 统计）。"""
    if msg.startswith("已归档死链 "):
        return "archived_links"
    if msg.startswith("死链 "):
        return "dead_links"
    if msg.startswith("链接警告 "):
        return "link_warnings"
    if msg.startswith("时效性："):
        return "staleness"
    if msg.startswith("段落级数值声明"):
        return "numeric_sourcing"
    return "other"


def _write_qc_debt(root: Path, rep: Report, exit_code: int) -> None:
    """把 advisory 项（warnings）与核心错误摘要写为 data/qc_debt.json，供交付交接。

    死链/时效/数值来源/链接警告等非阻断项落 debt 清单异步收尾；核心错误（errors）才是
    阻断交付的闸门。写入失败不影响退出码（debt 本身是 advisory）。
    """
    by_category: dict[str, int] = {}
    debt: list[dict] = []
    for msg in rep.warnings:
        cat = _categorize_warning(msg)
        by_category[cat] = by_category.get(cat, 0) + 1
        debt.append({"category": cat, "severity": "advisory", "detail": msg})
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "exit_code": exit_code,
        "core_passed": exit_code == 0,
        "summary": {
            "errors": len(rep.errors),
            "warnings": len(rep.warnings),
            "by_category": by_category,
        },
        "debt": debt,
    }
    out = root / "data" / "qc_debt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    diagrams = load_csv(root / "data" / "diagram_manifest.csv")

    check_citations(rep, md_text, citations, root, strict)
    check_source_freshness(rep, citations, strict)
    check_fact_citation_locality(rep, md_text, strict)
    check_numeric_claim_sourcing(rep, md_text, citations, strict)
    check_prohibited_content(rep, md_text, strict)
    check_evidence_independence(rep, root, depth, strict)
    check_figures(rep, md_text, figures, root, strict)
    check_diagrams(rep, md_text, diagrams, figures, root, strict)
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
    exit_code = rep.emit()
    # 两段式交付：advisory 项写 qc_debt.json 供异步收尾，核心错误才阻断（exit_code 已定）。
    try:
        _write_qc_debt(root, rep, exit_code)
    except OSError:
        pass
    return exit_code


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
