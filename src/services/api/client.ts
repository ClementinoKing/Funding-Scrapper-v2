import {
  mockMatches,
  mockNotificationEvents,
  mockNotificationPreferences,
  mockProfile,
  mockPrograms,
  mockScrapeRuns,
  mockSystemChangeLog
} from "@/data/mock-data";
import type { ApiClient } from "@/services/api/contracts";
import { useAuthStore } from "@/store/auth-store";
import { refreshSupabaseSession } from "@/services/auth/supabase-auth";
import type { FundingProgram, ScrapeRun, SystemChangeLogEntry, WebsiteSite } from "@/types/domain";
import type { ScrapedFundingProgramme } from "@/types/funding";

type NormalizedProgrammeFields = {
  id?: string;
  funder_name?: string | null;
  funder_slug?: string | null;
  program_slug?: string | null;
  parent_programme_name?: string | null;
  country_code?: string | null;
  status?: string | null;
  site_adapter?: string | null;
  page_type?: string | null;
  source_url?: string;
  source_urls?: string[];
  source_domain?: string | null;
  source_page_title?: string | null;
  scraped_at?: string;
  last_scraped_at?: string;
  last_verified_at?: string | null;
  raw_eligibility_data?: string | string[] | null;
  raw_funding_offer_data?: string[] | Record<string, unknown> | null;
  raw_terms_data?: string[] | Record<string, unknown> | null;
  raw_documents_data?: string[] | Record<string, unknown> | null;
  raw_application_data?: string[] | Record<string, unknown> | null;
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
  evidence_by_field?: Record<string, unknown>;
  extraction_confidence?: Record<string, number>;
  field_confidence?: Record<string, number>;
  related_documents?: string[];
  parser_version?: string | null;
  needs_review?: boolean | null;
  validation_errors?: string[] | Record<string, unknown> | null;
  deleted_at?: string | null;
  notes?: string[];
};

export type FundingProgrammeRecord = NormalizedProgrammeFields & {
  program_id?: string;
  program_name?: string | null;
  approval_status?: FundingProgram["approvalStatus"] | null;
};

export type ProgrammeRecord = FundingProgrammeRecord;

export type ProgrammeRecordBundle = {
  record?: ProgrammeRecord;
};

const localProgrammeModules = import.meta.glob<FundingProgrammeRecord[]>(
  "../../../scraper/output/normalized/funding_programmes.json",
  {
    eager: true,
    import: "default"
  }
);

type SourceProgrammeRow = FundingProgrammeRecord;

type PublishedProgrammeRow = FundingProgrammeRecord & {
  source_program_id?: string | null;
  published_at?: string | null;
};

type SiteRow = {
  site_key?: string | null;
  display_name?: string | null;
  primary_domain?: string | null;
  adapter_key?: string | null;
  seed_urls?: Array<string | { url?: string | null } | null> | null;
  adapter_config?: Record<string, unknown> | string | null;
  active?: boolean | null;
  notes?: Array<string | null> | string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type ScrapeRunRow = {
  run_id?: string | null;
  source_name?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  status?: string | null;
  seed_urls?: Array<string | { url?: string | null } | null> | null;
  total_urls_crawled?: number | null;
  pages_fetched_successfully?: number | null;
  pages_failed?: number | null;
  programmes_extracted?: number | null;
  programmes_after_dedupe?: number | null;
  records_with_missing_program_name?: number | null;
  records_with_missing_funder_name?: number | null;
  records_with_unknown_funding_type?: number | null;
  records_with_no_application_route?: number | null;
  records_with_low_confidence_extraction?: number | null;
  low_confidence_threshold?: number | null;
  errors?: Array<string | null> | string | null;
  warnings?: Array<string | null> | string | null;
};

const SCRAPE_RUN_SELECT_FIELDS =
  "run_id,source_name,started_at,completed_at,status,seed_urls,total_urls_crawled,pages_fetched_successfully,pages_failed,programmes_extracted,programmes_after_dedupe,records_with_missing_program_name,records_with_missing_funder_name,records_with_unknown_funding_type,records_with_no_application_route,records_with_low_confidence_extraction,low_confidence_threshold,errors,warnings";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL?.trim();
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();
const LOCAL_SITE_REGISTRY_KEY = "fundmatch.sites";
const LOCAL_DEV_ACCESS_TOKEN = "local-dev-token";

const supabaseHeaders =
  SUPABASE_URL && SUPABASE_ANON_KEY
    ? {
        apikey: SUPABASE_ANON_KEY,
        Authorization: `Bearer ${SUPABASE_ANON_KEY}`
      }
    : undefined;

const isSupabaseUnavailable = !SUPABASE_URL || !SUPABASE_ANON_KEY;
const isLocalDevSession = (): boolean => useAuthStore.getState().accessToken === LOCAL_DEV_ACCESS_TOKEN;

const toNumber = (value: number | string | null | undefined): number | undefined => {
  if (value === null || value === undefined || value === "") {
    return undefined;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const asArray = (value?: string[] | null): string[] => (value ?? []).filter(Boolean);

const parseSeedUrls = (value?: Array<string | { url?: string | null } | null> | null): string[] => {
  if (!value) return [];
  return value
    .map((item) => {
      if (!item) return "";
      if (typeof item === "string") return item.trim();
      return (item.url ?? "").trim();
    })
    .filter(Boolean);
};

const parseNotes = (value?: Array<string | null> | string | null): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value.map((item) => (item ?? "").trim()).filter(Boolean);
  }
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
};

const parseTextArray = (value?: Array<string | null> | string | null): string[] => {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value.map((item) => (item ?? "").trim()).filter(Boolean);
  }
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
};

const parseAdapterConfig = (value?: Record<string, unknown> | string | null): Record<string, unknown> => {
  if (!value) {
    return {};
  }
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value) as unknown;
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  }
  return value;
};

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
    approvalStatus: (record.approval_status ?? "pending") as FundingProgram["approvalStatus"],
    lastScrapedAt: record.scraped_at || new Date().toISOString(),
    createdAt: record.scraped_at || new Date().toISOString(),
    updatedAt: record.scraped_at || new Date().toISOString(),
    program_name: "program_name" in record ? record.program_name : undefined,
    funder_name: record.funder_name,
    parent_programme_name: record.parent_programme_name,
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

const readLocalProgrammeRecords = (): FundingProgrammeRecord[] =>
  (Object.values(localProgrammeModules)[0] ?? []) as FundingProgrammeRecord[];

const readLocalPublishedProgrammeRecords = (): FundingProgrammeRecord[] =>
  mockPrograms.map((program) => ({
    program_id: program.id.replace(/^main:/, ""),
    program_name: program.title,
    funder_name: program.providerName,
    source_url: program.sourceUrl,
    source_urls: [program.sourceUrl],
    source_domain: new URL(program.sourceUrl).hostname,
    source_page_title: program.sourceName,
    scraped_at: program.lastScrapedAt,
    raw_eligibility_data: program.eligibilitySummary,
    funding_type: program.fundingType,
    funding_lines: [],
    ticket_min: program.amountMin ?? null,
    ticket_max: program.amountMax ?? null,
    geography_scope: "Unknown",
    provinces: program.geography,
    municipalities: [],
    postal_code_ranges: [],
    industries: program.sectors,
    use_of_funds: [],
    business_stage_eligibility: [],
    ownership_targets: [],
    entity_types_allowed: [],
    certifications_required: [],
    security_required: "Unknown",
    equity_required: "Unknown",
    payback_months_min: null,
    payback_months_max: null,
    interest_type: "Unknown",
    repayment_frequency: "Unknown",
    exclusions: [],
    required_documents: [],
    application_channel: "Unknown",
    application_url: program.sourceUrl,
    contact_email: null,
    contact_phone: null,
    raw_text_snippets: {},
    extraction_confidence: { overall: program.scrapeConfidence },
    related_documents: [],
    notes: [],
    approval_status: "approved"
  }));

const readLocalSites = (): WebsiteSite[] => [];

const loadLocalSiteStore = (): WebsiteSite[] => {
  if (typeof window === "undefined") {
    return readLocalSites();
  }

  try {
    const raw = window.localStorage.getItem(LOCAL_SITE_REGISTRY_KEY);
    if (!raw) {
      return readLocalSites();
    }
    const parsed = JSON.parse(raw) as WebsiteSite[];
    if (!Array.isArray(parsed)) {
      return readLocalSites();
    }
    return parsed
      .filter((site) => site && typeof site === "object")
      .map((site) => ({
        ...site,
        seedUrls: Array.isArray(site.seedUrls) ? site.seedUrls.filter(Boolean) : [],
        adapterConfig: site.adapterConfig && typeof site.adapterConfig === "object" ? site.adapterConfig : {},
        notes: Array.isArray(site.notes) ? site.notes.filter(Boolean) : []
      }));
  } catch {
    return readLocalSites();
  }
};

const persistLocalSiteStore = (sites: WebsiteSite[]): void => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(LOCAL_SITE_REGISTRY_KEY, JSON.stringify(sites));
};

const readLocalSiteStore = (): WebsiteSite[] => loadLocalSiteStore();

const upsertLocalSite = (site: Omit<WebsiteSite, "createdAt" | "updatedAt">): WebsiteSite => {
  const currentSites = readLocalSiteStore();
  const existingIndex = currentSites.findIndex((candidate) => candidate.siteKey === site.siteKey);
  const timestamp = new Date().toISOString();
  const nextSite: WebsiteSite = {
    ...site,
    createdAt: existingIndex >= 0 ? currentSites[existingIndex].createdAt : timestamp,
    updatedAt: timestamp
  };

  const nextSites =
    existingIndex >= 0
      ? currentSites.map((candidate, index) => (index === existingIndex ? nextSite : candidate))
      : [...currentSites, nextSite];

  persistLocalSiteStore(nextSites);
  return nextSite;
};

const deleteLocalSite = (siteKey: string): void => {
  const nextSites = readLocalSiteStore().filter((site) => site.siteKey !== siteKey);
  persistLocalSiteStore(nextSites);
};

const refreshSiteSession = async (): Promise<boolean> => {
  const { refreshToken } = useAuthStore.getState();
  if (!refreshToken) {
    return false;
  }

  try {
    const session = await refreshSupabaseSession(refreshToken);
    useAuthStore.getState().setSession({
      user: {
        id: session.user.id,
        name: session.user.fullName,
        email: session.user.email,
        role: session.user.role
      },
      accessToken: session.accessToken,
      refreshToken: session.refreshToken
    });
    return true;
  } catch {
    return false;
  }
};

const siteConflictMessage = "Site key, display name, primary domain, or adapter key already exists.";

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

const mapSiteRowToSite = (row: SiteRow): WebsiteSite => ({
  siteKey: row.site_key?.trim() || row.primary_domain?.trim() || row.display_name?.trim() || "unknown-site",
  displayName: row.display_name?.trim() || row.site_key?.trim() || row.primary_domain?.trim() || "Unknown site",
  primaryDomain: row.primary_domain?.trim() || row.site_key?.trim() || "unknown",
  adapterKey: row.adapter_key?.trim() || row.site_key?.trim() || row.primary_domain?.trim() || "generic",
  seedUrls: parseSeedUrls(row.seed_urls),
  adapterConfig: parseAdapterConfig(row.adapter_config),
  active: row.active ?? true,
  notes: parseNotes(row.notes),
  createdAt: row.created_at ?? undefined,
  updatedAt: row.updated_at ?? undefined
});

export const fetchProgramsFromDatabase = async (): Promise<ScrapedFundingProgramme[]> => {
  if (isSupabaseUnavailable || isLocalDevSession()) {
    return readLocalPrograms();
  }

  const mainRecords = await fetchSupabaseRows<SourceProgrammeRow>("funding_programmes", "select=*");
  return mainRecords.map(mapRecordToProgram);
};

export const fetchPublishedProgramsFromDatabase = async (): Promise<ScrapedFundingProgramme[]> => {
  if (isSupabaseUnavailable || isLocalDevSession()) {
    return readLocalPublishedProgrammeRecords().map(mapRecordToProgram);
  }

  const publishedRecords = await fetchSupabaseRows<PublishedProgrammeRow>("final_funding_programmes", "select=*");
  return publishedRecords.map(mapRecordToProgram);
};

const mapScrapeRunRowToRun = (row: ScrapeRunRow): ScrapeRun => ({
  id: row.run_id?.trim() || "unknown-run",
  sourceName: row.source_name?.trim() || row.run_id?.trim() || "Unknown source",
  startedAt: row.started_at ?? new Date().toISOString(),
  completedAt: row.completed_at ?? undefined,
  status: (row.status?.trim() || "running") as "running" | "success" | "partial" | "failed",
  seedUrls: parseSeedUrls(row.seed_urls),
  urlsCrawled: row.total_urls_crawled ?? 0,
  pagesFetchedSuccessfully: row.pages_fetched_successfully ?? 0,
  pagesFailed: row.pages_failed ?? 0,
  recordsFound: row.programmes_extracted ?? row.total_urls_crawled ?? 0,
  recordsStored: row.programmes_after_dedupe ?? 0,
  recordsFlagged: row.records_with_low_confidence_extraction ?? 0,
  recordsWithMissingProgramName: row.records_with_missing_program_name ?? 0,
  recordsWithMissingFunderName: row.records_with_missing_funder_name ?? 0,
  recordsWithUnknownFundingType: row.records_with_unknown_funding_type ?? 0,
  recordsWithNoApplicationRoute: row.records_with_no_application_route ?? 0,
  lowConfidenceThreshold: row.low_confidence_threshold ?? undefined,
  warnings: parseTextArray(row.warnings),
  errors: parseTextArray(row.errors),
  errorSummary: [...parseTextArray(row.errors), ...parseTextArray(row.warnings)].slice(0, 2).join(" • ") || undefined
});

export const fetchScrapeRunsFromDatabase = async () => {
  if (isSupabaseUnavailable) {
    return mockScrapeRuns;
  }

  try {
    const rows = await fetchSupabaseRows<ScrapeRunRow>(
      "scrape_runs",
      `select=${SCRAPE_RUN_SELECT_FIELDS}&order=completed_at.desc.nullslast&limit=25`
    );
    if (rows.length > 0) {
      return rows.map(mapScrapeRunRowToRun);
    }
  } catch {
    // Fall back to mock scrape runs for local development or if the table is unavailable.
  }

  return mockScrapeRuns;
};

export const fetchScrapeRunByIdFromDatabase = async (
  runId: string
): Promise<ScrapeRun | undefined> => {
  if (isSupabaseUnavailable) {
    return mockScrapeRuns.find((run) => run.id === runId);
  }

  try {
    const rows = await fetchSupabaseRows<ScrapeRunRow>(
      "scrape_runs",
      `run_id=eq.${encodeURIComponent(runId)}&select=${SCRAPE_RUN_SELECT_FIELDS}&limit=1`
    );

    if (rows[0]) {
      return mapScrapeRunRowToRun(rows[0]);
    }
  } catch {
    // Fall back to list data if the detail query fails or the table is unavailable.
  }

  return mockScrapeRuns.find((run) => run.id === runId);
};

export const fetchSitesFromDatabase = async (): Promise<WebsiteSite[]> => {
  if (isSupabaseUnavailable || isLocalDevSession()) {
    return readLocalSiteStore();
  }

  try {
    const rows = await fetchSupabaseRows<SiteRow>("sites", "select=site_key,display_name,primary_domain,adapter_key,seed_urls,adapter_config,active,notes,created_at,updated_at&order=display_name.asc");
    if (rows.length > 0) {
      return rows.map(mapSiteRowToSite);
    }
  } catch {
    // Fall back to local site definitions when Supabase is unavailable or empty.
  }

  return readLocalSiteStore();
};

export const fetchSiteByKeyFromDatabase = async (siteKey: string): Promise<WebsiteSite | undefined> => {
  if (isSupabaseUnavailable || isLocalDevSession()) {
    return readLocalSiteStore().find((site) => site.siteKey === siteKey);
  }

  try {
    const rows = await fetchSupabaseRows<SiteRow>(
      "sites",
      `site_key=eq.${encodeURIComponent(siteKey)}&select=site_key,display_name,primary_domain,adapter_key,seed_urls,adapter_config,active,notes,created_at,updated_at`
    );
    return rows[0] ? mapSiteRowToSite(rows[0]) : undefined;
  } catch {
    return readLocalSiteStore().find((site) => site.siteKey === siteKey);
  }
};

export const createSiteInDatabase = async (
  site: Omit<WebsiteSite, "createdAt" | "updatedAt">
): Promise<WebsiteSite> => {
  if (isSupabaseUnavailable || isLocalDevSession()) {
    return upsertLocalSite(site);
  }

  if (!SUPABASE_URL) {
    throw new Error("Supabase environment variables are not configured.");
  }

  const accessToken = useAuthStore.getState().accessToken;
  if (!accessToken) {
    throw new Error("Sign in as an admin to add websites.");
  }

  const payload = {
    site_key: site.siteKey,
    display_name: site.displayName,
    primary_domain: site.primaryDomain,
    adapter_key: site.adapterKey,
    seed_urls: site.seedUrls,
    adapter_config: site.adapterConfig,
    active: site.active,
    notes: site.notes
  };
  const doCreate = async () =>
    fetch(`${SUPABASE_URL}/rest/v1/sites`, {
      method: "POST",
      headers: {
        apikey: SUPABASE_ANON_KEY ?? "",
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
        Prefer: "return=representation"
      },
      body: JSON.stringify(payload)
    });

  let response = await doCreate();
  if (!response.ok && response.status === 401 && (await refreshSiteSession())) {
    const refreshedAccessToken = useAuthStore.getState().accessToken;
    response = await fetch(`${SUPABASE_URL}/rest/v1/sites`, {
      method: "POST",
      headers: {
        apikey: SUPABASE_ANON_KEY ?? "",
        Authorization: `Bearer ${refreshedAccessToken ?? ""}`,
        "Content-Type": "application/json",
        Prefer: "return=representation"
      },
      body: JSON.stringify(payload)
    });
  }

  if (!response.ok) {
    if (response.status === 409) {
      throw new Error(siteConflictMessage);
    }
    throw new Error(`Failed to create record in sites (${response.status})`);
  }

  const [row] = (await response.json()) as SiteRow[];
  if (!row) {
    throw new Error("Supabase did not return the created site.");
  }
  return mapSiteRowToSite(row);
};

export const updateSiteInDatabase = async (site: WebsiteSite): Promise<WebsiteSite> => {
  if (isSupabaseUnavailable || isLocalDevSession()) {
    return upsertLocalSite(site);
  }

  if (!SUPABASE_URL) {
    throw new Error("Supabase environment variables are not configured.");
  }

  const accessToken = useAuthStore.getState().accessToken;
  if (!accessToken) {
    throw new Error("Sign in as an admin to update websites.");
  }

  const payload = {
    display_name: site.displayName,
    primary_domain: site.primaryDomain,
    adapter_key: site.adapterKey,
    seed_urls: site.seedUrls,
    adapter_config: site.adapterConfig,
    active: site.active,
    notes: site.notes
  };
  const doUpdate = async (bearer: string) =>
    fetch(`${SUPABASE_URL}/rest/v1/sites?site_key=eq.${encodeURIComponent(site.siteKey)}`, {
      method: "PATCH",
      headers: {
        apikey: SUPABASE_ANON_KEY ?? "",
        Authorization: `Bearer ${bearer}`,
        "Content-Type": "application/json",
        Prefer: "return=representation"
      },
      body: JSON.stringify(payload)
    });

  let response = await doUpdate(accessToken);
  if (!response.ok && response.status === 401 && (await refreshSiteSession())) {
    response = await doUpdate(useAuthStore.getState().accessToken ?? "");
  }

  if (!response.ok) {
    if (response.status === 409) {
      throw new Error(siteConflictMessage);
    }
    throw new Error(`Failed to update record in sites (${response.status})`);
  }

  const [row] = (await response.json()) as SiteRow[];
  if (!row) {
    throw new Error("Supabase did not return the updated site.");
  }
  return mapSiteRowToSite(row);
};

export const deleteSiteInDatabase = async (siteKey: string): Promise<void> => {
  if (isSupabaseUnavailable || isLocalDevSession()) {
    deleteLocalSite(siteKey);
    return;
  }

  if (!SUPABASE_URL) {
    throw new Error("Supabase environment variables are not configured.");
  }

  const accessToken = useAuthStore.getState().accessToken;
  if (!accessToken) {
    throw new Error("Sign in as an admin to delete websites.");
  }

  const doDelete = async (bearer: string) =>
    fetch(`${SUPABASE_URL}/rest/v1/sites?site_key=eq.${encodeURIComponent(siteKey)}`, {
      method: "DELETE",
      headers: {
        apikey: SUPABASE_ANON_KEY ?? "",
        Authorization: `Bearer ${bearer}`
      }
    });

  let response = await doDelete(accessToken);
  if (!response.ok && response.status === 401 && (await refreshSiteSession())) {
    response = await doDelete(useAuthStore.getState().accessToken ?? "");
  }

  if (!response.ok) {
    throw new Error(`Failed to delete record in sites (${response.status})`);
  }
};

export const fetchProgrammeRecordBundle = async (programId: string): Promise<ProgrammeRecordBundle> => {
  const { rawId } = parseProgrammeClientId(programId);

  if (!isSupabaseUnavailable && !isLocalDevSession()) {
    const [record] = await fetchSupabaseOptionalRows<SourceProgrammeRow>(
      "funding_programmes",
      `program_id=eq.${encodeURIComponent(rawId)}&select=*`
    );
    if (record) {
      return { record };
    }
    return {};
  }

  const record = readLocalProgrammeRecords().find((candidate) => candidate.program_id === rawId);
  return { record };
};

export const fetchPublishedProgrammeRecordBundle = async (programId: string): Promise<ProgrammeRecordBundle> => {
  const { rawId } = parseProgrammeClientId(programId);

  if (!isSupabaseUnavailable && !isLocalDevSession()) {
    const [record] = await fetchSupabaseOptionalRows<PublishedProgrammeRow>(
      "final_funding_programmes",
      `program_id=eq.${encodeURIComponent(rawId)}&select=*`
    );
    if (record) {
      return { record };
    }
    return {};
  }

  const record = readLocalPublishedProgrammeRecords().find((candidate) => candidate.program_id === rawId);
  return { record };
};

const updateProgrammeRecordInDatabase = async (programId: string, patch: Record<string, unknown>): Promise<void> => {
  const { rawId } = parseProgrammeClientId(programId);

  if (isSupabaseUnavailable || isLocalDevSession()) {
    const records = readLocalProgrammeRecords();
    const index = records.findIndex((candidate) => candidate.program_id === rawId);
    if (index >= 0) {
      records[index] = {
        ...records[index],
        ...patch
      } as FundingProgrammeRecord;
    }
    return;
  }

  if (!SUPABASE_URL) {
    throw new Error("Supabase environment variables are not configured.");
  }

  const accessToken = useAuthStore.getState().accessToken;
  if (!accessToken) {
    throw new Error("Sign in as an admin to update programmes.");
  }

  const doUpdate = async (bearer: string) =>
    fetch(`${SUPABASE_URL}/rest/v1/funding_programmes?program_id=eq.${encodeURIComponent(rawId)}`, {
      method: "PATCH",
      headers: {
        apikey: SUPABASE_ANON_KEY ?? "",
        Authorization: `Bearer ${bearer}`,
        "Content-Type": "application/json",
        Prefer: "return=representation"
      },
      body: JSON.stringify(patch)
    });

  let response = await doUpdate(accessToken);
  if (!response.ok && response.status === 401 && (await refreshSiteSession())) {
    response = await doUpdate(useAuthStore.getState().accessToken ?? "");
  }

  if (!response.ok) {
    throw new Error(`Failed to update record in funding_programmes (${response.status})`);
  }
};

const withLatency = async <T>(value: T): Promise<T> => {
  await new Promise((resolve) => setTimeout(resolve, 200));
  return value;
};

export const apiClient: ApiClient = {
  getCurrentUserProfile: () => withLatency(mockProfile),
  getPrograms: async () => {
    try {
      return withLatency(await fetchPublishedProgramsFromDatabase());
    } catch {
      return withLatency([]);
    }
  },
  getProgramById: async (programId) => {
    const records = await apiClient.getPrograms();
    return records.find((program) => program.id === programId);
  },
  updateProgrammeRecord: async (programId, patch) => {
    await updateProgrammeRecordInDatabase(programId, patch);
  },
  getSites: async () => withLatency(await fetchSitesFromDatabase()),
  getSiteByKey: async (siteKey) => withLatency(await fetchSiteByKeyFromDatabase(siteKey)),
  createSite: async (site) => withLatency(await createSiteInDatabase(site)),
  updateSite: async (site) => withLatency(await updateSiteInDatabase(site)),
  deleteSite: async (siteKey) => withLatency(await deleteSiteInDatabase(siteKey)),
  getMatchesByUser: async (userId) => {
    const matches = await withLatency(mockMatches);
    return matches.filter((match) => match.userId === userId);
  },
  getScrapeRuns: async () => withLatency(await fetchScrapeRunsFromDatabase()),
  getScrapeRunById: async (runId) => withLatency(await fetchScrapeRunByIdFromDatabase(runId)),
  getSystemChangeLog: async (): Promise<SystemChangeLogEntry[]> =>
    withLatency(
      [...mockSystemChangeLog].sort(
        (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
      )
    ),
  getNotificationPreferences: () => withLatency(mockNotificationPreferences),
  getNotificationEvents: async (userId) => {
    const events = await withLatency(mockNotificationEvents);
    return events.filter((event) => event.userId === userId);
  }
};
