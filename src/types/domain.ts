export type Role = "applicant" | "admin";

export interface ApplicantProfile {
  userId: string;
  fullName: string;
  email: string;
  phone?: string;
  country: string;
  region?: string;
  organizationType: "individual" | "startup" | "ngo" | "sme" | "academic";
  sectors: string[];
  stage: "idea" | "early" | "growth" | "established";
  annualRevenueBand?: string;
  teamSizeBand?: string;
  yearsOperating?: number;
  fundingNeeds: string[];
  preferredFundingTypes: Array<"grant" | "equity" | "loan" | "fellowship" | "guarantee" | "hybrid" | "other" | "unknown">;
  targetAmountMin?: number;
  targetAmountMax?: number;
  profileCompleteness: number;
  updatedAt: string;
}

export interface FundingProgram {
  id: string;
  title: string;
  providerName: string;
  sourceUrl: string;
  sourceName: string;
  geography: string[];
  sectors: string[];
  eligibilitySummary: string;
  fundingType: "grant" | "equity" | "loan" | "fellowship" | "guarantee" | "hybrid" | "other" | "unknown";
  amountMin?: number;
  amountMax?: number;
  deadlineAt?: string;
  status: "active" | "closing_soon" | "closed" | "draft";
  scrapeConfidence: number;
  approvalStatus: "pending" | "approved" | "rejected";
  lastScrapedAt: string;
  createdAt: string;
  updatedAt: string;
}

export interface MatchResult {
  id: string;
  userId: string;
  programId: string;
  score: number;
  reasons: string[];
  blockers: string[];
  status: "high_fit" | "medium_fit" | "low_fit" | "manual_review";
  updatedAt: string;
}

export interface ScrapeRun {
  id: string;
  sourceName: string;
  startedAt: string;
  completedAt?: string;
  status: "running" | "success" | "partial" | "failed";
  seedUrls: string[];
  urlsCrawled: number;
  pagesFetchedSuccessfully: number;
  pagesFailed: number;
  recordsFound: number;
  recordsStored: number;
  recordsFlagged: number;
  recordsWithMissingProgramName: number;
  recordsWithMissingFunderName: number;
  recordsWithUnknownFundingType: number;
  recordsWithNoApplicationRoute: number;
  lowConfidenceThreshold?: number;
  warnings: string[];
  errors: string[];
  errorSummary?: string;
}

export interface WebsiteSite {
  siteKey: string;
  displayName: string;
  primaryDomain: string;
  adapterKey: string;
  seedUrls: string[];
  adapterConfig: Record<string, unknown>;
  active: boolean;
  notes: string[];
  createdAt?: string;
  updatedAt?: string;
}

export interface SystemChangeLogEntry {
  id: string;
  title: string;
  summary: string;
  createdAt: string;
  area: "scraper" | "admin" | "data" | "matching" | "platform";
  impact: "high" | "medium" | "low";
  highlights: string[];
}

export interface NotificationPreference {
  emailEnabled: boolean;
  whatsappEnabled: boolean;
  smsEnabled: boolean;
  digestFrequency: "instant" | "daily" | "weekly";
}

export interface NotificationEvent {
  id: string;
  userId: string;
  channel: "email" | "whatsapp" | "sms";
  type: "new_match" | "deadline_alert" | "admin_note";
  status: "queued" | "sent" | "failed";
  createdAt: string;
}
