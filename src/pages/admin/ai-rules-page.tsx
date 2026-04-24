import { useEffect, useState } from "react";
import {
  Database,
  FileCode2,
  GitBranch,
  History,
  Layers3,
  PencilLine,
  ShieldCheck,
  Sparkles,
  SquareStack,
  Telescope
} from "lucide-react";
import { SectionHeader } from "@/components/shared/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type RuleStatus = "active" | "draft" | "review" | "locked";

type RuleBundle = {
  id: string;
  name: string;
  status: RuleStatus;
  scope: string;
  summary: string;
  updatedAt: string;
  prompt: string;
  outputShape: string;
  reviewNotes: string[];
};

const ruleBundles: RuleBundle[] = [
  {
    id: "page-decision",
    name: "Programme detection",
    status: "active",
    scope: "Page-level classification",
    summary: "Decides whether a page is a real funding programme or should be rejected as noise.",
    updatedAt: "Today",
    prompt:
      "Classify each page as funding_program, not_funding_program, or unclear. Reject articles, media pages, policies, gallery pages, and file-like assets unless the page clearly describes a programme.",
    outputShape:
      "page_decision, page_decision_confidence, records, notes",
    reviewNotes: [
      "Keep child programmes independent when they have their own rules.",
      "Never collapse siblings unless the source URL and parent programme context match."
    ]
  },
  {
    id: "eligibility",
    name: "Eligibility extraction",
    status: "draft",
    scope: "Raw eligibility data -> structured eligibility columns",
    summary: "Maps raw eligibility text into industries, use of funds, business stage, turnover, and related fields.",
    updatedAt: "Today",
    prompt:
      "Use raw_eligibility_data first. Extract short list items for industries, use_of_funds, business_stage_eligibility, turnover_min/max, years_in_business_min/max, employee_min/max, ownership_targets, entity_types_allowed, and certifications_required.",
    outputShape:
      "industries, use_of_funds, business_stage_eligibility, turnover_min, turnover_max, years_in_business_min, years_in_business_max, employee_min, employee_max, ownership_targets, entity_types_allowed, certifications_required",
    reviewNotes: [
      "Prefer exact wording from the source page.",
      "Only fill numeric ranges when the sentence clearly supports them."
    ]
  },
  {
    id: "funding-lines",
    name: "Funding lines",
    status: "review",
    scope: "Funding offer text",
    summary: "Keeps funding_lines and raw_funding_offer_data as arrays, not one paragraph.",
    updatedAt: "Yesterday",
    prompt:
      "Split funding lines into separate list items. Preserve the original order, remove duplicates, and do not merge unrelated offers into one long sentence.",
    outputShape: "funding_lines, raw_funding_offer_data",
    reviewNotes: [
      "Use list items for JSONB columns.",
      "Keep each product, facility, or line separate when the page names them separately."
    ]
  },
  {
    id: "provenance",
    name: "Source provenance",
    status: "locked",
    scope: "Source URL and related documents",
    summary: "Keeps source_url pinned to the page that was scraped and separates application/document links from provenance.",
    updatedAt: "2 days ago",
    prompt:
      "Always store the page URL as the provenance source. Related documents and application URLs may be captured separately, but they should not replace the page source.",
    outputShape: "source_url, source_urls, related_documents, application_url",
    reviewNotes: [
      "Only the page that supplied the data should appear in source_url/source_urls.",
      "Related links belong in their own columns."
    ]
  }
];

const versionHistory = [
  {
    version: "v1.4",
    status: "active" as const,
    title: "Eligibility mapping refinements",
    updatedAt: "Today",
    changes: [
      "Eligibility text now maps into structured columns instead of remaining a paragraph.",
      "Programs with their own page and rules stay independent during dedupe."
    ]
  },
  {
    version: "v1.3",
    status: "review" as const,
    title: "Funding line array handling",
    updatedAt: "Yesterday",
    changes: [
      "Funding lines are saved as JSON arrays.",
      "Paragraph-shaped evidence is split into list items before persistence."
    ]
  },
  {
    version: "v1.2",
    status: "locked" as const,
    title: "Non-program rejection rules",
    updatedAt: "2 days ago",
    changes: [
      "Image and article pages are rejected before persistence.",
      "Program detection is now an explicit AI decision."
    ]
  }
];

const schemaMap = [
  {
    source: "raw_eligibility_data",
    columns: "industries, use_of_funds, business_stage_eligibility, turnover_min/max, years_in_business_min/max, employee_min/max, ownership_targets, entity_types_allowed, certifications_required",
    note: "Eligibility text is read first, then split into structured arrays and numeric ranges."
  },
  {
    source: "raw_funding_offer_data",
    columns: "funding_lines, funding_type, ticket_min/max, program_budget_total",
    note: "Offer text is preserved as list items so each facility or line stays separate."
  },
  {
    source: "raw_terms_data",
    columns: "deadline_type, deadline_date, security_required, equity_required, interest_type, repayment_frequency",
    note: "Terms and structure are treated separately from eligibility."
  },
  {
    source: "full_body_text",
    columns: "page_decision, program_name, funder_name, application_channel, application_url",
    note: "Used when the page provides enough narrative context to identify the programme."
  },
  {
    source: "source_url",
    columns: "source_url, source_urls, source_domain, source_page_title",
    note: "Provenance stays pinned to the scraped page."
  }
];

function StatCard({
  icon: Icon,
  label,
  value,
  caption,
  tone
}: {
  icon: typeof Sparkles;
  label: string;
  value: string;
  caption: string;
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

export function AIRulesPage() {
  const [selectedBundleId, setSelectedBundleId] = useState(ruleBundles[0].id);
  const selectedBundle = ruleBundles.find((bundle) => bundle.id === selectedBundleId) ?? ruleBundles[0];
  const [bundleName, setBundleName] = useState(selectedBundle.name);
  const [bundlePrompt, setBundlePrompt] = useState(selectedBundle.prompt);
  const [bundleOutputShape, setBundleOutputShape] = useState(selectedBundle.outputShape);
  const [bundleNotes, setBundleNotes] = useState(selectedBundle.reviewNotes.join("\n"));

  useEffect(() => {
    setBundleName(selectedBundle.name);
    setBundlePrompt(selectedBundle.prompt);
    setBundleOutputShape(selectedBundle.outputShape);
    setBundleNotes(selectedBundle.reviewNotes.join("\n"));
  }, [selectedBundle]);

  const activeCount = ruleBundles.filter((bundle) => bundle.status === "active").length;
  const editableCount = ruleBundles.filter((bundle) => bundle.status !== "locked").length;
  const mappedColumns = schemaMap.reduce((total, entry) => total + entry.columns.split(",").length, 0);

  return (
    <div className="space-y-8 pb-10">
      <Card className="overflow-hidden border-emerald-200/70 bg-gradient-to-br from-emerald-50 via-background to-slate-50">
        <CardContent className="grid gap-6 p-6 xl:grid-cols-[1.1fr_0.9fr] xl:items-end">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
              <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
              UI only. Database-backed later.
            </div>
            <div className="space-y-2">
              <h1 className="text-3xl font-bold tracking-tight text-balance">AI Rules</h1>
              <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">
                This sidebar entry is a management surface for prompt bundles, eligibility rules, and version history.
                Later it can be backed by database tables so rules can be edited, versioned, and published without touching code.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                Active rules: {activeCount}
              </Badge>
              <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">
                Editable bundles: {editableCount}
              </Badge>
              <Badge variant="outline" className="border-violet-200 bg-violet-50 text-violet-700">
                Column mappings: {mappedColumns}
              </Badge>
            </div>
          </div>

          <Card className="border-border/70 bg-background/80 shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Planned management flow</CardTitle>
              <CardDescription>How the UI is intended to work once the database layer is added.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-full border bg-muted/40 p-2">
                  <Layers3 className="h-4 w-4 text-emerald-600" />
                </div>
                <p>Store prompt bundles and classifier rules as versioned records.</p>
              </div>
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-full border bg-muted/40 p-2">
                  <Database className="h-4 w-4 text-emerald-600" />
                </div>
                <p>Keep prompt text, field mappings, and rollout status in separate tables.</p>
              </div>
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-full border bg-muted/40 p-2">
                  <GitBranch className="h-4 w-4 text-emerald-600" />
                </div>
                <p>Publish one version as active while retaining older versions for rollback.</p>
              </div>
            </CardContent>
          </Card>
        </CardContent>
      </Card>

      <SectionHeader
        title="Rules workspace"
        description="Manage the shape of AI prompts and the fields they are allowed to populate."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          icon={Sparkles}
          label="Active bundles"
          value={String(activeCount)}
          caption="Rules currently treated as live"
          tone="border-emerald-200/70 bg-gradient-to-br from-emerald-50 via-background to-background"
        />
        <StatCard
          icon={ShieldCheck}
          label="Editable bundles"
          value={String(editableCount)}
          caption="Bundles that can be tweaked later"
          tone="border-sky-200/70 bg-gradient-to-br from-sky-50 via-background to-background"
        />
        <StatCard
          icon={FileCode2}
          label="Mapped columns"
          value={String(mappedColumns)}
          caption="Schema columns driven by eligibility and prompt rules"
          tone="border-violet-200/70 bg-gradient-to-br from-violet-50 via-background to-background"
        />
      </div>

      <Tabs defaultValue="bundles" className="space-y-6">
        <TabsList className="grid w-full max-w-2xl grid-cols-3">
          <TabsTrigger value="bundles">Bundles</TabsTrigger>
          <TabsTrigger value="schema">Schema map</TabsTrigger>
          <TabsTrigger value="versions">Versions</TabsTrigger>
        </TabsList>

        <TabsContent value="bundles" className="space-y-6">
          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <Card className="overflow-hidden">
              <CardHeader className="border-b bg-muted/20">
                <CardTitle>Prompt bundles</CardTitle>
                <CardDescription>Choose which classifier bundle to edit or review.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 p-4">
                {ruleBundles.map((bundle) => {
                  const selected = bundle.id === selectedBundleId;
                  return (
                    <button
                      key={bundle.id}
                      type="button"
                      onClick={() => setSelectedBundleId(bundle.id)}
                      className={cn(
                        "w-full rounded-2xl border p-4 text-left transition hover:border-emerald-300 hover:bg-emerald-50/50",
                        selected && "border-emerald-400 bg-emerald-50 shadow-sm"
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <p className="text-base font-semibold tracking-tight">{bundle.name}</p>
                          <p className="text-sm text-muted-foreground">{bundle.summary}</p>
                        </div>
                        <Badge
                          variant="outline"
                          className={cn(
                            "shrink-0 capitalize",
                            bundle.status === "active" && "border-emerald-200 bg-emerald-50 text-emerald-700",
                            bundle.status === "draft" && "border-sky-200 bg-sky-50 text-sky-700",
                            bundle.status === "review" && "border-amber-200 bg-amber-50 text-amber-700",
                            bundle.status === "locked" && "border-slate-200 bg-slate-50 text-slate-700"
                          )}
                        >
                          {bundle.status}
                        </Badge>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Badge variant="outline" className="border-border/70 bg-background/80">
                          {bundle.scope}
                        </Badge>
                        <Badge variant="outline" className="border-border/70 bg-background/80">
                          Updated {bundle.updatedAt}
                        </Badge>
                      </div>
                    </button>
                  );
                })}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader className="border-b bg-muted/20">
                  <CardTitle className="flex items-center gap-2">
                    <PencilLine className="h-4 w-4 text-emerald-600" />
                    Bundle editor
                  </CardTitle>
                  <CardDescription>
                    Editable shell for how this would work once prompt records live in the database.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5 p-6">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                      {selectedBundle.status}
                    </Badge>
                    <Badge variant="outline" className="border-border/70 bg-background/80">
                      {selectedBundle.scope}
                    </Badge>
                    <Badge variant="outline" className="border-border/70 bg-background/80">
                      Last edited {selectedBundle.updatedAt}
                    </Badge>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2 md:col-span-2">
                      <label className="text-sm font-medium">Bundle name</label>
                      <Input key={`${selectedBundle.id}-name`} defaultValue={bundleName} />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <label className="text-sm font-medium">Prompt text</label>
                      <Textarea
                        key={`${selectedBundle.id}-prompt`}
                        defaultValue={bundlePrompt}
                        className="min-h-[180px]"
                      />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <label className="text-sm font-medium">Expected output shape</label>
                      <Textarea
                        key={`${selectedBundle.id}-shape`}
                        defaultValue={bundleOutputShape}
                        className="min-h-[100px]"
                      />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <label className="text-sm font-medium">Reviewer notes</label>
                      <Textarea
                        key={`${selectedBundle.id}-notes`}
                        defaultValue={bundleNotes}
                        className="min-h-[120px]"
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <Button disabled>Save draft</Button>
                    <Button variant="outline" disabled>
                      Publish version
                    </Button>
                    <Button variant="ghost" disabled>
                      Reset to baseline
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    These buttons are visual only for now. Later they can write to database-backed rule tables with version history and approvals.
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="border-b bg-muted/20">
                  <CardTitle>Future tables</CardTitle>
                  <CardDescription>Suggested database shape for rule management.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-6 text-sm">
                  <div className="rounded-2xl border bg-background p-4">
                    <p className="font-medium">ai_rule_sets</p>
                    <p className="mt-1 text-muted-foreground">
                      One record per rule bundle, with name, purpose, active flag, and scope.
                    </p>
                  </div>
                  <div className="rounded-2xl border bg-background p-4">
                    <p className="font-medium">ai_rule_versions</p>
                    <p className="mt-1 text-muted-foreground">
                      Versioned prompt snapshots, reviewer notes, and publish history.
                    </p>
                  </div>
                  <div className="rounded-2xl border bg-background p-4">
                    <p className="font-medium">ai_rule_mappings</p>
                    <p className="mt-1 text-muted-foreground">
                      Column-level mapping rules for eligibility extraction and structured output fields.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="schema" className="space-y-6">
          <Card className="overflow-hidden">
            <CardHeader className="border-b bg-muted/20">
              <CardTitle>Source-to-column map</CardTitle>
              <CardDescription>
                This is the UI view for how raw text gets turned into the right columns later.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[22%]">Source field</TableHead>
                    <TableHead className="w-[38%]">Derived columns</TableHead>
                    <TableHead className="w-[40%]">Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {schemaMap.map((entry) => (
                    <TableRow key={entry.source}>
                      <TableCell className="font-medium">{entry.source}</TableCell>
                      <TableCell>{entry.columns}</TableCell>
                      <TableCell className="text-muted-foreground">{entry.note}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="versions" className="space-y-6">
          <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <Card className="overflow-hidden">
              <CardHeader className="border-b bg-muted/20">
                <CardTitle>Version history</CardTitle>
                <CardDescription>Track prompt changes and keep old versions available for rollback.</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y">
                  {versionHistory.map((version) => (
                    <article key={version.version} className="grid gap-4 px-6 py-5 lg:grid-cols-[0.3fr_0.7fr]">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <Badge
                            variant="outline"
                            className={cn(
                              "capitalize",
                              version.status === "active" && "border-emerald-200 bg-emerald-50 text-emerald-700",
                              version.status === "review" && "border-amber-200 bg-amber-50 text-amber-700",
                              version.status === "locked" && "border-slate-200 bg-slate-50 text-slate-700"
                            )}
                          >
                            {version.status}
                          </Badge>
                        </div>
                        <p className="text-lg font-semibold tracking-tight">{version.version}</p>
                        <p className="text-sm text-muted-foreground">{version.updatedAt}</p>
                      </div>
                      <div className="space-y-3">
                        <h3 className="text-base font-semibold tracking-tight">{version.title}</h3>
                        <div className="space-y-2">
                          {version.changes.map((change) => (
                            <div key={change} className="flex items-start gap-3 rounded-2xl border bg-background px-4 py-3">
                              <History className="mt-0.5 h-4 w-4 text-emerald-600" />
                              <p className="text-sm text-muted-foreground">{change}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader className="border-b bg-muted/20">
                  <CardTitle>Management model</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 p-6 text-sm">
                  <div className="flex items-start gap-3">
                    <div className="rounded-full border bg-muted/40 p-2">
                      <SquareStack className="h-4 w-4 text-emerald-600" />
                    </div>
                    <div>
                      <p className="font-medium">Draft</p>
                      <p className="text-muted-foreground">A bundle can be edited locally before it is published.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="rounded-full border bg-muted/40 p-2">
                      <Telescope className="h-4 w-4 text-emerald-600" />
                    </div>
                    <div>
                      <p className="font-medium">Review</p>
                      <p className="text-muted-foreground">A reviewer can inspect the prompt, expected shape, and mapped fields.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="rounded-full border bg-muted/40 p-2">
                      <Database className="h-4 w-4 text-emerald-600" />
                    </div>
                    <div>
                      <p className="font-medium">Publish</p>
                      <p className="text-muted-foreground">The active rule version becomes the one used by the scraper and AI layer.</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-emerald-200/70 bg-gradient-to-br from-emerald-50 via-background to-background">
                <CardContent className="space-y-3 p-6">
                  <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground">
                    <PencilLine className="h-3.5 w-3.5 text-emerald-600" />
                    UI management note
                  </div>
                  <p className="text-sm text-muted-foreground">
                    This screen is intentionally structured to make later database wiring simple: rule set name, version history,
                    prompt text, output shape, review notes, and status all already have dedicated places in the UI.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
