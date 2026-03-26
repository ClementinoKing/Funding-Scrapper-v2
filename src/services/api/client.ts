import {
  mockMatches,
  mockNotificationEvents,
  mockNotificationPreferences,
  mockProfile,
  mockScrapeRuns
} from "@/data/mock-data";
import type { ApiClient } from "@/services/api/contracts";
import type { FundingProgram } from "@/types/domain";
import type { ScrapedFundingProgramme } from "@/types/funding";

import fundingProgrammes from "../../../scraper/output/normalized/funding_programmes.json";

type NormalizedProgrammeFields = {
  funder_name?: string | null;
  site_adapter?: string | null;
  page_type?: string | null;
  source_url?: string;
  source_urls?: string[];
  source_domain?: string | null;
  source_page_title?: string | null;
  scraped_at?: string;
  raw_eligibility_data?: string | string[] | null;
  funding_type?: string;
  funding_lines?: string[];
  ticket_min?: number | string | null;
  ticket_max?: number | string | null;
  currency?: string | null;
  program_budget_total?: number | string | null;
  deadline_type?: string;
  deadline_date?: string | null;
  funding_speed_days_min?: number | null;
  funding_speed_days_max?: number | null;
  geography_scope?: string | null;
  provinces?: string[];
  municipalities?: string[];
  postal_code_ranges?: string[];
  industries?: string[];
  use_of_funds?: string[];
  business_stage_eligibility?: string[];
  turnover_min?: number | string | null;
  turnover_max?: number | string | null;
  years_in_business_min?: number | string | null;
  years_in_business_max?: number | string | null;
  employee_min?: number | null;
  employee_max?: number | null;
  ownership_targets?: string[];
  entity_types_allowed?: string[];
  certifications_required?: string[];
  security_required?: string;
  equity_required?: string;
  payback_months_min?: number | null;
  payback_months_max?: number | null;
  interest_type?: string;
  repayment_frequency?: string;
  exclusions?: string[];
  required_documents?: string[];
  application_channel?: string;
  application_url?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  raw_text_snippets?: Record<string, unknown>;
  extraction_confidence?: Record<string, number>;
  related_documents?: string[];
  notes?: string[];
};

export type FundingProgrammeRecord = NormalizedProgrammeFields & {
  program_id?: string;
  program_name?: string | null;
};

export type ProgrammeRecord = FundingProgrammeRecord;

export type ProgrammeRecordBundle = {
  record?: ProgrammeRecord;
};

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL?.trim();
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();

const supabaseHeaders =
  SUPABASE_URL && SUPABASE_ANON_KEY
    ? {
        apikey: SUPABASE_ANON_KEY,
        Authorization: `Bearer ${SUPABASE_ANON_KEY}`
      }
    : undefined;

const isSupabaseUnavailable = !SUPABASE_URL || !SUPABASE_ANON_KEY;

const toNumber = (value: number | string | null | undefined): number | undefined => {
  if (value === null || value === undefined || value === "") {
    return undefined;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const asArray = (value?: string[] | null): string[] => (value ?? []).filter(Boolean);

const getEligibilitySummary = (record: ProgrammeRecord): string => {
  if (Array.isArray(record.raw_eligibility_data)) {
    return record.raw_eligibility_data.filter(Boolean).join(" ");
  }
  if (typeof record.raw_eligibility_data === "string" && record.raw_eligibility_data.trim()) {
    return record.raw_eligibility_data.trim();
  }
  if (record.use_of_funds?.length) {
    return record.use_of_funds.join(", ");
  }
  if (record.notes?.length) {
    return record.notes.join(" ");
  }
  return "Eligibility details not captured yet.";
};

const getStatus = (record: ProgrammeRecord): FundingProgram["status"] => {
  if (!record.deadline_date) {
    return record.deadline_type === "Open" || record.deadline_type === "Rolling" ? "active" : "draft";
  }

  const deadline = new Date(record.deadline_date);
  if (Number.isNaN(deadline.getTime())) {
    return "draft";
  }

  const daysRemaining = (deadline.getTime() - Date.now()) / (1000 * 60 * 60 * 24);
  if (daysRemaining < 0) {
    return "closed";
  }
  if (daysRemaining <= 14) {
    return "closing_soon";
  }
  return "active";
};

const getRecordTitle = (record: ProgrammeRecord): string => {
  return (record as FundingProgrammeRecord).program_name?.trim() || "Untitled programme";
};

const getRecordIdValue = (record: ProgrammeRecord): string => {
  return (record as FundingProgrammeRecord).program_id || "";
};

export const makeProgrammeClientId = (record: ProgrammeRecord): string => {
  const rawId = getRecordIdValue(record) || `${record.funder_name || "provider"}-${getRecordTitle(record)}`.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `main:${rawId}`;
};

export const parseProgrammeClientId = (programId: string): { kind: "main"; rawId: string } => {
  if (programId.startsWith("main:")) {
    return { kind: "main", rawId: programId.slice(5) };
  }
  return { kind: "main", rawId: programId.replace(/^sub:/, "") };
};

const mapRecordToProgram = (record: ProgrammeRecord): ScrapedFundingProgramme => {
  const title = getRecordTitle(record);
  const providerName = record.funder_name?.trim() || record.source_domain || "Unknown provider";
  const geography = [
    ...asArray(record.provinces),
    ...asArray(record.municipalities),
    ...(record.geography_scope ? [record.geography_scope] : [])
  ].filter((value, index, values) => Boolean(value) && values.indexOf(value) === index);
  const fundingType = (record.funding_type || "Unknown").toLowerCase() as FundingProgram["fundingType"];
  const scrapeConfidence = record.extraction_confidence
    ? Object.values(record.extraction_confidence).reduce((sum, value) => sum + value, 0) /
      Math.max(Object.values(record.extraction_confidence).length, 1)
      : 0.5;

  return {
    id: makeProgrammeClientId(record),
    title,
    providerName,
    sourceUrl: record.source_url || "#",
    sourceName: record.source_page_title?.trim() || providerName,
    geography: geography.length ? geography : ["Unknown"],
    sectors: record.industries ?? [],
    eligibilitySummary: getEligibilitySummary(record),
    fundingType: [
      "grant",
      "equity",
      "loan",
      "fellowship",
      "guarantee",
      "hybrid",
      "other",
      "unknown"
    ].includes(fundingType)
      ? fundingType
      : "unknown",
    amountMin: toNumber(record.ticket_min),
    amountMax: toNumber(record.ticket_max),
    deadlineAt: record.deadline_date ? new Date(record.deadline_date).toISOString() : undefined,
    status: getStatus(record),
    scrapeConfidence,
    approvalStatus: "pending",
    lastScrapedAt: record.scraped_at || new Date().toISOString(),
    createdAt: record.scraped_at || new Date().toISOString(),
    updatedAt: record.scraped_at || new Date().toISOString(),
    program_name: "program_name" in record ? record.program_name : undefined,
    funder_name: record.funder_name,
    site_adapter: record.site_adapter,
    page_type: record.page_type,
    source_url: record.source_url,
    source_urls: record.source_urls,
    source_domain: record.source_domain,
    source_page_title: record.source_page_title,
    scraped_at: record.scraped_at,
    raw_eligibility_data: record.raw_eligibility_data,
    funding_type: record.funding_type,
    funding_lines: record.funding_lines,
    ticket_min: record.ticket_min,
    ticket_max: record.ticket_max,
    deadline_type: record.deadline_type,
    deadline_date: record.deadline_date,
    geography_scope: record.geography_scope,
    provinces: record.provinces,
    municipalities: record.municipalities,
    postal_code_ranges: record.postal_code_ranges,
    industries: record.industries,
    use_of_funds: record.use_of_funds,
    business_stage_eligibility: record.business_stage_eligibility,
    ownership_targets: record.ownership_targets,
    entity_types_allowed: record.entity_types_allowed,
    certifications_required: record.certifications_required,
    application_channel: record.application_channel,
    application_url: record.application_url,
    contact_email: record.contact_email,
    contact_phone: record.contact_phone,
    related_documents: record.related_documents,
    notes: record.notes
  };
};

const readLocalProgrammeRecords = (): FundingProgrammeRecord[] => fundingProgrammes as unknown as FundingProgrammeRecord[];

const fetchSupabaseRows = async <T>(table: string, query: string): Promise<T[]> => {
  if (isSupabaseUnavailable || !SUPABASE_URL || !supabaseHeaders) {
    throw new Error("Supabase environment variables are not configured.");
  }

  const response = await fetch(`${SUPABASE_URL}/rest/v1/${table}?${query}`, {
    headers: supabaseHeaders
  });

  if (!response.ok) {
    throw new Error(`Failed to load ${table} from Supabase (${response.status})`);
  }

  return (await response.json()) as T[];
};

const fetchSupabaseOptionalRows = async <T>(table: string, query: string): Promise<T[]> => {
  try {
    return await fetchSupabaseRows<T>(table, query);
  } catch (error) {
    if (error instanceof Error && error.message.includes("(404)")) {
      return [];
    }
    throw error;
  }
};

const readLocalPrograms = async (): Promise<ScrapedFundingProgramme[]> => readLocalProgrammeRecords().map(mapRecordToProgram);

export const fetchProgramsFromDatabase = async (): Promise<ScrapedFundingProgramme[]> => {
  const mainRecords = await fetchSupabaseRows<FundingProgrammeRecord>("funding_programmes", "select=*");
  return mainRecords.map(mapRecordToProgram);
};

export const fetchProgrammeRecordBundle = async (programId: string): Promise<ProgrammeRecordBundle> => {
  const { rawId } = parseProgrammeClientId(programId);

  if (!isSupabaseUnavailable) {
    const [record] = await fetchSupabaseOptionalRows<FundingProgrammeRecord>(
      "funding_programmes",
      `program_id=eq.${encodeURIComponent(rawId)}&select=*`
    );
    if (record) {
      return { record };
    }
  }

  const record = readLocalProgrammeRecords().find((candidate) => candidate.program_id === rawId);
  return { record };
};

const withLatency = async <T>(value: T): Promise<T> => {
  await new Promise((resolve) => setTimeout(resolve, 200));
  return value;
};

export const apiClient: ApiClient = {
  getCurrentUserProfile: () => withLatency(mockProfile),
  getPrograms: async () => {
    try {
      const remotePrograms = await fetchProgramsFromDatabase();
      if (remotePrograms.length > 0) {
        return withLatency(remotePrograms);
      }
    } catch {
      // Fall back to local scraper output for applicant-facing pages.
    }

    return withLatency(await readLocalPrograms());
  },
  getProgramById: async (programId) => {
    const records = await apiClient.getPrograms();
    return records.find((program) => program.id === programId);
  },
  getMatchesByUser: async (userId) => {
    const matches = await withLatency(mockMatches);
    return matches.filter((match) => match.userId === userId);
  },
  getScrapeRuns: () => withLatency(mockScrapeRuns),
  getNotificationPreferences: () => withLatency(mockNotificationPreferences),
  getNotificationEvents: async (userId) => {
    const events = await withLatency(mockNotificationEvents);
    return events.filter((event) => event.userId === userId);
  }
};
