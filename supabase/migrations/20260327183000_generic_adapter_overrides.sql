begin;

do $$
declare
  constraint_name text;
begin
  select c.conname
  into constraint_name
  from pg_constraint c
  join pg_class t on t.oid = c.conrelid
  join pg_attribute a on a.attrelid = t.oid
  where t.relname = 'sites'
    and a.attname = 'adapter_key'
    and c.contype = 'u'
    and a.attnum = any (c.conkey)
  limit 1;

  if constraint_name is not null then
    execute format('alter table public.sites drop constraint %I', constraint_name);
  end if;
end $$;

update public.sites
set adapter_config = $${
  "allowed_path_prefixes": ["/products-services/"],
  "include_url_terms": [
    "fund",
    "funding",
    "finance",
    "programme",
    "product",
    "transformation",
    "capital",
    "venture",
    "acquisition",
    "expansion",
    "entrepreneurship",
    "procurement",
    "franchise",
    "tourism",
    "furniture",
    "bakubung",
    "spaza",
    "film",
    "arts"
  ],
  "exclude_url_terms": [
    "/news/",
    "/media/",
    "/resources/",
    "/about/",
    "/careers/",
    "/contact/",
    "/search",
    "/archive"
  ],
  "strict_path_prefixes": true,
  "allow_root_url": true,
  "discovery_terms": [
    "fund",
    "funding",
    "finance",
    "programme",
    "product",
    "capital",
    "venture",
    "apply"
  ],
  "content_selectors": [
    "article.single-page-article .single-page-content",
    "article.single-page-article .entry-content",
    "article.single-page-article",
    ".single-page-content",
    ".entry-content"
  ],
  "candidate_selectors": [
    "article",
    "section",
    "div.card",
    ".card",
    ".programme-card",
    ".content-block"
  ],
  "parent_page_terms": [
    "iMbewu Fund",
    "uMnotho Fund",
    "Rural, Township and Community Development Fund",
    "Strategic Projects Fund",
    "Arts and Culture Venture Capital Fund",
    "Tourism Transformation Fund",
    "Furniture Fund",
    "Bakubung Fund",
    "Spaza Shop Support Fund",
    "Television and Film Fund"
  ],
  "child_page_terms": [
    "funding criteria",
    "eligibility criteria",
    "how to apply",
    "non-financial business support",
    "programme guidelines",
    "ttf checklist",
    "empowerment objectives"
  ],
  "support_page_terms": [
    "funding criteria",
    "eligibility criteria",
    "how to apply",
    "funding instruments",
    "non-financial business support",
    "checklist",
    "guidelines",
    "brochure",
    "application portal",
    "portal",
    "empowerment objectives"
  ],
  "program_name_strip_prefix_patterns": ["^\\s*\\d+\\s*[.)-]?\\s*"],
  "program_name_strip_suffix_patterns": ["\\s*(?:-|—|\\||::)\\s*National Empowerment Fund\\s*$"],
  "merge_aliases": {
    "how to apply": "",
    "programme guidelines": "",
    "funding criteria": "",
    "overview": "",
    "support fund": "fund"
  }
}$$::jsonb
where site_key = 'nefcorp';

update public.sites
set adapter_config = $${
  "crawl_mode": "funding_plus_support",
  "include_url_terms": [
    "grant",
    "voucher",
    "fund",
    "funding",
    "sponsorship",
    "thusano",
    "mentorship",
    "market linkage",
    "market linkages",
    "business management training",
    "entrepreneurship",
    "products-services",
    "apply",
    "application"
  ],
  "exclude_url_terms": [
    "/news/",
    "/media/",
    "/press/",
    "/careers/",
    "/jobs/",
    "/vacancies/",
    "/internship/",
    "/internships/",
    "/bursary/",
    "/bursaries/",
    "/about/"
  ],
  "strict_path_prefixes": false,
  "allow_root_url": true,
  "discovery_terms": [
    "grant",
    "voucher",
    "fund",
    "funding",
    "sponsorship",
    "thusano",
    "mentorship",
    "market linkage",
    "market linkages",
    "business management training",
    "support",
    "apply",
    "application",
    "products & services"
  ],
  "content_selectors": [
    "main",
    "article",
    ".content",
    ".single-page-content",
    ".entry-content",
    ".products-services"
  ],
  "candidate_selectors": [
    "article",
    "section",
    "div.card",
    ".card",
    ".programme-card",
    ".single-page-content",
    ".entry-content"
  ],
  "parent_page_terms": [
    "products & services",
    "products and services",
    "nyda grant programme",
    "voucher programme",
    "sponsorships",
    "thusano fund"
  ],
  "child_page_terms": [
    "mentorship",
    "market linkage",
    "market linkages",
    "business management training",
    "how to apply",
    "application form",
    "faq"
  ],
  "application_support_terms": [
    "how to apply",
    "application form",
    "faq",
    "checklist",
    "portal",
    "register",
    "application",
    "guidelines"
  ],
  "supporting_programme_terms": [
    "mentorship",
    "market linkage",
    "market linkages",
    "business management training"
  ],
  "support_page_terms": [
    "application form",
    "faq",
    "checklist",
    "portal",
    "register",
    "guidelines"
  ],
  "suppress_support_record_terms": [
    "mentorship",
    "market linkage",
    "market linkages",
    "business management training",
    "business support"
  ],
  "merge_aliases": {
    "nyda voucher programme": "voucher programme",
    "sponsorships & thusano fund": "thusano fund",
    "products & services": ""
  }
}$$::jsonb
where site_key = 'nyda';

commit;
