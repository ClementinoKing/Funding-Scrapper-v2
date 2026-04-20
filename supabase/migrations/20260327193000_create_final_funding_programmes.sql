begin;

alter table public.funding_programmes
  add column if not exists approval_status text not null default 'pending';

do $$
begin
  alter table public.funding_programmes
    add constraint funding_programmes_approval_status_check
    check (approval_status in ('pending', 'approved', 'rejected'));
exception
  when duplicate_object then null;
end $$;

create index if not exists idx_funding_programmes_approval_status on public.funding_programmes (approval_status);

drop policy if exists "Admin update funding programmes" on public.funding_programmes;
create policy "Admin update funding programmes"
on public.funding_programmes
for update
using (public.is_admin())
with check (public.is_admin());

create table if not exists public.final_funding_programmes (
  like public.funding_programmes including all
);

alter table public.final_funding_programmes
  add column if not exists source_program_id text not null unique references public.funding_programmes(program_id) on delete cascade;

alter table public.final_funding_programmes
  add column if not exists published_at timestamptz not null default now();

alter table public.final_funding_programmes
  add column if not exists source_approval_status text not null default 'approved';

do $$
begin
  alter table public.final_funding_programmes
    add constraint final_funding_programmes_source_approval_status_check
    check (source_approval_status in ('pending', 'approved', 'rejected'));
exception
  when duplicate_object then null;
end $$;

alter table public.final_funding_programmes enable row level security;

drop policy if exists "Public read final funding programmes" on public.final_funding_programmes;
create policy "Public read final funding programmes"
on public.final_funding_programmes
for select
using (true);

create or replace function public.sync_final_funding_programme()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'DELETE' then
    delete from public.final_funding_programmes
    where program_id = old.program_id;
    return old;
  end if;

  delete from public.final_funding_programmes
  where program_id = new.program_id;

  if coalesce(new.approval_status, 'pending') = 'approved' then
    insert into public.final_funding_programmes
    select
      new.*,
      new.program_id,
      now(),
      coalesce(new.approval_status, 'pending');
  end if;

  return new;
end;
$$;

drop trigger if exists trg_sync_final_funding_programme on public.funding_programmes;
create trigger trg_sync_final_funding_programme
after insert or update or delete on public.funding_programmes
for each row
execute function public.sync_final_funding_programme();

insert into public.final_funding_programmes
select
  fp.*,
  fp.program_id,
  coalesce(fp.scraped_at, now()),
  coalesce(fp.approval_status, 'pending')
from public.funding_programmes fp
where coalesce(fp.approval_status, 'pending') = 'approved'
on conflict (program_id) do nothing;

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
      notes,
      approval_status
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
      coalesce(rec->'notes', '[]'::jsonb),
      coalesce(nullif(rec->>'approval_status', ''), 'pending')
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
      approval_status = excluded.approval_status,
      updated_at = now();

    upserted_records := upserted_records + 1;
  end loop;

  insert into public.scrape_runs (
    run_id,
    source_name,
    started_at,
    completed_at,
    status,
    total_urls_crawled,
    pages_fetched_successfully,
    pages_failed,
    programmes_extracted,
    programmes_after_dedupe,
    records_with_low_confidence_extraction,
    errors,
    warnings
  )
  values (
    coalesce(run_summary->>'run_id', gen_random_uuid()::text),
    nullif(run_summary->>'source_name', ''),
    coalesce((run_summary->>'started_at')::timestamptz, now()),
    nullif(run_summary->>'completed_at', '')::timestamptz,
    coalesce(nullif(run_summary->>'status', ''), 'success'),
    coalesce((run_summary->>'total_urls_crawled')::integer, 0),
    coalesce((run_summary->>'pages_fetched_successfully')::integer, 0),
    coalesce((run_summary->>'pages_failed')::integer, 0),
    coalesce((run_summary->>'programmes_extracted')::integer, upserted_records),
    coalesce((run_summary->>'programmes_after_dedupe')::integer, upserted_records),
    coalesce((run_summary->>'records_with_low_confidence_extraction')::integer, 0),
    coalesce(run_summary->'errors', '[]'::jsonb),
    coalesce(run_summary->'warnings', '[]'::jsonb)
  )
  on conflict (run_id) do update
  set
    source_name = excluded.source_name,
    started_at = excluded.started_at,
    completed_at = excluded.completed_at,
    status = excluded.status,
    total_urls_crawled = excluded.total_urls_crawled,
    pages_fetched_successfully = excluded.pages_fetched_successfully,
    pages_failed = excluded.pages_failed,
    programmes_extracted = excluded.programmes_extracted,
    programmes_after_dedupe = excluded.programmes_after_dedupe,
    records_with_low_confidence_extraction = excluded.records_with_low_confidence_extraction,
    errors = excluded.errors,
    warnings = excluded.warnings;

  return jsonb_build_object('status', 'ok', 'upserted_records', upserted_records);
end;
$$;

grant execute on function public.ingest_funding_programmes(jsonb, jsonb) to anon, authenticated, service_role;
grant execute on function public.sync_final_funding_programme() to anon, authenticated, service_role;

commit;
