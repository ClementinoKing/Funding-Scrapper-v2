"""Ownership target mapping."""

from __future__ import annotations

from typing import Dict, List, Tuple

from scraper.config import ScraperSettings
from scraper.utils.text import match_keyword_map


def classify_ownership_targets(text: str, settings: ScraperSettings) -> Tuple[List[str], Dict[str, List[str]]]:
    return match_keyword_map(text, settings.ownership_target_keywords)

