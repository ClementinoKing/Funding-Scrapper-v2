begin;

alter table "users"
  add column if not exists "phone" text default null,
  add column if not exists "whatsapp_opt_in" boolean default false,
  add column if not exists "dob" date default null,
  add column if not exists "qualifications" text default null,
  add column if not exists "id_type" text default null,
  add column if not exists "id_number" text default null,
  add column if not exists "id_expiry" date default null,
  add column if not exists "id_document_url" text default null,
  add column if not exists "address_line1" text default null,
  add column if not exists "address_line2" text default null,
  add column if not exists "city" text default null,
  add column if not exists "state" text default null,
  add column if not exists "province" text default null,
  add column if not exists "postal_code" text default null,
  add column if not exists "country" text default null,
  add column if not exists "race" text default null,
  add column if not exists "gender" text default null;

commit;