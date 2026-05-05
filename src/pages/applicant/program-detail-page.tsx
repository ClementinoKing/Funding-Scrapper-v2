import type React from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft,ExternalLink } from "lucide-react";
import { format } from "date-fns";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {useProgram} from "@/hooks/use-programs"

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

const formatMoney = (value?: number | string | null, currency = "ZAR"): string => {
  if (value === null || value === undefined || value === "") return "Not specified";
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return "Not specified";
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency,
    maximumFractionDigits: 0
  }).format(numeric);
};

const asList = (value?: string[] | null): string[] => (value ?? []).filter(Boolean);

const listOrFallback = (value?: string[] | null): string => {
  const items = asList(value);
  return items.length ? items.join(", ") : "Not specified";
};

function DetailField({ label, value, className }: { label: string; value: React.ReactNode; className?: string }) {
  return (
    <div className={`space-y-1 rounded-lg bg-card p-4 flex-1 ${className}`}>
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
  const {data: program, isLoading } = useProgram(programId as string)

  if (!programId) {
    return <p>Missing program id.</p>;
  }

  if (!isLoading && !program) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline" size="sm">
          <Link to={"/app/programs"}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to programs
          </Link>
        </Button>
        <Card>
          <CardContent className="p-6">Loading programme details...</CardContent>
        </Card>
      </div>
    );
  }

  if (!program) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline" size="sm">
          <Link to={"/app/programs"}>
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
          <Link to={"/app/programs"}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to programs
          </Link>
        </Button>
      </div>

      <div className="flex items-center justify-between gap-4">
        <SectionHeader
          title={program.program_name}
          description={`${program.funder_name} • scraped ${formatDateTime(program.scraped_at)}`}
        />

        <a className="text-primary underline" href={program.source_url} target="_blank" rel="noreferrer">
          <Button variant="outline" size="sm" className="gap-2">
            <ExternalLink className="w-4 h-4" /> Open Source
          </Button>
        </a>
      </div>
      

      <div className="space-y-4">

        <Card>
          <CardHeader>
            <CardTitle>Funding Offer</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="w-full flex items-center gap-2">
              <DetailField label="Funding type" value={program.funding_type || "Unknown"} />
              <DetailField label="Funding amounts" value={
                <>
                  <div>
                    <span className="font-semibold">Range</span>{" "}
                    {formatMoney(program.ticket_min, program.currency || "ZAR")}{" "}to{" "}
                    {formatMoney(program.ticket_max, program.currency || "ZAR")}
                  </div>
                  <div>
                    <span className="font-semibold">Program Budget</span>{" "}
                    {formatMoney(program.program_budget_total, program.currency || "ZAR")}
                  </div>
                </>
              } />
            </div>            
            <DetailField label="Funding lines" value={<SectionList items={asList(program.funding_lines)} />} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Timing and Geography</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <DetailField label="Deadline type" value={program.deadline_type || "Unknown"} />
            <DetailField label="Deadline date" value={formatDate(program.deadline_date)} />
            <DetailField label="Funding speed" value={program.funding_speed_days_min || program.funding_speed_days_max ? `${program.funding_speed_days_min ?? "?"} to ${program.funding_speed_days_max ?? "?"} days` : "Not specified"} />
            <DetailField label="Geography scope" value={program.geography_scope || "Unknown"} />
            <DetailField label="Provinces" value={<SectionList items={asList(program.provinces)} />} />
            <DetailField label="Municipalities" value={<SectionList items={asList(program.municipalities)} />} />
            <DetailField label="Postal code ranges" value={listOrFallback(program.postal_code_ranges)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Eligibility</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <DetailField label="Industries" value={<SectionList items={asList(program.industries)} />} />
            <DetailField label="Use of funds" value={<SectionList items={asList(program.use_of_funds)} />} />
            <DetailField label="Business stage" value={<SectionList items={asList(program.business_stage_eligibility)} />} />
            <DetailField label="Turnover" value={program.turnover_min || program.turnover_max ? `${formatMoney(program.turnover_min)} to ${formatMoney(program.turnover_max)}` : "Not specified"} />
            <DetailField label="Years in business" value={program.years_in_business_min || program.years_in_business_max ? `${program.years_in_business_min ?? "?"} to ${program.years_in_business_max ?? "?"}` : "Not specified"} />
            <DetailField label="Employees" value={program.employee_min || program.employee_max ? `${program.employee_min ?? "?"} to ${program.employee_max ?? "?"}` : "Not specified"} />
            <DetailField label="Ownership targets" value={<SectionList items={asList(program.ownership_targets)} />} />
            <DetailField label="Entity types allowed" value={<SectionList items={asList(program.entity_types_allowed)} />} />
            <DetailField label="Certifications required" value={<SectionList items={asList(program.certifications_required)} />} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Terms and Structure</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <DetailField label="Security required" value={program.security_required || "Unknown"} />
            <DetailField label="Equity required" value={program.equity_required || "Unknown"} />
            <DetailField label="Payback" value={program.payback_months_min || program.payback_months_max ? `${program.payback_months_min ?? "?"} to ${program.payback_months_max ?? "?"} months` : "Not specified"} />
            <DetailField label="Interest type" value={program.interest_type || "Unknown"} />
            <DetailField label="Repayment frequency" value={program.repayment_frequency || "Unknown"} />
            <DetailField label="Exclusions" value={listOrFallback(program.exclusions)} />
            <DetailField label="Required documents" value={listOrFallback(program.required_documents)} className="col-span-1 md:col-span-4" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Application Route</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <DetailField label="Application channel" value={program.application_channel || "Unknown"} />
            <DetailField
              label="Application URL"
              value={
                program.application_url ? (
                  <a className="inline-flex items-center gap-2 text-primary underline" href={program.application_url} target="_blank" rel="noreferrer">
                    Open application
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  "Not specified"
                )
              }
            />
            <DetailField label="Contact email" value={program.contact_email || "Not specified"} />
            <DetailField label="Contact phone" value={program.contact_phone || "Not specified"} />
            <DetailField label="Related documents" value={<SectionList items={asList(program.related_documents)} />} className="col-span-1 md:col-span-4" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
