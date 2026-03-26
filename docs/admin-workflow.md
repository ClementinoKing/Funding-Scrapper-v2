# Admin Workflow

## Queues
- Program review queue: pending and low-confidence records.
- Scraper incidents queue: failed/partial runs needing triage.
- Match intervention queue: unmatched/high-potential applicants.

## Actions
- Edit normalized fields and confidence metadata.
- Approve/reject records for applicant visibility.
- Force rematch for a record or user segment.
- Manually link users to programs.
- Trigger custom notification events.

## Auditability
- Every admin action should write `actor_id`, `before`, `after`, and timestamp into an audit trail table.
