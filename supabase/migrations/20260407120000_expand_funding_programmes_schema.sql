begin;

create or replace function public.slugify_text(input text)
returns text
language sql
immutable
as $$
  select nullif(
    trim(both '-' from regexp_replace(lower(coalesce(input, '')), '[^a-z0-9]+', '-', 'g')),
    ''
  );
$$;

create or replace function public.derive_funding_programme_status(deadline_type text, deadline_date date)
returns text
language sql
stable
as $$
  select case
    when deadline_type in ('Open', 'Rolling') then 'active'
    when deadline_type = 'FixedDate' and deadline_date is not null and deadline_date < current_date then 'closed'
    when deadline_type = 'FixedDate' and deadline_date is not null then 'active'
    else 'unknown'
  end;
$$;

create or replace function public.build_funding_programme_validation_errors(
  program_name text,
  funder_name text,
  deadline_type text,
  deadline_date date,
  application_url text
)
returns jsonb
language sql
immutable
as $$
  select to_jsonb(
    array_remove(
      array[
        case when nullif(btrim(program_name), '') is null then 'missing program_name' end,
        case when nullif(btrim(funder_name), '') is null then 'missing funder_name' end,
        case when deadline_type = 'FixedDate' and deadline_date is null then 'missing deadline date for fixed-date programme' end,
        case when nullif(btrim(application_url), '') is null then 'missing application_url' end
      ]::text[],
      null
    )
  );
$$;

alter table public.funding_programmes
  add column if not exists id uuid,
  add column if not exists program_slug text,
  add column if not exists funder_slug text,
  add column if not exists country_code text,
  add column if not exists status text,
  add column if not exists raw_funding_offer_data jsonb,
  add column if not exists raw_terms_data jsonb,
  add column if not exists raw_documents_data jsonb,
  add column if not exists raw_application_data jsonb,
  add column if not exists evidence_by_field jsonb,
  add column if not exists field_confidence jsonb,
  add column if not exists parser_version text,
  add column if not exists needs_review boolean,
  add column if not exists validation_errors jsonb,
  add column if not exists last_scraped_at timestamptz,
  add column if not exists last_verified_at date,
  add column if not exists deleted_at timestamptz;

alter table public.final_funding_programmes
  add column if not exists id uuid,
  add column if not exists program_slug text,
  add column if not exists funder_slug text,
  add column if not exists country_code text,
  add column if not exists status text,
  add column if not exists raw_funding_offer_data jsonb,
  add column if not exists raw_terms_data jsonb,
  add column if not exists raw_documents_data jsonb,
  add column if not exists raw_application_data jsonb,
  add column if not exists evidence_by_field jsonb,
  add column if not exists field_confidence jsonb,
  add column if not exists parser_version text,
  add column if not exists needs_review boolean,
  add column if not exists validation_errors jsonb,
  add column if not exists last_scraped_at timestamptz,
  add column if not exists last_verified_at date,
  add column if not exists deleted_at timestamptz;

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
    insert into public.final_funding_programmes (
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
      created_at,
      updated_at,
      site_adapter,
      page_type,
      parent_programme_name,
      approval_status,
      source_program_id,
      published_at,
      source_approval_status,
      id,
      program_slug,
      funder_slug,
      country_code,
      status,
      raw_funding_offer_data,
      raw_terms_data,
      raw_documents_data,
      raw_application_data,
      evidence_by_field,
      field_confidence,
      parser_version,
      needs_review,
      validation_errors,
      last_scraped_at,
      last_verified_at,
      deleted_at
    )
    values (
      new.program_id,
      new.program_name,
      new.funder_name,
      new.source_url,
      new.source_urls,
      new.source_domain,
      new.source_page_title,
      new.scraped_at,
      new.raw_eligibility_data,
      new.funding_type,
      new.funding_lines,
      new.ticket_min,
      new.ticket_max,
      new.currency,
      new.program_budget_total,
      new.deadline_type,
      new.deadline_date,
      new.funding_speed_days_min,
      new.funding_speed_days_max,
      new.geography_scope,
      new.provinces,
      new.municipalities,
      new.postal_code_ranges,
      new.industries,
      new.use_of_funds,
      new.business_stage_eligibility,
      new.turnover_min,
      new.turnover_max,
      new.years_in_business_min,
      new.years_in_business_max,
      new.employee_min,
      new.employee_max,
      new.ownership_targets,
      new.entity_types_allowed,
      new.certifications_required,
      new.security_required,
      new.equity_required,
      new.payback_months_min,
      new.payback_months_max,
      new.interest_type,
      new.repayment_frequency,
      new.exclusions,
      new.required_documents,
      new.application_channel,
      new.application_url,
      new.contact_email,
      new.contact_phone,
      new.raw_text_snippets,
      new.extraction_confidence,
      new.related_documents,
      new.notes,
      new.created_at,
      new.updated_at,
      new.site_adapter,
      new.page_type,
      new.parent_programme_name,
      new.approval_status,
      new.program_id,
      now(),
      coalesce(new.approval_status, 'pending'),
      new.id,
      new.program_slug,
      new.funder_slug,
      new.country_code,
      new.status,
      new.raw_funding_offer_data,
      new.raw_terms_data,
      new.raw_documents_data,
      new.raw_application_data,
      new.evidence_by_field,
      new.field_confidence,
      new.parser_version,
      new.needs_review,
      new.validation_errors,
      new.last_scraped_at,
      new.last_verified_at,
      new.deleted_at
    );
  end if;

  return new;
end;
$$;

update public.funding_programmes
set
  id = coalesce(id, gen_random_uuid()),
  program_slug = coalesce(program_slug, public.slugify_text(coalesce(program_name, program_id))),
  funder_slug = coalesce(funder_slug, public.slugify_text(coalesce(funder_name, source_domain))),
  country_code = coalesce(nullif(country_code, ''), 'ZA'),
  status = coalesce(nullif(status, ''), public.derive_funding_programme_status(deadline_type, deadline_date)),
  raw_funding_offer_data = coalesce(
    raw_funding_offer_data,
    case when funding_lines <> '[]'::jsonb then funding_lines else null end
  ),
  raw_terms_data = coalesce(
    raw_terms_data,
    case
      when security_required <> 'Unknown'
        or equity_required <> 'Unknown'
        or payback_months_min is not null
        or payback_months_max is not null
        or interest_type <> 'Unknown'
        or repayment_frequency <> 'Unknown'
      then jsonb_strip_nulls(
        jsonb_build_object(
          'security_required', nullif(security_required, 'Unknown'),
          'equity_required', nullif(equity_required, 'Unknown'),
          'payback_months_min', payback_months_min,
          'payback_months_max', payback_months_max,
          'interest_type', nullif(interest_type, 'Unknown'),
          'repayment_frequency', nullif(repayment_frequency, 'Unknown')
        )
      )
      else null
    end
  ),
  raw_documents_data = coalesce(
    raw_documents_data,
    case when required_documents <> '[]'::jsonb then required_documents else null end
  ),
  raw_application_data = coalesce(
    raw_application_data,
    case
      when application_url is not null
        or contact_email is not null
        or contact_phone is not null
        or application_channel <> 'Unknown'
      then jsonb_strip_nulls(
        jsonb_build_object(
          'application_channel', nullif(application_channel, 'Unknown'),
          'application_url', application_url,
          'contact_email', contact_email,
          'contact_phone', contact_phone
        )
      )
      else null
    end
  ),
  evidence_by_field = coalesce(evidence_by_field, raw_text_snippets, '{}'::jsonb),
  field_confidence = coalesce(field_confidence, extraction_confidence, '{}'::jsonb),
  parser_version = coalesce(nullif(parser_version, ''), 'legacy'),
  validation_errors = coalesce(
    validation_errors,
    public.build_funding_programme_validation_errors(
      program_name,
      funder_name,
      deadline_type,
      deadline_date,
      application_url
    ),
    '[]'::jsonb
  ),
  last_scraped_at = coalesce(last_scraped_at, scraped_at, created_at),
  needs_review = coalesce(
    needs_review,
    jsonb_array_length(
      coalesce(
        validation_errors,
        public.build_funding_programme_validation_errors(
          program_name,
          funder_name,
          deadline_type,
          deadline_date,
          application_url
        ),
        '[]'::jsonb
      )
    ) > 0
  );

update public.final_funding_programmes
set
  id = coalesce(id, gen_random_uuid()),
  program_slug = coalesce(program_slug, public.slugify_text(coalesce(program_name, program_id))),
  funder_slug = coalesce(funder_slug, public.slugify_text(coalesce(funder_name, source_domain))),
  country_code = coalesce(nullif(country_code, ''), 'ZA'),
  status = coalesce(nullif(status, ''), public.derive_funding_programme_status(deadline_type, deadline_date)),
  raw_funding_offer_data = coalesce(
    raw_funding_offer_data,
    case when funding_lines <> '[]'::jsonb then funding_lines else null end
  ),
  raw_terms_data = coalesce(
    raw_terms_data,
    case
      when security_required <> 'Unknown'
        or equity_required <> 'Unknown'
        or payback_months_min is not null
        or payback_months_max is not null
        or interest_type <> 'Unknown'
        or repayment_frequency <> 'Unknown'
      then jsonb_strip_nulls(
        jsonb_build_object(
          'security_required', nullif(security_required, 'Unknown'),
          'equity_required', nullif(equity_required, 'Unknown'),
          'payback_months_min', payback_months_min,
          'payback_months_max', payback_months_max,
          'interest_type', nullif(interest_type, 'Unknown'),
          'repayment_frequency', nullif(repayment_frequency, 'Unknown')
        )
      )
      else null
    end
  ),
  raw_documents_data = coalesce(
    raw_documents_data,
    case when required_documents <> '[]'::jsonb then required_documents else null end
  ),
  raw_application_data = coalesce(
    raw_application_data,
    case
      when application_url is not null
        or contact_email is not null
        or contact_phone is not null
        or application_channel <> 'Unknown'
      then jsonb_strip_nulls(
        jsonb_build_object(
          'application_channel', nullif(application_channel, 'Unknown'),
          'application_url', application_url,
          'contact_email', contact_email,
          'contact_phone', contact_phone
        )
      )
      else null
    end
  ),
  evidence_by_field = coalesce(evidence_by_field, raw_text_snippets, '{}'::jsonb),
  field_confidence = coalesce(field_confidence, extraction_confidence, '{}'::jsonb),
  parser_version = coalesce(nullif(parser_version, ''), 'legacy'),
  validation_errors = coalesce(
    validation_errors,
    public.build_funding_programme_validation_errors(
      program_name,
      funder_name,
      deadline_type,
      deadline_date,
      application_url
    ),
    '[]'::jsonb
  ),
  last_scraped_at = coalesce(last_scraped_at, scraped_at, created_at),
  needs_review = coalesce(
    needs_review,
    jsonb_array_length(
      coalesce(
        validation_errors,
        public.build_funding_programme_validation_errors(
          program_name,
          funder_name,
          deadline_type,
          deadline_date,
          application_url
        ),
        '[]'::jsonb
      )
    ) > 0
  );

alter table public.funding_programmes
  alter column id set default gen_random_uuid(),
  alter column id set not null,
  alter column country_code set default 'ZA',
  alter column country_code set not null,
  alter column status set default 'unknown',
  alter column status set not null,
  alter column parser_version set default 'unknown',
  alter column parser_version set not null,
  alter column needs_review set default false,
  alter column needs_review set not null,
  alter column validation_errors set default '[]'::jsonb,
  alter column validation_errors set not null,
  alter column evidence_by_field set default '{}'::jsonb,
  alter column evidence_by_field set not null,
  alter column field_confidence set default '{}'::jsonb,
  alter column field_confidence set not null;

alter table public.final_funding_programmes
  alter column id set default gen_random_uuid(),
  alter column id set not null,
  alter column country_code set default 'ZA',
  alter column country_code set not null,
  alter column status set default 'unknown',
  alter column status set not null,
  alter column parser_version set default 'unknown',
  alter column parser_version set not null,
  alter column needs_review set default false,
  alter column needs_review set not null,
  alter column validation_errors set default '[]'::jsonb,
  alter column validation_errors set not null,
  alter column evidence_by_field set default '{}'::jsonb,
  alter column evidence_by_field set not null,
  alter column field_confidence set default '{}'::jsonb,
  alter column field_confidence set not null;

alter table public.funding_programmes
  drop constraint if exists funding_programmes_status_check;
alter table public.funding_programmes
  add constraint funding_programmes_status_check
  check (status in ('active', 'closed', 'opening_soon', 'suspended', 'unknown'));

alter table public.final_funding_programmes
  drop constraint if exists final_funding_programmes_status_check;
alter table public.final_funding_programmes
  add constraint final_funding_programmes_status_check
  check (status in ('active', 'closed', 'opening_soon', 'suspended', 'unknown'));

alter table public.funding_programmes
  drop constraint if exists funding_programmes_application_channel_check;
alter table public.funding_programmes
  add constraint funding_programmes_application_channel_check
  check (application_channel in ('Online form', 'Email', 'Branch', 'Partner referral', 'Manual / Contact first', 'Unknown'));

alter table public.final_funding_programmes
  drop constraint if exists final_funding_programmes_application_channel_check;
alter table public.final_funding_programmes
  add constraint final_funding_programmes_application_channel_check
  check (application_channel in ('Online form', 'Email', 'Branch', 'Partner referral', 'Manual / Contact first', 'Unknown'));

create unique index if not exists idx_funding_programmes_id on public.funding_programmes (id);
create unique index if not exists idx_final_funding_programmes_id on public.final_funding_programmes (id);
create index if not exists idx_funding_programmes_program_slug on public.funding_programmes (program_slug);
create index if not exists idx_funding_programmes_country_code on public.funding_programmes (country_code);
create index if not exists idx_funding_programmes_status on public.funding_programmes (status);
create index if not exists idx_final_funding_programmes_program_slug on public.final_funding_programmes (program_slug);
create index if not exists idx_final_funding_programmes_country_code on public.final_funding_programmes (country_code);
create index if not exists idx_final_funding_programmes_status on public.final_funding_programmes (status);

create or replace function public.ingest_funding_programmes(records jsonb, run_summary jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  rec jsonb;
  upserted_records integer := 0;
  derived_deadline_type text;
  derived_deadline_date date;
  derived_validation_errors jsonb;
begin
  if coalesce(jsonb_typeof(records), '') <> 'array' then
    raise exception 'records must be a json array';
  end if;

  for rec in
    select value
    from jsonb_array_elements(records)
  loop
    derived_deadline_type := coalesce(nullif(rec->>'deadline_type', ''), 'Unknown');
    derived_deadline_date := nullif(rec->>'deadline_date', '')::date;
    derived_validation_errors := coalesce(
      rec->'validation_errors',
      public.build_funding_programme_validation_errors(
        nullif(rec->>'program_name', ''),
        nullif(rec->>'funder_name', ''),
        derived_deadline_type,
        derived_deadline_date,
        nullif(rec->>'application_url', '')
      ),
      '[]'::jsonb
    );

    insert into public.funding_programmes (
      id,
      program_id,
      program_name,
      program_slug,
      funder_name,
      funder_slug,
      country_code,
      status,
      source_url,
      source_urls,
      source_domain,
      source_page_title,
      scraped_at,
      last_scraped_at,
      last_verified_at,
      raw_eligibility_data,
      raw_funding_offer_data,
      raw_terms_data,
      raw_documents_data,
      raw_application_data,
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
      evidence_by_field,
      extraction_confidence,
      field_confidence,
      related_documents,
      notes,
      parser_version,
      needs_review,
      validation_errors,
      deleted_at,
      approval_status
    )
    values (
      case
        when rec ? 'id' and nullif(rec->>'id', '') is not null then (rec->>'id')::uuid
        else gen_random_uuid()
      end,
      coalesce(rec->>'program_id', gen_random_uuid()::text),
      nullif(rec->>'program_name', ''),
      coalesce(nullif(rec->>'program_slug', ''), public.slugify_text(coalesce(nullif(rec->>'program_name', ''), rec->>'program_id'))),
      nullif(rec->>'funder_name', ''),
      coalesce(nullif(rec->>'funder_slug', ''), public.slugify_text(coalesce(nullif(rec->>'funder_name', ''), rec->>'source_domain'))),
      coalesce(nullif(rec->>'country_code', ''), 'ZA'),
      coalesce(nullif(rec->>'status', ''), public.derive_funding_programme_status(derived_deadline_type, derived_deadline_date)),
      rec->>'source_url',
      coalesce(rec->'source_urls', '[]'::jsonb),
      rec->>'source_domain',
      nullif(rec->>'source_page_title', ''),
      coalesce((rec->>'scraped_at')::timestamptz, now()),
      coalesce((rec->>'last_scraped_at')::timestamptz, (rec->>'scraped_at')::timestamptz, now()),
      nullif(rec->>'last_verified_at', '')::date,
      case when rec ? 'raw_eligibility_data' then rec->'raw_eligibility_data' else null end,
      case
        when rec ? 'raw_funding_offer_data' then rec->'raw_funding_offer_data'
        when coalesce(rec->'funding_lines', '[]'::jsonb) <> '[]'::jsonb then rec->'funding_lines'
        else null
      end,
      case when rec ? 'raw_terms_data' then rec->'raw_terms_data' else null end,
      case
        when rec ? 'raw_documents_data' then rec->'raw_documents_data'
        when coalesce(rec->'required_documents', '[]'::jsonb) <> '[]'::jsonb then rec->'required_documents'
        else null
      end,
      case
        when rec ? 'raw_application_data' then rec->'raw_application_data'
        else jsonb_strip_nulls(
          jsonb_build_object(
            'application_channel', nullif(rec->>'application_channel', ''),
            'application_url', nullif(rec->>'application_url', ''),
            'contact_email', nullif(rec->>'contact_email', ''),
            'contact_phone', nullif(rec->>'contact_phone', '')
          )
        )
      end,
      coalesce(nullif(rec->>'funding_type', ''), 'Unknown'),
      coalesce(rec->'funding_lines', '[]'::jsonb),
      nullif(rec->>'ticket_min', '')::numeric,
      nullif(rec->>'ticket_max', '')::numeric,
      nullif(rec->>'currency', ''),
      nullif(rec->>'program_budget_total', '')::numeric,
      derived_deadline_type,
      derived_deadline_date,
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
      coalesce(rec->'evidence_by_field', rec->'raw_text_snippets', '{}'::jsonb),
      coalesce(rec->'extraction_confidence', '{}'::jsonb),
      coalesce(rec->'field_confidence', rec->'extraction_confidence_by_field', rec->'extraction_confidence', '{}'::jsonb),
      coalesce(rec->'related_documents', '[]'::jsonb),
      coalesce(rec->'notes', '[]'::jsonb),
      coalesce(nullif(rec->>'parser_version', ''), nullif(run_summary->>'parser_version', ''), 'unknown'),
      case
        when rec ? 'needs_review' and nullif(rec->>'needs_review', '') is not null then (rec->>'needs_review')::boolean
        else jsonb_array_length(derived_validation_errors) > 0
      end,
      derived_validation_errors,
      nullif(rec->>'deleted_at', '')::timestamptz,
      coalesce(nullif(rec->>'approval_status', ''), 'pending')
    )
    on conflict (program_id) do update
    set
      program_name = excluded.program_name,
      program_slug = excluded.program_slug,
      funder_name = excluded.funder_name,
      funder_slug = excluded.funder_slug,
      country_code = excluded.country_code,
      status = excluded.status,
      source_url = excluded.source_url,
      source_urls = excluded.source_urls,
      source_domain = excluded.source_domain,
      source_page_title = excluded.source_page_title,
      scraped_at = excluded.scraped_at,
      last_scraped_at = excluded.last_scraped_at,
      last_verified_at = excluded.last_verified_at,
      raw_eligibility_data = excluded.raw_eligibility_data,
      raw_funding_offer_data = excluded.raw_funding_offer_data,
      raw_terms_data = excluded.raw_terms_data,
      raw_documents_data = excluded.raw_documents_data,
      raw_application_data = excluded.raw_application_data,
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
      evidence_by_field = excluded.evidence_by_field,
      extraction_confidence = excluded.extraction_confidence,
      field_confidence = excluded.field_confidence,
      related_documents = excluded.related_documents,
      notes = excluded.notes,
      parser_version = excluded.parser_version,
      needs_review = excluded.needs_review,
      validation_errors = excluded.validation_errors,
      deleted_at = excluded.deleted_at,
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

commit;
