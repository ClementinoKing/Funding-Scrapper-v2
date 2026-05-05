from __future__ import annotations

from datetime import datetime, timezone

from scraper.schemas import ApplicationChannel, DeadlineType, FundingProgrammeRecord, FundingType
from scraper.utils.quality import is_borderline_programme_record, is_real_programme_record, score_programme_quality


def _record(**overrides) -> FundingProgrammeRecord:
    base = dict(
        program_name="Youth Growth Loan",
        funder_name="Growth Finance Agency",
        source_url="https://example.org/programmes/youth-growth-loan",
        source_urls=["https://example.org/programmes/youth-growth-loan"],
        source_domain="example.org",
        scraped_at=datetime.now(timezone.utc),
        funding_type=FundingType.LOAN,
        funding_lines=["Youth Loan"],
        ticket_min=100000,
        ticket_max=500000,
        deadline_type=DeadlineType.OPEN,
        industries=["Manufacturing"],
        use_of_funds=["working capital"],
        business_stage_eligibility=["growth"],
        ownership_targets=["youth-owned"],
        application_channel=ApplicationChannel.ONLINE_FORM,
        application_url="https://example.org/apply/youth-growth-loan",
        contact_email="info@example.org",
        extraction_confidence={"program_name": 0.8, "funder_name": 0.8, "application_route": 0.7},
        notes=[],
    )
    base.update(overrides)
    return FundingProgrammeRecord(**base)


def test_quality_scoring_accepts_strong_programme() -> None:
    record = _record()
    score, reasons, blockers = score_programme_quality(record)

    assert score >= 60
    assert "Has programme name" in reasons
    assert blockers == []
    assert is_real_programme_record(record)


def test_quality_scoring_flags_borderline_programme_for_review() -> None:
    record = _record(
        funding_lines=[],
        ticket_min=None,
        ticket_max=None,
        deadline_type=DeadlineType.UNKNOWN,
        industries=[],
        use_of_funds=[],
        business_stage_eligibility=[],
        ownership_targets=[],
        application_channel=ApplicationChannel.UNKNOWN,
        application_url=None,
        contact_email=None,
        contact_phone=None,
        extraction_confidence={},
    )

    score, _reasons, blockers = score_programme_quality(record)

    assert 20 <= score < 45
    assert "Very low extraction confidence" in blockers
    assert not is_real_programme_record(record)
    assert is_borderline_programme_record(record)


def test_quality_scoring_rejects_weak_programme() -> None:
    record = _record(
        program_name=None,
        funder_name=None,
        funding_type=FundingType.UNKNOWN,
        funding_lines=[],
        ticket_min=None,
        ticket_max=None,
        deadline_type=DeadlineType.UNKNOWN,
        industries=[],
        use_of_funds=[],
        business_stage_eligibility=[],
        ownership_targets=[],
        application_channel=ApplicationChannel.UNKNOWN,
        application_url=None,
        contact_email=None,
        contact_phone=None,
        notes=["archived"],
    )

    score, _reasons, blockers = score_programme_quality(record)

    assert score < 35
    assert "Archived or closed programme" in blockers
    assert not is_real_programme_record(record)
    assert not is_borderline_programme_record(record)


def test_quality_scoring_demotes_article_publication_pages_to_review() -> None:
    record = _record(
        source_url="https://www.idc.co.za/press-releases/2018/idc-and-the-dti-launch-first-black-industrialist-owned-industrial-sanitation-and-water-treatment-chemicals-manufacturing-company-in-free-state",
        source_page_title="IDC and the DTI launch first black industrialist owned industrial sanitation and water treatment chemicals manufacturing company in Free State",
        application_channel=ApplicationChannel.ONLINE_FORM,
        application_url="https://www.idc.co.za/apply",
        contact_email="info@idc.co.za",
        contact_phone="012 345 6789",
        notes=["Page looks like an article/publication page: press release."],
    )

    score, _reasons, blockers = score_programme_quality(record)

    assert score >= 80
    assert is_real_programme_record(record)
    assert is_borderline_programme_record(record)
    assert "Article or publication page" in blockers
