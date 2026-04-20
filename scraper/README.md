# Funding Programme Scraper

Production-style, local-first funding programme scraper for SME and business finance websites.

## Highlights

- Python CLI built with Typer
- Static-first fetching with `httpx`
- JavaScript fallback via Playwright
- Fast parsing with `selectolax` plus BeautifulSoup fallback
- Strong Pydantic schemas and validation
- Local JSON as the primary artifact
- CSV export for analyst review
- Crawl logging, error logging, and QA summaries
- Dedupe and provenance-ready records for future Supabase ingestion

## Setup

Python `3.11+` is the target runtime.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

If you only have Python `3.9` locally, install a `3.11+` interpreter before running the scraper.

## Run Commands

```bash
python -m scraper.main scrape-url "https://example.com/funding/programme"
python -m scraper.main crawl-domain "https://example.com" --max-pages 100
python -m scraper.main run-seeds
python -m scraper.main export-csv
python -m scraper.main push-supabase
```

Common CLI flags:

- `--max-pages`
- `--depth-limit`
- `--output-path`
- `--headless/--no-headless`
- `--browser-fallback/--no-browser-fallback`
- `--respect-robots/--no-respect-robots`

## Output Structure

```text
scraper/output/
  raw/
    pages/
    extracted_programs.jsonl
  normalized/
    funding_programmes.json
    funding_programmes.csv
    low_confidence_review.json
  logs/
    crawl.log
    errors.log
    run_summary.json
```

## Notes

- The normalized JSON file is the primary artifact.
- Records preserve raw text evidence and source provenance.
- Unknown values stay `null`, `Unknown`, or empty lists rather than guessed.
- The storage layer is interface-based so Supabase can be added later without rewriting the crawler or parser.
- Seeded crawl targets now come from the `sites` table in Supabase when credentials are configured.

## Supabase Push

The repo supports Supabase credentials from `.env.local` at the project root. `.env.scraper` is still supported as a fallback for scraper-specific setups.

Apply the SQL migrations in [supabase/migrations/20260325190000_create_scraper_ingest.sql](../supabase/migrations/20260325190000_create_scraper_ingest.sql) and [supabase/migrations/20260326170000_create_sites.sql](../supabase/migrations/20260326170000_create_sites.sql), then push the latest normalized scraper output with:

```bash
python -m scraper.main push-supabase
```

This uses a Supabase RPC called `ingest_funding_programmes`. The provided anon key can call that RPC, while the tables themselves stay protected behind row-level security. If you later add a service-role key to `.env.local` or `.env.scraper`, the same command will automatically use it.

## Limitations

- Some deeply interactive or access-controlled sites may still need source-specific rules.
- The first strict geography taxonomy is South Africa-focused; non-South African pages fall back to generic geography extraction.
- `application_url` verification is best-effort and depends on network reachability.

## Next Steps

- Add source-specific parser overrides for high-volume funders
- Expand municipality and industry taxonomies
- Add PDF text extraction for application packs
- Add Supabase persistence behind the existing storage interface
