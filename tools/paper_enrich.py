#!/usr/bin/env python3
"""paper_enrich.py — 文献存在性验证与元数据回填。

对 `data/paper_list.csv` 逐行验证（借鉴 paper-orchestra 的两段式引用闸：发现→验证）：
有 DOI / arXiv ID 走确定性端点；否则按标题在 Crossref（可选加 Semantic Scholar，需
S2_API_KEY）检索。验证结果区分五种状态，其中只有 not_found / mismatch 需要人工核对：

  verified        找到高置信匹配，回填规范元数据（作者/年份/venue/DOI）
  mismatch        有候选但标题或年份对不上（可能是记忆错位的转引，人工核对）
  not_found       完成检索但无匹配（编造嫌疑；也可能是未被索引的中文文献/白皮书）
  network_error   网络/限流失败，不代表文献有问题，勿据此改稿
  skipped         行内既无标题也无 DOI/arXiv 标识，无法验证

输出：
  data/paper_list_enriched.csv  原列 + verification_status / matched_* / api_source 等
  data/paper_verification.json  汇总（qc.py 读取后生成 advisory，进 qc_debt，永不阻断）

用法:
  uv run python tools/paper_enrich.py --root projects/<slug> [--mail-to a@b.c]
  [--similarity-threshold 0.90] [--max-rows N] [--no-s2]

Crossref 建议 `--mail-to`（或环境变量 CROSSREF_MAILTO）进入 polite pool；
S2 默认在检测到 S2_API_KEY 时启用，调用间隔 ≥1s 避免限流。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(\S+)$", re.IGNORECASE)
ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?", re.IGNORECASE)
DOI_URL_RE = re.compile(r"(?:doi\.org|dx\.doi\.org)/(10\.\S+)", re.IGNORECASE)
DOI_FIELD_RE = re.compile(r"(10\.\d{4,9}/\S+)", re.IGNORECASE)
CROSSREF_API = "https://api.crossref.org/works"
ARXIV_API = "https://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"

VERIFIED = "verified"
MISMATCH = "mismatch"
NOT_FOUND = "not_found"
NETWORK_ERROR = "network_error"
SKIPPED = "skipped"

ENRICHED_HEADER_SUFFIX = [
    "verification_status", "matched_title", "matched_authors", "matched_year",
    "matched_venue", "matched_doi", "api_source", "similarity", "checked_at",
]


@dataclass
class Match:
    title: str = ""
    authors: str = ""
    year: str = ""
    venue: str = ""
    doi: str = ""
    similarity: float = 1.0
    api_source: str = ""


@dataclass
class RowResult:
    index: int
    title: str
    status: str
    reason: str = ""
    match: Match = field(default_factory=Match)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9一-鿿]", "", (text or "").lower())


def title_similarity(left: str, right: str) -> float:
    a, b = normalize_title(left), normalize_title(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def _year_of(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(19|20)\d{2}", str(text))
    return int(match.group(0)) if match else None


def extract_identifiers(row: dict[str, str]) -> tuple[str, str]:
    """从行内提取 (doi, arxiv_id)。arXiv DOI 折算成 arXiv ID 交给 arXiv API。"""
    doi = ""
    for source in (row.get("doi") or "", row.get("url") or ""):
        if ARXIV_DOI_RE.match(source.strip()):
            return "", ARXIV_DOI_RE.match(source.strip()).group(1)
        for pattern in (DOI_URL_RE, DOI_FIELD_RE):
            match = pattern.search(source)
            if match:
                doi = match.group(1).rstrip(".,;")
                break
        if doi:
            break
    arxiv_match = ARXIV_URL_RE.search(row.get("url") or "")
    return (doi, arxiv_match.group(1) if arxiv_match else "")


class ApiClient:
    """薄 HTTP 客户端；transport 可注入（测试用 httpx.MockTransport）。

    所有方法在失败时抛 TransportError/StatusError（由调用方归入 network_error），
    无匹配返回 None，命中返回 Match。
    """

    def __init__(self, *, mail_to: str = "", s2_api_key: str = "",
                 transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(
            timeout=20.0, follow_redirects=True,
            headers={"User-Agent": f"research-agent-paper-enrich/1.0 ({mail_to})" if mail_to
                     else "research-agent-paper-enrich/1.0"},
            transport=transport,
        )
        self._mail_to = mail_to
        self._s2_key = s2_api_key
        self._last_s2_call = 0.0

    def close(self) -> None:
        self._client.close()

    def _get(self, url: str, params: dict[str, str] | None = None,
             headers: dict[str, str] | None = None) -> httpx.Response:
        last_exc: Exception | None = None
        for _ in range(2):  # 网络抖动重试一次
            try:
                response = self._client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise  # 确定性「不存在」，交给调用方按无匹配处理
                last_exc = exc
            except (httpx.TransportError, httpx.HTTPError) as exc:
                last_exc = exc
                time.sleep(1.0)
        raise last_exc  # type: ignore[misc]

    def crossref_by_doi(self, doi: str) -> Match | None:
        try:
            response = self._get(f"{CROSSREF_API}/{doi}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        message = response.json().get("message", {})
        return _crossref_match(message, api="crossref:doi")

    def crossref_search(self, title: str) -> Match | None:
        params: dict[str, str] = {
            "query.bibliographic": title, "rows": "5",
            "select": "title,author,issued,container-title,DOI",
        }
        if self._mail_to:
            params["mailto"] = self._mail_to
        response = self._get(CROSSREF_API, params=params)
        items = response.json().get("message", {}).get("items", [])
        best: Match | None = None
        for item in items:
            match = _crossref_match(item, api="crossref:search")
            if best is None or match.similarity > best.similarity:
                best = match
        return best

    def arxiv_by_id(self, arxiv_id: str) -> Match | None:
        response = self._get(ARXIV_API, params={"id_list": arxiv_id, "max_results": "1"})
        root = ElementTree.fromstring(response.text)
        namespace = {"a": "http://www.w3.org/2005/Atom"}
        entry = root.find("a:entry", namespace)
        if entry is None:
            return None
        title = re.sub(r"\s+", " ", (entry.findtext("a:title", "", namespace) or "")).strip()
        published = entry.findtext("a:published", "", namespace) or ""
        authors = "; ".join(
            author.findtext("a:name", "", namespace) or ""
            for author in entry.findall("a:author", namespace)
        )[:300]
        if not title:
            return None
        return Match(
            title=title, authors=authors,
            year=published[:4] if published else "",
            venue="arXiv", doi=f"10.48550/arXiv.{arxiv_id}",
            similarity=1.0, api_source="arxiv:id",
        )

    def s2_search(self, title: str) -> Match | None:
        if not self._s2_key:
            return None
        # S2 公共池限流严格：调用间隔 ≥1s（与 paper-orchestra 的做法一致）
        wait = 1.05 - (time.monotonic() - self._last_s2_call)
        if wait > 0:
            time.sleep(wait)
        self._last_s2_call = time.monotonic()
        response = self._get(
            S2_API,
            params={"query": title, "limit": "3", "fields": "title,year,authors,venue,externalIds"},
            headers={"X-API-KEY": self._s2_key},
        )
        for item in response.json().get("data", []):
            match = Match(
                title=item.get("title") or "",
                authors="; ".join(a.get("name") or "" for a in item.get("authors", []))[:300],
                year=str(item.get("year") or ""),
                venue=item.get("venue") or "",
                doi=(item.get("externalIds") or {}).get("DOI", ""),
                api_source="s2:search",
            )
            match.similarity = title_similarity(title, match.title)
            return match  # 只取首位候选，调用方按阈值判定
        return None


def _crossref_match(message: dict[str, Any], *, api: str) -> Match:
    titles = message.get("title") or []
    authors = "; ".join(
        ((a.get("family") or "") + (", " + a.get("given", "") if a.get("given") else "")).strip(", ")
        for a in message.get("author", [])
    )[:300]
    issued = ((message.get("issued") or {}).get("date-parts") or [[None]])
    venues = message.get("container-title") or []
    match = Match(
        title=re.sub(r"\s+", " ", titles[0]).strip() if titles else "",
        authors=authors,
        year=str(issued[0][0] or "") if issued and issued[0] else "",
        venue=re.sub(r"\s+", " ", venues[0]).strip() if venues else "",
        doi=message.get("DOI") or "",
        api_source=api,
    )
    return match


def verify_row(
    row: dict[str, str],
    index: int,
    client: ApiClient,
    *,
    threshold: float = 0.90,
    use_s2: bool = True,
) -> RowResult:
    title = (row.get("title") or "").strip()
    doi, arxiv_id = extract_identifiers(row)
    if not title and not doi and not arxiv_id:
        return RowResult(index, title, SKIPPED, "无标题且无 DOI/arXiv 标识")

    network_failed = False
    attempts: list[Match | None] = []

    def attempt(call) -> Match | None:
        nonlocal network_failed
        try:
            return call()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            network_failed = True
            return None
        except (httpx.TransportError, httpx.HTTPError):
            network_failed = True
            return None

    # 1) 标识符优先：DOI / arXiv 是确定性锚点
    if arxiv_id:
        attempts.append(attempt(lambda: client.arxiv_by_id(arxiv_id)))
    if doi:
        attempts.append(attempt(lambda: client.crossref_by_doi(doi)))

    best: Match | None = None
    for candidate in attempts:
        if candidate is not None and candidate.title:
            best = candidate
            break

    # 2) 标题检索兜底（Crossref → 可选 S2）
    if best is None and title:
        crossref = attempt(lambda: client.crossref_search(title))
        if crossref is not None and crossref.title:
            crossref.similarity = title_similarity(title, crossref.title)
            best = crossref
        if best is None and use_s2:
            s2 = attempt(lambda: client.s2_search(title))
            if s2 is not None and s2.title:
                s2.similarity = title_similarity(title, s2.title)
                best = s2

    # 3) 判定
    if best is None:
        if network_failed and not attempts and title:
            # 连 Crossref 都没问成：无法下结论
            return RowResult(index, title, NETWORK_ERROR, "检索端点不可达")
        if network_failed:
            return RowResult(index, title, NETWORK_ERROR,
                             "部分端点网络失败，无匹配结论不可信，请重跑")
        return RowResult(index, title, NOT_FOUND,
                         "Crossref/arXiv" + ("/S2" if use_s2 else "") + " 检索后无匹配；"
                         "可能是转引错位、未被索引的中文文献或白皮书，请人工核对原文")

    row_year = _year_of(row.get("publish_date"))
    match_year = _year_of(best.year)
    if title and best.similarity < threshold:
        return RowResult(index, title, MISMATCH,
                         f"最佳候选相似度 {best.similarity:.2f} 低于阈值 {threshold}："
                         f"《{best.title[:80]}》", best)
    if (row_year and match_year and abs(row_year - match_year) > 1
            and best.api_source != "arxiv:id"):
        return RowResult(index, title, MISMATCH,
                         f"标题匹配但年份相差过大（登记 {row_year} / 库存 {match_year}）", best)
    reason = ""
    if row_year and match_year and row_year != match_year:
        reason = f"年份差 {abs(row_year - match_year)} 年（arXiv→会议常见），已按库存年份回填"
    return RowResult(index, title, VERIFIED, reason, best)


def verify_paper_list(
    rows: list[dict[str, str]],
    client: ApiClient,
    *,
    threshold: float = 0.90,
    use_s2: bool = True,
) -> list[RowResult]:
    return [
        verify_row(row, index, client, threshold=threshold, use_s2=use_s2)
        for index, row in enumerate(rows, start=1)
    ]


def write_outputs(
    root: Path,
    rows: list[dict[str, str]],
    results: list[RowResult],
    *,
    paper_list_rel: str = "data/paper_list.csv",
) -> tuple[Path, Path]:
    checked_at = now_iso()
    enriched_path = root / "data" / "paper_list_enriched.csv"
    enriched_path.parent.mkdir(parents=True, exist_ok=True)
    header = list(rows[0].keys()) if rows else []
    with enriched_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header + ENRICHED_HEADER_SUFFIX)
        writer.writeheader()
        for row, result in zip(rows, results):
            record = dict(row)
            match = result.match
            record.update({
                "verification_status": result.status,
                "matched_title": match.title,
                "matched_authors": match.authors,
                "matched_year": match.year,
                "matched_venue": match.venue,
                "matched_doi": match.doi,
                "api_source": match.api_source,
                "similarity": f"{match.similarity:.3f}",
                "checked_at": checked_at,
            })
            writer.writerow(record)

    by_status: dict[str, int] = {}
    for result in results:
        by_status[result.status] = by_status.get(result.status, 0) + 1
    manifest = {
        "generated_at": checked_at,
        "tool": "paper_enrich.py",
        "source": paper_list_rel,
        "threshold_note": "not_found ≠ 编造实锤：未被学术索引收录的文献会落入此状态，须人工核对",
        "total": len(results),
        "by_status": by_status,
        "rows": [
            {
                "row": result.index,
                "title": result.title,
                "status": result.status,
                "reason": result.reason,
                "matched_title": result.match.title,
                "matched_year": result.match.year,
                "matched_doi": result.match.doi,
                "api_source": result.match.api_source,
                "similarity": round(result.match.similarity, 3),
            }
            for result in results
        ],
    }
    verification_path = root / "data" / "paper_verification.json"
    verification_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return enriched_path, verification_path


def main() -> int:
    parser = argparse.ArgumentParser(description="paper_list 文献存在性验证与元数据回填")
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--paper-list", default="data/paper_list.csv",
                        help="相对项目根的文献清单路径")
    parser.add_argument("--mail-to", default=os.environ.get("CROSSREF_MAILTO", ""),
                        help="Crossref polite pool 邮箱（建议填写）")
    parser.add_argument("--similarity-threshold", type=float, default=0.90)
    parser.add_argument("--max-rows", type=int, default=0, help="只验证前 N 行（调试用）")
    parser.add_argument("--no-s2", action="store_true", help="禁用 Semantic Scholar")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paper_list = (root / args.paper_list).resolve()
    if not paper_list.exists():
        print(f"✗ 找不到文献清单：{paper_list}", file=sys.stderr)
        return 2
    with paper_list.open(encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if any((v or "").strip() for v in row.values())]
    if not rows:
        print("✓ paper_list.csv 无数据行，跳过验证")
        return 0
    if args.max_rows > 0:
        rows = rows[:args.max_rows]

    use_s2 = not args.no_s2
    client = ApiClient(
        mail_to=args.mail_to,
        s2_api_key=os.environ.get("S2_API_KEY", ""),
    )
    try:
        results = verify_paper_list(
            rows, client, threshold=args.similarity_threshold, use_s2=use_s2,
        )
    finally:
        client.close()

    enriched, manifest = write_outputs(root, rows, results, paper_list_rel=args.paper_list)
    by_status: dict[str, int] = {}
    for result in results:
        by_status[result.status] = by_status.get(result.status, 0) + 1
    print(f"✓ 验证完成：{len(results)} 行 → {by_status}")
    print(f"  - 明细：{enriched}")
    print(f"  - 汇总：{manifest}")
    for result in results:
        if result.status in (NOT_FOUND, MISMATCH):
            label = "未找到" if result.status == NOT_FOUND else "疑似错位"
            print(f"  ⚠ [{label}] 第{result.index}行《{result.title[:60]}》{result.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
