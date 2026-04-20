"""Validation helpers used beyond schema-level checks."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx

from scraper.schemas import ApplicationChannel, FundingProgrammeRecord


def has_valid_http_url(url: Optional[str]) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@lru_cache(maxsize=2048)
def _verify_application_url_cached(url: str, timeout_seconds: int) -> Tuple[bool, Optional[str]]:
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.head(url)
            if response.status_code == 405:
                response = client.get(url)
            if 200 <= response.status_code < 400:
                return True, None
            return False, "Application URL returned HTTP %s." % response.status_code
    except Exception as exc:  # pragma: no cover - network availability varies
        return False, "Could not verify application URL: %s" % exc


def verify_application_url(url: Optional[str], timeout_seconds: int = 10) -> Tuple[bool, Optional[str]]:
    if not has_valid_http_url(url):
        return False, "Application URL is missing or malformed."
    return _verify_application_url_cached(url, timeout_seconds)


def is_low_confidence(record: FundingProgrammeRecord, threshold: float) -> bool:
    return record.overall_confidence() < threshold


def add_application_verification_note(
    record: FundingProgrammeRecord,
    timeout_seconds: int,
) -> FundingProgrammeRecord:
    if record.application_channel != ApplicationChannel.ONLINE_FORM or not record.application_url:
        return record
    verified, note = verify_application_url(record.application_url, timeout_seconds=timeout_seconds)
    if not verified and note and note not in record.notes:
        record.notes.append(note)
        if note not in record.validation_errors:
            record.validation_errors.append(note)
        record.needs_review = True
    return record
