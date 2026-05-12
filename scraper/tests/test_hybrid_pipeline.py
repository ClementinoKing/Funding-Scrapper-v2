from __future__ import annotations

import json
from datetime import datetime, timezone

from typer.testing import CliRunner

from scraper.config import ScraperSettings
from scraper.hybrid import HybridScraperPipeline, merge_hybrid_records, normalized_programme_key
from scraper.main import app
from scraper.schemas import FundingProgrammeRecord, FundingType, RunSummary
from scraper.storage.json_store import LocalJsonStore
from scraper.storage.site_repository import SiteDefinition
from scraper.web_search.models import FunderWebSearchResult, WebSearchFunder


class FakeWebSearchPipeline:
    def __init__(self, results):
        self.results = list(results)
        self.calls: list[WebSearchFunder] = []

    def _process_funder(self, funder):
        self.calls.append(funder)
        return self.results.pop(0)


def _site(key: str = "nef", name: str = "NEF", domain: str = "www.nefcorp.co.za") -> SiteDefinition:
    return SiteDefinition(
        site_key=key,
        display_name=name,
        primary_domain=domain,
        adapter_key="generic",
        seed_urls=("https://%s/products-services" % domain,),
        adapter_config={},
    )


def _record(
    name: str = "uMnotho Fund",
    *,
    funder: str = "NEF",
    source_url: str = "https://www.nefcorp.co.za/products-services/umnotho",
    source_domain: str = "www.nefcorp.co.za",
    confidence: float = 0.9,
    eligibility: bool = True,
    amount: bool = True,
) -> FundingProgrammeRecord:
    return FundingProgrammeRecord(
        program_name=name,
        funder_name=funder,
        source_url=source_url,
        source_urls=[source_url],
        source_domain=source_domain,
        source_page_title=name,
        funding_type=FundingType.LOAN,
        ticket_min=1_000_000 if amount else None,
        ticket_max=10_000_000 if amount else None,
        raw_eligibility_criteria=["South African businesses may apply."] if eligibility else [],
        raw_funding_offer_data=["Funding for expansion."],
        extraction_confidence={"program_name": confidence, "source_url": confidence},
    )


def _summary(site: SiteDefinition, records: list[FundingProgrammeRecord], status: str = "success") -> RunSummary:
    return RunSummary(
        run_id="run_hybrid_test",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status=status,
        seed_urls=list(site.seed_urls),
        pages_fetched_successfully=1 if status != "failed" else 0,
        pages_failed=1 if status == "failed" else 0,
        programmes_extracted=len(records),
        programmes_after_dedupe=len(records),
        domain_telemetry=[
            {
                "site_key": site.site_key,
                "display_name": site.display_name,
                "domain": site.primary_domain,
                "completed": status != "failed",
                "records_accepted": len(records),
            }
        ],
        errors=["crawl failed"] if status == "failed" else [],
    )


def _crawler_runner(storage: LocalJsonStore, records: list[FundingProgrammeRecord], site: SiteDefinition, status: str = "success"):
    def run(_sites, _max_sites):
        storage.initialize_run("run_hybrid_test")
        storage.save_programmes(records)
        storage.write_borderline_review([])
        return _summary(site, records, status=status)

    return run


def test_scraper_mode_parsing_accepts_hybrid(monkeypatch) -> None:
    monkeypatch.setenv("SCRAPER_MODE", "hybrid")

    assert ScraperSettings.from_env().scraper_mode == "hybrid"


def test_hybrid_does_not_call_web_search_when_crawler_is_strong(tmp_path) -> None:
    site = _site()
    storage = LocalJsonStore(tmp_path)
    crawler_record = _record()
    web = FakeWebSearchPipeline([])
    pipeline = HybridScraperPipeline(
        ScraperSettings(output_path=tmp_path, scraper_mode="hybrid"),
        storage=storage,
        crawler_runner=_crawler_runner(storage, [crawler_record], site),
        web_search_pipeline=web,
    )

    summary = pipeline.run_sites([site])

    assert summary.status == "success"
    assert len(web.calls) == 0
    assert summary.domain_telemetry[0]["web_search_status"] == "not_needed"


def test_hybrid_calls_web_search_for_zero_accepted_records(tmp_path) -> None:
    site = _site()
    storage = LocalJsonStore(tmp_path)
    web_record = _record(name="uMnotho Fund")
    web = FakeWebSearchPipeline(
        [
            FunderWebSearchResult(
                funder=WebSearchFunder.from_site(site),
                records=[web_record],
                review_records=[],
                queries_run=1,
            )
        ]
    )
    pipeline = HybridScraperPipeline(
        ScraperSettings(output_path=tmp_path, scraper_mode="hybrid"),
        storage=storage,
        crawler_runner=_crawler_runner(storage, [], site),
        web_search_pipeline=web,
    )

    summary = pipeline.run_sites([site])
    payload = json.loads((tmp_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))

    assert len(web.calls) == 1
    assert summary.programmes_after_dedupe == 1
    assert payload[0]["program_name"] == "uMnotho Fund"
    assert payload[0]["raw_text_snippets"]["web_search_status"] == ["used_successfully"]


def test_hybrid_calls_web_search_for_missing_critical_fields(tmp_path) -> None:
    site = _site()
    storage = LocalJsonStore(tmp_path)
    weak_record = _record(eligibility=False, amount=False)
    web = FakeWebSearchPipeline(
        [
            FunderWebSearchResult(
                funder=WebSearchFunder.from_site(site),
                records=[],
                review_records=[],
                queries_run=1,
            )
        ]
    )
    pipeline = HybridScraperPipeline(
        ScraperSettings(output_path=tmp_path, scraper_mode="hybrid"),
        storage=storage,
        crawler_runner=_crawler_runner(storage, [weak_record], site),
        web_search_pipeline=web,
    )

    summary = pipeline.run_sites([site])

    assert len(web.calls) == 1
    assert "missing_eligibility" in summary.domain_telemetry[0]["hybrid_fallback_reason"]
    assert "missing_funding_amount" in summary.domain_telemetry[0]["hybrid_fallback_reason"]


def test_hybrid_quota_failure_preserves_crawler_records(tmp_path) -> None:
    site = _site()
    storage = LocalJsonStore(tmp_path)
    crawler_record = _record(eligibility=False)
    web = FakeWebSearchPipeline(
        [
            FunderWebSearchResult(
                funder=WebSearchFunder.from_site(site),
                records=[],
                review_records=[],
                queries_run=1,
                errors=["429 insufficient_quota"],
                completed=False,
            )
        ]
    )
    pipeline = HybridScraperPipeline(
        ScraperSettings(output_path=tmp_path, scraper_mode="hybrid"),
        storage=storage,
        crawler_runner=_crawler_runner(storage, [crawler_record], site),
        web_search_pipeline=web,
    )

    summary = pipeline.run_sites([site])
    payload = json.loads((tmp_path / "normalized" / "funding_programmes.json").read_text(encoding="utf-8"))

    assert summary.status == "partial"
    assert payload[0]["program_name"] == crawler_record.program_name
    assert summary.domain_telemetry[0]["web_search_status"] == "skipped_quota"


def test_hybrid_field_merge_fills_missing_fields_and_prefers_official_source(tmp_path) -> None:
    site = _site()
    crawler_record = _record(
        source_url="https://aggregator.example/nef-umnotho",
        source_domain="aggregator.example",
        eligibility=False,
        amount=False,
    )
    web_record = _record(
        name="NEF uMnotho Funding Programme",
        source_url="https://www.nefcorp.co.za/products-services/umnotho",
        source_domain="www.nefcorp.co.za",
        eligibility=True,
        amount=True,
    )

    merged = merge_hybrid_records(
        [crawler_record],
        [
            FunderWebSearchResult(
                funder=WebSearchFunder.from_site(site),
                records=[web_record],
                review_records=[],
                queries_run=1,
            )
        ],
        [site],
    )

    assert len(merged) == 1
    assert merged[0].program_name == "uMnotho Fund"
    assert merged[0].source_url == "https://www.nefcorp.co.za/products-services/umnotho"
    assert merged[0].ticket_min == 1_000_000
    assert merged[0].raw_eligibility_criteria == ["South African businesses may apply."]
    assert "extraction_sources" in merged[0].raw_text_snippets


def test_hybrid_duplicate_normalization_removes_programme_program_and_fund_terms() -> None:
    assert normalized_programme_key("NEF uMnotho Funding Programme", "NEF") == "umnotho"
    assert normalized_programme_key("uMnotho Fund", "NEF") == "umnotho"


def test_hybrid_dry_run_skips_supabase_upload(monkeypatch, tmp_path) -> None:
    class FakePipeline:
        def __init__(self, *args, **kwargs):
            pass

        def run_sites(self, sites, max_sites=None):
            return RunSummary(
                run_id="run_test",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status="success",
            )

    called = {"upload": False}
    monkeypatch.setattr("scraper.main.HybridScraperPipeline", FakePipeline)
    monkeypatch.setattr(
        "scraper.main._load_site_definitions",
        lambda: [_site()],
    )
    monkeypatch.setattr("scraper.main._upload_hybrid_artifacts", lambda settings: called.__setitem__("upload", True) if not settings.dry_run else None)

    result = CliRunner().invoke(
        app,
        ["run-seeds", "--output-path", str(tmp_path)],
        env={"SCRAPER_MODE": "hybrid", "SCRAPER_DRY_RUN": "true"},
    )

    assert result.exit_code == 0
    assert called["upload"] is False


def test_cli_routes_hybrid_mode_to_hybrid_pipeline(monkeypatch, tmp_path) -> None:
    called = {"hybrid": False}

    class FakePipeline:
        def __init__(self, *args, **kwargs):
            pass

        def run_sites(self, sites, max_sites=None):
            called["hybrid"] = True
            return RunSummary(
                run_id="run_test",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status="success",
            )

    monkeypatch.setattr("scraper.main.HybridScraperPipeline", FakePipeline)
    monkeypatch.setattr("scraper.main._load_site_definitions", lambda: [_site()])
    monkeypatch.setattr("scraper.main._upload_hybrid_artifacts", lambda settings: None)

    result = CliRunner().invoke(
        app,
        ["run-seeds", "--output-path", str(tmp_path)],
        env={"SCRAPER_MODE": "hybrid"},
    )

    assert result.exit_code == 0
    assert called["hybrid"] is True
