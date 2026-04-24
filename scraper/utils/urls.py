"""URL normalization and relevance helpers."""

from __future__ import annotations

import posixpath
from typing import Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urldefrag, urlparse, urlunparse

from scraper.utils.text import slugify


TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "mkt_")
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")


def canonicalize_url(url: str, base_url: Optional[str] = None) -> str:
    joined = urljoin(base_url, url) if base_url else url
    clean, _fragment = urldefrag(joined)
    parsed = urlparse(clean)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    path = parsed.path or "/"
    path = posixpath.normpath(path)
    if not path.startswith("/"):
        path = "/" + path
    if parsed.path.endswith("/") and not path.endswith("/"):
        path = path + "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not any(key.lower().startswith(prefix) for prefix in TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(filtered_query))
    return urlunparse((scheme, netloc, path, "", query, ""))


def extract_domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else "https://%s" % url)
    return parsed.netloc.lower().removeprefix("www.")


def extract_host(url: str) -> str:
    parsed = urlparse(url if "://" in url else "https://%s" % url)
    return parsed.netloc.lower()


def get_domain_slug(url_or_domain: str) -> str:
    domain = extract_domain(url_or_domain)
    return slugify(domain.replace(".", "-"), max_length=40)


def is_internal_url(url: str, allowed_domains: Sequence[str]) -> bool:
    if not allowed_domains:
        return True
    host = extract_host(url)
    for allowed in allowed_domains:
        normalized = extract_host(allowed)
        if host == normalized:
            return True
    return False


def is_probably_document_url(url: str) -> bool:
    lowered = url.lower()
    return any(lowered.endswith(extension) for extension in DOCUMENT_EXTENSIONS)


def looks_irrelevant_url(url: str, irrelevant_patterns: Sequence[str]) -> bool:
    lowered = url.lower()
    return any(pattern.lower() in lowered for pattern in irrelevant_patterns)


def score_url_relevance(
    url: str,
    anchor_text: str,
    relevant_keywords: Sequence[str],
    irrelevant_patterns: Sequence[str],
) -> int:
    if looks_irrelevant_url(url, irrelevant_patterns):
        return -100
    haystack = ("%s %s" % (url, anchor_text)).lower()
    score = 0
    for keyword in relevant_keywords:
        if keyword.lower() in haystack:
            score += 5
    if is_probably_document_url(url):
        score += 2
    return score


def filter_and_sort_links(
    links: Iterable[Tuple[str, str]],
    base_url: str,
    allowed_domains: Sequence[str],
    relevant_keywords: Sequence[str],
    irrelevant_patterns: Sequence[str],
) -> List[str]:
    scored = []
    seen = set()
    for href, text in links:
        canonical = canonicalize_url(href, base_url=base_url)
        if canonical in seen:
            continue
        if not is_internal_url(canonical, allowed_domains):
            continue
        score = score_url_relevance(canonical, text, relevant_keywords, irrelevant_patterns)
        if score <= 0:
            continue
        seen.add(canonical)
        scored.append((score, canonical))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [url for _score, url in scored]
