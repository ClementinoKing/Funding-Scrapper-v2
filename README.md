# Funding Opportunity Matcher Platform (Foundation)

Production-ready frontend foundation for a Funding Program Discovery and Matching Platform.

## Stack

- React + TypeScript + Vite
- Tailwind CSS + shadcn-style component architecture
- React Router (role-based app navigation)
- TanStack Query (API state orchestration)
- Zustand (auth/session state)

## Quick Start

```bash
npm install
npm run dev
```

## Implemented First-Phase Modules

- Applicant authentication and profile flow
- Applicant dashboard, programs listing, and match results
- Notification management surface (email first, extensible channels)
- Admin dashboard with program review workflow
- Scraper run monitoring and intervention queue
- Matching engine control surface
- Typed domain and API contracts ready for backend integration

## Architecture and Product Design Docs

- [Platform Architecture](./docs/architecture.md)
- [Database Schema](./docs/database-schema.md)
- [User Flows](./docs/user-flows.md)
- [Scraper Pipeline Design](./docs/scraper-pipeline.md)
- [Matching Logic Design](./docs/matching-logic.md)
- [Admin Workflow](./docs/admin-workflow.md)
- [Notification Flow](./docs/notification-flow.md)
# Funding-Scrapper-v2
