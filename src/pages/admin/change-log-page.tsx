import { format, formatDistanceToNow } from "date-fns";
import { History, Rocket, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/services/api/client";
import { cn } from "@/lib/utils";
import type { SystemChangeLogEntry } from "@/types/domain";

const areaLabel: Record<SystemChangeLogEntry["area"], string> = {
  scraper: "Scraper",
  admin: "Admin",
  data: "Data",
  matching: "Matching",
  platform: "Platform"
};

const areaTone: Record<SystemChangeLogEntry["area"], string> = {
  scraper: "bg-sky-50 text-sky-700 border-sky-200",
  admin: "bg-emerald-50 text-emerald-700 border-emerald-200",
  data: "bg-violet-50 text-violet-700 border-violet-200",
  matching: "bg-amber-50 text-amber-700 border-amber-200",
  platform: "bg-slate-50 text-slate-700 border-slate-200"
};

const impactTone: Record<SystemChangeLogEntry["impact"], string> = {
  high: "bg-rose-50 text-rose-700 border-rose-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-slate-50 text-slate-700 border-slate-200"
};

const impactLabel: Record<SystemChangeLogEntry["impact"], string> = {
  high: "High impact",
  medium: "Medium impact",
  low: "Low impact"
};

function ChangeMetric({
  label,
  value,
  caption,
  icon: Icon,
  tone
}: {
  label: string;
  value: string;
  caption: string;
  icon: typeof Rocket;
  tone: string;
}) {
  return (
    <Card className={cn("overflow-hidden border shadow-none", tone)}>
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

export function ChangeLogPage() {
  const { data: entries = [], isLoading } = useQuery({
    queryKey: ["system-change-log"],
    queryFn: apiClient.getSystemChangeLog
  });

  const highImpactCount = entries.filter((entry) => entry.impact === "high").length;
  const latestEntry = entries[0];
  const uniqueAreas = new Set(entries.map((entry) => entry.area)).size;

  return (
    <div className="space-y-8 pb-10">
      <Card className="overflow-hidden border-sky-200/70 bg-gradient-to-br from-sky-50 via-background to-emerald-50/50">
        <CardContent className="grid gap-6 p-6 xl:grid-cols-[1.25fr_0.75fr] xl:items-end">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
              <History className="h-3.5 w-3.5 text-sky-600" />
              System change log
            </div>
            <div className="space-y-2">
              <h1 className="text-3xl font-bold tracking-tight text-balance">Change Log</h1>
              <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
                A running admin-facing history of important system updates across scraping, review workflows, data structure, and platform operations.
              </p>
            </div>
          </div>

          <Card className="border-border/70 bg-background/80 shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Latest release note</CardTitle>
              <CardDescription>
                {latestEntry ? formatDistanceToNow(new Date(latestEntry.createdAt), { addSuffix: true }) : "No updates yet"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {latestEntry ? (
                <>
                  <p className="font-medium">{latestEntry.title}</p>
                  <p className="text-sm text-muted-foreground">{latestEntry.summary}</p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">System updates will appear here once entries are recorded.</p>
              )}
            </CardContent>
          </Card>
        </CardContent>
      </Card>

      <SectionHeader
        title="System history"
        description="Track notable product, scraper, and operational changes without leaving the admin workspace."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <ChangeMetric
          label="Logged changes"
          value={String(entries.length)}
          caption="Structured updates currently visible in the admin feed"
          icon={Sparkles}
          tone="border-sky-200/70 bg-gradient-to-br from-sky-50 via-background to-background"
        />
        <ChangeMetric
          label="High impact"
          value={String(highImpactCount)}
          caption="Changes likely to affect admin workflows or scraped data quality"
          icon={Rocket}
          tone="border-rose-200/70 bg-gradient-to-br from-rose-50 via-background to-background"
        />
        <ChangeMetric
          label="Areas touched"
          value={String(uniqueAreas)}
          caption="Distinct parts of the system represented in the feed"
          icon={Wrench}
          tone="border-emerald-200/70 bg-gradient-to-br from-emerald-50 via-background to-background"
        />
      </div>

      <Card className="overflow-hidden">
        <CardHeader className="border-b bg-muted/20">
          <CardTitle>Recent changes</CardTitle>
          <CardDescription>Latest entries first, with clear impact and scope markers.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-4 p-6">
              <div className="h-24 rounded-xl bg-muted/40" />
              <div className="h-24 rounded-xl bg-muted/30" />
              <div className="h-24 rounded-xl bg-muted/30" />
            </div>
          ) : entries.length === 0 ? (
            <div className="flex min-h-[240px] flex-col items-center justify-center gap-3 px-6 py-12 text-center">
              <div className="rounded-full border bg-muted/40 p-3">
                <ShieldCheck className="h-5 w-5 text-muted-foreground" />
              </div>
              <div className="space-y-1">
                <p className="text-base font-medium">No system changes logged yet</p>
                <p className="text-sm text-muted-foreground">Add structured change entries to keep admins informed about recent updates.</p>
              </div>
            </div>
          ) : (
            <div className="divide-y">
              {entries.map((entry) => (
                <article key={entry.id} className="grid gap-4 px-6 py-5 lg:grid-cols-[0.85fr_0.15fr]">
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className={cn("border", areaTone[entry.area])}>
                        {areaLabel[entry.area]}
                      </Badge>
                      <Badge variant="outline" className={cn("border", impactTone[entry.impact])}>
                        {impactLabel[entry.impact]}
                      </Badge>
                    </div>
                    <div className="space-y-1">
                      <h2 className="text-lg font-semibold tracking-tight">{entry.title}</h2>
                      <p className="max-w-3xl text-sm text-muted-foreground">{entry.summary}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {entry.highlights.map((highlight) => (
                        <Badge key={highlight} variant="secondary" className="bg-muted/40 font-normal">
                          {highlight}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1 text-sm text-muted-foreground lg:text-right">
                    <p className="font-medium text-foreground">{format(new Date(entry.createdAt), "PPP")}</p>
                    <p>{format(new Date(entry.createdAt), "p")}</p>
                    <p>{formatDistanceToNow(new Date(entry.createdAt), { addSuffix: true })}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
