# Scraper Pipeline Design

## Scheduled Ingestion Workflow
1. Daily cron triggers source runners.
2. Source-specific scraper extracts raw listing and detail data.
3. Parser and normalizer map source data into canonical `funding_programs` schema.
4. Validation service flags incomplete records and assigns `scrape_confidence`.
5. Approved-level confidence data goes to `pending` admin review or auto-approve policy.
6. Scrape run telemetry is written to `scrape_runs`.

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
