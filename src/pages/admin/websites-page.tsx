import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { PencilLine, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChipInput } from "@/components/admin/chip-input";
import { SectionHeader } from "@/components/shared/section-header";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/services/api/client";
import type { WebsiteSite } from "@/types/domain";

type SiteFormState = {
  siteKey: string;
  displayName: string;
  primaryDomain: string;
  adapterKey: string;
  seedUrls: string;
  notes: string;
  active: boolean;
  industries: string[];
  useOfFunds: string[];
  ownershipTargets: string[];
  allowedPathPrefixes: string[];
  includeUrlTerms: string[];
  excludeUrlTerms: string[];
  discoveryTerms: string[];
  parentPageTerms: string[];
  childPageTerms: string[];
  supportPageTerms: string[];
  strictPathPrefixes: boolean;
  allowRootUrl: boolean;
  playwrightRequiredByDefault: boolean;
};

const initialFormState: SiteFormState = {
  siteKey: "",
  displayName: "",
  primaryDomain: "",
  adapterKey: "",
  seedUrls: "",
  notes: "",
  active: true,
  industries: [],
  useOfFunds: [],
  ownershipTargets: [],
  allowedPathPrefixes: [],
  includeUrlTerms: [],
  excludeUrlTerms: [],
  discoveryTerms: [],
  parentPageTerms: [],
  childPageTerms: [],
  supportPageTerms: [],
  strictPathPrefixes: false,
  allowRootUrl: true,
  playwrightRequiredByDefault: false
};

const INDUSTRY_SUGGESTIONS = [
  "Agriculture",
  "Construction",
  "Creative industries",
  "Education",
  "Energy",
  "Finance",
  "Health",
  "Hospitality",
  "Manufacturing",
  "Retail",
  "Technology",
  "Tourism",
  "Transport",
  "Waste management"
];

const USE_OF_FUNDS_SUGGESTIONS = [
  "Working capital",
  "Inventory",
  "Equipment",
  "Machinery",
  "Expansion",
  "Marketing",
  "Training",
  "Research and development",
  "Digital tools",
  "Payroll",
  "Property",
  "Refinancing"
];

const OWNERSHIP_TARGETS_SUGGESTIONS = [
  "Black-owned",
  "Women-owned",
  "Youth-owned",
  "Disability-owned",
  "Rural businesses",
  "Township businesses",
  "Cooperatives",
  "SMEs"
];

const PATH_PREFIX_SUGGESTIONS = ["/products-services/", "/programmes/", "/programs/", "/funding/", "/grants/", "/apply/", "/portal/", "/resources/"];

const TERM_SUGGESTIONS = [
  "fund",
  "funding",
  "grant",
  "loan",
  "finance",
  "capital",
  "apply",
  "application",
  "programme",
  "program",
  "voucher",
  "support",
  "business",
  "entrepreneurship"
];

const PAGE_HINT_SUGGESTIONS = [
  "how to apply",
  "application form",
  "guidelines",
  "checklist",
  "faq",
  "portal",
  "brochure",
  "eligibility",
  "requirements"
];

const EXCLUDE_SUGGESTIONS = ["news", "media", "press", "careers", "jobs", "blog", "privacy", "about", "contact"];

const parseLines = (value: string): string[] =>
  value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

const deriveKeyFromDomain = (domain: string): string => {
  const normalized = domain.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "");
  if (!normalized) {
    return "";
  }
  const [host] = normalized.split("/");
  const parts = host.split(".").filter(Boolean);
  if (!parts.length) {
    return "";
  }
  const candidate = parts[0].replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  if (!candidate) {
    return "";
  }
  if (candidate.startsWith("the") && candidate.length > 3) {
    const stripped = candidate.slice(3).replace(/^-+|-+$/g, "");
    return stripped || candidate;
  }
  return candidate;
};

const deriveDisplayNameFromDomain = (domain: string): string => {
  const normalized = domain.trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "");
  if (!normalized) {
    return "";
  }
  const [host] = normalized.split("/");
  const parts = host.split(".").filter(Boolean);
  if (!parts.length) {
    return "";
  }
  const candidate = parts[0].replace(/[^a-z0-9]+/g, " ").trim();
  if (!candidate) {
    return "";
  }
  if (candidate.length <= 4) {
    return candidate.toUpperCase();
  }
  return candidate
    .split(/\s+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

const normalizeArray = (values: string[]): string[] => values.map((item) => item.trim()).filter(Boolean);

const buildAdapterConfig = (form: SiteFormState): Record<string, unknown> => ({
  industries: normalizeArray(form.industries),
  use_of_funds: normalizeArray(form.useOfFunds),
  ownership_targets: normalizeArray(form.ownershipTargets),
  allowed_path_prefixes: normalizeArray(form.allowedPathPrefixes),
  include_url_terms: normalizeArray(form.includeUrlTerms),
  exclude_url_terms: normalizeArray(form.excludeUrlTerms),
  discovery_terms: normalizeArray(form.discoveryTerms),
  parent_page_terms: normalizeArray(form.parentPageTerms),
  child_page_terms: normalizeArray(form.childPageTerms),
  support_page_terms: normalizeArray(form.supportPageTerms),
  strict_path_prefixes: form.strictPathPrefixes,
  allow_root_url: form.allowRootUrl,
  playwright_required_by_default: form.playwrightRequiredByDefault
});

const stepTitle = (step: 1 | 2) => (step === 1 ? "Basic Details" : "Adapter Rules");

export function WebsitesPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SiteFormState>(initialFormState);
  const [createStep, setCreateStep] = useState<1 | 2>(1);
  const [createOpen, setCreateOpen] = useState(false);

  const { data: sites = [], isLoading, error } = useQuery({
    queryKey: ["sites"],
    queryFn: apiClient.getSites
  });

  const siteKeys = useMemo(() => new Set(sites.map((site) => site.siteKey.toLowerCase())), [sites]);
  const primaryDomains = useMemo(() => new Set(sites.map((site) => site.primaryDomain.toLowerCase())), [sites]);
  const adapterKeys = useMemo(() => new Set(sites.map((site) => site.adapterKey.toLowerCase())), [sites]);
  const displayNames = useMemo(() => new Set(sites.map((site) => site.displayName.toLowerCase())), [sites]);

  const createSiteMutation = useMutation({
    mutationFn: apiClient.createSite,
    onSuccess: async () => {
      toast.success("Website saved.");
      setForm(initialFormState);
      setCreateStep(1);
      setCreateOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["sites"] });
    },
    onError: (mutationError) => {
      const message = mutationError instanceof Error ? mutationError.message : "Failed to save website.";
      toast.error(message);
    }
  });

  const deleteSiteMutation = useMutation({
    mutationFn: apiClient.deleteSite,
    onSuccess: async () => {
      toast.success("Website deleted.");
      await queryClient.invalidateQueries({ queryKey: ["sites"] });
    },
    onError: (mutationError) => {
      const message = mutationError instanceof Error ? mutationError.message : "Failed to delete website.";
      toast.error(message);
    }
  });

  const activeCount = useMemo(() => sites.filter((site) => site.active).length, [sites]);

  const submitCreateSite = async () => {
    const seedUrls = parseLines(form.seedUrls);
    const derivedKey = deriveKeyFromDomain(form.primaryDomain);
    const derivedDisplayName = deriveDisplayNameFromDomain(form.primaryDomain);
    const siteKey = form.siteKey.trim() || derivedKey;
    const adapterKey = form.adapterKey.trim() || derivedKey;
    const displayName = form.displayName.trim() || derivedDisplayName;

    if (!form.primaryDomain.trim()) {
      toast.error("Primary domain is required.");
      return;
    }
    if (!seedUrls.length) {
      toast.error("Add at least one seed URL.");
      return;
    }
    if (!siteKey || !adapterKey) {
      toast.error("Primary domain must resolve to a site key and adapter key.");
      return;
    }

    const duplicateErrors = [
      siteKeys.has(siteKey.toLowerCase()) ? "Site key already exists." : null,
      displayNames.has(displayName.toLowerCase()) ? "Display name already exists." : null,
      primaryDomains.has(form.primaryDomain.trim().toLowerCase()) ? "Primary domain already exists." : null,
      adapterKeys.has(adapterKey.toLowerCase()) ? "Adapter key already exists." : null
    ].filter(Boolean);
    if (duplicateErrors.length) {
      toast.error(duplicateErrors[0] as string);
      return;
    }

    await createSiteMutation.mutateAsync({
      siteKey,
      displayName,
      primaryDomain: form.primaryDomain.trim(),
      adapterKey,
      seedUrls,
      adapterConfig: buildAdapterConfig(form),
      notes: parseLines(form.notes),
      active: form.active
    });
  };

  const validateStepOne = () => {
    if (!form.primaryDomain.trim()) {
      toast.error("Primary domain is required.");
      return false;
    }
    if (!parseLines(form.seedUrls).length) {
      toast.error("Add at least one seed URL.");
      return false;
    }
    return true;
  };

  const handleNextStep = () => {
    if (validateStepOne()) {
      setCreateStep(2);
    }
  };

  const handleCreateSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (createStep === 1) {
      handleNextStep();
      return;
    }
    await submitCreateSite();
  };

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Website Registry"
        description="Create and review crawl targets that feed the scraper's site registry."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Registered sites</CardDescription>
            <CardTitle>{sites.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Active sites</CardDescription>
            <CardTitle>{activeCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Data source</CardDescription>
            <CardTitle>{isLoading ? "Loading..." : "Supabase sites"}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">Use the button to add a site in a focused modal, then review everything below.</p>
        <Dialog
          open={createOpen}
          onOpenChange={(open) => {
            setCreateOpen(open);
            if (!open) {
              setForm(initialFormState);
              setCreateStep(1);
            }
          }}
        >
          <DialogTrigger asChild>
            <Button onClick={() => setCreateOpen(true)}>Add Website</Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Website - {stepTitle(createStep)}</DialogTitle>
              <DialogDescription>
                Step {createStep} of 2. {createStep === 1 ? "Enter the core website details." : "Define the structured adapter rules."}
              </DialogDescription>
            </DialogHeader>

            <form id="website-create-form" className="space-y-4" onSubmit={handleCreateSubmit}>
              {createStep === 1 ? (
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="primary-domain">Primary Domain</Label>
                      <Input
                        id="primary-domain"
                        value={form.primaryDomain}
                        onChange={(event) => {
                          const primaryDomain = event.target.value;
                          const derivedKey = deriveKeyFromDomain(primaryDomain);
                          const derivedDisplayName = deriveDisplayNameFromDomain(primaryDomain);
                          setForm((current) => ({
                            ...current,
                            primaryDomain,
                            siteKey:
                              !current.siteKey.trim() || current.siteKey.trim() === deriveKeyFromDomain(current.primaryDomain)
                                ? derivedKey
                                : current.siteKey,
                            displayName:
                              !current.displayName.trim() ||
                              current.displayName.trim() === deriveDisplayNameFromDomain(current.primaryDomain)
                                ? derivedDisplayName
                                : current.displayName,
                            adapterKey:
                              !current.adapterKey.trim() || current.adapterKey.trim() === deriveKeyFromDomain(current.primaryDomain)
                                ? derivedKey
                                : current.adapterKey
                          }));
                        }}
                        placeholder="nefcorp.co.za"
                      />
                      <p className="text-xs text-muted-foreground">The generated name and keys will appear below and can be adjusted if needed.</p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="display-name">Display Name</Label>
                      <Input
                        id="display-name"
                        value={form.displayName}
                        onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
                        placeholder="NEF"
                      />
                      <p className="text-xs text-muted-foreground">
                        This is generated from the primary domain after you enter it.
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="seed-urls">Seed URLs</Label>
                    <Textarea
                      id="seed-urls"
                      value={form.seedUrls}
                      onChange={(event) => setForm((current) => ({ ...current, seedUrls: event.target.value }))}
                      placeholder={"https://www.nefcorp.co.za/products-services/\nhttps://www.nefcorp.co.za/"}
                      className="min-h-28"
                    />
                    <p className="text-xs text-muted-foreground">One URL per line.</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="notes">Notes</Label>
                    <Textarea
                      id="notes"
                      value={form.notes}
                      onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                      placeholder="Primary funding site"
                      className="min-h-24"
                    />
                  </div>
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input
                      type="checkbox"
                      checked={form.active}
                      onChange={(event) => setForm((current) => ({ ...current, active: event.target.checked }))}
                      className="h-4 w-4 rounded border border-input"
                    />
                    Active
                  </label>

                  <div className="rounded-lg border bg-muted/30 p-4">
                    <div className="mb-3">
                      <h3 className="text-sm font-semibold">Generated Identifiers</h3>
                      <p className="text-xs text-muted-foreground">
                        These are derived from the primary domain and must remain unique in the database.
                      </p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="site-key">Site Key</Label>
                        <Input
                          id="site-key"
                          value={form.siteKey}
                          onChange={(event) => setForm((current) => ({ ...current, siteKey: event.target.value }))}
                          placeholder="nefcorp"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="adapter-key">Adapter Key</Label>
                        <Input
                          id="adapter-key"
                          value={form.adapterKey}
                          onChange={(event) => setForm((current) => ({ ...current, adapterKey: event.target.value }))}
                          placeholder="nefcorp"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="grid gap-6 xl:grid-cols-2">
                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Business Signals
                      </h3>
                      <ChipInput
                        label="Industries"
                        placeholder="Select or type industries..."
                        values={form.industries}
                        onChange={(values) => setForm((current) => ({ ...current, industries: values }))}
                        suggestions={INDUSTRY_SUGGESTIONS}
                        description="Add sectors this site tends to support."
                      />
                      <ChipInput
                        label="Use of Funds"
                        placeholder="Select or type use of funds..."
                        values={form.useOfFunds}
                        onChange={(values) => setForm((current) => ({ ...current, useOfFunds: values }))}
                        suggestions={USE_OF_FUNDS_SUGGESTIONS}
                        description="Describe how funding is typically used."
                      />
                      <ChipInput
                        label="Ownership Targets"
                        placeholder="Select or type ownership targets..."
                        values={form.ownershipTargets}
                        onChange={(values) => setForm((current) => ({ ...current, ownershipTargets: values }))}
                        suggestions={OWNERSHIP_TARGETS_SUGGESTIONS}
                        description="Capture preferred ownership or demographic targets."
                      />
                    </div>

                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        Crawl Narrowing
                      </h3>
                      <ChipInput
                        label="Allowed Path Prefixes"
                        placeholder="Select or type path prefixes..."
                        values={form.allowedPathPrefixes}
                        onChange={(values) => setForm((current) => ({ ...current, allowedPathPrefixes: values }))}
                        suggestions={PATH_PREFIX_SUGGESTIONS}
                        description="Limit crawling to a section of the site."
                      />
                      <ChipInput
                        label="Include URL Terms"
                        placeholder="Select or type include terms..."
                        values={form.includeUrlTerms}
                        onChange={(values) => setForm((current) => ({ ...current, includeUrlTerms: values }))}
                        suggestions={TERM_SUGGESTIONS}
                        description="Helpful words that should keep a URL in scope."
                      />
                      <ChipInput
                        label="Exclude URL Terms"
                        placeholder="Select or type exclude terms..."
                        values={form.excludeUrlTerms}
                        onChange={(values) => setForm((current) => ({ ...current, excludeUrlTerms: values }))}
                        suggestions={EXCLUDE_SUGGESTIONS}
                        description="Words that should push a URL out of scope."
                      />
                    </div>
                  </div>

                  <div className="grid gap-6 xl:grid-cols-2">
                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Page Hints</h3>
                      <ChipInput
                        label="Discovery Terms"
                        placeholder="Select or type discovery terms..."
                        values={form.discoveryTerms}
                        onChange={(values) => setForm((current) => ({ ...current, discoveryTerms: values }))}
                        suggestions={TERM_SUGGESTIONS}
                        description="Words that help the crawler discover useful pages."
                      />
                      <ChipInput
                        label="Parent Page Terms"
                        placeholder="Select or type parent page terms..."
                        values={form.parentPageTerms}
                        onChange={(values) => setForm((current) => ({ ...current, parentPageTerms: values }))}
                        suggestions={PAGE_HINT_SUGGESTIONS}
                        description="Labels that hint a page is the primary programme page."
                      />
                    </div>
                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Support Pages</h3>
                      <ChipInput
                        label="Child Page Terms"
                        placeholder="Select or type child page terms..."
                        values={form.childPageTerms}
                        onChange={(values) => setForm((current) => ({ ...current, childPageTerms: values }))}
                        suggestions={PAGE_HINT_SUGGESTIONS}
                        description="Labels for supporting pages that enrich a parent programme."
                      />
                      <ChipInput
                        label="Support Page Terms"
                        placeholder="Select or type support page terms..."
                        values={form.supportPageTerms}
                        onChange={(values) => setForm((current) => ({ ...current, supportPageTerms: values }))}
                        suggestions={PAGE_HINT_SUGGESTIONS}
                        description="Labels that usually point to docs, FAQs, or portals."
                      />
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-3">
                    <label className="flex items-center gap-2 text-sm font-medium">
                      <input
                        type="checkbox"
                        checked={form.strictPathPrefixes}
                        onChange={(event) =>
                          setForm((current) => ({ ...current, strictPathPrefixes: event.target.checked }))
                        }
                        className="h-4 w-4 rounded border border-input"
                      />
                      Strict path prefixes
                    </label>
                    <label className="flex items-center gap-2 text-sm font-medium">
                      <input
                        type="checkbox"
                        checked={form.allowRootUrl}
                        onChange={(event) => setForm((current) => ({ ...current, allowRootUrl: event.target.checked }))}
                        className="h-4 w-4 rounded border border-input"
                      />
                      Allow root URL
                    </label>
                    <label className="flex items-center gap-2 text-sm font-medium">
                      <input
                        type="checkbox"
                        checked={form.playwrightRequiredByDefault}
                        onChange={(event) =>
                          setForm((current) => ({ ...current, playwrightRequiredByDefault: event.target.checked }))
                        }
                        className="h-4 w-4 rounded border border-input"
                      />
                      Prefer browser fetch
                    </label>
                  </div>
                </div>
              )}
            </form>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  if (createStep === 1) {
                    setCreateOpen(false);
                    return;
                  }
                  setCreateStep(1);
                }}
              >
                {createStep === 1 ? "Cancel" : "Back"}
              </Button>
              {createStep === 1 ? (
                <Button type="button" onClick={handleNextStep}>
                  Next
                </Button>
              ) : (
                <Button type="submit" form="website-create-form" disabled={createSiteMutation.isPending}>
                  {createSiteMutation.isPending ? "Saving..." : "Save Website"}
                </Button>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Registered Websites</CardTitle>
          <CardDescription>Loaded from Supabase when available, or from the local fallback seed file.</CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              {error instanceof Error ? error.message : "Failed to load websites."}
            </div>
          ) : null}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Site</TableHead>
                <TableHead>Domain</TableHead>
                <TableHead>Adapter</TableHead>
                <TableHead>Seeds</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sites.map((site: WebsiteSite) => (
                <TableRow key={`${site.siteKey}:${site.primaryDomain}`}>
                  <TableCell>
                    <div className="space-y-1">
                      <Link to={`/admin/websites/${site.siteKey}`} className="font-medium text-emerald-700 hover:underline">
                        {site.displayName}
                      </Link>
                      <p className="text-xs text-muted-foreground">{site.siteKey}</p>
                    </div>
                  </TableCell>
                  <TableCell>{site.primaryDomain}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{site.adapterKey}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="max-w-[320px] space-y-1">
                      {site.seedUrls.slice(0, 2).map((url) => (
                        <p key={url} className="truncate text-xs text-muted-foreground" title={url}>
                          {url}
                        </p>
                      ))}
                      {site.seedUrls.length > 2 ? (
                        <p className="text-xs text-muted-foreground">+{site.seedUrls.length - 2} more</p>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={site.active ? "success" : "secondary"}>{site.active ? "active" : "inactive"}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button asChild variant="outline" size="icon" aria-label={`Edit ${site.displayName}`}>
                        <Link to={`/admin/websites/${site.siteKey}`}>
                          <PencilLine className="h-4 w-4" />
                        </Link>
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            type="button"
                            variant="destructive"
                            size="icon"
                            disabled={deleteSiteMutation.isPending}
                            aria-label={`Delete ${site.displayName}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent size="sm">
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete {site.displayName}?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently remove the website from the registry and cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => {
                                void deleteSiteMutation.mutateAsync(site.siteKey);
                              }}
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {!sites.length && !isLoading ? (
            <p className="mt-4 text-sm text-muted-foreground">No websites found yet. Add one using the button above.</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
