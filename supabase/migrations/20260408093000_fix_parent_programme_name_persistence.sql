create or replace function public.infer_parent_programme_name_from_source_url(
  source_url text,
  current_program_name text default null
)
returns text
language plpgsql
as $$
declare
  path_text text;
  raw_segments text[];
  informative_segments text[] := '{}'::text[];
  segment text;
  parent_segment text;
  leaf_segment text;
  inferred_parent text;
begin
  if source_url is null or btrim(source_url) = '' then
    return null;
  end if;

  path_text := regexp_replace(
    split_part(split_part(source_url, '?', 1), '#', 1),
    '^https?://[^/]+',
    ''
  );
  raw_segments := string_to_array(trim(both '/' from coalesce(path_text, '')), '/');

  if coalesce(array_length(raw_segments, 1), 0) = 0 then
    return null;
  end if;

  foreach segment in array raw_segments loop
    segment := btrim(segment);
    if segment = '' then
      continue;
    end if;

    if lower(segment) in (
      'products-services',
      'product-services',
      'products',
      'services',
      'funding',
      'funding-solutions',
      'programmes',
      'programs',
      'opportunities',
      'support'
    ) then
      continue;
    end if;

    informative_segments := array_append(informative_segments, segment);
  end loop;

  if coalesce(array_length(informative_segments, 1), 0) < 2 then
    return null;
  end if;

  parent_segment := informative_segments[array_length(informative_segments, 1) - 1];
  leaf_segment := lower(informative_segments[array_length(informative_segments, 1)]);

  if leaf_segment !~ '^\d+(?:[-_].+)?$'
    and leaf_segment not like '%apply%'
    and leaf_segment not like '%application%'
    and leaf_segment not like '%programme-guidelines%'
    and leaf_segment not like '%program-guidelines%'
    and leaf_segment not like '%guidelines%'
    and leaf_segment not like '%eligibility%'
    and leaf_segment not like '%criteria%'
    and leaf_segment not like '%checklist%'
    and leaf_segment not like '%documents%'
    and leaf_segment not like '%required-documents%'
    and leaf_segment not like '%how-to-apply%'
    and leaf_segment not like '%application-form%'
    and leaf_segment not like '%overview%'
  then
    return null;
  end if;

  inferred_parent := initcap(replace(replace(parent_segment, '-', ' '), '_', ' '));
  inferred_parent := regexp_replace(inferred_parent, '\s+', ' ', 'g');

  if inferred_parent is null or btrim(inferred_parent) = '' then
    return null;
  end if;

  if current_program_name is not null and lower(btrim(current_program_name)) = lower(btrim(inferred_parent)) then
    return null;
  end if;

  return inferred_parent;
end;
$$;

create or replace function public.ensure_parent_programme_name()
returns trigger
language plpgsql
as $$
begin
  if nullif(new.parent_programme_name, '') is null then
    new.parent_programme_name := public.infer_parent_programme_name_from_source_url(new.source_url, new.program_name);
  end if;

  return new;
end;
$$;

drop trigger if exists trg_funding_programmes_parent_programme_name on public.funding_programmes;
create trigger trg_funding_programmes_parent_programme_name
before insert or update on public.funding_programmes
for each row
execute function public.ensure_parent_programme_name();

drop trigger if exists trg_final_funding_programmes_parent_programme_name on public.final_funding_programmes;
create trigger trg_final_funding_programmes_parent_programme_name
before insert or update on public.final_funding_programmes
for each row
execute function public.ensure_parent_programme_name();

update public.funding_programmes
set parent_programme_name = public.infer_parent_programme_name_from_source_url(source_url, program_name)
where nullif(parent_programme_name, '') is null;

update public.final_funding_programmes
set parent_programme_name = public.infer_parent_programme_name_from_source_url(source_url, program_name)
where nullif(parent_programme_name, '') is null;
