"""URL normalization and relevance helpers."""

from __future__ import annotations

import re
import posixpath
from typing import Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urldefrag, urlparse, urlunparse

from scraper.utils.text import slugify


TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "mkt_")
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff")

DOCUMENT_CONTEXT_MIN_SCORE = 8
DOCUMENT_CONTEXT_STOPWORDS = {
    "application",
    "brochure",
    "checklist",
    "document",
    "documents",
    "download",
    "form",
    "forms",
    "fund",
    "funding",
    "grant",
    "guide",
    "guideline",
    "guidelines",
    "investment",
    "loan",
    "media",
    "offer",
    "program",
    "programme",
    "project",
    "services",
    "support",
}


def _tokenize_url_text(text: str) -> List[str]:
    return [
        token
        for token in re.split(r"[^a-z0-9]+", (text or "").lower())
        if token and len(token) > 2
    ]


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


def _without_www(host: str) -> str:
    return (host or "").lower().removeprefix("www.")


def hosts_match(candidate_host: str, allowed_host: str) -> bool:
    candidate = extract_host(candidate_host)
    allowed = extract_host(allowed_host)
    if not candidate or not allowed:
        return False
    if candidate == allowed:
        return True
    return _without_www(candidate) == _without_www(allowed) and (
        candidate.startswith("www.") or allowed.startswith("www.")
    )


def get_domain_slug(url_or_domain: str) -> str:
    domain = extract_domain(url_or_domain)
    return slugify(domain.replace(".", "-"), max_length=40)


def is_internal_url(url: str, allowed_domains: Sequence[str]) -> bool:
    if not allowed_domains:
        return True
    host = extract_host(url)
    for allowed in allowed_domains:
        if hosts_match(host, allowed):
            return True
    return False


def is_probably_document_url(url: str) -> bool:
    lowered = url.lower()
    return any(lowered.endswith(extension) for extension in DOCUMENT_EXTENSIONS)


def score_document_link_relevance(url: str, context_text: str = "", anchor_text: str = "") -> int:
    """Score whether a document URL looks like it belongs to the current programme context."""
    lowered_url = (url or "").lower()
    lowered_anchor = (anchor_text or "").lower()
    if not lowered_url:
        return 0

    score = 0
    if is_probably_document_url(lowered_url):
        score += 4

    context_tokens = {token for token in _tokenize_url_text(context_text) if token not in DOCUMENT_CONTEXT_STOPWORDS}
    anchor_tokens = {token for token in _tokenize_url_text(lowered_anchor) if token not in DOCUMENT_CONTEXT_STOPWORDS}
    url_tokens = {token for token in _tokenize_url_text(urlparse(lowered_url).path) if token not in DOCUMENT_CONTEXT_STOPWORDS}
    url_tokens.update(token for token in _tokenize_url_text(urlparse(lowered_url).query) if token not in DOCUMENT_CONTEXT_STOPWORDS)

    overlap = (context_tokens & url_tokens) | (context_tokens & anchor_tokens)
    score += len(overlap) * 4

    if any(term in lowered_anchor for term in ("brochure", "checklist", "guidelines", "application form", "download")):
        score += 2

    return score


def document_link_matches_context(url: str, context_text: str = "", anchor_text: str = "") -> bool:
    if not context_text:
        return is_probably_document_url(url)
    return score_document_link_relevance(url, context_text=context_text, anchor_text=anchor_text) >= DOCUMENT_CONTEXT_MIN_SCORE


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
