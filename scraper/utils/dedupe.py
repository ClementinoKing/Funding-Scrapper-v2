"""Deduplication and merge logic for funding programme records."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from scraper.adapters.base import SiteAdapter
from scraper.schemas import FundingProgrammeRecord, FundingType, ProgrammeNature
from scraper.utils.text import completeness_score, generate_program_id, unique_preserve_order
from scraper.utils.urls import canonicalize_url


UNKNOWN_ENUMS = {"Unknown", None, ""}


def _normalized_name(value: Optional[str], adapter: Optional[SiteAdapter] = None, kind: str = "program") -> str:
    normalized = " ".join((value or "").lower().split())
    if adapter:
        if kind == "program":
            normalized = " ".join((adapter.program_name_for_merge(value) or "").lower().split())
        elif kind == "funder":
            normalized = " ".join((adapter.funder_name_for_merge(value) or "").lower().split())
    return normalized


def _canonical_source_urls(record: FundingProgrammeRecord) -> List[str]:
    return unique_preserve_order([canonicalize_url(url) for url in record.source_urls if url])


def _record_completeness(record: FundingProgrammeRecord) -> int:
    score = completeness_score(record.model_dump(mode="python")) + int(record.overall_confidence() * 100)
    if record.programme_nature == ProgrammeNature.DIRECT_FUNDING:
        score += 12
    elif record.programme_nature == ProgrammeNature.VOUCHER_SUPPORT:
        score += 6
    elif record.programme_nature == ProgrammeNature.NON_FINANCIAL_SUPPORT:
        score -= 8
    return score


def _scalar_is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() in UNKNOWN_ENUMS:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _is_generic_support_program(program_name: Optional[str]) -> bool:
    return False


def _should_merge(
    left: FundingProgrammeRecord,
    right: FundingProgrammeRecord,
    fuzzy_threshold: int,
    adapter: Optional[SiteAdapter] = None,
) -> bool:
    left_program = _normalized_name(left.program_name, adapter=adapter, kind="program")
    right_program = _normalized_name(right.program_name, adapter=adapter, kind="program")
    left_funder = _normalized_name(left.funder_name, adapter=adapter, kind="funder")
    right_funder = _normalized_name(right.funder_name, adapter=adapter, kind="funder")
    if left_program and right_program and left_funder and right_funder:
        if left_program == right_program and left_funder == right_funder:
            return True

    if left.source_domain != right.source_domain:
        return False

    if left_program and right_program:
        program_similarity = fuzz.token_sort_ratio(left_program, right_program)
    else:
        program_similarity = 0
    if left_funder and right_funder:
        funder_similarity = fuzz.token_sort_ratio(left_funder, right_funder)
    else:
        funder_similarity = 85 if left_program and right_program else 0

    return program_similarity >= fuzzy_threshold and funder_similarity >= 80


def _merge_lists(left: List[str], right: List[str]) -> List[str]:
    return unique_preserve_order(list(left) + list(right))


def _merge_record_pair(
    primary: FundingProgrammeRecord,
    secondary: FundingProgrammeRecord,
    adapter: Optional[SiteAdapter] = None,
) -> FundingProgrammeRecord:
    merged = primary.model_copy(deep=True)
    secondary_data = secondary.model_dump(mode="python")

    for field_name, candidate_value in secondary_data.items():
        current_value = getattr(merged, field_name)
        if isinstance(current_value, list):
            if isinstance(candidate_value, list):
                setattr(merged, field_name, _merge_lists(current_value, candidate_value))
            elif not _scalar_is_empty(candidate_value):
                setattr(merged, field_name, _merge_lists(current_value, [candidate_value]))  # type: ignore[list-item]
        elif isinstance(current_value, dict):
            updated = dict(current_value)
            if isinstance(candidate_value, dict):
                for key, value in candidate_value.items():
                    if isinstance(value, list):
                        existing = updated.get(key, [])
                        if not isinstance(existing, list):
                            existing = [existing] if not _scalar_is_empty(existing) else []
                        updated[key] = _merge_lists(existing, value)
                    elif isinstance(value, (int, float)):
                        updated[key] = max(float(updated.get(key, 0.0)), float(value))
                    elif key not in updated or _scalar_is_empty(updated[key]):
                        updated[key] = value
            setattr(merged, field_name, updated)
        elif field_name == "program_name":
            if _is_generic_support_program(current_value) and not _is_generic_support_program(candidate_value):
                setattr(merged, field_name, candidate_value)
            elif _scalar_is_empty(current_value) and not _scalar_is_empty(candidate_value):
                setattr(merged, field_name, candidate_value)
        elif _scalar_is_empty(current_value) and not _scalar_is_empty(candidate_value):
            setattr(merged, field_name, candidate_value)

    merged.source_urls = _merge_lists(primary.source_urls, secondary.source_urls)
    if merged.source_url not in merged.source_urls and merged.source_urls:
        merged.source_url = merged.source_urls[0]
    if adapter:
        merged.program_name = adapter.program_name_for_merge(merged.program_name)
        merged.funder_name = adapter.funder_name_for_merge(merged.funder_name)
    merged.program_id = generate_program_id(merged.source_domain, merged.funder_name, merged.program_name)
    return FundingProgrammeRecord.model_validate(merged.model_dump(mode="python"))


def _merge_cluster(cluster: List[FundingProgrammeRecord], adapter: Optional[SiteAdapter] = None) -> FundingProgrammeRecord:
    ordered = sorted(
        cluster,
        key=lambda record: (
            _record_completeness(record),
        ),
        reverse=True,
    )
    merged = ordered[0]
    for candidate in ordered[1:]:
        merged = _merge_record_pair(merged, candidate, adapter=adapter)
    return merged


def _dedupe_internal(
    records: List[FundingProgrammeRecord],
    fuzzy_threshold: int = 90,
    adapter: Optional[SiteAdapter] = None,
) -> Tuple[List[FundingProgrammeRecord], List[Dict[str, object]]]:
    working = list(records)
    merged_records: List[FundingProgrammeRecord] = []
    merge_trace: List[Dict[str, object]] = []

    while working:
        base = working.pop(0)
        cluster = [base]
        remaining: List[FundingProgrammeRecord] = []
        for candidate in working:
            if _should_merge(base, candidate, fuzzy_threshold=fuzzy_threshold, adapter=adapter):
                cluster.append(candidate)
            else:
                remaining.append(candidate)
        merged_records.append(_merge_cluster(cluster, adapter=adapter))
        merge_trace.append(
            {
                "final_program_id": merged_records[-1].program_id,
                "final_program_name": merged_records[-1].program_name,
                "source_urls": merged_records[-1].source_urls,
                "cluster_size": len(cluster),
                "merged_program_ids": [record.program_id for record in cluster],
                "merged_program_names": [record.program_name for record in cluster],
            }
        )
        working = remaining

    merged_records.sort(key=lambda record: (record.funder_name or "", record.program_name or "", record.source_domain))
    return merged_records, merge_trace


def dedupe_records(
    records: List[FundingProgrammeRecord],
    fuzzy_threshold: int = 90,
    adapter: Optional[SiteAdapter] = None,
) -> List[FundingProgrammeRecord]:
    merged_records, _trace = _dedupe_internal(records, fuzzy_threshold=fuzzy_threshold, adapter=adapter)
    return merged_records


def dedupe_records_with_trace(
    records: List[FundingProgrammeRecord],
    fuzzy_threshold: int = 90,
    adapter: Optional[SiteAdapter] = None,
) -> Tuple[List[FundingProgrammeRecord], List[Dict[str, object]]]:
    return _dedupe_internal(records, fuzzy_threshold=fuzzy_threshold, adapter=adapter)
