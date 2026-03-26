import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
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
import type { ScoredProgramme, ScrapedFundingProgramme } from "@/types/funding";
import { cn } from "@/lib/utils";

const getScoreVariant = (score: number): "success" | "warning" | "secondary" =>
  getScoreTone(score) === "high" ? "success" : getScoreTone(score) === "medium" ? "warning" : "secondary";

const getRowClassName = (programme: ScoredProgramme): string => {
  if (programme.scoreBand === "high") {
    return "bg-accent/5";
  }
  if (programme.scoreBand === "medium") {
    return "bg-amber-50/50";
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

function ProgrammeReviewTable({
  title,
  description,
  programmes,
  navigate
}: {
  title: string;
  description: string;
  programmes: ScoredProgramme[];
  navigate: ReturnType<typeof useNavigate>;
}) {
  return (
    <div className="space-y-4 rounded-xl border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <Badge variant="secondary">{programmes.length} programmes</Badge>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Programme</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Priority</TableHead>
            <TableHead>Quality</TableHead>
            <TableHead>Match</TableHead>
            <TableHead>Approval</TableHead>
            <TableHead>Funding range</TableHead>
            <TableHead>Signals</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {programmes.map((program) => (
            <TableRow
              key={program.id}
              className={cn("cursor-pointer transition-colors hover:bg-muted/50", getRowClassName(program))}
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
              <TableCell className="font-medium">
                <div className="space-y-1">
                  <p>{program.title}</p>
                  <p className="text-xs text-muted-foreground">{program.reasonTags.slice(0, 2).join(" • ")}</p>
                </div>
              </TableCell>
              <TableCell>{program.providerName}</TableCell>
              <TableCell>
                <Badge variant={getScoreVariant(program.importanceScore)}>
                  {program.importanceScore}%
                </Badge>
              </TableCell>
              <TableCell>{program.qualityScore}</TableCell>
              <TableCell>{program.matchScore}</TableCell>
              <TableCell>
                <Badge
                  variant={
                    program.approvalStatus === "approved"
                      ? "success"
                      : program.approvalStatus === "pending"
                        ? "warning"
                        : "secondary"
                  }
                >
                  {program.approvalStatus}
                </Badge>
              </TableCell>
              <TableCell>
                {formatMoney(program.amountMin)}
                {program.amountMax ? ` - ${formatMoney(program.amountMax)}` : ""}
              </TableCell>
              <TableCell className="max-w-[220px]">
                <div className="flex flex-wrap gap-1">
                  {program.reasonTags.slice(0, 3).map((reason) => (
                    <Badge key={reason} variant="outline" title={reason}>
                      {reason}
                    </Badge>
                  ))}
                </div>
              </TableCell>
              <TableCell className="space-x-2 text-right">
                <Button variant="outline" size="sm" onClick={(event) => event.stopPropagation()}>
                  Edit
                </Button>
                <Button size="sm" onClick={(event) => event.stopPropagation()}>
                  Approve
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function ProgramReviewPage() {
  const navigate = useNavigate();
  const [programs, setPrograms] = useState<ScrapedFundingProgramme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    () => scoredPrograms.filter((program) => program.scoreBand === "high" || program.importanceScore >= 70),
    [scoredPrograms]
  );
  const reviewQueue = useMemo(
    () => scoredPrograms.filter((program) => !readyForApproval.includes(program)),
    [readyForApproval, scoredPrograms]
  );

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Program Review Queue"
        description="Review Supabase-backed programmes in priority order, then approve the strongest records."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border bg-card p-4">
          <p className="text-sm text-muted-foreground">Ready to approve</p>
          <p className="mt-2 text-2xl font-semibold">{readyForApproval.length}</p>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-sm text-muted-foreground">Needs review</p>
          <p className="mt-2 text-2xl font-semibold">{reviewQueue.length}</p>
        </div>
        <div className="rounded-xl border bg-card p-4">
          <p className="text-sm text-muted-foreground">Loaded from Supabase</p>
          <p className="mt-2 text-2xl font-semibold">{loading ? "..." : scoredPrograms.length}</p>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {!loading ? (
        <div className="grid gap-6">
          {readyForApproval.length > 0 ? (
            <ProgrammeReviewTable
              title="Ready to approve"
              description="High-quality programmes with strong scoring signals."
              programmes={readyForApproval}
              navigate={navigate}
            />
          ) : null}

          <ProgrammeReviewTable
            title="Needs review"
            description="Useful records, but with weaker evidence or lower match strength."
            programmes={reviewQueue}
            navigate={navigate}
          />
        </div>
      ) : null}
    </div>
  );
}
