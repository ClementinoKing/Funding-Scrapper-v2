import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { format, formatDistanceToNow } from "date-fns";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, Database } from "lucide-react";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  formatScrapeRunDuration,
  formatScrapeRunStatus,
  getScrapeRunIssueCount,
  getScrapeRunStatusTone,
  getScrapeRunStatusVariant
} from "@/lib/scrape-runs";
import { apiClient } from "@/services/api/client";
import type { ScrapeRun } from "@/types/domain";

function RunRow({ run }: { run: ScrapeRun }) {
  const issueCount = getScrapeRunIssueCount(run);

  return (
    <TableRow
      className={cn(
        "transition-colors",
        run.status === "failed"
          ? "bg-rose-50/35 hover:bg-rose-50/55"
          : run.status === "partial"
            ? "bg-amber-50/25 hover:bg-amber-50/45"
            : "hover:bg-muted/30"
      )}
    >
      <TableCell className="pl-6">
        <div className="space-y-1">
          <p className="font-medium text-foreground">{run.sourceName}</p>
          <p className="text-xs text-muted-foreground">{run.id}</p>
        </div>
      </TableCell>
      <TableCell>
        <div className="space-y-1">
          <p className="font-medium">{format(new Date(run.startedAt), "MMM d, yyyy")}</p>
          <p className="text-xs text-muted-foreground">
            {format(new Date(run.startedAt), "p")} • {formatDistanceToNow(new Date(run.startedAt), { addSuffix: true })}
          </p>
        </div>
      </TableCell>
      <TableCell className="font-medium">{formatScrapeRunDuration(run)}</TableCell>
      <TableCell>
        <Badge
          variant={getScrapeRunStatusVariant(run.status)}
          className={cn("border font-medium", getScrapeRunStatusTone(run.status))}
        >
          {formatScrapeRunStatus(run.status)}
        </Badge>
      </TableCell>
      <TableCell>
        <div className="space-y-1">
          <p className="font-medium">
            {run.recordsFound} / {run.recordsStored} / {run.recordsFlagged}
          </p>
          <p className="text-xs text-muted-foreground">Found / stored / flagged</p>
        </div>
      </TableCell>
      <TableCell>
        {issueCount > 0 ? (
          <div className="space-y-1">
            <p className="font-medium">{issueCount} issue{issueCount === 1 ? "" : "s"}</p>
            <p className="max-w-[360px] truncate text-xs text-muted-foreground">
              {run.errorSummary ?? "Warnings or errors were recorded for this run."}
            </p>
          </div>
        ) : (
          <span className="text-sm text-muted-foreground">No issues</span>
        )}
      </TableCell>
      <TableCell className="pr-6 text-right">
        <Button variant="ghost" size="sm" asChild>
          <Link to={run.id} className="inline-flex items-center gap-2">
            View details
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </TableCell>
    </TableRow>
  );
}

export function ScraperRunsPage() {
  const { data: runs = [], isLoading, error } = useQuery({
    queryKey: ["scrape-runs"],
    queryFn: apiClient.getScrapeRuns
  });

  const successfulRuns = runs.filter((run) => run.status === "success").length;
  const attentionRuns = runs.filter((run) => run.status === "failed" || run.status === "partial").length;
  const totalStored = runs.reduce((sum, run) => sum + run.recordsStored, 0);

  return (
    <div className="space-y-6 pb-10">
      <div className="space-y-4">
        <SectionHeader
          title="Scraper Runs"
          description="Review recent scrape activity, scan for failures quickly, and open a run for full diagnostics."
        />

        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary" className="gap-1.5 px-3 py-1">
            <Clock3 className="h-3.5 w-3.5" />
            {runs.length} total runs
          </Badge>
          <Badge variant="outline" className="gap-1.5 bg-background px-3 py-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            {successfulRuns} successful
          </Badge>
          <Badge variant="outline" className="gap-1.5 bg-background px-3 py-1">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
            {attentionRuns} need attention
          </Badge>
          <Badge variant="outline" className="gap-1.5 bg-background px-3 py-1">
            <Database className="h-3.5 w-3.5 text-sky-600" />
            {totalStored} stored
          </Badge>
        </div>
      </div>

      <Card className="overflow-hidden border-border/80 shadow-sm">
        <CardHeader className="border-b bg-muted/15">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Run History</CardTitle>
              <CardDescription>
                Keep this page focused on quick scanning. Open any run to inspect crawl health, warnings, and raw details.
              </CardDescription>
            </div>
            <Badge variant="secondary" className="shrink-0">
              {runs.length} loaded
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="px-6 py-12 text-sm text-muted-foreground">Loading scraper runs...</div>
          ) : error ? (
            <div className="px-6 py-12 text-sm text-rose-600">
              Failed to load scraper runs. Please refresh and try again.
            </div>
          ) : runs.length === 0 ? (
            <div className="px-6 py-12 text-sm text-muted-foreground">
              No scrape runs are available yet.
            </div>
          ) : (
            <Table className="min-w-[980px]">
              <TableHeader>
                <TableRow className="bg-muted/20 hover:bg-muted/20">
                  <TableHead className="pl-6">Source</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Programmes</TableHead>
                  <TableHead>Issue summary</TableHead>
                  <TableHead className="pr-6 text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <RunRow key={run.id} run={run} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
