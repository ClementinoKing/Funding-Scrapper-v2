begin;

alter table public.funding_programmes
  add column if not exists ai_enriched boolean;

alter table public.final_funding_programmes
  add column if not exists ai_enriched boolean;

update public.funding_programmes
set ai_enriched = coalesce(ai_enriched, false);

update public.final_funding_programmes
set ai_enriched = coalesce(ai_enriched, false);

alter table public.funding_programmes
  alter column ai_enriched set default false,
  alter column ai_enriched set not null;

alter table public.final_funding_programmes
  alter column ai_enriched set default false,
  alter column ai_enriched set not null;

do $$
declare
  sync_def text;
begin
  sync_def := pg_get_functiondef('public.sync_final_funding_programme()'::regprocedure);
  sync_def := replace(
    sync_def,
    E'      parser_version,\n      needs_review,\n      validation_errors,',
    E'      parser_version,\n      ai_enriched,\n      needs_review,\n      validation_errors,'
  );
  sync_def := replace(
    sync_def,
    E'      new.field_confidence,\n      new.parser_version,\n      new.needs_review,',
    E'      new.field_confidence,\n      new.parser_version,\n      new.ai_enriched,\n      new.needs_review,'
  );
  execute sync_def;
end
$$;

do $$
declare
  ingest_def text;
begin
  ingest_def := pg_get_functiondef('public.ingest_funding_programmes(jsonb, jsonb)'::regprocedure);
  ingest_def := replace(
    ingest_def,
    E'      field_confidence,\n      parser_version,\n      needs_review,\n      validation_errors,',
    E'      field_confidence,\n      parser_version,\n      ai_enriched,\n      needs_review,\n      validation_errors,'
  );
  ingest_def := replace(
    ingest_def,
    E'      coalesce(rec->''related_documents'', ''[]''::jsonb),\n      coalesce(rec->''notes'', ''[]''::jsonb),\n      coalesce(nullif(rec->>''parser_version'', ''''), nullif(run_summary->>''parser_version'', ''''), ''unknown''),\n      case',
    E'      coalesce(rec->''related_documents'', ''[]''::jsonb),\n      coalesce(rec->''notes'', ''[]''::jsonb),\n      coalesce(nullif(rec->>''parser_version'', ''''), nullif(run_summary->>''parser_version'', ''''), ''unknown''),\n      coalesce((rec->>''ai_enriched'')::boolean, false),\n      case'
  );
  ingest_def := replace(
    ingest_def,
    E'      parser_version = excluded.parser_version,\n      needs_review = excluded.needs_review,',
    E'      parser_version = excluded.parser_version,\n      ai_enriched = excluded.ai_enriched,\n      needs_review = excluded.needs_review,'
  );
  execute ingest_def;
end
$$;

grant execute on function public.ingest_funding_programmes(jsonb, jsonb) to anon, authenticated, service_role;
grant execute on function public.sync_final_funding_programme() to anon, authenticated, service_role;

commit;
