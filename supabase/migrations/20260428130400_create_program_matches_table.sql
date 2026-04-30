begin;

drop table if exists program_matches;

create table public.program_matches (
  id uuid not null default gen_random_uuid (),
  business_id uuid not null,
  program_id text not null,
  program_title text,
  final_score numeric(5, 2) not null,
  rule_score numeric(5, 2) null,
  ai_score numeric(5, 2) null,
  match_reasons jsonb null,
  eligibility_gaps jsonb null,
  ai_analysis text null,
  ai_confidence real null,
  match_type character varying(50) null default 'initial'::character varying,
  created_at timestamp with time zone null default now(),
  constraint program_matches_pkey primary key (id),
  constraint program_matches_business_id_program_id_key unique (business_id, program_id),
  constraint program_matches_business_id_fkey foreign KEY (business_id) references businesses (id),
  constraint program_matches_program_id_fkey foreign KEY (program_id) references funding_programmes (program_id)
);

commit;