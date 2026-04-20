import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  FileWarning,
  Globe,
  TriangleAlert
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  formatScrapeRunDuration,
  formatScrapeRunStatus,
  getScrapeRunFetchRate,
  getScrapeRunIssueCount,
  getScrapeRunStatusTone,
  getScrapeRunStatusVariant
} from "@/lib/scrape-runs";
import { apiClient } from "@/services/api/client";

function DetailMetric({
  label,
  value,
  caption
}: {
  label: string;
  value: string;
  caption: string;
}) {
  return (
    <div className="rounded-xl border bg-background/80 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{caption}</p>
    </div>
  );
}

export function ScrapeRunDetailPage() {
  const { runId = "" } = useParams();
  const { data: run, isLoading, error } = useQuery({
    queryKey: ["scrape-run", runId],
    queryFn: () => apiClient.getScrapeRunById(runId),
    enabled: Boolean(runId)
  });

  if (isLoading) {
    return <div className="py-12 text-sm text-muted-foreground">Loading scrape run details...</div>;
  }

  if (error) {
    return (
      <Card className="border-rose-200 bg-rose-50/60">
        <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium text-rose-800">Failed to load scrape run details.</p>
            <p className="text-sm text-rose-700">Please go back to the runs page and try again.</p>
          </div>
          <Button variant="outline" asChild>
            <Link to="/admin/scraper-runs">Back to runs</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!run) {
    return (
      <Card>
        <CardContent className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium">Scrape run not found.</p>
            <p className="text-sm text-muted-foreground">
              The requested run may have been removed or is no longer in the current dataset.
            </p>
          </div>
          <Button variant="outline" asChild>
            <Link to="/admin/scraper-runs">Back to runs</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const issueCount = getScrapeRunIssueCount(run);
  const fetchRate = getScrapeRunFetchRate(run);
  const qualityChecks = [
    {
      label: "Low-confidence extraction",
      value: run.recordsFlagged,
      description:
        run.lowConfidenceThreshold !== undefined
          ? `Threshold ${Math.round(run.lowConfidenceThreshold * 100)}% confidence`
          : "Records needing manual review"
    },
    {
      label: "Missing programme name",
      value: run.recordsWithMissingProgramName,
      description: "Potentially incomplete programme titles"
    },
    {
      label: "Missing funder name",
      value: run.recordsWithMissingFunderName,
      description: "Records where provider attribution was not captured"
    },
    {
      label: "Unknown funding type",
      value: run.recordsWithUnknownFundingType,
      description: "Programmes without a clear funding type classification"
    },
    {
      label: "No application route",
      value: run.recordsWithNoApplicationRoute,
      description: "Programmes missing a clear application path or link"
    }
  ];

  return (
    <div className="space-y-8 pb-10">
      <Card className="overflow-hidden border-sky-200/70 bg-gradient-to-br from-sky-50 via-background to-emerald-50/60">
        <CardContent className="grid gap-6 p-6 xl:grid-cols-[1.3fr_0.9fr] xl:items-end">
          <div className="space-y-4">
            <Button variant="ghost" size="sm" asChild className="w-fit px-0 text-muted-foreground hover:bg-transparent">
              <Link to="/admin/scraper-runs" className="inline-flex items-center gap-2">
                <ArrowLeft className="h-4 w-4" />
                Back to scraper runs
              </Link>
            </Button>
            <div className="space-y-2">
              <h1 className="text-3xl font-bold tracking-tight text-balance">{run.sourceName}</h1>
              <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
                Full telemetry for run <span className="font-medium text-foreground">{run.id}</span>, including crawl coverage, programme throughput, and quality warnings.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge
                variant={getScrapeRunStatusVariant(run.status)}
                className={cn("gap-1.5 border", getScrapeRunStatusTone(run.status))}
              >
                {formatScrapeRunStatus(run.status)}
              </Badge>
              <Badge variant="outline" className="gap-1.5 bg-background/80">
                <Clock3 className="h-3.5 w-3.5" />
                {formatScrapeRunDuration(run)}
              </Badge>
              <Badge variant="outline" className="gap-1.5 bg-background/80">
                <Globe className="h-3.5 w-3.5" />
                {run.seedUrls.length} seed URLs
              </Badge>
            </div>
          </div>

          <Card className="border-border/70 bg-background/80 shadow-none backdrop-blur">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Run summary</CardTitle>
              <CardDescription>Started {formatDistanceToNow(new Date(run.startedAt), { addSuffix: true })}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border bg-muted/20 px-4 py-3">
                <div>
                  <p className="text-sm font-medium">Fetch success rate</p>
                  <p className="text-xs text-muted-foreground">Pages fetched successfully out of all crawled URLs</p>
                </div>
                <p className="text-2xl font-semibold">{fetchRate}%</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border bg-background/70 p-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Warnings</p>
                  <p className="mt-1 text-xl font-semibold text-amber-700">{run.warnings.length}</p>
                </div>
                <div className="rounded-lg border bg-background/70 p-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Errors</p>
                  <p className="mt-1 text-xl font-semibold text-rose-700">{run.errors.length}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-4">
        <DetailMetric
          label="URLs crawled"
          value={String(run.urlsCrawled)}
          caption={`${run.pagesFetchedSuccessfully} fetched successfully`}
        />
        <DetailMetric
          label="Pages failed"
          value={String(run.pagesFailed)}
          caption="Fetches that failed after retries"
        />
        <DetailMetric
          label="Programmes stored"
          value={String(run.recordsStored)}
          caption={`${run.recordsFound} extracted before dedupe`}
        />
        <DetailMetric
          label="Issues recorded"
          value={String(issueCount)}
          caption="Combined warnings and errors captured for this run"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-muted/20">
            <CardTitle>Timeline and inputs</CardTitle>
            <CardDescription>When the run executed and which source URLs kicked it off.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 p-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Started</p>
                <p className="mt-1 font-medium">{format(new Date(run.startedAt), "PPP p")}</p>
              </div>
              <div className="rounded-xl border p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Completed</p>
                <p className="mt-1 font-medium">
                  {run.completedAt ? format(new Date(run.completedAt), "PPP p") : "Still running"}
                </p>
              </div>
            </div>

            <div className="rounded-xl border p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">Seed URLs</p>
                  <p className="text-sm text-muted-foreground">Entry points used to begin discovery for this run.</p>
                </div>
                <Badge variant="secondary">{run.seedUrls.length}</Badge>
              </div>
              <div className="mt-4 space-y-2">
                {run.seedUrls.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No seed URLs were captured for this run.</p>
                ) : (
                  run.seedUrls.map((url) => (
                    <a
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-lg border bg-muted/20 px-3 py-2 text-sm text-foreground transition hover:bg-muted/40"
                    >
                      {url}
                    </a>
                  ))
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-muted/20">
            <CardTitle>Quality diagnostics</CardTitle>
            <CardDescription>Signals that point to records needing review or extractor tuning.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 p-6 sm:grid-cols-2">
            {qualityChecks.map((item) => (
              <div key={item.label} className="rounded-xl border p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{item.label}</p>
                <p className="mt-1 text-2xl font-semibold tracking-tight">{item.value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-muted/20">
            <div className="flex items-center gap-2">
              <TriangleAlert className="h-4 w-4 text-amber-600" />
              <div>
                <CardTitle>Warnings</CardTitle>
                <CardDescription>Recoverable issues that may still affect data quality.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 p-6">
            {run.warnings.length === 0 ? (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 text-sm text-emerald-800">
                No warnings were recorded for this run.
              </div>
            ) : (
              run.warnings.map((warning) => (
                <div key={warning} className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 text-sm text-amber-900">
                  {warning}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-muted/20">
            <div className="flex items-center gap-2">
              <FileWarning className="h-4 w-4 text-rose-600" />
              <div>
                <CardTitle>Errors</CardTitle>
                <CardDescription>Failures that likely require site rule changes, retries, or investigation.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 p-6">
            {run.errors.length === 0 ? (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
                <div className="flex items-center gap-2 text-sm text-emerald-800">
                  <CheckCircle2 className="h-4 w-4" />
                  No hard errors were recorded for this run.
                </div>
              </div>
            ) : (
              run.errors.map((issue) => (
                <div key={issue} className="rounded-xl border border-rose-200 bg-rose-50/60 p-4 text-sm text-rose-900">
                  {issue}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {run.errorSummary ? (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="flex items-start gap-3 p-6">
            <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-700" />
            <div>
              <p className="font-medium text-amber-900">Primary incident summary</p>
              <p className="mt-1 text-sm text-amber-800">{run.errorSummary}</p>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
