import type React from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Edit3, ExternalLink, Save } from "lucide-react";
import { format } from "date-fns";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import type { FundingProgram } from "@/types/domain";
import { apiClient, fetchProgrammeRecordBundle, fetchPublishedProgrammeRecordBundle } from "@/services/api/client";
import type { FundingProgrammeRecord } from "@/services/api/client";

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

const formatConfidenceLabel = (key: string): string =>
  key
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const formatConfidencePercent = (value: number): string => `${Math.round(value * 100)}%`;

const getConfidenceTone = (value: number): string => {
  if (value >= 0.85) return "bg-emerald-500";
  if (value >= 0.7) return "bg-amber-500";
  return "bg-rose-500";
};

type ProgrammeEditDraft = {
  program_name: string;
  funder_name: string;
  source_url: string;
  source_urls: string;
  source_domain: string;
  source_page_title: string;
  scraped_at: string;
  raw_eligibility_data: string;
  funding_type: string;
  funding_lines: string;
  ticket_min: string;
  ticket_max: string;
  currency: string;
  program_budget_total: string;
  deadline_type: string;
  deadline_date: string;
  funding_speed_days_min: string;
  funding_speed_days_max: string;
  geography_scope: string;
  provinces: string;
  municipalities: string;
  postal_code_ranges: string;
  industries: string;
  use_of_funds: string;
  business_stage_eligibility: string;
  turnover_min: string;
  turnover_max: string;
  years_in_business_min: string;
  years_in_business_max: string;
  employee_min: string;
  employee_max: string;
  ownership_targets: string;
  entity_types_allowed: string;
  certifications_required: string;
  security_required: string;
  equity_required: string;
  payback_months_min: string;
  payback_months_max: string;
  interest_type: string;
  repayment_frequency: string;
  exclusions: string;
  required_documents: string;
  application_channel: string;
  application_url: string;
  contact_email: string;
  contact_phone: string;
  related_documents: string;
  notes: string;
  raw_text_snippets: string;
  extraction_confidence: string;
  approval_status: FundingProgram["approvalStatus"];
};

const listToText = (value?: string[] | null): string => (value ?? []).filter(Boolean).join("\n");

const textToList = (value: string): string[] =>
  value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const numberToText = (value?: number | string | null): string => {
  if (value === null || value === undefined || value === "") return "";
  return String(value);
};

const parseNumberOrNull = (value: string): number | null => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

const parseJsonOrThrow = (value: string): Record<string, unknown> => {
  const trimmed = value.trim();
  if (!trimmed) {
    return {};
  }
  const parsed = JSON.parse(trimmed) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("JSON fields must contain an object");
  }
  return parsed as Record<string, unknown>;
};

const buildDraftFromRecord = (record: FundingProgrammeRecord): ProgrammeEditDraft => ({
  program_name: record.program_name ?? "",
  funder_name: record.funder_name ?? "",
  source_url: record.source_url ?? "",
  source_urls: listToText(record.source_urls),
  source_domain: record.source_domain ?? "",
  source_page_title: record.source_page_title ?? "",
  scraped_at: record.scraped_at ?? "",
  raw_eligibility_data: Array.isArray(record.raw_eligibility_data)
    ? record.raw_eligibility_data.join("\n")
    : record.raw_eligibility_data ?? "",
  funding_type: record.funding_type ?? "Unknown",
  funding_lines: listToText(record.funding_lines),
  ticket_min: numberToText(record.ticket_min),
  ticket_max: numberToText(record.ticket_max),
  currency: record.currency ?? "",
  program_budget_total: numberToText(record.program_budget_total),
  deadline_type: record.deadline_type ?? "Unknown",
  deadline_date: record.deadline_date ?? "",
  funding_speed_days_min: numberToText(record.funding_speed_days_min),
  funding_speed_days_max: numberToText(record.funding_speed_days_max),
  geography_scope: record.geography_scope ?? "Unknown",
  provinces: listToText(record.provinces),
  municipalities: listToText(record.municipalities),
  postal_code_ranges: listToText(record.postal_code_ranges),
  industries: listToText(record.industries),
  use_of_funds: listToText(record.use_of_funds),
  business_stage_eligibility: listToText(record.business_stage_eligibility),
  turnover_min: numberToText(record.turnover_min),
  turnover_max: numberToText(record.turnover_max),
  years_in_business_min: numberToText(record.years_in_business_min),
  years_in_business_max: numberToText(record.years_in_business_max),
  employee_min: numberToText(record.employee_min),
  employee_max: numberToText(record.employee_max),
  ownership_targets: listToText(record.ownership_targets),
  entity_types_allowed: listToText(record.entity_types_allowed),
  certifications_required: listToText(record.certifications_required),
  security_required: record.security_required ?? "Unknown",
  equity_required: record.equity_required ?? "Unknown",
  payback_months_min: numberToText(record.payback_months_min),
  payback_months_max: numberToText(record.payback_months_max),
  interest_type: record.interest_type ?? "Unknown",
  repayment_frequency: record.repayment_frequency ?? "Unknown",
  exclusions: listToText(record.exclusions),
  required_documents: listToText(record.required_documents),
  application_channel: record.application_channel ?? "Unknown",
  application_url: record.application_url ?? "",
  contact_email: record.contact_email ?? "",
  contact_phone: record.contact_phone ?? "",
  related_documents: listToText(record.related_documents),
  notes: listToText(record.notes),
  raw_text_snippets: JSON.stringify(record.raw_text_snippets ?? {}, null, 2),
  extraction_confidence: JSON.stringify(record.extraction_confidence ?? {}, null, 2),
  approval_status: record.approval_status ?? "pending"
});

const buildProgrammePatch = (record: FundingProgrammeRecord, draft: ProgrammeEditDraft): Record<string, unknown> => ({
  program_name: draft.program_name.trim() || record.program_name || null,
  funder_name: draft.funder_name.trim() || record.funder_name || null,
  source_url: draft.source_url.trim() || record.source_url,
  source_urls: textToList(draft.source_urls),
  source_domain: draft.source_domain.trim() || record.source_domain || null,
  source_page_title: draft.source_page_title.trim() || record.source_page_title || null,
  scraped_at: draft.scraped_at.trim() || record.scraped_at || null,
  raw_eligibility_data: draft.raw_eligibility_data.trim()
    ? textToList(draft.raw_eligibility_data).join("\n")
    : record.raw_eligibility_data,
  funding_type: draft.funding_type.trim() || record.funding_type || "Unknown",
  funding_lines: textToList(draft.funding_lines),
  ticket_min: parseNumberOrNull(draft.ticket_min),
  ticket_max: parseNumberOrNull(draft.ticket_max),
  currency: draft.currency.trim() || record.currency || null,
  program_budget_total: parseNumberOrNull(draft.program_budget_total),
  deadline_type: draft.deadline_type.trim() || record.deadline_type || "Unknown",
  deadline_date: draft.deadline_date.trim() || null,
  funding_speed_days_min: parseNumberOrNull(draft.funding_speed_days_min),
  funding_speed_days_max: parseNumberOrNull(draft.funding_speed_days_max),
  geography_scope: draft.geography_scope.trim() || record.geography_scope || "Unknown",
  provinces: textToList(draft.provinces),
  municipalities: textToList(draft.municipalities),
  postal_code_ranges: textToList(draft.postal_code_ranges),
  industries: textToList(draft.industries),
  use_of_funds: textToList(draft.use_of_funds),
  business_stage_eligibility: textToList(draft.business_stage_eligibility),
  turnover_min: parseNumberOrNull(draft.turnover_min),
  turnover_max: parseNumberOrNull(draft.turnover_max),
  years_in_business_min: parseNumberOrNull(draft.years_in_business_min),
  years_in_business_max: parseNumberOrNull(draft.years_in_business_max),
  employee_min: parseNumberOrNull(draft.employee_min),
  employee_max: parseNumberOrNull(draft.employee_max),
  ownership_targets: textToList(draft.ownership_targets),
  entity_types_allowed: textToList(draft.entity_types_allowed),
  certifications_required: textToList(draft.certifications_required),
  security_required: draft.security_required.trim() || record.security_required || "Unknown",
  equity_required: draft.equity_required.trim() || record.equity_required || "Unknown",
  payback_months_min: parseNumberOrNull(draft.payback_months_min),
  payback_months_max: parseNumberOrNull(draft.payback_months_max),
  interest_type: draft.interest_type.trim() || record.interest_type || "Unknown",
  repayment_frequency: draft.repayment_frequency.trim() || record.repayment_frequency || "Unknown",
  exclusions: textToList(draft.exclusions),
  required_documents: textToList(draft.required_documents),
  application_channel: draft.application_channel.trim() || record.application_channel || "Unknown",
  application_url: draft.application_url.trim() || null,
  contact_email: draft.contact_email.trim() || null,
  contact_phone: draft.contact_phone.trim() || null,
  related_documents: textToList(draft.related_documents),
  notes: textToList(draft.notes),
  raw_text_snippets: parseJsonOrThrow(draft.raw_text_snippets),
  extraction_confidence: parseJsonOrThrow(draft.extraction_confidence),
  approval_status: draft.approval_status
});

function ProgrammeEditDialog({
  programme,
  open,
  onOpenChange,
  onSave,
  saving
}: {
  programme: FundingProgrammeRecord | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (programme: FundingProgrammeRecord, draft: ProgrammeEditDraft) => void;
  saving: boolean;
}) {
  const [draft, setDraft] = useState<ProgrammeEditDraft | null>(null);

  useEffect(() => {
    setDraft(programme ? buildDraftFromRecord(programme) : null);
  }, [programme]);

  const updateField = <K extends keyof ProgrammeEditDraft>(key: K, value: ProgrammeEditDraft[K]) => {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
  };

  const sectionTitle = "text-xs font-semibold uppercase tracking-wide text-muted-foreground";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit programme</DialogTitle>
          <DialogDescription>Update the source record, then publish it by approving the programme.</DialogDescription>
        </DialogHeader>

        {programme && draft ? (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <Label className={sectionTitle}>Identity</Label>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="programme-name">Programme name</Label>
                    <Input id="programme-name" value={draft.program_name} onChange={(event) => updateField("program_name", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-provider">Provider</Label>
                    <Input id="programme-provider" value={draft.funder_name} onChange={(event) => updateField("funder_name", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-source-url">Source URL</Label>
                    <Input id="programme-source-url" value={draft.source_url} onChange={(event) => updateField("source_url", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-source-domain">Source domain</Label>
                    <Input id="programme-source-domain" value={draft.source_domain} onChange={(event) => updateField("source_domain", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-source-title">Source page title</Label>
                    <Input id="programme-source-title" value={draft.source_page_title} onChange={(event) => updateField("source_page_title", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-scraped-at">Scraped at</Label>
                    <Input id="programme-scraped-at" value={draft.scraped_at} onChange={(event) => updateField("scraped_at", event.target.value)} />
                  </div>
                </div>
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label className={sectionTitle}>Funding and timing</Label>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <Label htmlFor="programme-funding-type">Funding type</Label>
                    <Input id="programme-funding-type" value={draft.funding_type} onChange={(event) => updateField("funding_type", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-deadline-type">Deadline type</Label>
                    <Input id="programme-deadline-type" value={draft.deadline_type} onChange={(event) => updateField("deadline_type", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-deadline-date">Deadline date</Label>
                    <Input id="programme-deadline-date" value={draft.deadline_date} onChange={(event) => updateField("deadline_date", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-ticket-min">Funding amount min</Label>
                    <Input id="programme-ticket-min" inputMode="numeric" value={draft.ticket_min} onChange={(event) => updateField("ticket_min", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-ticket-max">Funding amount max</Label>
                    <Input id="programme-ticket-max" inputMode="numeric" value={draft.ticket_max} onChange={(event) => updateField("ticket_max", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-budget">Programme budget total</Label>
                    <Input id="programme-budget" inputMode="numeric" value={draft.program_budget_total} onChange={(event) => updateField("program_budget_total", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-speed-min">Funding speed min</Label>
                    <Input id="programme-speed-min" inputMode="numeric" value={draft.funding_speed_days_min} onChange={(event) => updateField("funding_speed_days_min", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-speed-max">Funding speed max</Label>
                    <Input id="programme-speed-max" inputMode="numeric" value={draft.funding_speed_days_max} onChange={(event) => updateField("funding_speed_days_max", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-currency">Currency</Label>
                    <Input id="programme-currency" value={draft.currency} onChange={(event) => updateField("currency", event.target.value)} />
                  </div>
                </div>
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label className={sectionTitle}>Geography and eligibility</Label>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="programme-geography">Geography scope</Label>
                    <Input id="programme-geography" value={draft.geography_scope} onChange={(event) => updateField("geography_scope", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-status">Approval status</Label>
                    <Select value={draft.approval_status} onValueChange={(value) => updateField("approval_status", value as FundingProgram["approvalStatus"])}>
                      <SelectTrigger id="programme-status">
                        <SelectValue placeholder="Select approval status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="pending">pending</SelectItem>
                        <SelectItem value="approved">approved</SelectItem>
                        <SelectItem value="rejected">rejected</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="programme-provinces">Provinces</Label>
                    <Textarea id="programme-provinces" value={draft.provinces} onChange={(event) => updateField("provinces", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="programme-municipalities">Municipalities</Label>
                    <Textarea id="programme-municipalities" value={draft.municipalities} onChange={(event) => updateField("municipalities", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-postal">Postal code ranges</Label>
                    <Textarea id="programme-postal" value={draft.postal_code_ranges} onChange={(event) => updateField("postal_code_ranges", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-industries">Industries</Label>
                    <Textarea id="programme-industries" value={draft.industries} onChange={(event) => updateField("industries", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-use-of-funds">Use of funds</Label>
                    <Textarea id="programme-use-of-funds" value={draft.use_of_funds} onChange={(event) => updateField("use_of_funds", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-business-stage">Business stage eligibility</Label>
                    <Textarea id="programme-business-stage" value={draft.business_stage_eligibility} onChange={(event) => updateField("business_stage_eligibility", event.target.value)} className="min-h-20" />
                  </div>
                </div>
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label className={sectionTitle}>Terms and structure</Label>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <Label htmlFor="programme-security">Security required</Label>
                    <Input id="programme-security" value={draft.security_required} onChange={(event) => updateField("security_required", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-equity">Equity required</Label>
                    <Input id="programme-equity" value={draft.equity_required} onChange={(event) => updateField("equity_required", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-interest">Interest type</Label>
                    <Input id="programme-interest" value={draft.interest_type} onChange={(event) => updateField("interest_type", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-repayment">Repayment frequency</Label>
                    <Input id="programme-repayment" value={draft.repayment_frequency} onChange={(event) => updateField("repayment_frequency", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-payback-min">Payback min</Label>
                    <Input id="programme-payback-min" inputMode="numeric" value={draft.payback_months_min} onChange={(event) => updateField("payback_months_min", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-payback-max">Payback max</Label>
                    <Input id="programme-payback-max" inputMode="numeric" value={draft.payback_months_max} onChange={(event) => updateField("payback_months_max", event.target.value)} />
                  </div>
                  <div className="space-y-2 md:col-span-3">
                    <Label htmlFor="programme-exclusions">Exclusions</Label>
                    <Textarea id="programme-exclusions" value={draft.exclusions} onChange={(event) => updateField("exclusions", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2 md:col-span-3">
                    <Label htmlFor="programme-docs">Required documents</Label>
                    <Textarea id="programme-docs" value={draft.required_documents} onChange={(event) => updateField("required_documents", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2 md:col-span-3">
                    <Label htmlFor="programme-ownership">Ownership targets</Label>
                    <Textarea id="programme-ownership" value={draft.ownership_targets} onChange={(event) => updateField("ownership_targets", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2 md:col-span-3">
                    <Label htmlFor="programme-entity-types">Entity types allowed</Label>
                    <Textarea id="programme-entity-types" value={draft.entity_types_allowed} onChange={(event) => updateField("entity_types_allowed", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2 md:col-span-3">
                    <Label htmlFor="programme-certifications">Certifications required</Label>
                    <Textarea id="programme-certifications" value={draft.certifications_required} onChange={(event) => updateField("certifications_required", event.target.value)} className="min-h-20" />
                  </div>
                </div>
              </div>

              <div className="space-y-2 md:col-span-2">
                <Label className={sectionTitle}>Application and traceability</Label>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="programme-application-channel">Application channel</Label>
                    <Input id="programme-application-channel" value={draft.application_channel} onChange={(event) => updateField("application_channel", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-application-url">Application URL</Label>
                    <Input id="programme-application-url" value={draft.application_url} onChange={(event) => updateField("application_url", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-contact-email">Contact email</Label>
                    <Input id="programme-contact-email" value={draft.contact_email} onChange={(event) => updateField("contact_email", event.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="programme-contact-phone">Contact phone</Label>
                    <Input id="programme-contact-phone" value={draft.contact_phone} onChange={(event) => updateField("contact_phone", event.target.value)} />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="programme-related-documents">Related documents</Label>
                    <Textarea id="programme-related-documents" value={draft.related_documents} onChange={(event) => updateField("related_documents", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="programme-notes">Notes</Label>
                    <Textarea id="programme-notes" value={draft.notes} onChange={(event) => updateField("notes", event.target.value)} className="min-h-20" />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="programme-raw-eligibility">Raw eligibility data</Label>
                    <Textarea id="programme-raw-eligibility" value={draft.raw_eligibility_data} onChange={(event) => updateField("raw_eligibility_data", event.target.value)} className="min-h-24" />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="programme-confidence">Extraction confidence JSON</Label>
                    <Textarea id="programme-confidence" value={draft.extraction_confidence} onChange={(event) => updateField("extraction_confidence", event.target.value)} className="min-h-24 font-mono text-xs" />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="programme-snippets">Raw text snippets JSON</Label>
                    <Textarea id="programme-snippets" value={draft.raw_text_snippets} onChange={(event) => updateField("raw_text_snippets", event.target.value)} className="min-h-24 font-mono text-xs" />
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
              <p className="text-sm text-muted-foreground">
                Blank values fall back to the existing record. JSON fields must remain valid objects.
              </p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
                  Cancel
                </Button>
                <Button
                  onClick={() => onSave(programme, draft)}
                  disabled={saving}
                >
                  <Save className="mr-2 h-4 w-4" />
                  Save changes
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

const mapToProgram = (record?: FundingProgrammeRecord): FundingProgram | undefined => {
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
    approvalStatus: (record.approval_status ?? "pending") as FundingProgram["approvalStatus"],
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

function ConfidenceBreakdown({ values }: { values?: Record<string, number> | null }) {
  if (!values || Object.keys(values).length === 0) {
    return <p className="text-sm text-muted-foreground">Not captured</p>;
  }

  const entries = Object.entries(values)
    .filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]))
    .sort((a, b) => b[1] - a[1]);

  if (!entries.length) {
    return <p className="text-sm text-muted-foreground">Not captured</p>;
  }

  const average = entries.reduce((sum, [, value]) => sum + value, 0) / entries.length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-lg border bg-muted/20 px-3 py-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Average confidence</p>
          <p className="text-xs text-muted-foreground">{entries.length} extracted fields scored</p>
        </div>
        <Badge variant="outline" className="bg-background text-sm font-semibold">
          {formatConfidencePercent(average)}
        </Badge>
      </div>
      <div className="space-y-3">
        {entries.map(([field, value]) => (
          <div key={field} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-medium">{formatConfidenceLabel(field)}</p>
              <span className="text-xs font-semibold text-muted-foreground">{formatConfidencePercent(value)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${getConfidenceTone(value)}`}
                style={{ width: `${Math.max(6, Math.round(value * 100))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProgramDetailPage() {
  const { programId } = useParams<{ programId: string }>();
  const location = useLocation();
  const queryClient = useQueryClient();
  const isAdminRoute = location.pathname.startsWith("/admin");
  const adminBackTarget = new URLSearchParams(location.search).get("from") === "final-programmes" ? "/admin/final-programmes" : "/admin/programs";
  const backPath = isAdminRoute ? adminBackTarget : "/app/programs";

  const { data: record, isLoading } = useQuery({
    queryKey: ["program-detail", isAdminRoute ? "admin" : "app", programId],
    queryFn: async () => {
      if (!programId) return undefined;
      return isAdminRoute ? fetchProgrammeRecordBundle(programId) : fetchPublishedProgrammeRecordBundle(programId);
    },
    enabled: Boolean(programId)
  });

  const detailRecord = record?.record as FundingProgrammeRecord | undefined;
  const program = useMemo(() => mapToProgram(detailRecord), [detailRecord]);
  const [editorOpen, setEditorOpen] = useState(false);

  const saveMutation = useMutation({
    mutationFn: async ({ sourceRecord, draft }: { sourceRecord: FundingProgrammeRecord; draft: ProgrammeEditDraft }) => {
      if (!programId) {
        throw new Error("Missing program id.");
      }
      await apiClient.updateProgrammeRecord(programId, buildProgrammePatch(sourceRecord, draft));
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["program-detail", isAdminRoute ? "admin" : "app", programId] });
      toast.success("Programme updated");
      setEditorOpen(false);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to update programme.");
    }
  });

  const approveMutation = useMutation({
    mutationFn: async () => {
      if (!programId) {
        throw new Error("Missing program id.");
      }
      await apiClient.updateProgrammeRecord(programId, { approval_status: "approved" });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["program-detail", isAdminRoute ? "admin" : "app", programId] });
      toast.success("Programme published");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to publish programme.");
    }
  });

  if (!programId) {
    return <p>Missing program id.</p>;
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline" size="sm">
          <Link to={backPath}>
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
        <div className="flex items-center gap-2">
          <Badge variant={program.status === "active" ? "success" : "warning"}>{program.status}</Badge>
          <Badge variant={program.approvalStatus === "approved" ? "success" : program.approvalStatus === "pending" ? "warning" : "secondary"}>
            {program.approvalStatus}
          </Badge>
          {isAdminRoute ? (
            <>
              <Button variant="outline" size="sm" onClick={() => setEditorOpen(true)}>
                <Edit3 className="mr-2 h-4 w-4" />
                Edit programme
              </Button>
              <Button
                size="sm"
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending || detailRecord.approval_status === "approved"}
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                {detailRecord.approval_status === "approved" ? "Published" : "Approve & publish"}
              </Button>
            </>
          ) : null}
        </div>
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
            <DetailField label="Funding amount min" value={formatMoney(detailRecord.ticket_min)} />
            <DetailField label="Funding amount max" value={formatMoney(detailRecord.ticket_max)} />
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
            <DetailField label="Extraction confidence" value={<ConfidenceBreakdown values={detailRecord.extraction_confidence} />} />
            <DetailField label="Raw text snippets" value={detailRecord.raw_text_snippets ? <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">{JSON.stringify(detailRecord.raw_text_snippets, null, 2)}</pre> : "Not captured"} />
          </CardContent>
        </Card>
      </div>

      {isAdminRoute ? (
        <ProgrammeEditDialog
          programme={detailRecord}
          open={editorOpen}
          onOpenChange={setEditorOpen}
          onSave={(sourceRecord, draft) => saveMutation.mutate({ sourceRecord, draft })}
          saving={saveMutation.isPending}
        />
      ) : null}
    </div>
  );
}
