# Platform Architecture

## Core Layers

1. Applicant UI Layer
- Auth, profile, program discovery, matches, and notifications.

2. Data Ingestion + Matching Layer
- Scheduled scraping jobs write normalized opportunities into a central database.
- Matching jobs compute results from stored records for fast retrieval.

3. Admin Oversight Layer
- Review queue for low-confidence scrapes and approval pipeline.
- Matching controls, intervention queue, and notification oversight.

## Frontend Module Structure

- `src/app`: App composition, providers, router
- `src/components/ui`: Reusable design system primitives
- `src/components/layout`: Shared layout shell
- `src/pages/applicant`: Applicant-facing pages
- `src/pages/admin`: Admin-facing pages
- `src/services`: API client contracts and domain logic
- `src/store`: Session/auth and app state
- `src/types`: Typed shared domain models

## Extensibility Strategy

- Add new scraper sources via source adapter interfaces at backend layer.
- Add new channels (WhatsApp/SMS) through notification provider abstraction.
- Add new matching rules using composable weighted rule engine.
- Support future multi-tenant organizations with tenant-scoped IDs in schema.
