begin;

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.funding_programmes (
  program_id text primary key,
  program_name text,
  funder_name text,
  source_url text not null,
  source_urls jsonb not null default '[]'::jsonb,
  source_domain text not null,
  source_page_title text,
  scraped_at timestamptz not null default now(),
  raw_eligibility_data jsonb,
  funding_type text not null default 'Unknown' check (funding_type in ('Grant', 'Loan', 'Equity', 'Guarantee', 'Hybrid', 'Other', 'Unknown')),
  funding_lines jsonb not null default '[]'::jsonb,
  ticket_min numeric,
  ticket_max numeric,
  currency text,
  program_budget_total numeric,
  deadline_type text not null default 'Unknown' check (deadline_type in ('FixedDate', 'Rolling', 'Open', 'Unknown')),
  deadline_date date,
  funding_speed_days_min integer,
  funding_speed_days_max integer,
  geography_scope text not null default 'Unknown' check (geography_scope in ('National', 'Province', 'Municipality', 'Local', 'International', 'Unknown')),
  provinces jsonb not null default '[]'::jsonb,
  municipalities jsonb not null default '[]'::jsonb,
  postal_code_ranges jsonb not null default '[]'::jsonb,
  industries jsonb not null default '[]'::jsonb,
  use_of_funds jsonb not null default '[]'::jsonb,
  business_stage_eligibility jsonb not null default '[]'::jsonb,
  turnover_min numeric,
  turnover_max numeric,
  years_in_business_min numeric,
  years_in_business_max numeric,
  employee_min integer,
  employee_max integer,
  ownership_targets jsonb not null default '[]'::jsonb,
  entity_types_allowed jsonb not null default '[]'::jsonb,
  certifications_required jsonb not null default '[]'::jsonb,
  security_required text not null default 'Unknown' check (security_required in ('Yes', 'No', 'Maybe', 'Unknown')),
  equity_required text not null default 'Unknown' check (equity_required in ('Yes', 'No', 'Maybe', 'Unknown')),
  payback_months_min integer,
  payback_months_max integer,
  interest_type text not null default 'Unknown' check (interest_type in ('Fixed', 'Prime-linked', 'Factor-rate', 'Unknown')),
  repayment_frequency text not null default 'Unknown' check (repayment_frequency in ('Weekly', 'Monthly', 'Variable', 'Unknown')),
  exclusions jsonb not null default '[]'::jsonb,
  required_documents jsonb not null default '[]'::jsonb,
  application_channel text not null default 'Unknown' check (application_channel in ('Online form', 'Email', 'Branch', 'Partner referral', 'Unknown')),
  application_url text,
  contact_email text,
  contact_phone text,
  raw_text_snippets jsonb not null default '{}'::jsonb,
  extraction_confidence jsonb not null default '{}'::jsonb,
  related_documents jsonb not null default '[]'::jsonb,
  notes jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.scrape_runs (
  run_id text primary key,
  source_name text,
  started_at timestamptz,
  completed_at timestamptz,
  status text not null default 'running',
  seed_urls jsonb not null default '[]'::jsonb,
  total_urls_crawled integer not null default 0,
  pages_fetched_successfully integer not null default 0,
  pages_failed integer not null default 0,
  programmes_extracted integer not null default 0,
  programmes_after_dedupe integer not null default 0,
  records_with_missing_program_name integer not null default 0,
  records_with_missing_funder_name integer not null default 0,
  records_with_unknown_funding_type integer not null default 0,
  records_with_no_application_route integer not null default 0,
  records_with_low_confidence_extraction integer not null default 0,
  low_confidence_threshold numeric,
  errors jsonb not null default '[]'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_funding_programmes_funder_name on public.funding_programmes (funder_name);
create index if not exists idx_funding_programmes_program_name on public.funding_programmes (program_name);
create index if not exists idx_funding_programmes_source_domain on public.funding_programmes (source_domain);
create index if not exists idx_funding_programmes_scraped_at on public.funding_programmes (scraped_at desc);
create index if not exists idx_scrape_runs_completed_at on public.scrape_runs (completed_at desc);

drop trigger if exists trg_funding_programmes_updated_at on public.funding_programmes;
create trigger trg_funding_programmes_updated_at
before update on public.funding_programmes
for each row
execute procedure public.set_updated_at();

drop trigger if exists trg_scrape_runs_updated_at on public.scrape_runs;
create trigger trg_scrape_runs_updated_at
before update on public.scrape_runs
for each row
execute procedure public.set_updated_at();

alter table public.funding_programmes enable row level security;
alter table public.scrape_runs enable row level security;

drop policy if exists "Public read funding programmes" on public.funding_programmes;
create policy "Public read funding programmes"
on public.funding_programmes
for select
using (true);

drop policy if exists "Public read scrape runs" on public.scrape_runs;
create policy "Public read scrape runs"
on public.scrape_runs
for select
using (true);

create or replace function public.ingest_funding_programmes(records jsonb, run_summary jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  rec jsonb;
  upserted_records integer := 0;
begin
  if coalesce(jsonb_typeof(records), '') <> 'array' then
    raise exception 'records must be a json array';
  end if;

  for rec in
    select value
    from jsonb_array_elements(records)
  loop
    insert into public.funding_programmes (
      program_id,
      program_name,
      funder_name,
      source_url,
      source_urls,
      source_domain,
      source_page_title,
      scraped_at,
      raw_eligibility_data,
      funding_type,
      funding_lines,
      ticket_min,
      ticket_max,
      currency,
      program_budget_total,
      deadline_type,
      deadline_date,
      funding_speed_days_min,
      funding_speed_days_max,
      geography_scope,
      provinces,
      municipalities,
      postal_code_ranges,
      industries,
      use_of_funds,
      business_stage_eligibility,
      turnover_min,
      turnover_max,
      years_in_business_min,
      years_in_business_max,
      employee_min,
      employee_max,
      ownership_targets,
      entity_types_allowed,
      certifications_required,
      security_required,
      equity_required,
      payback_months_min,
      payback_months_max,
      interest_type,
      repayment_frequency,
      exclusions,
      required_documents,
      application_channel,
      application_url,
      contact_email,
      contact_phone,
      raw_text_snippets,
      extraction_confidence,
      related_documents,
      notes
    )
    values (
      coalesce(rec->>'program_id', gen_random_uuid()::text),
      nullif(rec->>'program_name', ''),
      nullif(rec->>'funder_name', ''),
      rec->>'source_url',
      coalesce(rec->'source_urls', '[]'::jsonb),
      rec->>'source_domain',
      nullif(rec->>'source_page_title', ''),
      coalesce((rec->>'scraped_at')::timestamptz, now()),
      case when rec ? 'raw_eligibility_data' then rec->'raw_eligibility_data' else null end,
      coalesce(nullif(rec->>'funding_type', ''), 'Unknown'),
      coalesce(rec->'funding_lines', '[]'::jsonb),
      nullif(rec->>'ticket_min', '')::numeric,
      nullif(rec->>'ticket_max', '')::numeric,
      nullif(rec->>'currency', ''),
      nullif(rec->>'program_budget_total', '')::numeric,
      coalesce(nullif(rec->>'deadline_type', ''), 'Unknown'),
      nullif(rec->>'deadline_date', '')::date,
      nullif(rec->>'funding_speed_days_min', '')::integer,
      nullif(rec->>'funding_speed_days_max', '')::integer,
      coalesce(nullif(rec->>'geography_scope', ''), 'Unknown'),
      coalesce(rec->'provinces', '[]'::jsonb),
      coalesce(rec->'municipalities', '[]'::jsonb),
      coalesce(rec->'postal_code_ranges', '[]'::jsonb),
      coalesce(rec->'industries', '[]'::jsonb),
      coalesce(rec->'use_of_funds', '[]'::jsonb),
      coalesce(rec->'business_stage_eligibility', '[]'::jsonb),
      nullif(rec->>'turnover_min', '')::numeric,
      nullif(rec->>'turnover_max', '')::numeric,
      nullif(rec->>'years_in_business_min', '')::numeric,
      nullif(rec->>'years_in_business_max', '')::numeric,
      nullif(rec->>'employee_min', '')::integer,
      nullif(rec->>'employee_max', '')::integer,
      coalesce(rec->'ownership_targets', '[]'::jsonb),
      coalesce(rec->'entity_types_allowed', '[]'::jsonb),
      coalesce(rec->'certifications_required', '[]'::jsonb),
      coalesce(nullif(rec->>'security_required', ''), 'Unknown'),
      coalesce(nullif(rec->>'equity_required', ''), 'Unknown'),
      nullif(rec->>'payback_months_min', '')::integer,
      nullif(rec->>'payback_months_max', '')::integer,
      coalesce(nullif(rec->>'interest_type', ''), 'Unknown'),
      coalesce(nullif(rec->>'repayment_frequency', ''), 'Unknown'),
      coalesce(rec->'exclusions', '[]'::jsonb),
      coalesce(rec->'required_documents', '[]'::jsonb),
      coalesce(nullif(rec->>'application_channel', ''), 'Unknown'),
      nullif(rec->>'application_url', ''),
      nullif(rec->>'contact_email', ''),
      nullif(rec->>'contact_phone', ''),
      coalesce(rec->'raw_text_snippets', '{}'::jsonb),
      coalesce(rec->'extraction_confidence', '{}'::jsonb),
      coalesce(rec->'related_documents', '[]'::jsonb),
      coalesce(rec->'notes', '[]'::jsonb)
    )
    on conflict (program_id) do update
    set
      program_name = excluded.program_name,
      funder_name = excluded.funder_name,
      source_url = excluded.source_url,
      source_urls = excluded.source_urls,
      source_domain = excluded.source_domain,
      source_page_title = excluded.source_page_title,
      scraped_at = excluded.scraped_at,
      raw_eligibility_data = excluded.raw_eligibility_data,
      funding_type = excluded.funding_type,
      funding_lines = excluded.funding_lines,
      ticket_min = excluded.ticket_min,
      ticket_max = excluded.ticket_max,
      currency = excluded.currency,
      program_budget_total = excluded.program_budget_total,
      deadline_type = excluded.deadline_type,
      deadline_date = excluded.deadline_date,
      funding_speed_days_min = excluded.funding_speed_days_min,
      funding_speed_days_max = excluded.funding_speed_days_max,
      geography_scope = excluded.geography_scope,
      provinces = excluded.provinces,
      municipalities = excluded.municipalities,
      postal_code_ranges = excluded.postal_code_ranges,
      industries = excluded.industries,
      use_of_funds = excluded.use_of_funds,
      business_stage_eligibility = excluded.business_stage_eligibility,
      turnover_min = excluded.turnover_min,
      turnover_max = excluded.turnover_max,
      years_in_business_min = excluded.years_in_business_min,
      years_in_business_max = excluded.years_in_business_max,
      employee_min = excluded.employee_min,
      employee_max = excluded.employee_max,
      ownership_targets = excluded.ownership_targets,
      entity_types_allowed = excluded.entity_types_allowed,
      certifications_required = excluded.certifications_required,
      security_required = excluded.security_required,
      equity_required = excluded.equity_required,
      payback_months_min = excluded.payback_months_min,
      payback_months_max = excluded.payback_months_max,
      interest_type = excluded.interest_type,
      repayment_frequency = excluded.repayment_frequency,
      exclusions = excluded.exclusions,
      required_documents = excluded.required_documents,
      application_channel = excluded.application_channel,
      application_url = excluded.application_url,
      contact_email = excluded.contact_email,
      contact_phone = excluded.contact_phone,
      raw_text_snippets = excluded.raw_text_snippets,
      extraction_confidence = excluded.extraction_confidence,
      related_documents = excluded.related_documents,
      notes = excluded.notes,
      updated_at = now();

    upserted_records := upserted_records + 1;
  end loop;

  if coalesce(jsonb_typeof(run_summary), '') = 'object' and coalesce(run_summary->>'run_id', '') <> '' then
    insert into public.scrape_runs (
      run_id,
      source_name,
      started_at,
      completed_at,
      status,
      seed_urls,
      total_urls_crawled,
      pages_fetched_successfully,
      pages_failed,
      programmes_extracted,
      programmes_after_dedupe,
      records_with_missing_program_name,
      records_with_missing_funder_name,
      records_with_unknown_funding_type,
      records_with_no_application_route,
      records_with_low_confidence_extraction,
      low_confidence_threshold,
      errors,
      warnings
    )
    values (
      run_summary->>'run_id',
      nullif(run_summary->>'source_name', ''),
      nullif(run_summary->>'started_at', '')::timestamptz,
      nullif(run_summary->>'completed_at', '')::timestamptz,
      coalesce(nullif(run_summary->>'status', ''), 'running'),
      coalesce(run_summary->'seed_urls', '[]'::jsonb),
      coalesce(nullif(run_summary->>'total_urls_crawled', '')::integer, 0),
      coalesce(nullif(run_summary->>'pages_fetched_successfully', '')::integer, 0),
      coalesce(nullif(run_summary->>'pages_failed', '')::integer, 0),
      coalesce(nullif(run_summary->>'programmes_extracted', '')::integer, 0),
      coalesce(nullif(run_summary->>'programmes_after_dedupe', '')::integer, 0),
      coalesce(nullif(run_summary->>'records_with_missing_program_name', '')::integer, 0),
      coalesce(nullif(run_summary->>'records_with_missing_funder_name', '')::integer, 0),
      coalesce(nullif(run_summary->>'records_with_unknown_funding_type', '')::integer, 0),
      coalesce(nullif(run_summary->>'records_with_no_application_route', '')::integer, 0),
      coalesce(nullif(run_summary->>'records_with_low_confidence_extraction', '')::integer, 0),
      nullif(run_summary->>'low_confidence_threshold', '')::numeric,
      coalesce(run_summary->'errors', '[]'::jsonb),
      coalesce(run_summary->'warnings', '[]'::jsonb)
    )
    on conflict (run_id) do update
    set
      source_name = excluded.source_name,
      started_at = excluded.started_at,
      completed_at = excluded.completed_at,
      status = excluded.status,
      seed_urls = excluded.seed_urls,
      total_urls_crawled = excluded.total_urls_crawled,
      pages_fetched_successfully = excluded.pages_fetched_successfully,
      pages_failed = excluded.pages_failed,
      programmes_extracted = excluded.programmes_extracted,
      programmes_after_dedupe = excluded.programmes_after_dedupe,
      records_with_missing_program_name = excluded.records_with_missing_program_name,
      records_with_missing_funder_name = excluded.records_with_missing_funder_name,
      records_with_unknown_funding_type = excluded.records_with_unknown_funding_type,
      records_with_no_application_route = excluded.records_with_no_application_route,
      records_with_low_confidence_extraction = excluded.records_with_low_confidence_extraction,
      low_confidence_threshold = excluded.low_confidence_threshold,
      errors = excluded.errors,
      warnings = excluded.warnings,
      updated_at = now();
  end if;

  return jsonb_build_object(
    'upserted_records', upserted_records,
    'run_id', nullif(run_summary->>'run_id', ''),
    'rpc', 'ingest_funding_programmes'
  );
end;
$$;

revoke all on function public.ingest_funding_programmes(jsonb, jsonb) from public;
grant execute on function public.ingest_funding_programmes(jsonb, jsonb) to anon, authenticated, service_role;

commit;

