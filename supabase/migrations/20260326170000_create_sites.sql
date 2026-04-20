begin;

create table if not exists public.sites (
  site_key text primary key,
  display_name text not null unique,
  primary_domain text not null unique,
  adapter_key text not null unique,
  seed_urls jsonb not null default '[]'::jsonb,
  adapter_config jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  notes jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_sites_active on public.sites (active);
create index if not exists idx_sites_adapter_key on public.sites (adapter_key);

drop trigger if exists trg_sites_updated_at on public.sites;
create trigger trg_sites_updated_at
before update on public.sites
for each row
execute procedure public.set_updated_at();

alter table public.sites enable row level security;

drop policy if exists "Public read sites" on public.sites;
create policy "Public read sites"
on public.sites
for select
using (true);

drop policy if exists "Admin insert sites" on public.sites;
create policy "Admin insert sites"
on public.sites
for insert
with check (public.is_admin());

drop policy if exists "Admin update sites" on public.sites;
create policy "Admin update sites"
on public.sites
for update
using (public.is_admin())
with check (public.is_admin());

drop policy if exists "Admin delete sites" on public.sites;
create policy "Admin delete sites"
on public.sites
for delete
using (public.is_admin());

insert into public.sites (
  site_key,
  display_name,
  primary_domain,
  adapter_key,
  seed_urls,
  adapter_config,
  active,
  notes
)
values
  (
    'sefa',
    'SEFA Direct Lending Products',
    'sedfa.org.za',
    'sefa',
    '["https://www.sedfa.org.za/products/direct-lending-products"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'idc',
    'IDC',
    'idc.co.za',
    'idc',
    '["https://www.idc.co.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'nyda',
    'NYDA',
    'nyda.gov.za',
    'nyda',
    '[
      "https://www.nyda.gov.za/",
      "https://www.nyda.gov.za/Products-Services/NYDA-Voucher-Programme.html",
      "https://www.nyda.gov.za/Products-Services/Sponsorships-Thusano-Fund.html",
      "https://www.nyda.gov.za/Portals/0/WebSitesCreative_MyContentManager/1092/NYDA_Grant_Programme.pdf",
      "https://www.nyda.gov.za/Portals/0/Downloads/Forms/Grant%20and%20Voucher%20Application%20Form.pdf",
      "https://erp.nyda.gov.za/faq"
    ]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'dtic',
    'DTIC',
    'thedtic.gov.za',
    'dtic',
    '["https://www.thedtic.gov.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'nefcorp',
    'NEF',
    'nefcorp.co.za',
    'nefcorp',
    '["https://www.nefcorp.co.za/products-services/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'dsbd',
    'DSBD',
    'dsbd.gov.za',
    'dsbd',
    '["http://dsbd.gov.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'dbsa',
    'DBSA',
    'dbsa.org',
    'dbsa',
    '["https://www.dbsa.org"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'gep',
    'GEP',
    'gep.co.za',
    'gep',
    '["https://www.gep.co.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'tia',
    'TIA Funding Instruments',
    'tia.org.za',
    'tia',
    '["https://www.tia.org.za/funding-instruments/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'pic',
    'PIC',
    'pic.gov.za',
    'pic',
    '["https://www.pic.gov.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'landbank',
    'Land Bank',
    'landbank.co.za',
    'landbank',
    '["https://landbank.co.za/Pages/Home.aspx"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'ithala',
    'ITHALA',
    'ithala.co.za',
    'ithala',
    '["https://www.ithala.co.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'lieda',
    'LEDA',
    'lieda.co.za',
    'lieda',
    '["https://www.lieda.co.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'mega',
    'MEGA',
    'mega.gov.za',
    'mega',
    '["https://mega.gov.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'nwdc',
    'NWDC',
    'nwdc.co.za',
    'nwdc',
    '["https://nwdc.co.za/"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  ),
  (
    'nceda',
    'NCEDA',
    'northern-cape.gov.za',
    'nceda',
    '["http://www.northern-cape.gov.za/dedat/index.php"]'::jsonb,
    '{}'::jsonb,
    true,
    '["Seeded from the existing local seed list."]'::jsonb
  )
on conflict (site_key) do update
set
  display_name = excluded.display_name,
  primary_domain = excluded.primary_domain,
  adapter_key = excluded.adapter_key,
  seed_urls = excluded.seed_urls,
  adapter_config = excluded.adapter_config,
  active = excluded.active,
  notes = excluded.notes;

commit;
