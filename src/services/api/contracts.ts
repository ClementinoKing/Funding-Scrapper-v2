import type {
  ApplicantProfile,
  MatchResult,
  NotificationEvent,
  NotificationPreference,
  ScrapeRun,
  SystemChangeLogEntry,
  WebsiteSite
} from "@/types/domain";
import type { ScrapedFundingProgramme } from "@/types/funding";

export interface ApiClient {
  getCurrentUserProfile: () => Promise<ApplicantProfile>;
  getPrograms: () => Promise<ScrapedFundingProgramme[]>;
  getProgramById: (programId: string) => Promise<ScrapedFundingProgramme | undefined>;
  updateProgrammeRecord: (programId: string, patch: Record<string, unknown>) => Promise<void>;
  getSites: () => Promise<WebsiteSite[]>;
  getSiteByKey: (siteKey: string) => Promise<WebsiteSite | undefined>;
  createSite: (site: Omit<WebsiteSite, "createdAt" | "updatedAt">) => Promise<WebsiteSite>;
  updateSite: (site: WebsiteSite) => Promise<WebsiteSite>;
  deleteSite: (siteKey: string) => Promise<void>;
  getMatchesByUser: (userId: string) => Promise<MatchResult[]>;
  getScrapeRuns: () => Promise<ScrapeRun[]>;
  getScrapeRunById: (runId: string) => Promise<ScrapeRun | undefined>;
  getSystemChangeLog: () => Promise<SystemChangeLogEntry[]>;
  getNotificationPreferences: (userId: string) => Promise<NotificationPreference>;
  getNotificationEvents: (userId: string) => Promise<NotificationEvent[]>;
}
