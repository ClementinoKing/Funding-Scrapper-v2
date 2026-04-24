import { useEffect, useMemo, useState, type ComponentType } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  Clock3,
  Database,
  Filter,
  Search,
  X
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { fetchProgramsFromDatabase } from "@/services/api/client";
import { getScoreTone, rankProgrammes } from "@/lib/fundingScoring";
import { cn } from "@/lib/utils";
import type { ScoredProgramme, ScrapedFundingProgramme } from "@/types/funding";

const getScoreVariant = (score: number): "success" | "warning" | "secondary" =>
  getScoreTone(score) === "high" ? "success" : getScoreTone(score) === "medium" ? "warning" : "secondary";

const getApprovalVariant = (status: ScrapedFundingProgramme["approvalStatus"]): "success" | "warning" | "secondary" =>
  status === "approved" ? "success" : status === "pending" ? "warning" : "secondary";

const getAiEnrichmentVariant = (programme: ScrapedFundingProgramme): "success" | "secondary" =>
  programme.ai_enriched ? "success" : "secondary";

const getAiEnrichmentLabel = (programme: ScrapedFundingProgramme): string =>
  programme.ai_enriched ? "AI enriched" : "Deterministic";

const getRowClassName = (programme: ScoredProgramme): string => {
  if (programme.approvalStatus === "approved") {
    return "border-l-4 border-l-emerald-500/70 bg-emerald-50/30";
  }
  if (programme.scoreBand === "high") {
    return "border-l-4 border-l-emerald-500/60 bg-emerald-50/20";
  }
  if (programme.scoreBand === "medium") {
    return "border-l-4 border-l-amber-500/60 bg-amber-50/20";
  }
  return "";
};

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

function QueueMetric({
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

function ReviewProgrammesTable({ programmes }: { programmes: ScoredProgramme[] }) {
  const navigate = useNavigate();

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-muted/20">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>Review queue</CardTitle>
            <CardDescription>Records that still need a human pass before they can be published.</CardDescription>
          </div>
          <Badge variant="secondary">{programmes.length} programmes</Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {programmes.length === 0 ? (
          <div className="flex min-h-[220px] flex-col items-center justify-center gap-3 px-6 py-12 text-center">
            <div className="rounded-full border bg-muted/40 p-3">
              <Clock3 className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="space-y-1">
              <p className="text-base font-medium">No programmes in this lane yet</p>
              <p className="text-sm text-muted-foreground">
                Once the filters or approval states change, records will appear here automatically.
              </p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table className="min-w-[1200px]">
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  <TableHead className="pl-6">Programme</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Quality</TableHead>
                  <TableHead>Approval</TableHead>
                  <TableHead>AI</TableHead>
                  <TableHead>Funding range</TableHead>
                  <TableHead>Signals</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {programmes.map((program) => (
	                  <TableRow
                    key={program.id}
                    className={cn(
                      "group cursor-pointer transition-all hover:bg-muted/40 focus-within:bg-muted/40",
                      getRowClassName(program)
                    )}
                    onClick={() => navigate(`/admin/programs/${program.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        navigate(`/admin/programs/${program.id}`);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Open ${program.title}`}
	                  >
	                    <TableCell className="pl-6 align-middle">
	                      <div className="space-y-2">
	                        <p className="max-w-[320px] font-medium leading-snug">{program.title}</p>
	                        {program.parent_programme_name ? (
	                          <Badge
	                            variant="outline"
	                            className="max-w-fit bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 border-sky-200"
	                            title={`Parent programme: ${program.parent_programme_name}`}
	                          >
	                            {program.parent_programme_name}
	                          </Badge>
	                        ) : null}
	                      </div>
	                    </TableCell>
                    <TableCell className="align-middle text-sm text-muted-foreground">{program.providerName}</TableCell>
                    <TableCell className="align-middle">
                      <Badge variant={getScoreVariant(program.importanceScore)} className="min-w-[56px] justify-center">
                        {program.importanceScore}%
                      </Badge>
                    </TableCell>
                    <TableCell className="align-middle">
                      <Badge variant={getScoreVariant(program.qualityScore)} className="min-w-[56px] justify-center">
                        {program.qualityScore}%
                      </Badge>
                    </TableCell>
                    <TableCell className="align-middle">
                      <Badge variant={getApprovalVariant(program.approvalStatus)}>{program.approvalStatus}</Badge>
                    </TableCell>
                    <TableCell className="align-middle">
                      <Badge variant={getAiEnrichmentVariant(program)}>{getAiEnrichmentLabel(program)}</Badge>
                    </TableCell>
                    <TableCell className="align-middle text-sm">
                      <div className="space-y-0.5">
                        <p className="font-medium">{formatFundingRange(program.amountMin, program.amountMax)}</p>
                        <p className="text-xs text-muted-foreground">Budget band</p>
                      </div>
                    </TableCell>
                    <TableCell className="align-middle">
                      <div className="flex max-w-[240px] flex-wrap gap-1">
                        {program.reasonTags.slice(0, 3).map((reason) => (
                          <Badge
                            key={reason}
                            variant="outline"
                            title={reason}
                            className="bg-background/90 px-2 py-0.5 text-[11px] font-normal"
                          >
                            {reason}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function ProgramReviewPage() {
  const [programs, setPrograms] = useState<ScrapedFundingProgramme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [laneFilter, setLaneFilter] = useState<"all" | "ready" | "review">("all");
  const [approvalFilter, setApprovalFilter] = useState<"all" | "approved" | "pending" | "draft" | "rejected">("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const records = await fetchProgramsFromDatabase();
        if (!active) return;
        setPrograms(records);
      } catch (loadError) {
        if (!active) return;
        const message = loadError instanceof Error ? loadError.message : "Failed to load programmes from Supabase.";
        setError(message);
        setPrograms([]);
        toast.error(message);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, []);

  const scoredPrograms = useMemo(() => rankProgrammes(programs), [programs]);

  const readyForApproval = useMemo(
    () =>
      scoredPrograms.filter(
        (program) => program.approvalStatus !== "approved" && (program.scoreBand === "high" || program.importanceScore >= 70)
      ),
    [scoredPrograms]
  );
  const reviewQueue = useMemo(
    () =>
      scoredPrograms.filter(
        (program) => program.approvalStatus !== "approved" && !(program.scoreBand === "high" || program.importanceScore >= 70)
      ),
    [scoredPrograms]
  );
  const finalPrograms = useMemo(
    () => scoredPrograms.filter((program) => program.approvalStatus === "approved"),
    [scoredPrograms]
  );
  const providerOptions = useMemo(
    () =>
      Array.from(new Set(scoredPrograms.map((program) => program.providerName?.trim() || "Unknown provider").filter(Boolean))).sort(
        (left, right) => left.localeCompare(right)
      ),
    [scoredPrograms]
  );

  const filteredPrograms = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return scoredPrograms.filter((program) => {
      const providerName = program.providerName?.trim() || "Unknown provider";
      const laneMatches =
        laneFilter === "all" ||
        (laneFilter === "ready" && program.approvalStatus !== "approved" && (program.scoreBand === "high" || program.importanceScore >= 70)) ||
        (laneFilter === "review" &&
          program.approvalStatus !== "approved" &&
          !(program.scoreBand === "high" || program.importanceScore >= 70));

      const approvalMatches = approvalFilter === "all" || program.approvalStatus === approvalFilter;
      const providerMatches = providerFilter === "all" || providerName === providerFilter;
	      const queryMatches =
	        normalizedQuery.length === 0 ||
	        [program.title, providerName, program.parent_programme_name, ...(program.reasonTags ?? [])]
	          .filter(Boolean)
	          .some((value) => String(value).toLowerCase().includes(normalizedQuery));

      return laneMatches && approvalMatches && providerMatches && queryMatches;
    });
  }, [approvalFilter, laneFilter, providerFilter, query, scoredPrograms]);

  const filteredReadyForApproval = useMemo(
    () =>
      filteredPrograms.filter(
        (program) => program.approvalStatus !== "approved" && (program.scoreBand === "high" || program.importanceScore >= 70)
      ),
    [filteredPrograms]
  );
  const filteredReviewQueue = useMemo(
    () =>
      filteredPrograms.filter(
        (program) => program.approvalStatus !== "approved" && !(program.scoreBand === "high" || program.importanceScore >= 70)
      ),
    [filteredPrograms]
  );
  const hasActiveFilters =
    query.trim().length > 0 || laneFilter !== "all" || approvalFilter !== "all" || providerFilter !== "all";

  const clearFilters = () => {
    setQuery("");
    setLaneFilter("all");
    setApprovalFilter("all");
    setProviderFilter("all");
  };

  return (
    <div className="space-y-8 pb-10">
      <div className="grid gap-4 md:grid-cols-3">
        <QueueMetric
          label="Ready to approve"
          value={String(readyForApproval.length)}
          caption="High-confidence programmes still waiting on approval"
          icon={Clock3}
          tone="amber"
        />
        <QueueMetric
          label="Needs review"
          value={String(reviewQueue.length)}
          caption="Useful records that need a closer look"
          icon={Database}
          tone="blue"
        />
        <QueueMetric
          label="Final programmes"
          value={String(finalPrograms.length)}
          caption="Approved and visible to applicants"
          icon={CheckCircle2}
          tone="emerald"
        />
      </div>

      <Card className="border-muted/70">
        <CardContent className="p-3">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search programme, provider, or signal"
                className="h-10 pl-9"
              />
            </div>

            <Button
              type="button"
              variant="outline"
              size="icon"
              className="relative h-10 w-10 shrink-0"
              onClick={() => setFiltersOpen(true)}
              aria-label="Open filters"
              title="Open filters"
            >
              <Filter className="h-4 w-4" />
              {hasActiveFilters ? <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-emerald-500" /> : null}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={filtersOpen} onOpenChange={setFiltersOpen}>
        <DialogContent className="left-auto right-0 top-0 h-full w-full max-w-md translate-x-0 translate-y-0 rounded-none border-l p-0">
          <div className="flex h-full flex-col">
            <DialogHeader className="border-b px-6 py-5">
              <DialogTitle>Filters</DialogTitle>
              <DialogDescription>Refine the queue by lane, approval status, and provider.</DialogDescription>
            </DialogHeader>

            <div className="flex-1 space-y-5 overflow-y-auto px-6 py-5">
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Lane</p>
                <Select value={laneFilter} onValueChange={(value) => setLaneFilter(value as typeof laneFilter)}>
                  <SelectTrigger className="h-10">
                    <SelectValue placeholder="Filter lane" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All lanes</SelectItem>
                    <SelectItem value="ready">Ready to approve</SelectItem>
                    <SelectItem value="review">Needs review</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Approval</p>
                <Select value={approvalFilter} onValueChange={(value) => setApprovalFilter(value as typeof approvalFilter)}>
                  <SelectTrigger className="h-10">
                    <SelectValue placeholder="Filter approval" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All approval states</SelectItem>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="rejected">Rejected</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Provider</p>
                <Select value={providerFilter} onValueChange={setProviderFilter}>
                  <SelectTrigger className="h-10">
                    <SelectValue placeholder="Filter provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All providers</SelectItem>
                    {providerOptions.map((providerName) => (
                      <SelectItem key={providerName} value={providerName}>
                        {providerName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="border-t px-6 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">
                  {hasActiveFilters ? "Filters are active." : "No filters applied."}
                </p>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" onClick={clearFilters} disabled={!hasActiveFilters} className="h-10">
                    <X className="h-4 w-4" />
                    Clear
                  </Button>
                  <Button type="button" onClick={() => setFiltersOpen(false)} className="h-10">
                    Done
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>
      ) : null}

      {loading ? (
        <Card className="overflow-hidden">
          <CardHeader className="border-b bg-muted/20">
            <CardTitle className="text-lg">Loading programmes</CardTitle>
            <CardDescription>Fetching the latest Supabase-backed records and scoring them for review.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 p-6">
            <div className="h-10 rounded-md bg-muted/50" />
            <div className="h-16 rounded-md bg-muted/30" />
            <div className="h-16 rounded-md bg-muted/30" />
            <div className="h-16 rounded-md bg-muted/30" />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6">
          {filteredReadyForApproval.length > 0 ? <ReviewProgrammesTable programmes={filteredReadyForApproval} /> : null}

        <ReviewProgrammesTable programmes={filteredReviewQueue} />
      </div>
    )}
  </div>
  );
}
