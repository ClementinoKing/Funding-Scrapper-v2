# Scraper Pipeline Design

## Scheduled Ingestion Workflow
1. Daily cron triggers source runners.
2. The scraper loads active crawl targets from the `sites` table.
3. Each site resolves to an adapter via `adapter_key`, then extracts raw listing and detail data.
4. Parser and normalizer map source data into canonical `funding_programs` schema.
5. Validation service flags incomplete records and assigns `scrape_confidence`.
6. Approved-level confidence data goes to `pending` admin review or auto-approve policy.
7. Scrape run telemetry is written to `scrape_runs`.

## Reliability Patterns
- Retry with exponential backoff per source.
- Store raw payload snapshots for debugging.
- Alert when source fails consecutively.
- Use idempotency keys to avoid duplicate program records.

## Daily Cron Recommendation
- 02:00 UTC scrape all sources.
- 03:00 UTC run normalization and dedupe.
- 03:30 UTC run matching job for changed records + active applicants.
- 04:00 UTC queue notifications for new high-fit matches.
