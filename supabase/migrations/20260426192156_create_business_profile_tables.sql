begin;

DROP TABLE IF EXISTS "program_matches" CASCADE;
DROP TABLE IF EXISTS "funding_repayment_terms" CASCADE;
DROP TABLE IF EXISTS "financial_documents" CASCADE;
DROP TABLE IF EXISTS "demographics" CASCADE;
DROP TABLE IF EXISTS "team_compliances" CASCADE;
DROP TABLE IF EXISTS "financial_moneyflows" CASCADE;
DROP TABLE IF EXISTS "payment_types" CASCADE;
DROP TABLE IF EXISTS "funding_need_purposes" CASCADE;
DROP TABLE IF EXISTS "funding_needs" CASCADE;
DROP TABLE IF EXISTS "funding_purposes" CASCADE;
DROP TABLE IF EXISTS "business_compliance" CASCADE;
DROP TABLE IF EXISTS "business_industries" CASCADE;
DROP TABLE IF EXISTS "business_locations" CASCADE;
DROP TABLE IF EXISTS "businesses" CASCADE;

CREATE TABLE "businesses" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "profile_id" uuid,
  "business_name" text,
  "registration_number" text,
  "registration_date" date,
  "tax_number" text,
  "business_type" text,
  "business_age_band" text,
  "employees_band" text,
  "website" text,
  "impact_focus" text,
  "monthly_customers" text,
  "revenue_from_biggest_customer" text,
  "customer_payment_speed" text,
  "needs_matching" bool default true,
  "demographics" jsonb null,
  "financial_documents" jsonb null,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT business_pkey PRIMARY KEY (id)
);

CREATE TABLE "business_locations" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "type" text,
  "province" text,
  "municipality" text,
  "postal_code" text,
  "latitude" float,
  "longitude" float,
  "is_primary" bool,
  "physical_address" text,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT business_locations_pkey PRIMARY KEY (id)
);

CREATE TABLE "business_industries" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "industry_name" text,
  "specialisation" text,
  "target_consumer" text,
  "regulator" text,
  "seasonality" text,
  "is_export" bool,
  "is_primary" bool,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT business_industries_pkey PRIMARY KEY (id)
);

CREATE TABLE "business_compliance" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT business_compliance_pkey PRIMARY KEY (id)
);

CREATE TABLE "funding_purposes" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "code" text,
  "category" text,
  CONSTRAINT funding_purposes_pkey PRIMARY KEY (id)
);

CREATE TABLE "funding_needs" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "amount_mode" text,
  "amount_min" float,
  "amount_max" float,
  "amount_exact" float,
  "timeline_band" text,
  "purposes" jsonb null,
  "description" text,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT funding_needs_pkey PRIMARY KEY (id)
);

CREATE TABLE "funding_need_purposes" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "funding_need_id" uuid,
  "funding_purpose_id" uuid,
  CONSTRAINT funding_need_purposes_pkey PRIMARY KEY (id)
);

CREATE TABLE "payment_types" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "payment_name" text,
  "provider" text,
  "is_invoice_issued" bool,
  "turnover" float,
  "payment_term" text,
  "customer_percentage" text,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT payment_types_pkey PRIMARY KEY (id)
);

CREATE TABLE "financial_moneyflows" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "type" text,
  "bank_name" text,
  "account_age" text,
  "monthly_income_band" text,
  "monthly_income_exact" float,
  "tracking_method" text,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT financial_moneyflows_pkey PRIMARY KEY (id)
);

CREATE TABLE "team_compliances" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "team_size" text,
  "team_stage" text,
  "owners_background" jsonb null,
  "sars_status" text,
  "vat_status" text,
  "bbee_certification" text,
  "demographics" jsonb null,
  "financial_documents" jsonb null,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT team_compliances_pkey PRIMARY KEY (id)
);

CREATE TABLE "demographics" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "description" text,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT demographics_pkey PRIMARY KEY (id)
);

CREATE TABLE "financial_documents" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "document_type" text,
  "description" text,
  "is_available" bool,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT financial_documents_pkey PRIMARY KEY (id)
);

CREATE TABLE "funding_repayment_terms" (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  "business_id" uuid,
  "frequency" text,
  "period" text,
  "investors_share" text,
  "collateral" text,
  "created_at" timestamp with time zone null default now(),
  "updated_at" timestamp with time zone null default now(),
  CONSTRAINT funding_repayment_terms_pkey PRIMARY KEY (id)
);

CREATE TABLE "program_matches" (
  id uuid not null default gen_random_uuid (),
  business_id uuid not null,
  program_id text not null,
  match_score numeric(5, 2) not null,
  rule_score numeric(5, 2) null,
  ai_score numeric(5, 2) null,
  match_reasons jsonb null,
  eligibility_gaps jsonb null,
  ai_analysis text null,
  match_type character varying(50) null default 'initial'::character varying,
  created_at timestamp with time zone null default now(),
  ai_confidence real null,
  constraint program_matches_pkey primary key (id),
  constraint program_matches_business_id_program_id_key unique (business_id, program_id),
  constraint program_matches_business_id_fkey foreign KEY (business_id) references businesses (id),
  constraint program_matches_program_id_fkey foreign KEY (program_id) references funding_programmes (program_id)
);

ALTER TABLE "businesses" ADD FOREIGN KEY ("profile_id") REFERENCES "users" ("id");

ALTER TABLE "business_locations" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "business_industries" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "business_compliance" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "funding_needs" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "funding_need_purposes" ADD FOREIGN KEY ("funding_need_id") REFERENCES "funding_needs" ("id");

ALTER TABLE "funding_need_purposes" ADD FOREIGN KEY ("funding_purpose_id") REFERENCES "funding_purposes" ("id");

ALTER TABLE "payment_types" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "financial_moneyflows" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "team_compliances" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "demographics" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "financial_documents" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "funding_repayment_terms" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "program_matches" ADD FOREIGN KEY ("business_id") REFERENCES "businesses" ("id");

ALTER TABLE "program_matches" ADD FOREIGN KEY ("program_id") REFERENCES "funding_programmes" ("program_id");

CREATE INDEX ON businesses(profile_id);
CREATE INDEX ON funding_needs(business_id);

commit;