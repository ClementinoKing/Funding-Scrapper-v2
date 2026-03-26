import type {
  ApplicantProfile,
  MatchResult,
  NotificationEvent,
  NotificationPreference,
  ScrapeRun
} from "@/types/domain";
import type { ScrapedFundingProgramme } from "@/types/funding";

export interface ApiClient {
  getCurrentUserProfile: () => Promise<ApplicantProfile>;
  getPrograms: () => Promise<ScrapedFundingProgramme[]>;
  getProgramById: (programId: string) => Promise<ScrapedFundingProgramme | undefined>;
  getMatchesByUser: (userId: string) => Promise<MatchResult[]>;
  getScrapeRuns: () => Promise<ScrapeRun[]>;
  getNotificationPreferences: (userId: string) => Promise<NotificationPreference>;
  getNotificationEvents: (userId: string) => Promise<NotificationEvent[]>;
}
