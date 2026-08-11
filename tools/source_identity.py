"""来源 URL 规范化与独立性分组的共享实现。"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

TRACKING_QUERY_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid",
    "igshid", "vero_conv", "vero_id", "mkt_tok",
}
MULTI_LABEL_PUBLIC_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.cn", "net.cn", "org.cn", "gov.cn",
    "com.au", "net.au", "org.au", "co.jp", "co.kr", "co.in",
}


def canonical_url_key(url: str) -> str:
    """消除协议、www、跟踪参数、片段及常见 DOI/arXiv 版本别名。"""
    raw = url.strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError:
        return raw.rstrip("/").lower()
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if port and not (
        (parts.scheme.lower() == "http" and port == 80)
        or (parts.scheme.lower() == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")

    if host in {"doi.org", "dx.doi.org"}:
        host = "doi.org"
        path = "/" + path.lstrip("/").lower()
    elif host == "arxiv.org":
        paper = re.fullmatch(r"/(?:abs|pdf)/(.+?)(?:\.pdf)?", path, flags=re.IGNORECASE)
        if paper:
            identifier = re.sub(r"v\d+$", "", paper.group(1), flags=re.IGNORECASE)
            path = f"/abs/{identifier.lower()}"

    path = path.rstrip("/") or "/"
    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
    ]
    query = urlencode(sorted(query_items))
    return host + path + (f"?{query}" if query else "")


def registrable_host(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    if not host:
        return ""
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    suffix = ".".join(labels[-2:])
    return ".".join(labels[-3:]) if suffix in MULTI_LABEL_PUBLIC_SUFFIXES else suffix


def source_independence_key(source: dict) -> str:
    """优先使用人工声明的分组，其次机构，再保守回退到注册域。"""
    explicit = str(source.get("independence_group") or "").strip().lower()
    if explicit:
        return f"group:{explicit}"
    organization = str(
        source.get("organization") or source.get("author_org") or ""
    ).strip().lower()
    if organization:
        return f"org:{organization}"
    host = registrable_host(str(source.get("url") or "").strip())
    return f"domain:{host}" if host else "unknown"
