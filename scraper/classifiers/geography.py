"""Geography extraction helpers."""

from __future__ import annotations

import re
from typing import Dict, List

from scraper.config import ScraperSettings
from scraper.schemas import GeographyScope
from scraper.utils.text import unique_preserve_order


POSTAL_RANGE_RE = re.compile(r"\b\d{4}\s*-\s*\d{4}\b|\b\d{4}\b")

PROVINCE_ALIASES = {
    "eastern cape": "Eastern Cape",
    "free state": "Free State",
    "gauteng": "Gauteng",
    "kwazulu-natal": "KwaZulu-Natal",
    "kwazulu natal": "KwaZulu-Natal",
    "limpopo": "Limpopo",
    "mpumalanga": "Mpumalanga",
    "north west": "North West",
    "northwest": "North West",
    "northern cape": "Northern Cape",
    "western cape": "Western Cape",
}


def classify_geography(text: str, settings: ScraperSettings) -> Dict[str, object]:
    lowered = (text or "").lower()
    matched_provinces: List[str] = []
    matched_municipalities: List[str] = []

    for alias, normalized in PROVINCE_ALIASES.items():
        if alias in lowered:
            matched_provinces.append(normalized)

    for municipality in settings.municipality_list:
        if municipality.lower() in lowered:
            matched_municipalities.append(municipality)

    postal_ranges = unique_preserve_order([match.group(0).replace(" ", "") for match in POSTAL_RANGE_RE.finditer(text or "")])
    if all(len(item) == 4 for item in postal_ranges):
        postal_ranges = []

    notes: List[str] = []
    evidence: List[str] = []

    if "national" in lowered or "nationwide" in lowered or "across south africa" in lowered:
        scope = GeographyScope.NATIONAL
        evidence.append("national")
    elif matched_municipalities:
        scope = GeographyScope.MUNICIPALITY
        evidence.extend(matched_municipalities)
    elif matched_provinces:
        scope = GeographyScope.PROVINCE
        evidence.extend(matched_provinces)
    elif any(term in lowered for term in ["international", "regional", "across africa", "sub-saharan africa"]):
        scope = GeographyScope.INTERNATIONAL
        evidence.append("international")
    elif any(term in lowered for term in ["local area", "township", "district", "rural area"]):
        scope = GeographyScope.LOCAL
        evidence.append("local")
    else:
        scope = GeographyScope.UNKNOWN

    if matched_provinces or matched_municipalities:
        notes.append("South Africa geography normalization applied.")

    return {
        "geography_scope": scope,
        "provinces": unique_preserve_order(matched_provinces),
        "municipalities": unique_preserve_order(matched_municipalities),
        "postal_code_ranges": postal_ranges,
        "notes": notes,
        "evidence": unique_preserve_order(evidence),
    }

