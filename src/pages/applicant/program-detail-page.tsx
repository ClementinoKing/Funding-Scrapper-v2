import type React from "react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { format } from "date-fns";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FundingProgram } from "@/types/domain";
import { fetchProgrammeRecordBundle } from "@/services/api/client";

type ScraperRecord = {
  program_id?: string;
  program_name?: string | null;
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

const formatDate = (value?: string | null): string => {
  if (!value) return "Not specified";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : format(date, "PPP");
};

const formatDateTime = (value?: string | null): string => {
  if (!value) return "Not specified";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : format(date, "PPP p");
};

const formatMoney = (value?: number | string | null): string => {
  if (value === null || value === undefined || value === "") return "Not specified";
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return "Not specified";
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 0
  }).format(numeric);
};

const asList = (value?: string[] | null): string[] => (value ?? []).filter(Boolean);

const listOrFallback = (value?: string[] | null): string => {
  const items = asList(value);
  return items.length ? items.join(", ") : "Not specified";
};

const mapToProgram = (record?: ScraperRecord): FundingProgram | undefined => {
  if (!record) return undefined;
  const title = record.program_name?.trim() || "Untitled programme";
  return {
    ...(record.program_id ? { id: `main:${record.program_id}` } : { id: `${title}-${record.source_domain ?? "source"}` }),
    title,
    providerName: record.funder_name?.trim() || record.source_domain || "Unknown provider",
    sourceUrl: record.source_url || "#",
    sourceName: record.source_page_title?.trim() || record.funder_name?.trim() || "Unknown source",
    geography: [...asList(record.provinces), ...asList(record.municipalities), ...(record.geography_scope ? [record.geography_scope] : [])],
    sectors: asList(record.industries),
    eligibilitySummary:
      typeof record.raw_eligibility_data === "string"
        ? record.raw_eligibility_data
        : Array.isArray(record.raw_eligibility_data)
          ? record.raw_eligibility_data.join(" ")
          : listOrFallback(record.use_of_funds) || "Eligibility details not captured yet.",
    fundingType: (record.funding_type?.toLowerCase() as FundingProgram["fundingType"]) || "unknown",
    amountMin: typeof record.ticket_min === "number" ? record.ticket_min : Number.isFinite(Number(record.ticket_min)) ? Number(record.ticket_min) : undefined,
    amountMax: typeof record.ticket_max === "number" ? record.ticket_max : Number.isFinite(Number(record.ticket_max)) ? Number(record.ticket_max) : undefined,
    deadlineAt: record.deadline_date || undefined,
    status: "active",
    scrapeConfidence: record.extraction_confidence
      ? Object.values(record.extraction_confidence).reduce((sum, value) => sum + value, 0) /
        Math.max(Object.values(record.extraction_confidence).length, 1)
      : 0.5,
    approvalStatus: "pending",
    lastScrapedAt: record.scraped_at || new Date().toISOString(),
    createdAt: record.scraped_at || new Date().toISOString(),
    updatedAt: record.scraped_at || new Date().toISOString()
  };
};

function DetailField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-1 rounded-lg border bg-card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="text-sm">{value}</div>
    </div>
  );
}

function SectionList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">Not specified</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <Badge key={item} variant="secondary">
          {item}
        </Badge>
      ))}
    </div>
  );
}

export function ProgramDetailPage() {
  const { programId } = useParams<{ programId: string }>();
  const location = useLocation();
  const backPath = location.pathname.startsWith("/admin") ? "/admin/programs" : "/app/programs";

  const { data: record } = useQuery({
    queryKey: ["program-detail", programId],
    queryFn: async () => {
      if (!programId) return undefined;
      return fetchProgrammeRecordBundle(programId);
    },
    enabled: Boolean(programId)
  });

  const bundle = record;
  const program = useMemo(() => mapToProgram(bundle?.record as ScraperRecord | undefined), [bundle]);
  const detailRecord = bundle?.record as ScraperRecord | undefined;

  if (!programId) {
    return <p>Missing program id.</p>;
  }

  if (!detailRecord || !program) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline" size="sm">
          <Link to={backPath}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to programs
          </Link>
        </Button>
        <SectionHeader
          title="Program not found"
          description="We could not find that programme in the current scraper dataset or Supabase table."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <Button asChild variant="outline" size="sm">
          <Link to={backPath}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to programs
          </Link>
        </Button>
        <Badge variant={program.status === "active" ? "success" : "warning"}>{program.status}</Badge>
      </div>

      <SectionHeader
        title={program.title}
        description={`${program.providerName} • scraped ${formatDateTime(detailRecord.scraped_at)}`}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Identity</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <DetailField label="Program ID" value={detailRecord.program_id || program.id} />
            <DetailField label="Provider" value={detailRecord.funder_name || "Not specified"} />
            <DetailField label="Source domain" value={detailRecord.source_domain || "Not specified"} />
            <DetailField label="Source page" value={detailRecord.source_page_title || "Not specified"} />
            <DetailField label="Program kind" value="Main funding" />
            <DetailField
              label="Source URL"
              value={
                detailRecord.source_url ? (
                  <a className="text-primary underline" href={detailRecord.source_url} target="_blank" rel="noreferrer">
                    Open source
                  </a>
                ) : (
                  "Not specified"
                )
              }
            />
            <DetailField label="Source URLs" value={<SectionList items={asList(detailRecord.source_urls)} />} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Funding Offer</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <DetailField label="Funding type" value={detailRecord.funding_type || "Unknown"} />
            <DetailField label="Funding lines" value={<SectionList items={asList(detailRecord.funding_lines)} />} />
            <DetailField label="Ticket min" value={formatMoney(detailRecord.ticket_min)} />
            <DetailField label="Ticket max" value={formatMoney(detailRecord.ticket_max)} />
            <DetailField label="Currency" value={detailRecord.currency || "Not specified"} />
            <DetailField label="Programme budget total" value={formatMoney(detailRecord.program_budget_total)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Timing and Geography</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <DetailField label="Deadline type" value={detailRecord.deadline_type || "Unknown"} />
            <DetailField label="Deadline date" value={formatDate(detailRecord.deadline_date)} />
            <DetailField label="Funding speed" value={detailRecord.funding_speed_days_min || detailRecord.funding_speed_days_max ? `${detailRecord.funding_speed_days_min ?? "?"} to ${detailRecord.funding_speed_days_max ?? "?"} days` : "Not specified"} />
            <DetailField label="Geography scope" value={detailRecord.geography_scope || "Unknown"} />
            <DetailField label="Provinces" value={<SectionList items={asList(detailRecord.provinces)} />} />
            <DetailField label="Municipalities" value={<SectionList items={asList(detailRecord.municipalities)} />} />
            <DetailField label="Postal code ranges" value={listOrFallback(detailRecord.postal_code_ranges)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Eligibility</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <DetailField label="Industries" value={<SectionList items={asList(detailRecord.industries)} />} />
            <DetailField label="Use of funds" value={<SectionList items={asList(detailRecord.use_of_funds)} />} />
            <DetailField label="Business stage" value={<SectionList items={asList(detailRecord.business_stage_eligibility)} />} />
            <DetailField label="Turnover" value={detailRecord.turnover_min || detailRecord.turnover_max ? `${formatMoney(detailRecord.turnover_min)} to ${formatMoney(detailRecord.turnover_max)}` : "Not specified"} />
            <DetailField label="Years in business" value={detailRecord.years_in_business_min || detailRecord.years_in_business_max ? `${detailRecord.years_in_business_min ?? "?"} to ${detailRecord.years_in_business_max ?? "?"}` : "Not specified"} />
            <DetailField label="Employees" value={detailRecord.employee_min || detailRecord.employee_max ? `${detailRecord.employee_min ?? "?"} to ${detailRecord.employee_max ?? "?"}` : "Not specified"} />
            <DetailField label="Ownership targets" value={<SectionList items={asList(detailRecord.ownership_targets)} />} />
            <DetailField label="Entity types allowed" value={<SectionList items={asList(detailRecord.entity_types_allowed)} />} />
            <DetailField label="Certifications required" value={<SectionList items={asList(detailRecord.certifications_required)} />} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Terms and Structure</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <DetailField label="Security required" value={detailRecord.security_required || "Unknown"} />
            <DetailField label="Equity required" value={detailRecord.equity_required || "Unknown"} />
            <DetailField label="Payback" value={detailRecord.payback_months_min || detailRecord.payback_months_max ? `${detailRecord.payback_months_min ?? "?"} to ${detailRecord.payback_months_max ?? "?"} months` : "Not specified"} />
            <DetailField label="Interest type" value={detailRecord.interest_type || "Unknown"} />
            <DetailField label="Repayment frequency" value={detailRecord.repayment_frequency || "Unknown"} />
            <DetailField label="Exclusions" value={listOrFallback(detailRecord.exclusions)} />
            <DetailField label="Required documents" value={listOrFallback(detailRecord.required_documents)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Application Route</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <DetailField label="Application channel" value={detailRecord.application_channel || "Unknown"} />
            <DetailField
              label="Application URL"
              value={
                detailRecord.application_url ? (
                  <a className="inline-flex items-center gap-2 text-primary underline" href={detailRecord.application_url} target="_blank" rel="noreferrer">
                    Open application
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  "Not specified"
                )
              }
            />
            <DetailField label="Contact email" value={detailRecord.contact_email || "Not specified"} />
            <DetailField label="Contact phone" value={detailRecord.contact_phone || "Not specified"} />
            <DetailField label="Related documents" value={<SectionList items={asList(detailRecord.related_documents)} />} />
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Traceability</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <DetailField label="Raw eligibility data" value={typeof detailRecord.raw_eligibility_data === "string" ? detailRecord.raw_eligibility_data : Array.isArray(detailRecord.raw_eligibility_data) ? detailRecord.raw_eligibility_data.join("\n") : "Not captured"} />
            <DetailField label="Notes" value={listOrFallback(detailRecord.notes)} />
            <DetailField label="Extraction confidence" value={detailRecord.extraction_confidence ? JSON.stringify(detailRecord.extraction_confidence, null, 2) : "Not captured"} />
            <DetailField label="Raw text snippets" value={detailRecord.raw_text_snippets ? <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">{JSON.stringify(detailRecord.raw_text_snippets, null, 2)}</pre> : "Not captured"} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
