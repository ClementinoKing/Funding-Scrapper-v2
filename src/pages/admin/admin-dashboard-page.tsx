import { useMemo, type ComponentType } from "react";
import { format, formatDistanceToNow } from "date-fns";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Database,
  Sparkles,
  Activity,
  History
} from "lucide-react";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiClient } from "@/services/api/client";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import type { FundingProgram } from "@/types/domain";

function MetricCard({
  label,
  value,
  caption,
  icon: Icon,
  tone
}: {
  label: string;
  value: string;
  caption: string;
  icon: ComponentType<{ className?: string }>;
  tone: "emerald" | "amber" | "slate" | "blue";
}) {
  const toneClasses =
    tone === "emerald"
      ? "from-emerald-50 via-background to-background border-emerald-200/70 text-emerald-700"
      : tone === "amber"
        ? "from-amber-50 via-background to-background border-amber-200/70 text-amber-700"
        : tone === "blue"
          ? "from-sky-50 via-background to-background border-sky-200/70 text-sky-700"
          : "from-slate-50 via-background to-background border-slate-200/70 text-slate-700";

  return (
    <Card className={cn("overflow-hidden border bg-gradient-to-br shadow-none", toneClasses)}>
      <CardContent className="flex items-start gap-3 p-4">
        <div className="rounded-xl border border-white/70 bg-background/90 p-2.5 shadow-sm">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{caption}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function getStatusVariant(status: string): "success" | "warning" | "secondary" {
  if (status === "success" || status === "completed") {
    return "success";
  }
  if (status === "failed" || status === "partial") {
    return "warning";
  }
  return "secondary";
}

function getStatusTone(status: string): string {
  if (status === "success" || status === "completed") {
    return "bg-emerald-50 text-emerald-700 border-emerald-200";
  }
  if (status === "failed") {
    return "bg-amber-50 text-amber-700 border-amber-200";
  }
  if (status === "partial") {
    return "bg-orange-50 text-orange-700 border-orange-200";
  }
  return "bg-slate-50 text-slate-700 border-slate-200";
}

const formatMoney = (value?: number | null): string => {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "Not specified";
  }
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    maximumFractionDigits: 0
  }).format(value);
};

const formatFundingRange = (min?: number | null, max?: number | null): string => {
  const lower = formatMoney(min);
  const upper = formatMoney(max);

  if (lower === "Not specified" && upper === "Not specified") {
    return "Not specified";
  }

  if (max === undefined || max === null || Number.isNaN(max)) {
    return lower;
  }

  return `${lower} - ${upper}`;
};

const getProgrammeStatusVariant = (status: FundingProgram["status"]): "success" | "warning" | "secondary" =>
  status === "active" ? "success" : status === "closing_soon" ? "warning" : "secondary";

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const { data: runs = [] } = useQuery({
    queryKey: ["scrape-runs"],
    queryFn: apiClient.getScrapeRuns
  });

  const { data: finalProgrammes = [] } = useQuery({
    queryKey: ["published-programmes"],
    queryFn: apiClient.getPrograms
  });
  const { data: systemChanges = [] } = useQuery({
    queryKey: ["system-change-log"],
    queryFn: apiClient.getSystemChangeLog
  });

  const failedCount = runs.filter((run) => run.status === "failed" || run.status === "partial").length;
  const latestRuns = runs.slice(0, 5);
  const featuredProgrammes = useMemo(
    () => [...finalProgrammes].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()),
    [finalProgrammes]
  );
  const completedRuns = runs.filter((run) => run.completedAt);
  const successCount = runs.filter((run) => run.status === "success").length;
  const attentionRate = runs.length ? Math.round((failedCount / runs.length) * 100) : 0;
  const latestSystemChanges = systemChanges.slice(0, 3);

  const statusSummary = useMemo(
    () => [
      { label: "Success", count: successCount, tone: "emerald" as const },
      { label: "Partial", count: runs.filter((run) => run.status === "partial").length, tone: "amber" as const },
      { label: "Failed", count: runs.filter((run) => run.status === "failed").length, tone: "slate" as const }
    ],
    [failedCount, runs, successCount]
  );

  return (
    <div className="space-y-8 pb-10">
      <Card className="overflow-hidden border-emerald-200/70 bg-gradient-to-br from-emerald-50 via-background to-sky-50/60">
        <CardContent className="grid gap-6 p-6 xl:grid-cols-[1.3fr_0.9fr] xl:items-end">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
              <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
              Live admin overview
            </div>
            <div className="space-y-2">
              <h1 className="text-3xl font-bold tracking-tight text-balance">Admin Dashboard</h1>
              <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
                A quick pulse on scraper health, queue pressure, and where the system needs human attention next.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary" className="gap-1.5">
                <Database className="h-3.5 w-3.5" />
                {runs.length} scrape runs
              </Badge>
              <Badge variant="outline" className="gap-1.5 bg-background/80">
                <AlertTriangle className="h-3.5 w-3.5" />
                {failedCount} need attention
              </Badge>
              <Badge variant="outline" className="gap-1.5 bg-background/80">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {completedRuns.length} completed
              </Badge>
            </div>
          </div>

          <Card className="border-border/70 bg-background/80 shadow-none backdrop-blur">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">System pulse</CardTitle>
              <CardDescription>Fast snapshot of current scraper health and attention pressure.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between rounded-lg border bg-muted/20 px-4 py-3">
                <div>
                  <p className="text-sm font-medium">Attention rate</p>
                  <p className="text-xs text-muted-foreground">Failed or partial runs</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-semibold">{attentionRate}%</p>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {statusSummary.map((item) => (
                  <div key={item.label} className="rounded-lg border bg-background/70 p-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{item.label}</p>
                    <p className={cn("mt-1 text-xl font-semibold", item.tone === "emerald" ? "text-emerald-700" : item.tone === "amber" ? "text-amber-700" : "text-slate-700")}>
                      {item.count}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </CardContent>
      </Card>

      <SectionHeader
        title="Admin Dashboard"
        description="Monitor scraper health, content review queues, and matching quality metrics."
      />

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard
          label="Scrape runs"
          value={String(runs.length)}
          caption="Loaded from scrape_runs"
          icon={Activity}
          tone="blue"
        />
        <MetricCard
          label="Attention required"
          value={String(failedCount)}
          caption="Partial or failed sources"
          icon={AlertTriangle}
          tone="amber"
        />
        <MetricCard
          label="Completed runs"
          value={String(completedRuns.length)}
          caption="Finished runs with timestamps"
          icon={CheckCircle2}
          tone="emerald"
        />
        <MetricCard
          label="Manual interventions"
          value="3"
          caption="Unmatched high-potential applicants"
          icon={ArrowUpRight}
          tone="slate"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-muted/20">
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>Recent scraper runs</CardTitle>
                <CardDescription>Latest runs, timestamped and color-coded by status.</CardDescription>
              </div>
              <Badge variant="secondary">{latestRuns.length} shown</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table className="min-w-[860px]">
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead className="pl-6">Source</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Found / Stored / Flagged</TableHead>
                    <TableHead className="pr-6">Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {latestRuns.map((run) => (
                    <TableRow
                      key={run.id}
                      className={cn(
                        "transition-colors",
                        run.status === "failed" || run.status === "partial" ? "bg-amber-50/30 hover:bg-amber-50/50" : "hover:bg-muted/40"
                      )}
                    >
                      <TableCell className="pl-6">
                        <div className="space-y-1">
                          <p className="font-medium">{run.sourceName}</p>
                          <p className="text-xs text-muted-foreground">{run.id}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <p>{format(new Date(run.startedAt), "PPP p")}</p>
                          <p className="text-xs text-muted-foreground">
                            {formatDistanceToNow(new Date(run.startedAt), { addSuffix: true })}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={getStatusVariant(run.status)} className={cn("border", getStatusTone(run.status))}>
                          {run.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium">
                        {run.recordsFound}/{run.recordsStored}/{run.recordsFlagged}
                      </TableCell>
                      <TableCell className="pr-6 text-muted-foreground">{run.errorSummary ?? "-"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-muted/20">
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>Final programmes</CardTitle>
                <CardDescription>Approved programmes ready to be shown to applicants.</CardDescription>
              </div>
              <Badge variant="success">{featuredProgrammes.length} shown</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {featuredProgrammes.length === 0 ? (
              <div className="flex min-h-[260px] flex-col items-center justify-center gap-3 px-6 py-12 text-center">
                <div className="rounded-full border bg-emerald-50 p-3">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                </div>
                <div className="space-y-1">
                  <p className="text-base font-medium">No final programmes yet</p>
                  <p className="text-sm text-muted-foreground">
                    Approve programmes from the review queue and they will appear here automatically.
                  </p>
                </div>
                <Button variant="outline" asChild>
                  <a href="/admin/programs" className="inline-flex items-center gap-2">
                    Open review queue
                    <ArrowRight className="h-4 w-4" />
                  </a>
                </Button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table className="min-w-[720px]">
                  <TableHeader>
                    <TableRow className="bg-emerald-50/40 hover:bg-emerald-50/40">
                      <TableHead className="pl-6">Programme</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>Funding range</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {featuredProgrammes.map((programme) => (
                      <TableRow
                        key={programme.id}
                        className="cursor-pointer hover:bg-emerald-50/30"
                        onClick={() => navigate(`/admin/programs/${programme.id}?from=final-programmes`)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            navigate(`/admin/programs/${programme.id}?from=final-programmes`);
                          }
                        }}
                        tabIndex={0}
                        role="button"
                        aria-label={`Open ${programme.title}`}
                      >
                        <TableCell className="pl-6">
                          <div className="space-y-1">
                            <p className="font-medium">{programme.title}</p>
                            <p className="text-xs text-muted-foreground">{programme.id}</p>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{programme.providerName}</TableCell>
                        <TableCell className="text-sm">
                          <div className="space-y-0.5">
                            <p className="font-medium">{formatFundingRange(programme.amountMin, programme.amountMax)}</p>
                            <p className="text-xs text-muted-foreground">
                              Updated {formatDistanceToNow(new Date(programme.updatedAt), { addSuffix: true })}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={getProgrammeStatusVariant(programme.status)} className="capitalize">
                            {programme.status.replace("_", " ")}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            <div className="flex items-center justify-between gap-3 border-t p-6">
              <p className="text-sm text-muted-foreground">Showing the most recent published programmes in the catalogue.</p>
              <Button variant="ghost" className="h-9 px-0 text-emerald-700 hover:bg-transparent hover:text-emerald-800" asChild>
                <a href="/admin/final-programmes" className="inline-flex items-center gap-2">
                  Open full list
                  <ArrowRight className="h-4 w-4" />
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <CardHeader className="border-b bg-muted/20">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>System change log</CardTitle>
              <CardDescription>Recent product, scraper, and data-layer updates visible to the admin team.</CardDescription>
            </div>
            <Badge variant="secondary">{systemChanges.length} logged</Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {latestSystemChanges.length === 0 ? (
            <div className="flex min-h-[220px] flex-col items-center justify-center gap-3 px-6 py-12 text-center">
              <div className="rounded-full border bg-muted/40 p-3">
                <History className="h-5 w-5 text-muted-foreground" />
              </div>
              <div className="space-y-1">
                <p className="text-base font-medium">No changes logged yet</p>
                <p className="text-sm text-muted-foreground">Recent system updates will appear here once entries are recorded.</p>
              </div>
            </div>
          ) : (
            <div className="divide-y">
              {latestSystemChanges.map((entry) => (
                <div key={entry.id} className="flex flex-col gap-3 px-6 py-4 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="bg-background/90">
                        {entry.area}
                      </Badge>
                      <Badge variant="outline" className="bg-background/90">
                        {entry.impact} impact
                      </Badge>
                    </div>
                    <p className="font-medium">{entry.title}</p>
                    <p className="max-w-3xl text-sm text-muted-foreground">{entry.summary}</p>
                  </div>
                  <div className="shrink-0 text-sm text-muted-foreground md:text-right">
                    <p>{format(new Date(entry.createdAt), "PPP")}</p>
                    <p>{formatDistanceToNow(new Date(entry.createdAt), { addSuffix: true })}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between gap-3 border-t p-6">
            <p className="text-sm text-muted-foreground">Open the full change log to review detailed highlights across the system.</p>
            <Button variant="ghost" className="h-9 px-0 text-sky-700 hover:bg-transparent hover:text-sky-800" asChild>
              <a href="/admin/change-log" className="inline-flex items-center gap-2">
                Open full change log
                <ArrowRight className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
