import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/services/api/client";

type SiteFormState = {
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
  adapterConfigExtras: Record<string, unknown>;
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

const PATH_PREFIX_SUGGESTIONS = [
  "/products-services/",
  "/programmes/",
  "/programs/",
  "/funding/",
  "/grants/",
  "/apply/",
  "/portal/",
  "/resources/"
];

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

const parseLines = (value: string): string[] =>
  value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

const toTextArray = (value: unknown): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") {
          return item.trim();
        }
        if (item && typeof item === "object") {
          const record = item as Record<string, unknown>;
          return (
            (typeof record.value === "string" ? record.value : "") ||
            (typeof record.text === "string" ? record.text : "") ||
            (typeof record.label === "string" ? record.label : "") ||
            (typeof record.url === "string" ? record.url : "")
          ).trim();
        }
        return "";
      })
      .filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  }
  return [];
};

const toBoolean = (value: unknown, fallback = false): boolean => {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const lowered = value.trim().toLowerCase();
    if (["true", "1", "yes", "on"].includes(lowered)) return true;
    if (["false", "0", "no", "off"].includes(lowered)) return false;
  }
  return fallback;
};

const knownConfigKeys = new Set([
  "industries",
  "use_of_funds",
  "ownership_targets",
  "allowed_path_prefixes",
  "include_url_terms",
  "exclude_url_terms",
  "discovery_terms",
  "parent_page_terms",
  "child_page_terms",
  "support_page_terms",
  "strict_path_prefixes",
  "allow_root_url",
  "playwright_required_by_default"
]);

const defaultFormState: SiteFormState = {
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
  playwrightRequiredByDefault: false,
  adapterConfigExtras: {}
};

const adapterConfigFromSite = (
  adapterConfig: Record<string, unknown>
): Pick<
  SiteFormState,
  | "industries"
  | "useOfFunds"
  | "ownershipTargets"
  | "allowedPathPrefixes"
  | "includeUrlTerms"
  | "excludeUrlTerms"
  | "discoveryTerms"
  | "parentPageTerms"
  | "childPageTerms"
  | "supportPageTerms"
  | "strictPathPrefixes"
  | "allowRootUrl"
  | "playwrightRequiredByDefault"
  | "adapterConfigExtras"
> => {
  const extras: Record<string, unknown> = {};
  Object.entries(adapterConfig).forEach(([key, value]) => {
    if (!knownConfigKeys.has(key)) {
      extras[key] = value;
    }
  });

  return {
    industries: toTextArray(adapterConfig.industries),
    useOfFunds: toTextArray(adapterConfig.use_of_funds),
    ownershipTargets: toTextArray(adapterConfig.ownership_targets),
    allowedPathPrefixes: toTextArray(adapterConfig.allowed_path_prefixes),
    includeUrlTerms: toTextArray(adapterConfig.include_url_terms),
    excludeUrlTerms: toTextArray(adapterConfig.exclude_url_terms),
    discoveryTerms: toTextArray(adapterConfig.discovery_terms),
    parentPageTerms: toTextArray(adapterConfig.parent_page_terms),
    childPageTerms: toTextArray(adapterConfig.child_page_terms),
    supportPageTerms: toTextArray(adapterConfig.support_page_terms),
    strictPathPrefixes: toBoolean(adapterConfig.strict_path_prefixes, false),
    allowRootUrl: toBoolean(adapterConfig.allow_root_url, true),
    playwrightRequiredByDefault: toBoolean(adapterConfig.playwright_required_by_default, false),
    adapterConfigExtras: extras
  };
};

const buildAdapterConfig = (form: SiteFormState): Record<string, unknown> => ({
  ...form.adapterConfigExtras,
  industries: form.industries,
  use_of_funds: form.useOfFunds,
  ownership_targets: form.ownershipTargets,
  allowed_path_prefixes: form.allowedPathPrefixes,
  include_url_terms: form.includeUrlTerms,
  exclude_url_terms: form.excludeUrlTerms,
  discovery_terms: form.discoveryTerms,
  parent_page_terms: form.parentPageTerms,
  child_page_terms: form.childPageTerms,
  support_page_terms: form.supportPageTerms,
  strict_path_prefixes: form.strictPathPrefixes,
  allow_root_url: form.allowRootUrl,
  playwright_required_by_default: form.playwrightRequiredByDefault
});

const emptyToUndefined = (values: string[]): string[] => values.filter(Boolean);

const fieldCount = (values: string[]): number => emptyToUndefined(values).length;

export function WebsiteDetailPage() {
  const { siteKey } = useParams<{ siteKey: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SiteFormState>(defaultFormState);

  const { data: site, isLoading, error } = useQuery({
    queryKey: ["sites", siteKey],
    queryFn: () => (siteKey ? apiClient.getSiteByKey(siteKey) : Promise.resolve(undefined)),
    enabled: Boolean(siteKey)
  });

  useEffect(() => {
    if (!site) {
      return;
    }
    const config = site.adapterConfig ?? {};
    const structuredConfig = adapterConfigFromSite(config);
    setForm({
      ...defaultFormState,
      displayName: site.displayName,
      primaryDomain: site.primaryDomain,
      adapterKey: site.adapterKey,
      seedUrls: site.seedUrls.join("\n"),
      notes: site.notes.join("\n"),
      active: site.active,
      ...structuredConfig
    });
  }, [site]);

  const activeLabel = useMemo(() => (site?.active ? "active" : "inactive"), [site?.active]);
  const adapterExtras = useMemo(() => Object.keys(form.adapterConfigExtras), [form.adapterConfigExtras]);

  const updateMutation = useMutation({
    mutationFn: apiClient.updateSite,
    onSuccess: async () => {
      toast.success("Website updated.");
      await queryClient.invalidateQueries({ queryKey: ["sites"] });
      await queryClient.invalidateQueries({ queryKey: ["sites", siteKey] });
    },
    onError: (mutationError) => {
      const message = mutationError instanceof Error ? mutationError.message : "Failed to update website.";
      toast.error(message);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: apiClient.deleteSite,
    onSuccess: async () => {
      toast.success("Website removed.");
      await queryClient.invalidateQueries({ queryKey: ["sites"] });
      await queryClient.invalidateQueries({ queryKey: ["sites", siteKey] });
      navigate("/admin/websites");
    },
    onError: (mutationError) => {
      const message = mutationError instanceof Error ? mutationError.message : "Failed to delete website.";
      toast.error(message);
    }
  });

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!site || !siteKey) {
      toast.error("Website not found.");
      return;
    }

    const seedUrls = parseLines(form.seedUrls);
    if (!form.displayName.trim() || !form.primaryDomain.trim() || !form.adapterKey.trim()) {
      toast.error("Display name, primary domain, and adapter key are required.");
      return;
    }
    if (!seedUrls.length) {
      toast.error("Add at least one seed URL.");
      return;
    }

    await updateMutation.mutateAsync({
      siteKey: site.siteKey,
      displayName: form.displayName.trim(),
      primaryDomain: form.primaryDomain.trim(),
      adapterKey: form.adapterKey.trim(),
      seedUrls,
      adapterConfig: buildAdapterConfig(form),
      notes: parseLines(form.notes),
      active: form.active
    });
  };

  if (!siteKey) {
    return (
      <div className="space-y-6">
        <SectionHeader title="Website Detail" description="No website selected." />
        <Button asChild variant="outline">
          <Link to="/admin/websites">Back to websites</Link>
        </Button>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <SectionHeader title="Website Detail" description="Inspect and edit one crawl target at a time." />
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load website."}
        </div>
        <Button asChild variant="outline">
          <Link to="/admin/websites">Back to websites</Link>
        </Button>
      </div>
    );
  }

  if (!isLoading && !site) {
    return (
      <div className="space-y-6">
        <SectionHeader title="Website Detail" description="Inspect and edit one crawl target at a time." />
        <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">Website not found.</div>
        <Button asChild variant="outline">
          <Link to="/admin/websites">Back to websites</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <SectionHeader
        title={site?.displayName ?? "Website Detail"}
        description="Edit the crawl rules, seed URLs, and structured metadata for this website."
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button asChild variant="outline">
          <Link to="/admin/websites">Back to websites</Link>
        </Button>
        <Badge variant={site?.active ? "success" : "secondary"}>{activeLabel}</Badge>
        <Badge variant="secondary">{site?.adapterKey ?? "..."}</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Primary domain</CardDescription>
            <CardTitle>{site?.primaryDomain ?? "..."}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Seed URLs</CardDescription>
            <CardTitle>{site?.seedUrls.length ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Extra config keys</CardDescription>
            <CardTitle>{adapterExtras.length}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,320px)]">
        <Card>
          <CardHeader>
            <CardTitle>Edit Website</CardTitle>
            <CardDescription>Update the details that drive the scraper and the admin registry.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-6" onSubmit={handleSubmit}>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="display-name">Display Name</Label>
                  <Input
                    id="display-name"
                    value={form.displayName}
                    onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="primary-domain">Primary Domain</Label>
                  <Input
                    id="primary-domain"
                    value={form.primaryDomain}
                    onChange={(event) => setForm((current) => ({ ...current, primaryDomain: event.target.value }))}
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="adapter-key">Adapter Key</Label>
                  <Input
                    id="adapter-key"
                    value={form.adapterKey}
                    onChange={(event) => setForm((current) => ({ ...current, adapterKey: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="seed-count">Seed URLs</Label>
                  <Input id="seed-count" value={`${fieldCount(parseLines(form.seedUrls))}`} readOnly />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="seed-urls">Seed URLs</Label>
                <Textarea
                  id="seed-urls"
                  value={form.seedUrls}
                  onChange={(event) => setForm((current) => ({ ...current, seedUrls: event.target.value }))}
                  placeholder={"https://www.nefcorp.co.za/products-services/\nhttps://www.nefcorp.co.za/"}
                  className="min-h-32"
                />
              </div>

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
                    suggestions={["news", "media", "press", "careers", "jobs", "blog", "privacy", "about", "contact"]}
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
                    onChange={(event) => setForm((current) => ({ ...current, strictPathPrefixes: event.target.checked }))}
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

              <div className="flex flex-wrap gap-3">
                <Button type="submit" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? "Saving..." : "Save Changes"}
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button type="button" variant="destructive" disabled={deleteMutation.isPending}>
                      {deleteMutation.isPending ? "Deleting..." : "Delete Website"}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent size="sm">
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete {site?.displayName ?? "this website"}?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will permanently remove the website from the registry and cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => {
                          if (siteKey) {
                            void deleteMutation.mutateAsync(siteKey);
                          }
                        }}
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Current Values</CardTitle>
            <CardDescription>Quick read-only summary of the stored structured config.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Structured fields</p>
              <div className="flex flex-wrap gap-2">
                {adapterExtras.length ? (
                  adapterExtras.map((key) => (
                    <Badge key={key} variant="secondary">
                      {key}
                    </Badge>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No extra keys preserved.</p>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Enabled arrays</p>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>Industries: {fieldCount(form.industries)}</p>
                <p>Use of funds: {fieldCount(form.useOfFunds)}</p>
                <p>Ownership targets: {fieldCount(form.ownershipTargets)}</p>
                <p>Allowed path prefixes: {fieldCount(form.allowedPathPrefixes)}</p>
                <p>Include terms: {fieldCount(form.includeUrlTerms)}</p>
                <p>Exclude terms: {fieldCount(form.excludeUrlTerms)}</p>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Behavior</p>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>Strict prefixes: {form.strictPathPrefixes ? "on" : "off"}</p>
                <p>Allow root URL: {form.allowRootUrl ? "on" : "off"}</p>
                <p>Prefer browser fetch: {form.playwrightRequiredByDefault ? "on" : "off"}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
