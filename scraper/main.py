"""CLI entrypoint for the funding programme scraper."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Optional

import typer

from scraper.config import PACKAGE_ROOT, SupabaseSettings
from scraper.adapters.registry import build_default_registry
from scraper.pipeline import ScraperPipeline, build_settings_from_options
from scraper.storage.site_repository import SiteRepository
from scraper.storage.supabase_store import SupabaseUploader


app = typer.Typer(add_completion=False, no_args_is_help=True)


def _print_summary(summary) -> None:
    typer.echo("Run ID: %s" % summary.run_id)
    typer.echo("Status: %s" % summary.status)
    typer.echo("URLs crawled: %s" % summary.total_urls_crawled)
    typer.echo("Pages fetched successfully: %s" % summary.pages_fetched_successfully)
    typer.echo("Pages failed: %s" % summary.pages_failed)
    typer.echo("Programmes extracted: %s" % summary.programmes_extracted)
    typer.echo("Programmes after dedupe: %s" % summary.programmes_after_dedupe)
    typer.echo("Low-confidence records: %s" % summary.records_with_low_confidence_extraction)
    typer.echo("Borderline review records: %s" % summary.records_with_borderline_review)
    typer.echo("Rejected records: %s" % summary.records_rejected_for_quality)
    typer.echo("Browser fallbacks: %s" % summary.browser_fallback_count)
    typer.echo("Retries: %s" % summary.retry_count)
    typer.echo("Average fetch time: %.3fs" % summary.average_fetch_time_seconds)
    if summary.errors:
        typer.echo("Errors: %s" % len(summary.errors))


def _clear_local_scrape_output(output_root: Path) -> None:
    for directory in (output_root / "logs", output_root / "normalized", output_root / "raw"):
        if directory.exists():
            shutil.rmtree(directory)


def _run_seed_pipeline(
    max_pages: int,
    depth_limit: int,
    output_path: Optional[Path],
    headless: bool,
    browser_fallback: bool,
    respect_robots: bool,
    fresh: bool,
    ai_enrichment: Optional[bool],
    domain_concurrency: Optional[int] = None,
    max_queue_urls: Optional[int] = None,
    max_links_per_page: Optional[int] = None,
    fetch_cache: Optional[bool] = None,
    max_domains: Optional[int] = None,
):
    settings = build_settings_from_options(
        output_path,
        max_pages,
        depth_limit,
        headless,
        browser_fallback,
        respect_robots,
        ai_enrichment,
        domain_concurrency,
        max_queue_urls,
        max_links_per_page,
        fetch_cache,
    )
    if fresh:
        _clear_local_scrape_output(settings.output_path)
    registry = build_default_registry()
    try:
        supabase_settings = SupabaseSettings.from_env()
    except ValueError:
        supabase_settings = None
    site_repository = SiteRepository(
        settings=supabase_settings,
        adapter_registry=registry,
    )
    sites = site_repository.load_sites()
    if not sites:
        typer.echo("No active sites were found in Supabase.")
        raise typer.Exit(code=1)
    pipeline = ScraperPipeline(settings, adapter_registry=registry)
    return pipeline.run_sites(sites, max_sites=max_domains)


@app.command("scrape-url")
def scrape_url(
    url: str = typer.Argument(..., help="The funding page URL to scrape."),
    max_pages: int = typer.Option(1, help="Maximum pages to crawl."),
    depth_limit: int = typer.Option(0, help="Maximum link depth from the seed URL."),
    output_path: Optional[Path] = typer.Option(None, help="Optional output directory override."),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    browser_fallback: bool = typer.Option(True, "--browser-fallback/--no-browser-fallback"),
    respect_robots: bool = typer.Option(True, "--respect-robots/--no-respect-robots"),
    ai_enrichment: Optional[bool] = typer.Option(
        None,
        "--ai-enrichment/--no-ai-enrichment",
        help="Enable or disable AI enrichment for this run.",
    ),
    domain_concurrency: Optional[int] = typer.Option(None, help="Maximum domains to process concurrently."),
    max_queue_urls: Optional[int] = typer.Option(None, help="Maximum queued URLs per domain."),
    max_links_per_page: Optional[int] = typer.Option(None, help="Maximum discovered links to score per fetched page."),
    fetch_cache: Optional[bool] = typer.Option(None, "--fetch-cache/--no-fetch-cache", help="Enable in-run fetch caching."),
) -> None:
    settings = build_settings_from_options(
        output_path,
        max_pages,
        depth_limit,
        headless,
        browser_fallback,
        respect_robots,
        ai_enrichment,
        domain_concurrency,
        max_queue_urls,
        max_links_per_page,
        fetch_cache,
    )
    pipeline = ScraperPipeline(settings, adapter_registry=build_default_registry())
    summary = pipeline.run([url])
    _print_summary(summary)


@app.command("crawl-domain")
def crawl_domain(
    url: str = typer.Argument(..., help="The domain root or listing page to crawl."),
    max_pages: int = typer.Option(50, help="Maximum pages to crawl."),
    depth_limit: int = typer.Option(2, help="Maximum depth from the seed URL."),
    output_path: Optional[Path] = typer.Option(None, help="Optional output directory override."),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    browser_fallback: bool = typer.Option(True, "--browser-fallback/--no-browser-fallback"),
    respect_robots: bool = typer.Option(True, "--respect-robots/--no-respect-robots"),
    ai_enrichment: Optional[bool] = typer.Option(
        None,
        "--ai-enrichment/--no-ai-enrichment",
        help="Enable or disable AI enrichment for this run.",
    ),
    domain_concurrency: Optional[int] = typer.Option(None, help="Maximum domains to process concurrently."),
    max_queue_urls: Optional[int] = typer.Option(None, help="Maximum queued URLs per domain."),
    max_links_per_page: Optional[int] = typer.Option(None, help="Maximum discovered links to score per fetched page."),
    fetch_cache: Optional[bool] = typer.Option(None, "--fetch-cache/--no-fetch-cache", help="Enable in-run fetch caching."),
) -> None:
    settings = build_settings_from_options(
        output_path,
        max_pages,
        depth_limit,
        headless,
        browser_fallback,
        respect_robots,
        ai_enrichment,
        domain_concurrency,
        max_queue_urls,
        max_links_per_page,
        fetch_cache,
    )
    pipeline = ScraperPipeline(settings, adapter_registry=build_default_registry())
    summary = pipeline.run([url])
    _print_summary(summary)


@app.command("run-seeds")
def run_seeds(
    max_pages: int = typer.Option(50, help="Maximum pages to crawl."),
    depth_limit: int = typer.Option(2, help="Maximum crawl depth."),
    output_path: Optional[Path] = typer.Option(None, help="Optional output directory override."),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    browser_fallback: bool = typer.Option(True, "--browser-fallback/--no-browser-fallback"),
    respect_robots: bool = typer.Option(True, "--respect-robots/--no-respect-robots"),
    ai_enrichment: Optional[bool] = typer.Option(
        None,
        "--ai-enrichment/--no-ai-enrichment",
        help="Enable or disable AI enrichment for this run.",
    ),
    fresh: bool = typer.Option(
        True,
        "--fresh/--resume",
        help="Clear previous local scrape artifacts before running. Use --resume to keep crawl state and outputs.",
    ),
    max_domains: Optional[int] = typer.Option(None, help="Maximum domains to process in this run."),
    domain_concurrency: Optional[int] = typer.Option(None, help="Maximum domains to process concurrently."),
    max_queue_urls: Optional[int] = typer.Option(None, help="Maximum queued URLs per domain."),
    max_links_per_page: Optional[int] = typer.Option(None, help="Maximum discovered links to score per fetched page."),
    fetch_cache: Optional[bool] = typer.Option(None, "--fetch-cache/--no-fetch-cache", help="Enable in-run fetch caching."),
) -> None:
    summary = _run_seed_pipeline(
        max_pages=max_pages,
        depth_limit=depth_limit,
        output_path=output_path,
        headless=headless,
        browser_fallback=browser_fallback,
        respect_robots=respect_robots,
        ai_enrichment=ai_enrichment,
        domain_concurrency=domain_concurrency,
        max_queue_urls=max_queue_urls,
        max_links_per_page=max_links_per_page,
        fetch_cache=fetch_cache,
        fresh=fresh,
        max_domains=max_domains,
    )
    _print_summary(summary)


@app.command("run-next-seed")
def run_next_seed(
    max_pages: int = typer.Option(50, help="Maximum pages to crawl."),
    depth_limit: int = typer.Option(2, help="Maximum crawl depth."),
    output_path: Optional[Path] = typer.Option(None, help="Optional output directory override."),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    browser_fallback: bool = typer.Option(True, "--browser-fallback/--no-browser-fallback"),
    respect_robots: bool = typer.Option(True, "--respect-robots/--no-respect-robots"),
    ai_enrichment: Optional[bool] = typer.Option(
        None,
        "--ai-enrichment/--no-ai-enrichment",
        help="Enable or disable AI enrichment for this run.",
    ),
    domain_concurrency: Optional[int] = typer.Option(None, help="Maximum domains to process concurrently."),
    max_queue_urls: Optional[int] = typer.Option(None, help="Maximum queued URLs per domain."),
    max_links_per_page: Optional[int] = typer.Option(None, help="Maximum discovered links to score per fetched page."),
    fetch_cache: Optional[bool] = typer.Option(None, "--fetch-cache/--no-fetch-cache", help="Enable in-run fetch caching."),
) -> None:
    summary = _run_seed_pipeline(
        max_pages=max_pages,
        depth_limit=depth_limit,
        output_path=output_path,
        headless=headless,
        browser_fallback=browser_fallback,
        respect_robots=respect_robots,
        ai_enrichment=ai_enrichment,
        domain_concurrency=domain_concurrency,
        max_queue_urls=max_queue_urls,
        max_links_per_page=max_links_per_page,
        fetch_cache=fetch_cache,
        fresh=False,
        max_domains=1,
    )
    _print_summary(summary)


@app.command("export-csv")
def export_csv(
    output_path: Optional[Path] = typer.Option(None, help="Optional output directory override."),
    csv_path: Optional[Path] = typer.Option(None, help="Optional explicit CSV target path."),
) -> None:
    settings = build_settings_from_options(output_path, None, None, None, None, None)
    pipeline = ScraperPipeline(settings, adapter_registry=build_default_registry())
    target = pipeline.export_csv(csv_path)
    typer.echo("CSV exported to %s" % target)


@app.command("push-supabase")
def push_supabase(
    normalized_json: Path = typer.Option(
        PACKAGE_ROOT / "output" / "normalized" / "funding_programmes.json",
        help="Normalized JSON file to upload.",
    ),
    run_summary: Path = typer.Option(
        PACKAGE_ROOT / "output" / "logs" / "run_summary.json",
        help="Run summary JSON file to upload alongside the records.",
    ),
) -> None:
    try:
        supabase_settings = SupabaseSettings.from_env()
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    if not normalized_json.exists():
        typer.echo("Normalized JSON not found: %s" % normalized_json)
        raise typer.Exit(code=1)

    uploader = SupabaseUploader(supabase_settings)
    try:
        result = uploader.upload_from_files(normalized_json, run_summary)
    except Exception as exc:
        typer.echo("Supabase upload failed: %s" % exc)
        raise typer.Exit(code=1)

    typer.echo("Supabase upload complete.")
    typer.echo("Project URL: %s" % supabase_settings.url)
    typer.echo("RPC: %s" % supabase_settings.rpc_name)
    upload_meta = result.pop("_upload_meta", None) if isinstance(result, dict) else None
    if upload_meta:
        typer.echo(
            "Upload sanitizer: %s -> %s records (%s duplicate page groups collapsed)"
            % (
                upload_meta.get("input_records", 0),
                upload_meta.get("sanitized_records", 0),
                upload_meta.get("collapsed_source_url_groups", 0),
            )
        )
    typer.echo("Result: %s" % result)


if __name__ == "__main__":
    app()
