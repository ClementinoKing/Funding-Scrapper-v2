import { memo, useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DollarSign,
  Calendar,
  Building2,
  ArrowRight,
  Bookmark,
  BookmarkCheck,
  Share2,
  Clock,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

type ProgramCardProps = {
  program: Record<string, any>;
  variant?: "grid" | "list" | 'compact';
  className?: string;
  isSubprogram?: boolean;
};

export const ProgramCard = memo(function ProgramCard({
  program,
  variant = "grid",
  className,
  isSubprogram = false,
}: ProgramCardProps) {
    const [isSaved, setIsSaved] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    const handleSaveToggle = () => {
        setIsSaved(!isSaved)
    }

  if (variant === "list") {
    return <Link
        to={`/app/matches/${program?.program_slug || program?.program_id}`}
        className="block group"
      >
        <Card className="h-full hover:shadow-md hover:border-green-500/50 transition-all duration-200">
          <CardContent className="p-4">
            <div className="flex items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-base font-semibold line-clamp-2 group-hover:text-green-600 dark:group-hover:text-green-400 transition-colors">
                      {program?.program_name || "Untitled program"}
                    </CardTitle>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Badge
                            variant="default"
                            className={`mt-2 gap-1 text-xs ${program?.final_score >= 70 ? "bg-green-600 hover:bg-green-700" : "bg-amber-600 hover:bg-amber-700"}`}
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            Qualified (
                            {program?.final_score}%)
                          </Badge>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <div className="text-xs space-y-1">
                            <p className="font-semibold">Why this qualifies:</p>
                            {program?.match_reasons
                              ?.slice(0, 3)
                              .map((r: { score: number; reason: string }, idx: number) => (
                                <p key={idx}>• {r.reason}</p>
                              ))}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-green-600 dark:group-hover:text-green-400 transition-colors flex-shrink-0 mt-1" />
                </div>
                <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
                  {program?.program_eligibility?.join(", ") ?? "No summary available."}
                </p>
                <div className="flex flex-wrap items-center gap-3 text-xs">
                  {program?.program_funding_amount && (
                    <div className="flex items-center gap-1.5 text-muted-foreground">
                      <DollarSign className="w-3.5 h-3.5 text-green-600 dark:text-green-400" />
                      <span className="line-clamp-2">
                        {program?.program_funding_amount}
                      </span>
                    </div>
                  )}
                  {program?.program_deadline_date && (
                    <div
                      className={cn(
                        "flex items-center gap-1.5",
                        (new Date(program.program_deadline_date).getTime() - Date.now() < 3 * 24 * 60 * 60 * 1000)
                          ? "text-orange-600 dark:text-orange-400"
                          : "text-muted-foreground",
                      )}
                    >
                      <Clock className="w-3.5 h-3.5" />
                      <span className="line-clamp-2">
                        {program?.program_deadline_date}
                      </span>
                    </div>
                  )}
                  <div className="flex items-center gap-1.5 text-muted-foreground">
                    <Building2 className="w-3.5 h-3.5" />
                    <span className="truncate">{program?.program_source}</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end gap-2 flex-shrink-0">
                <div className="flex gap-1">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={handleSaveToggle}
                          disabled={isSaving || !program?.program_id}
                        >
                          {isSaved ? (
                            <BookmarkCheck className="h-4 w-4 text-green-600 dark:text-green-400 fill-current" />
                          ) : (
                            <Bookmark className="h-4 w-4" />
                          )}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {isSaved ? "Unsave program" : "Save program"}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => {
                            e.preventDefault();
                            // TODO: Implement share functionality
                          }}
                        >
                          <Share2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Share program</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                {program?.program_sectors && (
                  <div className="flex flex-wrap gap-1 justify-end">
                    {program?.program_sectors
                      ?.slice(0, 2)
                      .map((sector: string, idx: number) => (
                        <Badge
                          key={idx}
                          variant="secondary"
                          className="text-xs"
                        >
                          {sector.trim()}
                        </Badge>
                      ))}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </Link>;
  } else {
    return <Link
      to={`/app/matches/${program?.program_slug || program?.program_id}`}
      className="block group"
    >
      <Card
        className={cn(
          "h-full hover:shadow-lg hover:border-green-500/50 transition-all duration-200 flex flex-col",
          className,
        )}
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <CardTitle className="text-base font-semibold line-clamp-2 group-hover:text-green-600 dark:group-hover:text-green-400 transition-colors">
                {program?.program_name || "Untitled program"}
              </CardTitle>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge
                      variant="default"
                      className={`mt-2 gap-1 ${program?.final_score >= 70 ? "bg-green-600 hover:bg-green-700" : "bg-amber-600 hover:bg-amber-700"}`}
                    >
                      <CheckCircle2 className="w-3 h-3" />
                      Qualified ({program?.final_score}%
                      match)
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <div className="text-xs space-y-1">
                      <p className="font-semibold">Why this qualifies:</p>
                      {/* {program?.match_reasons?.slice(0, 3).map((reason, idx) => (
                        <p key={idx}>• {reason}</p>
                      ))} */}
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-green-600 dark:group-hover:text-green-400 transition-colors flex-shrink-0 mt-1" />
          </div>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col">
          <div className="space-y-2 mb-4">
            {program?.program_funding_amount && (
              <div className="flex items-start gap-2 text-xs">
                <DollarSign className="w-3.5 h-3.5 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                <span className="text-muted-foreground  line-clamp-2">
                  <span className="font-medium text-foreground">Funding: </span>
                  {program?.program_funding_amount}
                </span>
              </div>
            )}
            {program?.program_deadline_date && (
              <div
                className={cn(
                  "flex items-start gap-2 text-xs",
                  (new Date(program.program_deadline_date).getTime() - Date.now() < 3 * 24 * 60 * 60 * 1000)
                    && "text-orange-600 dark:text-orange-400",
                )}
              >
                <Clock
                  className={cn(
                    "w-3.5 h-3.5 mt-0.5 flex-shrink-0",
                    (new Date(program.program_deadline_date).getTime() - Date.now() < 3 * 24 * 60 * 60 * 1000)
                      ? "text-orange-600 dark:text-orange-400"
                      : "text-muted-foreground",
                  )}
                />
                <span className="text-muted-foreground line-clamp-2">
                  <span className="font-medium text-foreground">
                    Deadline:{" "}
                  </span>
                  {program?.program_deadline_date}
                </span>
              </div>
            )}
            {program?.program_eligibility && (
              <div className="flex items-start gap-2 text-xs">
                <Building2 className="w-3.5 h-3.5 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                <span className="text-muted-foreground line-clamp-2">
                  <span className="font-medium text-foreground">
                    Eligibility:{" "}
                  </span>
                  {program?.program_eligibility}
                </span>
              </div>
            )}
          </div>

          {program?.program_sectors && (
            <div className="flex flex-wrap gap-1 mb-4">
              {program?.program_sectors?.slice(0, 3).map((sector: string, idx: number) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {sector.trim()}
                </Badge>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between pt-3 border-t">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded bg-gradient-to-br from-green-500 to-slate-500 flex items-center justify-center flex-shrink-0">
                <Building2 className="w-3 h-3 text-white" />
              </div>
              <span className="text-xs text-muted-foreground truncate">
                {program?.program_source}
              </span>
            </div>
            <div className="flex gap-1">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={handleSaveToggle}
                      disabled={isSaving || !program?.program_id}
                    >
                      {isSaved ? (
                        <BookmarkCheck className="h-3.5 w-3.5 text-green-600 dark:text-green-400 fill-current" />
                      ) : (
                        <Bookmark className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{isSaved ? "Unsave" : "Save"}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>;
  }
});
