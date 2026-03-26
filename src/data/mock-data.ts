import type {
  ApplicantProfile,
  FundingProgram,
  MatchResult,
  NotificationEvent,
  NotificationPreference,
  ScrapeRun
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
    recordsFound: 16,
    recordsStored: 14,
    recordsFlagged: 2
  },
  {
    id: "run_1103",
    sourceName: "Inclusive Finance Initiative",
    startedAt: "2026-03-13T05:10:00Z",
    completedAt: "2026-03-13T05:16:00Z",
    status: "partial",
    recordsFound: 8,
    recordsStored: 4,
    recordsFlagged: 4,
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
