import type {
  ApplicantProfile,
  FundingProgram,
  MatchResult,
  NotificationEvent,
  NotificationPreference,
  ScrapeRun,
  SystemChangeLogEntry
} from "@/types/domain";

export const mockProfile: ApplicantProfile = {
  userId: "user_001",
  fullName: "Clementino King",
  email: "clementino@example.com",
  phone: "+265999111222",
  country: "Malawi",
  region: "Southern Region",
  organizationType: "startup",
  sectors: ["AgriTech", "Climate"],
  stage: "early",
  annualRevenueBand: "<10k",
  teamSizeBand: "2-10",
  yearsOperating: 2,
  fundingNeeds: ["Equipment", "Product development", "Hiring"],
  preferredFundingTypes: ["grant", "equity"],
  targetAmountMin: 10000,
  targetAmountMax: 80000,
  profileCompleteness: 87,
  updatedAt: "2026-03-13T08:31:00Z"
};

export const mockPrograms: FundingProgram[] = [
  {
    id: "prog_001",
    title: "Green Enterprise Growth Grant",
    providerName: "Africa Climate Fund",
    sourceUrl: "https://example.org/green-enterprise-grant",
    sourceName: "Africa Climate Fund",
    geography: ["Malawi", "Zambia", "Tanzania"],
    sectors: ["Climate", "AgriTech"],
    eligibilitySummary: "Early-stage ventures with measurable climate outcomes.",
    fundingType: "grant",
    amountMin: 15000,
    amountMax: 120000,
    deadlineAt: "2026-04-30T23:59:00Z",
    status: "active",
    scrapeConfidence: 0.93,
    approvalStatus: "approved",
    lastScrapedAt: "2026-03-13T05:00:00Z",
    createdAt: "2026-01-12T11:00:00Z",
    updatedAt: "2026-03-13T05:00:00Z"
  },
  {
    id: "prog_002",
    title: "Youth Innovation Equity Window",
    providerName: "Launch Capital Africa",
    sourceUrl: "https://example.org/youth-innovation-window",
    sourceName: "Launch Capital Africa",
    geography: ["Sub-Saharan Africa"],
    sectors: ["FinTech", "HealthTech", "AgriTech"],
    eligibilitySummary: "Founders under 35 with revenue traction.",
    fundingType: "equity",
    amountMin: 50000,
    amountMax: 250000,
    deadlineAt: "2026-05-10T23:59:00Z",
    status: "active",
    scrapeConfidence: 0.89,
    approvalStatus: "approved",
    lastScrapedAt: "2026-03-13T05:05:00Z",
    createdAt: "2026-02-01T08:00:00Z",
    updatedAt: "2026-03-13T05:05:00Z"
  },
  {
    id: "prog_003",
    title: "Women in Rural Business Loan Facility",
    providerName: "Inclusive Finance Initiative",
    sourceUrl: "https://example.org/rural-business-loans",
    sourceName: "Inclusive Finance Initiative",
    geography: ["Malawi"],
    sectors: ["Agriculture", "Manufacturing"],
    eligibilitySummary: "Registered SMEs operating in rural districts.",
    fundingType: "loan",
    amountMin: 5000,
    amountMax: 50000,
    deadlineAt: "2026-03-26T23:59:00Z",
    status: "closing_soon",
    scrapeConfidence: 0.61,
    approvalStatus: "pending",
    lastScrapedAt: "2026-03-13T05:10:00Z",
    createdAt: "2026-03-02T08:00:00Z",
    updatedAt: "2026-03-13T05:10:00Z"
  }
];

export const mockMatches: MatchResult[] = [
  {
    id: "match_001",
    userId: "user_001",
    programId: "prog_001",
    score: 91,
    reasons: [
      "Sector overlap on Climate and AgriTech",
      "Country eligibility includes Malawi",
      "Funding amount matches preferred range"
    ],
    blockers: [],
    status: "high_fit",
    updatedAt: "2026-03-13T06:00:00Z"
  },
  {
    id: "match_002",
    userId: "user_001",
    programId: "prog_002",
    score: 74,
    reasons: ["AgriTech sector match", "Funding type preference includes equity"],
    blockers: ["Founder age requirement not yet verified"],
    status: "manual_review",
    updatedAt: "2026-03-13T06:00:00Z"
  }
];

export const mockScrapeRuns: ScrapeRun[] = [
  {
    id: "run_1102",
    sourceName: "Africa Climate Fund",
    startedAt: "2026-03-13T05:00:00Z",
    completedAt: "2026-03-13T05:03:00Z",
    status: "success",
    seedUrls: ["https://africaclimatefund.org/funding"],
    urlsCrawled: 24,
    pagesFetchedSuccessfully: 24,
    pagesFailed: 0,
    recordsFound: 16,
    recordsStored: 14,
    recordsFlagged: 2,
    recordsWithMissingProgramName: 0,
    recordsWithMissingFunderName: 0,
    recordsWithUnknownFundingType: 1,
    recordsWithNoApplicationRoute: 2,
    lowConfidenceThreshold: 0.45,
    warnings: ["Two records were routed to review because the application URL was not explicit."],
    errors: []
  },
  {
    id: "run_1103",
    sourceName: "Inclusive Finance Initiative",
    startedAt: "2026-03-13T05:10:00Z",
    completedAt: "2026-03-13T05:16:00Z",
    status: "partial",
    seedUrls: [
      "https://inclusivefinance.africa/programmes",
      "https://inclusivefinance.africa/rural-sme-support"
    ],
    urlsCrawled: 19,
    pagesFetchedSuccessfully: 13,
    pagesFailed: 6,
    recordsFound: 8,
    recordsStored: 4,
    recordsFlagged: 4,
    recordsWithMissingProgramName: 1,
    recordsWithMissingFunderName: 0,
    recordsWithUnknownFundingType: 2,
    recordsWithNoApplicationRoute: 3,
    lowConfidenceThreshold: 0.45,
    warnings: [
      "Several detail pages returned incomplete deadline metadata.",
      "Four extracted records were flagged for low-confidence eligibility parsing."
    ],
    errors: [
      "Captcha encountered on listing detail pages",
      "Six programme detail pages timed out after retry."
    ],
    errorSummary: "Captcha encountered on listing detail pages"
  }
];

export const mockNotificationPreferences: NotificationPreference = {
  emailEnabled: true,
  whatsappEnabled: false,
  smsEnabled: false,
  digestFrequency: "daily"
};

export const mockNotificationEvents: NotificationEvent[] = [
  {
    id: "evt_1",
    userId: "user_001",
    channel: "email",
    type: "new_match",
    status: "sent",
    createdAt: "2026-03-13T06:10:00Z"
  },
  {
    id: "evt_2",
    userId: "user_001",
    channel: "email",
    type: "deadline_alert",
    status: "queued",
    createdAt: "2026-03-13T09:00:00Z"
  }
];

export const mockSystemChangeLog: SystemChangeLogEntry[] = [
  {
    id: "chg_2026_04_24_ai-rules-console",
    title: "Admin sidebar now includes an AI Rules console",
    summary: "The admin sidebar now exposes a dedicated AI Rules workspace for managing prompt bundles, schema mappings, and future database-backed rule editing.",
    createdAt: "2026-04-24T10:15:00Z",
    area: "admin",
    impact: "medium",
    highlights: [
      "Added a dedicated AI Rules entry to the admin sidebar",
      "The new workspace shows prompt bundles, schema mappings, and version history UI",
      "The layout is ready for future database-backed rule editing without changing the screen structure"
    ]
  },
  {
    id: "chg_2026_04_24_ai-merge-judge",
    title: "AI-assisted dedupe now keeps sibling programmes separate unless the page context clearly matches",
    summary: "The merge step now uses a stricter AI judge for ambiguous same-name records so sibling programmes like different Expansion Capital pages do not collapse into one programme by mistake.",
    createdAt: "2026-04-24T10:05:00Z",
    area: "scraper",
    impact: "high",
    highlights: [
      "Dedupe now only auto-merges exact source-page duplicates immediately",
      "Ambiguous same-name records can be sent to AI for a merge or separate decision",
      "The AI merge prompt now requires clear page URL or parent programme context before merging"
    ]
  },
  {
    id: "chg_2026_04_23_scraper-ai-first-refactor",
    title: "Scraper now extracts raw page content first and classifies programmes with AI",
    summary: "The scraper was refactored into a lightweight content extraction layer plus an AI classification step, with raw content, AI prompts, and AI outputs all persisted for review.",
    createdAt: "2026-04-23T21:30:00Z",
    area: "scraper",
    impact: "high",
    highlights: [
      "Generic page extraction now captures title, headings, cleaned body text, and optional structured sections without field-specific scraping",
      "Adapters now only discover valid programme URLs and filter irrelevant pages, leaving field mapping to the AI layer",
      "The pipeline now logs raw page content plus AI input and output artifacts before saving normalized programme records"
    ]
  },
  {
    id: "chg_2026_04_23_scraper-host-strict-ai-enrichment",
    title: "Scraper now keeps exact seed hosts and shows AI enrichment status in admin",
    summary: "Seed loading now preserves the exact host from Supabase, the crawler stops following sibling subdomains, and the admin review screens now show whether a record passed through AI enrichment.",
    createdAt: "2026-04-23T18:45:00Z",
    area: "scraper",
    impact: "high",
    highlights: [
      "run-seeds now preserves exact seed hosts instead of collapsing www and bare-domain variants",
      "Crawler link matching is now host-strict, so sibling subdomains like online.nefcorp.co.za are no longer queued",
      "Admin review and detail views now show a visible AI enriched badge for records that actually passed through the AI step"
    ]
  },
  {
    id: "chg_2026_04_08_supabase-upload-fix",
    title: "Supabase programme uploads now recover from duplicate-page scraper noise",
    summary: "The upload path now normalizes record identity, collapses duplicate page candidates, and returns clear database errors so scraper pushes are much more reliable.",
    createdAt: "2026-04-08T16:35:00Z",
    area: "data",
    impact: "high",
    highlights: [
      "Fixed a dedupe bug where programme IDs changed but UUID record IDs did not",
      "Push-to-Supabase now keeps the strongest candidate per duplicate source page before upload",
      "Upload failures now surface the real Postgres error body instead of a generic 409 conflict"
    ]
  },
  {
    id: "chg_2026_04_08_ingest-stability",
    title: "Scraper ingest is now more stable for noisy funding sites",
    summary: "The system now handles multi-record pages more safely, especially on NEF-style sites where headings and support content can create duplicate candidates from one page.",
    createdAt: "2026-04-08T16:10:00Z",
    area: "scraper",
    impact: "high",
    highlights: [
      "Upload sanitization reduced one noisy NEF payload from 48 records to 30 valid candidates",
      "Low-quality heading-only records are deprioritized during upload conflict cleanup",
      "Canonical funding pages like Women Empowerment Fund are preserved over junk sub-records"
    ]
  },
  {
    id: "chg_2026_04_08_site-profiles",
    title: "Scraper now supports reusable site profiles for extraction",
    summary: "Sites can now define parser-specific extraction behavior through a structured profile layer instead of relying only on crawl boundaries and generic heuristics.",
    createdAt: "2026-04-08T14:20:00Z",
    area: "scraper",
    impact: "high",
    highlights: [
      "Added site-profile support for content scoping and content exclusions",
      "Sites can now define candidate selectors and section heading selectors",
      "Section aliases let sites map custom labels like Who qualifies into the standard schema"
    ]
  },
  {
    id: "chg_2026_04_08_parent-persistence",
    title: "Parent programme names now persist from scraper output into the system",
    summary: "Parent-child programme relationships are now inferred, persisted, and surfaced consistently so admin reviewers can identify sub-programmes correctly.",
    createdAt: "2026-04-08T12:05:00Z",
    area: "data",
    impact: "high",
    highlights: [
      "Child NEF-style URLs now infer parent programme names during scraping",
      "Database persistence was fixed so parent names are no longer dropped on ingest",
      "Admin review queue can now show parent names for sub-programmes"
    ]
  },
  {
    id: "chg_2026_04_08_admin-change-log",
    title: "Admin dashboard now includes a dedicated system change log",
    summary: "Admins can browse a structured history of meaningful product, scraper, and data-layer changes directly from the workspace.",
    createdAt: "2026-04-08T10:40:00Z",
    area: "admin",
    impact: "medium",
    highlights: [
      "Added a dedicated admin change-log page",
      "Dashboard now previews recent system changes",
      "Navigation includes a direct Change Log entry"
    ]
  },
  {
    id: "chg_2026_04_08_parent-programmes",
    title: "Parent programme relationships now surface across admin review",
    summary: "Child funding products now retain their parent programme relationship so reviewers can understand nested product families at a glance.",
    createdAt: "2026-04-08T09:30:00Z",
    area: "admin",
    impact: "high",
    highlights: [
      "Review queue now supports parent-programme badges for child records",
      "Search can match child rows by parent programme name",
      "Scraper inference now fills parent names for NEF-style child URLs"
    ]
  },
  {
    id: "chg_2026_04_08_application-routing",
    title: "Application-link extraction prefers live portals over dead downloads",
    summary: "Application routing is stricter and now avoids treating PDFs and support downloads as canonical application URLs.",
    createdAt: "2026-04-08T08:45:00Z",
    area: "scraper",
    impact: "high",
    highlights: [
      "Document downloads no longer count as application links",
      "Portal and online apply URLs are ranked above weaker candidates",
      "NEF pages now prefer the live application portal over the dead PDF"
    ]
  },
  {
    id: "chg_2026_04_07_scraper-run-detail",
    title: "Scraper runs now have a dedicated detail view",
    summary: "Admins can open an individual scrape run to inspect coverage, timing, warnings, errors, and quality telemetry without leaving the workspace.",
    createdAt: "2026-04-07T16:50:00Z",
    area: "admin",
    impact: "medium",
    highlights: [
      "Scraper runs page now links into a full detail route",
      "Run detail view shows timing, seeds, diagnostics, and QA counts",
      "The list page was simplified to stay table-first"
    ]
  },
  {
    id: "chg_2026_04_07_schema-expansion",
    title: "Funding programme schema expanded for richer provenance and QA",
    summary: "Programme records now support richer raw source fields, explainability metadata, validation state, and operational tracking fields.",
    createdAt: "2026-04-07T13:10:00Z",
    area: "data",
    impact: "high",
    highlights: [
      "Expanded programme schema now covers slugs, review flags, evidence, and validation errors",
      "Final published table was updated to keep parity with source records",
      "Scraper output was aligned to emit the new fields directly"
    ]
  },
  {
    id: "chg_2026_04_07_deadline-fix",
    title: "Deadline parsing now ignores percentage-based false positives",
    summary: "The parser no longer mistakes eligibility percentages like 51% for future fixed dates.",
    createdAt: "2026-04-07T11:40:00Z",
    area: "scraper",
    impact: "medium",
    highlights: [
      "Fixed-date extraction now requires real date-shaped text",
      "False positives like 7 April 2051 from 51% ownership wording were eliminated",
      "Regression coverage was added for eligibility-percentage cases"
    ]
  }
];
