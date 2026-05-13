"""Deduplication and merge logic for funding programme records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from rapidfuzz import fuzz

from scraper.adapters.base import PARENT_HUB_SEGMENTS, PARENT_SUPPORT_SEGMENT_TERMS, SiteAdapter
from scraper.schemas import FieldEvidence, FundingProgrammeRecord, FundingType, ProgrammeNature
from scraper.utils.text import clean_text, completeness_score, generate_program_id, slugify, strip_leading_numbered_prefix, unique_preserve_order
from scraper.utils.urls import canonicalize_url
from scraper.utils.page_classification import PAGE_TYPE_FUNDING_PROGRAMME, PAGE_TYPE_FUNDING_LISTING, PAGE_TYPE_OPEN_CALL, normalize_page_type


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


def _path_segments(url: str) -> List[str]:
    return [segment for segment in urlparse(url).path.split("/") if segment]


def _strip_support_suffix(segment: str) -> str:
    cleaned = clean_text(segment or "").lower().replace("_", "-")
    if not cleaned:
        return ""
    support_suffixes = {
        "apply",
        "application",
        "applications",
        "guidelines",
        "eligibility",
        "criteria",
        "checklist",
        "documents",
        "required-documents",
        "how-to-apply",
        "application-form",
        "overview",
        "background",
        "preamble",
        "contact-details",
        "disclaimer",
        "other-conditions",
        "adjudication-process",
        "post-investment-monitoring",
        "terms-and-structure",
        "timing",
        "deadline",
        "terms",
    }
    for suffix in sorted(support_suffixes, key=len, reverse=True):
        if cleaned == suffix:
            return ""
        if cleaned.endswith("-" + suffix):
            return cleaned[: -(len(suffix) + 1)]
    return cleaned


def _leaf_base_slug(segment: str) -> str:
    stripped = strip_leading_numbered_prefix(segment or "")
    cleaned = clean_text(stripped).lower().replace("_", "-")
    return _strip_support_suffix(cleaned)


def _source_context_keys(record: FundingProgrammeRecord) -> Set[str]:
    keys: Set[str] = set()
    for url in _canonical_source_urls(record):
        segments = [segment for segment in _path_segments(url) if segment]
        if len(segments) < 3:
            continue
        parent_segment = clean_text(segments[-2]).lower().replace("_", "-")
        leaf_segment = clean_text(segments[-1]).lower().replace("_", "-")
        if not parent_segment or not leaf_segment:
            continue
        if parent_segment in PARENT_HUB_SEGMENTS:
            continue
        if any(term in leaf_segment for term in PARENT_SUPPORT_SEGMENT_TERMS):
            keys.add(parent_segment)
            continue
        if _leaf_base_slug(leaf_segment):
            keys.add(parent_segment)
    return keys


def _source_leaf_base_keys(record: FundingProgrammeRecord) -> Set[str]:
    keys: Set[str] = set()
    for url in _canonical_source_urls(record):
        segments = [segment for segment in _path_segments(url) if segment]
        if not segments:
            continue
        leaf_segment = segments[-1]
        leaf_base = _leaf_base_slug(leaf_segment)
        if leaf_base:
            keys.add(leaf_base)
    return keys


def _normalized_parent_name(record: FundingProgrammeRecord, adapter: Optional[SiteAdapter] = None) -> str:
    return _normalized_name(record.parent_programme_name, adapter=adapter, kind="program")


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
    normalized = clean_text(program_name or "").casefold()
    if not normalized:
        return True
    generic_terms = {
        "eligibility",
        "eligibility criteria",
        "requirements",
        "how to apply",
        "application",
        "application process",
        "documents",
        "required documents",
        "funding",
        "funding offer",
        "terms",
        "overview",
        "support",
    }
    return normalized in generic_terms or normalized.endswith(":")


def _shared_grouping_evidence(left: FundingProgrammeRecord, right: FundingProgrammeRecord) -> bool:
    left_context = _source_context_keys(left) | _source_leaf_base_keys(left)
    right_context = _source_context_keys(right) | _source_leaf_base_keys(right)
    if left_context and right_context and left_context & right_context:
        return True
    left_links = set(left.related_documents + ([left.application_url] if left.application_url else []))
    right_links = set(right.related_documents + ([right.application_url] if right.application_url else []))
    if left_links and right_links and left_links & right_links:
        return True
    left_parent = clean_text(left.parent_programme_name or "").casefold()
    right_parent = clean_text(right.parent_programme_name or "").casefold()
    return bool(left_parent and right_parent and left_parent == right_parent)


def _should_merge(
    left: FundingProgrammeRecord,
    right: FundingProgrammeRecord,
    fuzzy_threshold: int,
    adapter: Optional[SiteAdapter] = None,
    merge_decider: Optional[Any] = None,
) -> bool:
    left_sources = set(_canonical_source_urls(left))
    right_sources = set(_canonical_source_urls(right))

    left_program = _normalized_name(left.program_name, adapter=adapter, kind="program")
    right_program = _normalized_name(right.program_name, adapter=adapter, kind="program")
    left_funder = _normalized_name(left.funder_name, adapter=adapter, kind="funder")
    right_funder = _normalized_name(right.funder_name, adapter=adapter, kind="funder")
    left_parent = _normalized_parent_name(left, adapter=adapter)
    right_parent = _normalized_parent_name(right, adapter=adapter)

    if left_sources & right_sources:
        if (
            left_program
            and right_program
            and left_program != right_program
            and not (_is_generic_support_program(left_program) or _is_generic_support_program(right_program))
        ):
            return False
        if left_parent and right_parent and left_parent != right_parent:
            return False
        if left_funder and right_funder and left_funder != right_funder:
            return False
        return True

    if left.source_domain != right.source_domain:
        return False

    if (
        merge_decider
        and hasattr(merge_decider, "score_duplicate_records")
    ):
        score_result = merge_decider.score_duplicate_records(left, right)
        if isinstance(score_result, dict):
            decision = str(score_result.get("decision") or "").casefold()
            if decision == "merge":
                return True
            if decision == "separate":
                return False

    if (
        merge_decider
        and left_program
        and right_program
        and left_funder
        and right_funder
        and left_program == right_program
        and left_funder == right_funder
        and hasattr(merge_decider, "should_merge_records")
    ):
        ai_decision = merge_decider.should_merge_records(left, right)
        if ai_decision is not None:
            return bool(ai_decision)

    if left_parent and right_parent and left_parent != right_parent:
        return False

    left_context_keys = _source_context_keys(left)
    right_context_keys = _source_context_keys(right)
    if left_context_keys and right_context_keys and not (left_context_keys & right_context_keys):
        return False

    if not (left_program and right_program and left_funder and right_funder):
        if left.source_domain != right.source_domain or not _shared_grouping_evidence(left, right):
            return False
        if left_program and right_program and left_program != right_program:
            return False
        if left_funder and right_funder and left_funder != right_funder:
            return False
        return True
    if left_program != right_program or left_funder != right_funder:
        if not _shared_grouping_evidence(left, right):
            return False
        if left_program and right_program and not (_is_generic_support_program(left_program) or _is_generic_support_program(right_program)):
            return False
        if left_funder and right_funder and left_funder != right_funder:
            return False
        return True
    if left_parent or right_parent:
        return bool(left_parent) and bool(right_parent) and left_parent == right_parent

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


def _evidence_fingerprint(item: FieldEvidence | dict) -> Tuple[str, str, str, str, str]:
    if isinstance(item, FieldEvidence):
        normalized = item.normalized_value
        evidence_text = item.evidence_text
        source_url = item.source_url
        source_section = item.source_section or ""
        source_scope = item.source_scope or ""
    else:
        normalized = item.get("normalized_value")
        evidence_text = str(item.get("evidence_text") or "")
        source_url = str(item.get("source_url") or "")
        source_section = str(item.get("source_section") or "")
        source_scope = str(item.get("source_scope") or "")
    return (
        str(normalized),
        evidence_text,
        source_url,
        source_section,
        source_scope,
    )


def _merge_field_evidence(left: Dict[str, List[FieldEvidence]], right: Dict[str, List[FieldEvidence]]) -> Dict[str, List[FieldEvidence]]:
    merged: Dict[str, List[FieldEvidence]] = {field: list(items) for field, items in left.items()}
    for field_name, items in right.items():
        existing = merged.setdefault(field_name, [])
        seen = {_evidence_fingerprint(item) for item in existing}
        for item in items:
            fingerprint = _evidence_fingerprint(item)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            existing.append(item)
    return merged


def _merge_record_pair(
    primary: FundingProgrammeRecord,
    secondary: FundingProgrammeRecord,
    adapter: Optional[SiteAdapter] = None,
) -> FundingProgrammeRecord:
    merged = primary.model_copy(deep=True)
    secondary_data = secondary.model_dump(mode="python")
    primary_page_type = normalize_page_type(primary.page_type)
    secondary_page_type = normalize_page_type(secondary.page_type)

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
                if field_name == "field_evidence":
                    current_evidence = {
                        key: [FieldEvidence.model_validate(item) if isinstance(item, dict) else item for item in value]
                        for key, value in updated.items()
                        if isinstance(value, list)
                    }
                    candidate_evidence = {
                        key: [FieldEvidence.model_validate(item) if isinstance(item, dict) else item for item in value]
                        for key, value in candidate_value.items()
                        if isinstance(value, list)
                    }
                    setattr(merged, field_name, _merge_field_evidence(current_evidence, candidate_evidence))
                    continue
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
        elif field_name == "page_type":
            preferred = _preferred_page_type(primary_page_type, secondary_page_type)
            setattr(merged, field_name, preferred)
        elif field_name == "page_role":
            if _scalar_is_empty(current_value) or current_value == "generic":
                setattr(merged, field_name, candidate_value)
        elif _scalar_is_empty(current_value) and not _scalar_is_empty(candidate_value):
            setattr(merged, field_name, candidate_value)

    merged.source_urls = _merge_lists(primary.source_urls, secondary.source_urls)
    if merged.source_url not in merged.source_urls and merged.source_urls:
        merged.source_url = merged.source_urls[0]
    if len(merged.source_urls) > 1:
        merged.needs_review_reasons = unique_preserve_order([*merged.needs_review_reasons, "merged_multi_page_record"])
    if not merged.page_debug_package and secondary.page_debug_package:
        merged.page_debug_package = secondary.page_debug_package
    if adapter:
        merged.program_name = adapter.program_name_for_merge(merged.program_name)
        merged.funder_name = adapter.funder_name_for_merge(merged.funder_name)
    merged.program_id = generate_program_id(merged.source_domain, merged.funder_name, merged.program_name)
    merged.id = str(uuid5(NAMESPACE_URL, f"{merged.source_domain}:{merged.program_id}"))
    merged.program_slug = slugify(merged.program_name or merged.program_id, max_length=80)
    merged.funder_slug = slugify(merged.funder_name or merged.source_domain, max_length=80)
    return FundingProgrammeRecord.model_validate(merged.model_dump(mode="python"))


def _preferred_page_type(left: str, right: str) -> str:
    priority = {
        PAGE_TYPE_FUNDING_PROGRAMME: 4,
        PAGE_TYPE_OPEN_CALL: 3,
        PAGE_TYPE_FUNDING_LISTING: 2,
    }
    return left if priority.get(left, 0) >= priority.get(right, 0) else right


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
    merge_decider: Optional[Any] = None,
) -> Tuple[List[FundingProgrammeRecord], List[Dict[str, object]]]:
    working = list(records)
    merged_records: List[FundingProgrammeRecord] = []
    merge_trace: List[Dict[str, object]] = []

    while working:
        base = working.pop(0)
        cluster = [base]
        remaining: List[FundingProgrammeRecord] = []
        for candidate in working:
            if _should_merge(
                base,
                candidate,
                fuzzy_threshold=fuzzy_threshold,
                adapter=adapter,
                merge_decider=merge_decider,
            ):
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
    merge_decider: Optional[Any] = None,
) -> List[FundingProgrammeRecord]:
    merged_records, _trace = _dedupe_internal(
        records,
        fuzzy_threshold=fuzzy_threshold,
        adapter=adapter,
        merge_decider=merge_decider,
    )
    return merged_records


def dedupe_records_with_trace(
    records: List[FundingProgrammeRecord],
    fuzzy_threshold: int = 90,
    adapter: Optional[SiteAdapter] = None,
    merge_decider: Optional[Any] = None,
) -> Tuple[List[FundingProgrammeRecord], List[Dict[str, object]]]:
    return _dedupe_internal(
        records,
        fuzzy_threshold=fuzzy_threshold,
        adapter=adapter,
        merge_decider=merge_decider,
    )
