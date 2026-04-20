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

## funding_programmes
- `id (uuid, unique technical id)`
- `program_id (text, pk)`
- `program_name`, `program_slug`
- `funder_name`, `funder_slug`
- `country_code`
- `status (active, closed, opening_soon, suspended, unknown)`
- `source_url`, `source_urls (jsonb)`, `source_domain`, `source_page_title`
- `scraped_at`, `last_scraped_at`, `last_verified_at`
- `raw_eligibility_data`, `raw_funding_offer_data`, `raw_terms_data`, `raw_documents_data`, `raw_application_data`
- `funding_type`, `funding_lines`
- `ticket_min`, `ticket_max`, `currency`, `program_budget_total`
- `deadline_type`, `deadline_date`
- `funding_speed_days_min`, `funding_speed_days_max`
- `geography_scope`, `provinces (jsonb)`, `municipalities (jsonb)`, `postal_code_ranges (jsonb)`
- `industries (jsonb)`, `use_of_funds (jsonb)`, `business_stage_eligibility (jsonb)`
- `turnover_min`, `turnover_max`
- `years_in_business_min`, `years_in_business_max`
- `employee_min`, `employee_max`
- `ownership_targets (jsonb)`, `entity_types_allowed (jsonb)`, `certifications_required (jsonb)`
- `security_required`, `equity_required`
- `payback_months_min`, `payback_months_max`
- `interest_type`, `repayment_frequency`
- `exclusions (jsonb)`, `required_documents (jsonb)`
- `application_channel`, `application_url`, `contact_email`, `contact_phone`
- `raw_text_snippets (jsonb)`, `evidence_by_field (jsonb)`
- `extraction_confidence (jsonb)`, `field_confidence (jsonb)`
- `related_documents (jsonb)`, `notes (jsonb)`
- `site_adapter`, `page_type`, `parent_programme_name`
- `parser_version`, `needs_review`, `validation_errors (jsonb)`
- `approval_status (pending, approved, rejected)`
- `created_at`, `updated_at`, `deleted_at`

## final_funding_programmes
- Mirrors `funding_programmes` for applicant-facing published records
- Includes the same programme columns as `funding_programmes`
- Additional published-record fields:
- `source_program_id (text, unique, fk -> funding_programmes.program_id)`
- `published_at`
- `source_approval_status (pending, approved, rejected)`

## sites
- `site_key (text, pk)`
- `display_name`
- `primary_domain (unique)`
- `adapter_key`
- `seed_urls (jsonb)`
- `active`
- `notes (jsonb)`
- `created_at`, `updated_at`

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
