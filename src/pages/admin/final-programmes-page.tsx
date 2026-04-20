import { useMemo } from "react";
import { formatDistanceToNow } from "date-fns";
import { CheckCircle2, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiClient } from "@/services/api/client";
import { rankProgrammes } from "@/lib/fundingScoring";
import { cn } from "@/lib/utils";
import type { FundingProgram } from "@/types/domain";

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

export function FinalProgrammesPage() {
  const navigate = useNavigate();
  const { data: programmes = [] } = useQuery({
    queryKey: ["final-programmes"],
    queryFn: apiClient.getPrograms
  });

  const finalProgrammes = useMemo(
    () =>
      rankProgrammes(programmes)
        .filter((programme) => programme.approvalStatus === "approved")
        .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()),
    [programmes]
  );

  return (
    <div className="space-y-8 pb-10">
      <Card className="overflow-hidden border-emerald-200/70 bg-gradient-to-br from-emerald-50 via-background to-sky-50/60">
        <CardContent className="grid gap-6 p-6 xl:grid-cols-[1.3fr_0.9fr] xl:items-end">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
              <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
              Applicant catalogue
            </div>
            <div className="space-y-2">
              <h1 className="text-3xl font-bold tracking-tight text-balance">Final Programmes</h1>
              <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
                Approved programmes that are ready to be shown to applicants.
              </p>
            </div>
          </div>

          <Card className="border-border/70 bg-background/80 shadow-none backdrop-blur">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Published catalogue</CardTitle>
              <CardDescription>These records are visible to applicants.</CardDescription>
            </CardHeader>
            <CardContent className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium">Final programmes</p>
                <p className="text-xs text-muted-foreground">Approved and ready for discovery</p>
              </div>
              <Badge variant="success" className="gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {finalProgrammes.length} published
              </Badge>
            </CardContent>
          </Card>
        </CardContent>
      </Card>

      <SectionHeader
        title="Final Programmes"
        description="Browse the published catalogue that applicants can already see."
      />

      <Card className="overflow-hidden border-emerald-200/70">
        <CardHeader className="border-b bg-emerald-50/50">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Final programmes table</CardTitle>
              <CardDescription>Approved programmes ordered by most recent update.</CardDescription>
            </div>
            <Badge variant="success">{finalProgrammes.length} published</Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {finalProgrammes.length === 0 ? (
            <div className="flex min-h-[220px] flex-col items-center justify-center gap-3 px-6 py-12 text-center">
              <div className="rounded-full border bg-emerald-50 p-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              </div>
              <div className="space-y-1">
                <p className="text-base font-medium">No final programmes yet</p>
                <p className="text-sm text-muted-foreground">
                  Approve a programme in the review queue and it will appear here.
                </p>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table className="min-w-[920px]">
                <TableHeader>
                  <TableRow className="bg-emerald-50/40 hover:bg-emerald-50/40">
                    <TableHead className="pl-6">Programme</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Funding range</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {finalProgrammes.map((programme) => (
                    <TableRow
                      key={programme.id}
                      className={cn("cursor-pointer hover:bg-emerald-50/30")}
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
                          <p className="text-xs text-muted-foreground">Visible to applicants</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={getProgrammeStatusVariant(programme.status)} className="capitalize">
                          {programme.status.replace("_", " ")}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDistanceToNow(new Date(programme.updatedAt), { addSuffix: true })}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
