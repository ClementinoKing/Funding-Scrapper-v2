"""Dynamic OpenAI Web Search query generation."""

from __future__ import annotations

from typing import Iterable, List, Optional

from scraper.web_search.models import WebSearchFunder
from scraper.utils.text import clean_text, unique_preserve_order
from scraper.utils.urls import extract_host


DOMAIN_QUERY_PATTERNS = [
    "site:{domain} funding programmes",
    "site:{domain} funding products",
    "site:{domain} investment programmes",
    "site:{domain} investment products",
    "site:{domain} finance products",
    "site:{domain} business funding",
    "site:{domain} SME funding",
    "site:{domain} enterprise development",
    "site:{domain} development finance",
    "site:{domain} funding criteria",
    "site:{domain} eligibility criteria",
    "site:{domain} qualifying criteria",
    "site:{domain} application process",
    "site:{domain} required documents",
    "site:{domain} investment range",
    "site:{domain} ticket size",
    "site:{domain} funding amount",
    "site:{domain} repayment terms",
]

FUNDER_QUERY_PATTERNS = [
    '"{funder_name}" funding programmes',
    '"{funder_name}" investment programmes',
    '"{funder_name}" funding products',
    '"{funder_name}" application criteria',
]


def normalized_search_domain(url_or_domain: str) -> str:
    host = extract_host(url_or_domain)
    return host[4:] if host.startswith("www.") else host


def generate_funder_queries(
    funder: WebSearchFunder,
    max_queries: int | None = None,
    *,
    programme_hints: Optional[Iterable[str]] = None,
) -> List[str]:
    """Generate funder/domain search queries without funder-specific logic."""

    domain = normalized_search_domain(funder.website_url)
    funder_name = clean_text(funder.funder_name)
    targeted_queries = []
    for programme_name in programme_hints or funder.raw.get("programme_hints", []):
        name = clean_text(str(programme_name))
        if not name:
            continue
        if domain:
            targeted_queries.extend(
                [
                    f'site:{domain} "{name}"',
                    f'site:{domain} "{name}" funding',
                    f'site:{domain} "{name}" application',
                ]
            )
        else:
            targeted_queries.extend(
                [
                    f'"{name}"',
                    f'"{name}" funding',
                    f'"{name}" application',
                ]
            )
    queries = [
        pattern.format(domain=domain, funder_name=funder_name)
        for pattern in [*DOMAIN_QUERY_PATTERNS, *FUNDER_QUERY_PATTERNS]
        if domain or "{domain}" not in pattern
    ]
    deduped = unique_preserve_order([*targeted_queries, *queries])
    if max_queries is not None:
        return deduped[: max(1, max_queries)]
    return deduped
