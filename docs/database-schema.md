# Database Schema (Initial)

## users
- `id (uuid, pk)`
- `email (unique)`
- `password_hash`
- `role (enum: applicant, admin)`
- `created_at`, `updated_at`

## applicant_profiles
- `user_id (pk, fk -> users.id)`
- `full_name`, `phone`, `country`, `region`
- `organization_type`, `stage`, `annual_revenue_band`, `team_size_band`, `years_operating`
- `sectors (jsonb)`
- `funding_needs (jsonb)`
- `preferred_funding_types (jsonb)`
- `target_amount_min`, `target_amount_max`
- `profile_completeness`
- `updated_at`

## funding_programs
- `id (uuid, pk)`
- `title`, `provider_name`, `source_name`, `source_url`
- `geography (jsonb)`, `sectors (jsonb)`
- `eligibility_summary`
- `funding_type`
- `amount_min`, `amount_max`
- `deadline_at`
- `status (active, closing_soon, closed, draft)`
- `scrape_confidence`
- `approval_status (pending, approved, rejected)`
- `created_at`, `updated_at`, `last_scraped_at`

## scrape_runs
- `id (uuid, pk)`
- `source_name`
- `status (running, success, partial, failed)`
- `started_at`, `completed_at`
- `records_found`, `records_stored`, `records_flagged`
- `error_summary`

## match_results
- `id (uuid, pk)`
- `user_id (fk -> users.id)`
- `program_id (fk -> funding_programs.id)`
- `score`
- `status (high_fit, medium_fit, low_fit, manual_review)`
- `reasons (jsonb)`, `blockers (jsonb)`
- `updated_at`
- unique index: `(user_id, program_id)`

## admin_interventions
- `id (uuid, pk)`
- `user_id (fk -> users.id)`
- `program_id (nullable fk -> funding_programs.id)`
- `case_type`, `reason`, `status`
- `assigned_to (fk -> users.id)`
- `resolution_notes`
- `created_at`, `updated_at`

## notifications
- `id (uuid, pk)`
- `user_id (fk -> users.id)`
- `channel (email, whatsapp, sms)`
- `type (new_match, deadline_alert, admin_note)`
- `status (queued, sent, failed)`
- `payload (jsonb)`
- `created_at`, `sent_at`

## notification_preferences
- `user_id (pk, fk -> users.id)`
- `email_enabled`, `whatsapp_enabled`, `sms_enabled`
- `digest_frequency (instant, daily, weekly)`
- `updated_at`
