begin;

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
select
  site_key,
  display_name,
  primary_domain,
  adapter_key,
  seed_urls,
  adapter_config,
  active,
  notes
from jsonb_to_recordset($$[
  {
    "site_key": "sefa",
    "display_name": "Sefa",
    "primary_domain": "www.sefa.org.za",
    "adapter_key": "sefa",
    "seed_urls": ["https://www.sefa.org.za/products/direct-lending-products"],
    "active": true,
    "notes": ["Aliases: SEFA, Small Enterprise Finance Agency, SEDFA. SEDFA is an alias only; sefa.org.za is canonical."],
    "adapter_config": {
      "allowed_path_prefixes": ["/products/", "/services/", "/funding/"],
      "include_url_terms": ["direct-lending", "fund", "funding", "loan", "finance", "credit", "apply", "product"],
      "exclude_url_terms": ["/news/", "/media/", "/press/", "/careers/", "/vacancies/", "/tenders/", "/procurement/", "/about/", "/contact/"],
      "discovery_terms": ["direct lending", "funding", "loan", "finance", "application", "eligibility"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".elementor", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".panel", ".elementor-widget", ".accordion", ".tab-pane"],
      "max_pages": 35,
      "depth_limit": 3
    }
  },
  {
    "site_key": "idc",
    "display_name": "IDC",
    "primary_domain": "www.idc.co.za",
    "adapter_key": "idc",
    "seed_urls": ["https://www.idc.co.za/"],
    "active": true,
    "notes": ["Aliases: Industrial Development Corporation."],
    "adapter_config": {
      "allowed_path_prefixes": ["/funding-solutions/", "/sectors/", "/products/", "/how-to-apply/"],
      "include_url_terms": ["funding", "fund", "finance", "loan", "equity", "sector", "apply", "incentive", "scheme"],
      "exclude_url_terms": ["/news/", "/media/", "/press/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about-us/", "/contact-us/"],
      "discovery_terms": ["funding solutions", "funding", "finance", "application", "sector"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".wp-block-group", ".elementor", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".tile", ".panel", ".wp-block-column", ".accordion", ".tab-pane"],
      "max_pages": 60,
      "depth_limit": 3
    }
  },
  {
    "site_key": "nyda",
    "display_name": "NYDA",
    "primary_domain": "www.nyda.gov.za",
    "adapter_key": "nyda",
    "seed_urls": [
      "https://www.nyda.gov.za/",
      "https://www.nyda.gov.za/Products-Services/NYDA-Voucher-Programme.html",
      "https://www.nyda.gov.za/Products-Services/Sponsorships-Thusano-Fund.html",
      "https://www.nyda.gov.za/Portals/0/WebSitesCreative_MyContentManager/1092/NYDA_Grant_Programme.pdf",
      "https://www.nyda.gov.za/Portals/0/Downloads/Forms/Grant%20and%20Voucher%20Application%20Form.pdf",
      "https://erp.nyda.gov.za/faq"
    ],
    "active": true,
    "notes": ["Aliases: National Youth Development Agency."],
    "adapter_config": {
      "crawl_mode": "funding_plus_support",
      "allowed_hosts": ["erp.nyda.gov.za"],
      "include_url_terms": ["grant", "voucher", "fund", "funding", "sponsorship", "thusano", "products-services", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/press/", "/careers/", "/jobs/", "/vacancies/", "/internship/", "/internships/", "/bursary/", "/bursaries/", "/about/"],
      "discovery_terms": ["grant", "voucher", "fund", "funding", "sponsorship", "thusano", "apply", "application", "products & services"],
      "content_selectors": ["main", "article", ".content", ".single-page-content", ".entry-content", ".products-services"],
      "candidate_selectors": ["article", "section", "div.card", ".card", ".programme-card", ".single-page-content", ".entry-content"],
      "support_page_terms": ["application form", "faq", "checklist", "portal", "register", "guidelines"],
      "suppress_support_record_terms": ["mentorship", "market linkage", "market linkages", "business management training", "business support"],
      "max_pages": 45,
      "depth_limit": 3
    }
  },
  {
    "site_key": "dtic",
    "display_name": "DTIC",
    "primary_domain": "www.thedtic.gov.za",
    "adapter_key": "dtic",
    "seed_urls": ["https://www.thedtic.gov.za/"],
    "active": true,
    "notes": ["Aliases: the dtic, Department of Trade Industry and Competition."],
    "adapter_config": {
      "allowed_path_prefixes": ["/financial-and-non-financial-support/", "/sectors-and-services/", "/trade-investment-and-exports/", "/industrial-development/"],
      "include_url_terms": ["incentive", "fund", "funding", "grant", "finance", "scheme", "programme", "program", "support", "apply"],
      "exclude_url_terms": ["/news/", "/media/", "/speeches/", "/events/", "/careers/", "/tenders/", "/procurement/", "/documents/", "/legislation/", "/about-the-dtic/"],
      "discovery_terms": ["incentives", "financial support", "funding", "grant", "scheme", "application"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".elementor", ".wp-block-group", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".panel", ".elementor-widget", ".wp-block-column", ".accordion"],
      "max_pages": 70,
      "depth_limit": 3
    }
  },
  {
    "site_key": "nefcorp",
    "display_name": "NEF",
    "primary_domain": "www.nefcorp.co.za",
    "adapter_key": "nefcorp",
    "seed_urls": ["https://www.nefcorp.co.za/products-services/"],
    "active": true,
    "notes": ["Aliases: National Empowerment Fund."],
    "adapter_config": {
      "allowed_path_prefixes": ["/products-services/"],
      "include_url_terms": ["fund", "funding", "finance", "programme", "product", "transformation", "capital", "venture", "acquisition", "expansion", "entrepreneurship", "franchise", "tourism", "furniture", "bakubung", "spaza", "film", "arts"],
      "exclude_url_terms": ["/news/", "/media/", "/resources/", "/about/", "/careers/", "/contact/", "/search", "/archive", "/tenders/", "/procurement/"],
      "strict_path_prefixes": true,
      "allow_root_url": true,
      "discovery_terms": ["fund", "funding", "finance", "programme", "product", "capital", "venture", "apply"],
      "content_selectors": ["article.single-page-article .single-page-content", "article.single-page-article .entry-content", "article.single-page-article", ".single-page-content", ".entry-content"],
      "candidate_selectors": ["article", "section", "div.card", ".card", ".programme-card", ".content-block"],
      "parent_page_terms": ["iMbewu Fund", "uMnotho Fund", "Rural, Township and Community Development Fund", "Strategic Projects Fund", "Arts and Culture Venture Capital Fund", "Tourism Transformation Fund", "Furniture Fund", "Bakubung Fund", "Spaza Shop Support Fund", "Television and Film Fund"],
      "child_page_terms": ["funding criteria", "eligibility criteria", "how to apply", "non-financial business support", "programme guidelines", "ttf checklist", "empowerment objectives"],
      "support_page_terms": ["funding criteria", "eligibility criteria", "how to apply", "funding instruments", "non-financial business support", "checklist", "guidelines", "brochure", "application portal", "portal", "empowerment objectives"],
      "program_name_strip_prefix_patterns": ["^\\s*\\d+\\s*[.)-]?\\s*"],
      "program_name_strip_suffix_patterns": ["\\s*(?:-|--|\\||::)\\s*National Empowerment Fund\\s*$"],
      "merge_aliases": {"how to apply": "", "programme guidelines": "", "funding criteria": "", "overview": "", "support fund": "fund"},
      "max_pages": 60,
      "depth_limit": 3
    }
  },
  {
    "site_key": "dsbd",
    "display_name": "DSBD",
    "primary_domain": "www.dsbd.gov.za",
    "adapter_key": "dsbd",
    "seed_urls": ["https://www.dsbd.gov.za/"],
    "active": true,
    "notes": ["Aliases: DSMD, Department of Small Business Development. DSBD is canonical because the supplied URL is dsbd.gov.za."],
    "adapter_config": {
      "allowed_path_prefixes": ["/programmes/", "/programs/", "/services/", "/funding/", "/spaza-shop-support-fund/"],
      "include_url_terms": ["fund", "funding", "grant", "scheme", "incentive", "programme", "program", "support", "spaza", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/speeches/", "/events/", "/careers/", "/tenders/", "/procurement/", "/vacancies/", "/about/"],
      "discovery_terms": ["fund", "funding", "grant", "incentive", "support fund", "application"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".content", ".region-content"],
      "candidate_selectors": ["article", "section", ".card", ".views-row", ".field-content", ".accordion", ".tab-pane"],
      "max_pages": 55,
      "depth_limit": 3
    }
  },
  {
    "site_key": "dbsa",
    "display_name": "DBSA",
    "primary_domain": "www.dbsa.org",
    "adapter_key": "dbsa",
    "seed_urls": ["https://www.dbsa.org"],
    "active": true,
    "notes": ["Aliases: Development Bank of Southern Africa."],
    "adapter_config": {
      "allowed_path_prefixes": ["/solutions/", "/products-services/", "/financing/", "/projects/"],
      "include_url_terms": ["fund", "funding", "finance", "financing", "loan", "infrastructure", "programme", "program", "facility", "apply"],
      "exclude_url_terms": ["/news/", "/media/", "/press/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about-us/", "/contact-us/"],
      "discovery_terms": ["financing", "funding", "infrastructure", "loan", "facility", "apply"],
      "content_selectors": ["main", "article", ".content", ".field-content", ".views-row", ".node__content", ".region-content"],
      "candidate_selectors": ["article", "section", ".card", ".views-row", ".field-content", ".accordion", ".tab-pane"],
      "max_pages": 55,
      "depth_limit": 3
    }
  },
  {
    "site_key": "gep",
    "display_name": "GEF",
    "primary_domain": "www.gep.co.za",
    "adapter_key": "gep",
    "seed_urls": ["https://www.gep.co.za/"],
    "active": true,
    "notes": ["Aliases: GEP, Gauteng Enterprise Propeller. Supplied name was GEF but the URL is GEP."],
    "adapter_config": {
      "allowed_path_prefixes": ["/funding/", "/financial-support/", "/programmes/", "/services/", "/products/"],
      "include_url_terms": ["fund", "funding", "finance", "loan", "grant", "programme", "program", "support", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/press/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about/", "/contact/"],
      "discovery_terms": ["funding", "finance", "loan", "grant", "support", "application"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".elementor", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".elementor-widget", ".accordion", ".tab-pane"],
      "max_pages": 50,
      "depth_limit": 3
    }
  },
  {
    "site_key": "tia",
    "display_name": "TIA",
    "primary_domain": "www.tia.org.za",
    "adapter_key": "tia",
    "seed_urls": ["https://www.tia.org.za/funding-instruments/"],
    "active": true,
    "notes": ["Aliases: Technology Innovation Agency."],
    "adapter_config": {
      "allowed_path_prefixes": ["/funding-instruments/", "/funding/", "/programmes/", "/services/"],
      "include_url_terms": ["funding-instruments", "fund", "funding", "grant", "innovation", "technology", "seed", "commercialisation", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/press/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about/", "/contact/"],
      "discovery_terms": ["funding instruments", "funding", "innovation", "technology", "application"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".elementor", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".elementor-widget", ".accordion", ".tab-pane"],
      "max_pages": 45,
      "depth_limit": 3
    }
  },
  {
    "site_key": "pic",
    "display_name": "PIC",
    "primary_domain": "www.pic.gov.za",
    "adapter_key": "pic",
    "seed_urls": ["https://www.pic.gov.za/"],
    "active": true,
    "notes": ["Aliases: Public Investment Corporation."],
    "adapter_config": {
      "allowed_path_prefixes": ["/isibaya/", "/early-stage-fund/", "/unlisted-investments/", "/properties/", "/apply-for-funding/"],
      "include_url_terms": ["isibaya", "early-stage", "fund", "funding", "investment", "unlisted", "developmental", "application", "apply"],
      "exclude_url_terms": ["/news/", "/media/", "/press/", "/careers/", "/vacationwork", "/graduate", "/bursaries", "/corporate-procurement", "/property-procurement", "/procurement", "/tenders", "/risk-and-compliance", "/code-of-ethics", "/complaints", "/copyright", "/popia", "/protection-personal-information-act", "/whistle-blowers"],
      "discovery_terms": ["isibaya", "early stage fund", "developmental investments", "unlisted investments", "application", "funding"],
      "content_selectors": ["main", "article", ".content", ".ms-rtestate-field", ".spPageContent", ".shortpoint-content", ".shortpoint-block", ".shortpoint-section"],
      "candidate_selectors": ["article", "section", ".card", ".panel", ".accordion", ".tab-content", ".tab-pane", ".ms-rtestate-field", ".shortpoint-content", ".shortpoint-block"],
      "force_browser_url_terms": ["pic.gov.za"],
      "playwright_required_by_default": true,
      "suppress_support_record_terms": ["graduate", "bursary", "vacation work", "procurement", "tender", "policy", "complaints"],
      "program_name_strip_suffix_patterns": ["\\s*(?:-|--|\\||::)\\s*PIC\\s*$"],
      "max_pages": 45,
      "depth_limit": 3
    }
  },
  {
    "site_key": "landbank",
    "display_name": "Land Bank",
    "primary_domain": "landbank.co.za",
    "adapter_key": "landbank",
    "seed_urls": ["https://landbank.co.za/Pages/Home.aspx"],
    "active": true,
    "notes": ["Aliases: Land and Agricultural Development Bank of South Africa."],
    "adapter_config": {
      "allowed_path_prefixes": ["/Pages/", "/Products/", "/Services/", "/Funding/"],
      "include_url_terms": ["fund", "funding", "finance", "loan", "credit", "agri", "agriculture", "farmer", "apply", "application"],
      "exclude_url_terms": ["/News/", "/Media/", "/Careers/", "/Tenders/", "/Procurement/", "/About/", "/Contact/", "/Policies/"],
      "discovery_terms": ["funding", "finance", "loan", "credit", "agriculture", "application"],
      "content_selectors": ["main", "article", ".content", ".ms-rtestate-field", ".page-content", "#content"],
      "candidate_selectors": ["article", "section", ".card", ".panel", ".accordion", ".tab-pane", "tr"],
      "max_pages": 45,
      "depth_limit": 3
    }
  },
  {
    "site_key": "ithala",
    "display_name": "ITHALA (KZN)",
    "primary_domain": "www.ithala.co.za",
    "adapter_key": "ithala",
    "seed_urls": ["https://www.ithala.co.za/"],
    "active": true,
    "notes": ["Aliases: Ithala Development Finance Corporation."],
    "adapter_config": {
      "allowed_path_prefixes": ["/business-finance/", "/funding/", "/products/", "/services/"],
      "include_url_terms": ["fund", "funding", "finance", "loan", "business", "enterprise", "kzn", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about/", "/contact/"],
      "discovery_terms": ["business finance", "funding", "loan", "enterprise", "application"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".elementor", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".elementor-widget", ".accordion", ".tab-pane"],
      "max_pages": 45,
      "depth_limit": 3
    }
  },
  {
    "site_key": "lieda",
    "display_name": "LEDA (LIMPOPO)",
    "primary_domain": "www.lieda.co.za",
    "adapter_key": "lieda",
    "seed_urls": ["https://www.lieda.co.za/"],
    "active": true,
    "notes": ["Aliases: Limpopo Economic Development Agency, Lieda."],
    "adapter_config": {
      "allowed_path_prefixes": ["/funding/", "/business-support/", "/programmes/", "/services/", "/enterprise-development/"],
      "include_url_terms": ["fund", "funding", "finance", "loan", "grant", "business", "enterprise", "programme", "program", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about/", "/contact/"],
      "discovery_terms": ["funding", "business support", "enterprise development", "application"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".elementor", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".elementor-widget", ".accordion", ".tab-pane"],
      "max_pages": 45,
      "depth_limit": 3
    }
  },
  {
    "site_key": "mega",
    "display_name": "MEGA (MPUMALANGA)",
    "primary_domain": "mega.gov.za",
    "adapter_key": "mega",
    "seed_urls": ["https://mega.gov.za/"],
    "active": true,
    "notes": ["Aliases: Mpumalanga Economic Growth Agency."],
    "adapter_config": {
      "allowed_path_prefixes": ["/funding/", "/business/", "/enterprise-development/", "/services/", "/programmes/"],
      "include_url_terms": ["fund", "funding", "finance", "loan", "business", "enterprise", "development", "programme", "program", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about/", "/contact/"],
      "discovery_terms": ["funding", "enterprise development", "business support", "application"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".elementor", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".elementor-widget", ".accordion", ".tab-pane"],
      "max_pages": 45,
      "depth_limit": 3
    }
  },
  {
    "site_key": "nwdc",
    "display_name": "NWDC (NORTH WEST)",
    "primary_domain": "nwdc.co.za",
    "adapter_key": "nwdc",
    "seed_urls": ["https://nwdc.co.za/"],
    "active": true,
    "notes": ["Aliases: North West Development Corporation."],
    "adapter_config": {
      "allowed_path_prefixes": ["/funding/", "/business-support/", "/investment/", "/services/", "/programmes/"],
      "include_url_terms": ["fund", "funding", "finance", "loan", "business", "enterprise", "investment", "development", "programme", "program", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about/", "/contact/"],
      "discovery_terms": ["funding", "business support", "investment", "enterprise", "application"],
      "content_selectors": ["main", "article", ".entry-content", ".page-content", ".elementor", ".content"],
      "candidate_selectors": ["article", "section", ".card", ".elementor-widget", ".accordion", ".tab-pane"],
      "max_pages": 45,
      "depth_limit": 3
    }
  },
  {
    "site_key": "nceda",
    "display_name": "NCEDA (NORTHERN CAPE)",
    "primary_domain": "www.northern-cape.gov.za",
    "adapter_key": "nceda",
    "seed_urls": ["http://www.northern-cape.gov.za/dedat/index.php"],
    "active": true,
    "notes": ["Aliases: Northern Cape Economic Development Agency, Northern Cape DEDAT."],
    "adapter_config": {
      "allowed_path_prefixes": ["/dedat/"],
      "include_url_terms": ["fund", "funding", "finance", "loan", "grant", "business", "enterprise", "development", "incentive", "programme", "program", "apply", "application"],
      "exclude_url_terms": ["/news/", "/media/", "/careers/", "/tenders/", "/procurement/", "/events/", "/about/", "/contact/"],
      "discovery_terms": ["funding", "enterprise development", "business support", "incentive", "application"],
      "content_selectors": ["main", "article", "#content", ".content", ".item-page", ".blog", ".page-content"],
      "candidate_selectors": ["article", "section", ".item", ".card", ".panel", ".accordion", "tr"],
      "max_pages": 45,
      "depth_limit": 3
    }
  }
]$$::jsonb) as source_registry(
  site_key text,
  display_name text,
  primary_domain text,
  adapter_key text,
  seed_urls jsonb,
  adapter_config jsonb,
  active boolean,
  notes jsonb
)
on conflict (site_key) do update
set
  display_name = excluded.display_name,
  primary_domain = excluded.primary_domain,
  adapter_key = excluded.adapter_key,
  seed_urls = excluded.seed_urls,
  adapter_config = excluded.adapter_config,
  active = excluded.active,
  notes = excluded.notes,
  updated_at = now();

commit;
