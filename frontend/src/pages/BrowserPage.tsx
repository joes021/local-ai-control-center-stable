import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CompatibilityCalculatorModal } from "../components/CompatibilityCalculatorModal";
import { CustomSelect } from "../components/CustomSelect";
import { ModelDownloadProgressCard } from "../components/ModelDownloadProgressCard";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { RuntimePilotIcon } from "../components/RuntimePilotIcon";
import { SupportPageDeck } from "../components/shell/SupportPageDeck";
import type { CompatibilityLaunchTarget } from "../lib/compatibility";
import {
  addBrowserModelToLocal,
  awaitModelActionResult,
  downloadBrowserModel,
  downloadBrowserCatalogModel,
  fetchBrowserCatalog,
  fetchDownloadProgress,
  refreshBrowserCatalog,
} from "../lib/api";
import type { BrowserCatalogQuery } from "../lib/api";
import type {
  ActionResult,
  BrowserCatalogItem,
  BrowserCatalogPayload,
  BrowserFitStatus,
  BrowserMtpStatus,
  CompatibilityCheckRequest,
  DownloadProgressPayload,
} from "../lib/types";

type BrowserCatalogEnvelope =
  | BrowserCatalogPayload
  | {
      items?: unknown;
      models?: unknown;
      catalog?: unknown;
      fetchedAt?: unknown;
      updatedAt?: unknown;
      sources?: unknown;
      refresh?: unknown;
    };

type SortKey =
  | "quant-asc"
  | "quant-desc"
  | "updated-desc"
  | "updated-asc"
  | "size-desc"
  | "size-asc"
  | "family-asc"
  | "fit-desc"
  | "source-asc";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function readString(value: unknown, fallback = ""): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

function readNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function readArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function normalizeSource(value: string): BrowserCatalogItem["source"] {
  const lowered = value.trim().toLowerCase();
  if (lowered.includes("hugging")) {
    return "huggingface";
  }
  if (lowered.includes("unsloth")) {
    return "unsloth";
  }
  return lowered || "other";
}

function normalizeMtpStatus(value: unknown): BrowserMtpStatus {
  const lowered = readString(value, "unknown").trim().toLowerCase();
  if (lowered.includes("has") || lowered.includes("mtp")) {
    return lowered.includes("no") || lowered.includes("bez") ? "no-mtp" : "has-mtp";
  }
  return lowered.includes("no") || lowered.includes("bez") ? "no-mtp" : "unknown";
}

function mtpLabel(status: BrowserMtpStatus): string {
  if (status === "has-mtp") {
    return "Has MTP";
  }
  if (status === "no-mtp") {
    return "No MTP";
  }
  return "Nepoznato";
}

function sourceLabel(source: string): string {
  if (source === "huggingface") {
    return "Hugging Face";
  }
  if (source === "unsloth") {
    return "Unsloth";
  }
  if (source === "other") {
    return "Other";
  }
  return source;
}

function normalizeQuantFilterKey(value: string): string {
  const upper = readString(value, "Nepoznato").trim().toUpperCase();
  if (!upper) {
    return "UNKNOWN";
  }
  const segments = upper.split("-");
  const quantIndex = segments.findIndex((segment) => /^(IQ\d|Q\d|BF16|F16|MXFP|NVFP)/.test(segment));
  if (quantIndex > 0) {
    return segments.slice(quantIndex).join("-");
  }
  return upper;
}

function normalizeFitStatus(value: unknown): BrowserFitStatus {
  const lowered = readString(value, "unknown").trim().toLowerCase();
  if (lowered.includes("radi")) {
    return "radi";
  }
  if (lowered.includes("granic")) {
    return "granicno";
  }
  if (lowered.includes("ne radi")) {
    return "ne radi";
  }
  return "nije provereno";
}

function fitLabel(status: BrowserFitStatus): string {
  if (status === "radi") {
    return "Radi";
  }
  if (status === "granicno") {
    return "Granicno";
  }
  if (status === "ne radi") {
    return "Ne radi";
  }
  return "Nije provereno";
}

function compactMtpLabel(status: BrowserMtpStatus): string {
  if (status === "has-mtp") {
    return "MTP";
  }
  if (status === "no-mtp") {
    return "No";
  }
  return "?";
}

function compactFitLabel(status: BrowserFitStatus): string {
  if (status === "radi") {
    return "OK";
  }
  if (status === "granicno") {
    return "~";
  }
  if (status === "ne radi") {
    return "No";
  }
  return "?";
}

function mtpDownloadOnlyGuidance(item: BrowserCatalogItem): string | null {
  if (item.mtpStatus === "has-mtp") {
    return "MTP modeli koriste llama.cpp draft-mtp put. Ako je TurboQuant izabran, panel će za takav model pasti nazad na llama.cpp.";
  }
  return null;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Nepoznato";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("sr-RS", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(parsed);
}

function formatSize(item: BrowserCatalogItem): string {
  if (item.sizeLabel) {
    return item.sizeLabel;
  }
  if (item.sizeBytes === null) {
    return "Nepoznato";
  }
  return `${(item.sizeBytes / 1024 ** 3).toFixed(1)} GiB`;
}

function formatCount(value: number | null): string {
  if (value === null) {
    return "Nepoznato";
  }
  return new Intl.NumberFormat("en-US").format(value);
}

function quantSortToken(value: string): { bits: number; familyRank: number; label: string } {
  const normalized = normalizeQuantFilterKey(value);
  if (normalized === "BF16" || normalized === "F16") {
    return { bits: 16, familyRank: 3, label: normalized };
  }
  const numericMatch = normalized.match(/(IQ|Q)(\d+)/);
  if (numericMatch) {
    return {
      bits: Number(numericMatch[2]),
      familyRank: numericMatch[1] === "IQ" ? 0 : 1,
      label: normalized,
    };
  }
  if (normalized.startsWith("MXFP")) {
    return { bits: 4, familyRank: 2, label: normalized };
  }
  if (normalized.startsWith("NVFP")) {
    return { bits: 4, familyRank: 2, label: normalized };
  }
  return { bits: Number.MAX_SAFE_INTEGER, familyRank: 4, label: normalized };
}

function compareQuantization(left: string, right: string): number {
  const leftToken = quantSortToken(left);
  const rightToken = quantSortToken(right);
  return (
    leftToken.bits - rightToken.bits ||
    leftToken.familyRank - rightToken.familyRank ||
    leftToken.label.localeCompare(rightToken.label)
  );
}

function buildItem(record: Record<string, unknown>): BrowserCatalogItem {
  const source = normalizeSource(
    readString(record.source || record.provider || record.catalogSource || record.origin, "other"),
  );
  const model = readString(record.model || record.label || record.name || record.title, "Nepoznat model");
  const family = readString(record.family || record.modelFamily || record.architecture, "Nepoznato");
  const quantization = readString(record.quantization || record.quant || record.gguf || record.variant, "Nepoznato");
  const sizeBytesGiB = readNumber(record.approxSizeGiB || record.sizeGiB);
  const sizeBytes =
    readNumber(record.sizeBytes || record.fileSizeBytes || record.bytes || record.approxSizeBytes) ??
    (sizeBytesGiB === null ? null : Math.round(sizeBytesGiB * 1024 ** 3));
  const sizeLabel =
    readString(record.sizeLabel || record.fileSizeLabel || record.approxSize || record.size, "") ||
    (sizeBytes === null ? "Nepoznato" : `${(sizeBytes / 1024 ** 3).toFixed(1)} GiB`);
  const mtpStatus = normalizeMtpStatus(record.mtpStatus || record.mtp || record.mtp_state);
  const fit = asRecord(record.fit);
  const fitStatus = normalizeFitStatus(record.fitStatus || fit.status || record.compatibility);
  const repo = readString(record.repo || record.repoId || record.repository || record.slug);
  const filename = readString(record.filename || record.fileName || record.ggufFilename);
  const id =
    readString(record.id) ||
    [source, repo || model, filename || quantization].filter(Boolean).join(":").replace(/\s+/g, "-");

  return {
    id,
    model,
    family,
    source,
    repoId: repo,
    quantization,
    quantFilterKey: normalizeQuantFilterKey(quantization),
    sizeLabel,
    sizeBytes,
    updatedAt: readString(record.updatedAt || record.lastUpdated || record.publishedAt || record.date) || null,
    mtpStatus,
    mtpLabel: readString(record.mtpLabel) || mtpLabel(mtpStatus),
    fitStatus,
    fitLabel: readString(record.fitLabel || fit.fitLabel || record.compatibilityLabel) || fitLabel(fitStatus),
    sourceUrl: readString(record.sourceUrl || record.url || record.webUrl || record.pageUrl),
    downloadUrl: readString(record.downloadUrl || record.fileUrl),
    summary: readString(record.summary || record.description || record.notes),
    filename,
    repo,
    tags: readArray(record.tags).map((entry) => readString(entry)).filter(Boolean),
    contextWindow: readNumber(record.contextWindow || record.ctx || record.context),
    downloads: readNumber(record.downloads || record.downloadCount),
    likes: readNumber(record.likes || record.likeCount || record.stars),
    addedToLocal: Boolean(record.addedToLocal || record.inLocalCatalog || record.local),
    localModelId: readString(record.localModelId || record.modelId || record.local_id) || null,
  };
}

function buildRefreshActionResult(source: string | undefined, payload: BrowserCatalogPayload): ActionResult {
  const sourceLabelText =
    !source || source === "all" ? "internet" : source === "huggingface" ? "Hugging Face" : source === "unsloth" ? "Unsloth" : source;
  const count = Number(payload.refresh.counts?.all ?? 0);
  const warningCount = payload.refresh.warnings.length;
  const errorCount = payload.refresh.errors.length;
  const summaryParts = [`Catalog refresh završen za ${sourceLabelText}.`, `Modela: ${count}.`];
  if (warningCount > 0) {
    summaryParts.push(`Warnings: ${warningCount}.`);
  }
  if (errorCount > 0) {
    summaryParts.push(`Errors: ${errorCount}.`);
  }
  const detailsLines = [
    `Last refresh: ${payload.refresh.lastRefresh || "--"}`,
    `HF: ${String(payload.refresh.counts?.huggingface ?? 0)}`,
    `Unsloth: ${String(payload.refresh.counts?.unsloth ?? 0)}`,
    ...(warningCount ? ["", "Warnings:", ...payload.refresh.warnings] : []),
    ...(errorCount ? ["", "Errors:", ...payload.refresh.errors] : []),
  ];
  return {
    status: errorCount ? "error" : "ok",
    action: "browser-refresh",
    summary: summaryParts.join(" "),
    details: {
      returncode: errorCount ? 1 : 0,
      stdout: detailsLines.join("\n"),
      stderr: errorCount ? payload.refresh.errors.join("\n") : "",
    },
  };
}

function nextSortKey(current: SortKey, column: "quant" | "size" | "updated"): SortKey {
  if (column === "quant") {
    return current === "quant-asc" ? "quant-desc" : "quant-asc";
  }
  if (column === "size") {
    return current === "size-desc" ? "size-asc" : "size-desc";
  }
  return current === "updated-desc" ? "updated-asc" : "updated-desc";
}

function normalizeCatalogPayload(payload: BrowserCatalogEnvelope): BrowserCatalogPayload {
  const envelope = asRecord(payload);
  const itemsSource = readArray(envelope.items ?? envelope.models ?? envelope.catalog);
  const items = itemsSource.map((entry) => buildItem(asRecord(entry))).filter((item) => item.id);
  const refresh = asRecord(envelope.refresh);

  return {
    models: items as unknown as Array<Record<string, unknown>>,
    refresh: {
      lastRefresh: readString(refresh.lastRefresh || envelope.fetchedAt || envelope.updatedAt),
      counts: asRecord(refresh.counts) as Record<string, number>,
      warnings: readArray(refresh.warnings).map((item) => readString(item)).filter(Boolean),
      errors: readArray(refresh.errors).map((item) => readString(item)).filter(Boolean),
      sources: asRecord(refresh.sources) as Record<string, Record<string, unknown>>,
    },
  };
}

function isDefaultBrowserQuery(query: BrowserCatalogQuery): boolean {
  return (
    (query.source ?? "all") === "all" &&
    !(query.search ?? "").trim() &&
    (query.family ?? "all") === "all" &&
    (query.quant ?? "all") === "all" &&
    (query.size ?? "all") === "all" &&
    (query.mtp ?? "all") === "all" &&
    (query.date ?? "all") === "all" &&
    (query.sort ?? "updated-desc") === "updated-desc" &&
    !query.limit
  );
}

function compareItems(left: BrowserCatalogItem, right: BrowserCatalogItem, sortKey: SortKey): number {
  const fitRank: Record<BrowserFitStatus, number> = {
    radi: 3,
    granicno: 2,
    "ne radi": 1,
    "nije provereno": 0,
  };

  if (sortKey === "updated-desc") {
    return (new Date(right.updatedAt ?? 0).getTime() || 0) - (new Date(left.updatedAt ?? 0).getTime() || 0);
  }
  if (sortKey === "updated-asc") {
    return (new Date(left.updatedAt ?? 0).getTime() || 0) - (new Date(right.updatedAt ?? 0).getTime() || 0);
  }
  if (sortKey === "quant-asc") {
    return compareQuantization(left.quantization, right.quantization) || left.model.localeCompare(right.model);
  }
  if (sortKey === "quant-desc") {
    return compareQuantization(right.quantization, left.quantization) || left.model.localeCompare(right.model);
  }
  if (sortKey === "size-desc") {
    return (right.sizeBytes ?? -1) - (left.sizeBytes ?? -1);
  }
  if (sortKey === "size-asc") {
    return (left.sizeBytes ?? Number.MAX_SAFE_INTEGER) - (right.sizeBytes ?? Number.MAX_SAFE_INTEGER);
  }
  if (sortKey === "family-asc") {
    return left.family.localeCompare(right.family) || left.model.localeCompare(right.model);
  }
  if (sortKey === "fit-desc") {
    return fitRank[right.fitStatus] - fitRank[left.fitStatus] || left.model.localeCompare(right.model);
  }
  return left.source.localeCompare(right.source) || left.model.localeCompare(right.model);
}

export function BrowserPage({
  onOpenCompatibilityTab,
}: {
  onOpenCompatibilityTab?: (target: CompatibilityLaunchTarget) => void;
}) {
  const rowsPerPage = 25;
  const [catalog, setCatalog] = useState<BrowserCatalogPayload | null>(null);
  const [catalogIndex, setCatalogIndex] = useState<BrowserCatalogPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [familyFilter, setFamilyFilter] = useState("all");
  const [quantFilter, setQuantFilter] = useState("all");
  const [sizeFilter, setSizeFilter] = useState("all");
  const [mtpFilter, setMtpFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("updated-desc");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [compatibilityRequest, setCompatibilityRequest] = useState<CompatibilityCheckRequest | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [downloadOffer, setDownloadOffer] = useState<{ modelId: string; label: string } | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgressPayload | null>(null);
  const [warningsExpanded, setWarningsExpanded] = useState(false);
  const [errorsExpanded, setErrorsExpanded] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageJumpValue, setPageJumpValue] = useState("1");
  const [initialRefreshTriggered, setInitialRefreshTriggered] = useState(false);
  const deferredSearch = useDeferredValue(search);
  const progressStatusRef = useRef<string | null>(null);
  const catalogRequestRef = useRef(0);
  const catalogIndexRequestRef = useRef(0);

  const browserQuery = useMemo<BrowserCatalogQuery>(
    () => ({
      source: sourceFilter,
      search: deferredSearch.trim(),
      family: familyFilter,
      quant: quantFilter,
      size: sizeFilter,
      mtp: mtpFilter,
      date: dateFilter,
      sort: sortKey,
    }),
    [dateFilter, deferredSearch, familyFilter, mtpFilter, quantFilter, sizeFilter, sortKey, sourceFilter],
  );

  function applyCatalogToView(payload: BrowserCatalogPayload) {
    setCatalog(payload);
    const models = payload.models.map((item) => buildItem(asRecord(item)));
    setSelectedId((current) => {
      if (current && models.some((item) => item.id === current)) {
        return current;
      }
      return models[0]?.id ?? null;
    });
  }

  async function loadCatalog(query: BrowserCatalogQuery = browserQuery) {
    const requestId = ++catalogRequestRef.current;
    try {
      const payload = await fetchBrowserCatalog(query);
      const normalized = normalizeCatalogPayload(payload as BrowserCatalogEnvelope);
      if (requestId != catalogRequestRef.current) {
        return null;
      }
      applyCatalogToView(normalized);
      setError(null);
      return normalized;
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Browser catalog request failed.";
      setError(message);
      return null;
    }
  }

  async function loadCatalogIndex(options: { syncTable?: boolean } = {}) {
    const requestId = ++catalogIndexRequestRef.current;
    try {
      const payload = await fetchBrowserCatalog();
      const normalized = normalizeCatalogPayload(payload as BrowserCatalogEnvelope);
      if (requestId != catalogIndexRequestRef.current) {
        return null;
      }
      setCatalogIndex(normalized);
      if (options.syncTable || !catalog) {
        applyCatalogToView(normalized);
      }
      setError(null);
      return normalized;
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Browser catalog request failed.";
      setError(message);
      return null;
    }
  }

  async function refreshCatalogViewFromCache(options: { syncTable?: boolean } = {}) {
    const defaultView = isDefaultBrowserQuery(browserQuery);
    const indexPayload = await loadCatalogIndex({ syncTable: options.syncTable ?? defaultView });
    if (!indexPayload || defaultView) {
      return;
    }
    await loadCatalog(browserQuery);
  }

  useEffect(() => {
    void refreshCatalogViewFromCache({ syncTable: true });
    void fetchDownloadProgress()
      .then((payload) => {
        setDownloadProgress(payload);
        progressStatusRef.current = payload.status;
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    if (!catalogIndex) {
      return;
    }
    if (isDefaultBrowserQuery(browserQuery)) {
      applyCatalogToView(catalogIndex);
      return;
    }
    void loadCatalog();
  }, [browserQuery, catalogIndex]);

  useEffect(() => {
    if (!catalog || initialRefreshTriggered || pendingAction?.startsWith("refresh-")) {
      return;
    }
    if (catalog.models.length > 0 || catalog.refresh.lastRefresh) {
      return;
    }
    setInitialRefreshTriggered(true);
    void handleRefresh();
  }, [catalog, initialRefreshTriggered, pendingAction]);

  useEffect(() => {
    let cancelled = false;

    async function pollProgress() {
      try {
        const payload = await fetchDownloadProgress();
        if (cancelled) {
          return;
        }
        const previousStatus = progressStatusRef.current;
        progressStatusRef.current = payload.status;
        setDownloadProgress(payload);
        if (
          previousStatus !== payload.status &&
          (payload.status === "completed" || payload.status === "already-installed" || payload.status === "error")
        ) {
          await refreshCatalogViewFromCache();
        }
      } catch {
        if (!cancelled) {
          setDownloadProgress(null);
        }
      }
    }

    void pollProgress();
    const timer = window.setInterval(() => {
      void pollProgress();
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const familyOptions = useMemo(() => {
    if (!catalogIndex) {
      return [];
    }
    const items = catalogIndex.models
      .map((item) => buildItem(asRecord(item)))
      .filter((item) => sourceFilter === "all" || item.source === sourceFilter);
    return Array.from(new Set(items.map((item) => item.family).filter(Boolean))).sort();
  }, [catalogIndex, sourceFilter]);

  const quantOptions = useMemo(() => {
    if (!catalogIndex) {
      return [];
    }
    const items = catalogIndex.models
      .map((item) => buildItem(asRecord(item)))
      .filter((item) => sourceFilter === "all" || item.source === sourceFilter)
      .filter((item) => familyFilter === "all" || item.family === familyFilter);
    return Array.from(new Set(items.map((item) => item.quantFilterKey).filter(Boolean))).sort(compareQuantization);
  }, [catalogIndex, familyFilter, sourceFilter]);

  const filteredItems = useMemo(() => {
    if (!catalog) {
      return [];
    }
    return catalog.models.map((entry) => buildItem(asRecord(entry)));
  }, [catalog]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / rowsPerPage));
  const pageStart = (currentPage - 1) * rowsPerPage;
  const paginatedItems = filteredItems.slice(pageStart, pageStart + rowsPerPage);

  function jumpToCatalogPage(rawValue: string) {
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) {
      setPageJumpValue(String(currentPage));
      return;
    }
    const nextPage = Math.min(totalPages, Math.max(1, Math.trunc(parsed)));
    setCurrentPage(nextPage);
    setPageJumpValue(String(nextPage));
  }

  useEffect(() => {
    setCurrentPage(1);
  }, [deferredSearch, sourceFilter, familyFilter, quantFilter, sizeFilter, mtpFilter, dateFilter, sortKey]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  useEffect(() => {
    setPageJumpValue(String(currentPage));
  }, [currentPage]);

  useEffect(() => {
    if (!filteredItems.length) {
      setSelectedId(null);
      setCompatibilityRequest(null);
      return;
    }

    if (!selectedId || !paginatedItems.some((item) => item.id === selectedId)) {
      setSelectedId(paginatedItems[0]?.id ?? filteredItems[0].id);
      setCompatibilityRequest(null);
    }
  }, [filteredItems, paginatedItems, selectedId]);

  const selectedItem = filteredItems.find((item) => item.id === selectedId) ?? null;

  async function handleRefresh(source?: string) {
    setPendingAction(`refresh-${source ?? "all"}`);
    setResult({
      status: "pending",
      action: "browser-refresh",
      summary: source ? `Osvežavam ${source} katalog...` : "Osvežavam sa interneta...",
      details: { returncode: 0, stdout: "", stderr: "" },
    });

    try {
      const refreshPayload = normalizeCatalogPayload(await refreshBrowserCatalog(source));
      setCatalogIndex(refreshPayload);
      if (isDefaultBrowserQuery(browserQuery)) {
        applyCatalogToView(refreshPayload);
      }
      setResult(buildRefreshActionResult(source, refreshPayload));
      setError(null);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Osvežavanje sa interneta nije uspelo.";
      setResult({
        status: "error",
        action: "browser-refresh",
        summary: message,
        details: { returncode: 1, stdout: "", stderr: message },
      });
    } finally {
      setPendingAction(null);
    }
  }

  async function handleAddToLocal(item: BrowserCatalogItem) {
    setPendingAction(`add-${item.id}`);
    setResult({
      status: "pending",
      action: "browser-add",
      summary: `Dodajem ${item.model} u lokalni katalog...`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });

    try {
      const addResult = await addBrowserModelToLocal({
        source: item.source,
        repoId: item.repo,
        filename: item.filename,
        label: item.model,
        family: item.family,
      });
      const finalResult = await awaitModelActionResult(addResult, setResult);
      setResult(finalResult);
      setDownloadOffer({
        modelId: addResult.localModelId || item.localModelId || item.id,
        label: item.model,
      });
      setCatalog((current) =>
        current
          ? {
              ...current,
              models: current.models.map((entry) =>
                buildItem(asRecord(entry)).id === item.id
                  ? {
                      ...entry,
                      addedToLocal: true,
                      localModelId: addResult.localModelId || entry.localModelId || item.id,
                    }
                  : entry,
              ),
            }
          : current,
      );
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Dodavanje u lokalni katalog nije uspelo.";
      setResult({
        status: "error",
        action: "browser-add",
        summary: message,
        details: { returncode: 1, stdout: "", stderr: message },
      });
    } finally {
      setPendingAction(null);
    }
  }

  async function handleDownload(modelId: string, label: string) {
    setPendingAction(`download-${modelId}`);
    setResult({
      status: "pending",
      action: "browser-download",
      summary: `Pokrećem preuzimanje za ${label}...`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });

    try {
      const downloadResult = await downloadBrowserModel(modelId);
      const finalResult = await awaitModelActionResult(downloadResult, setResult);
      setResult(finalResult);
      setDownloadOffer(null);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Preuzimanje nije uspelo.";
      setResult({
        status: "error",
        action: "browser-download",
        summary: message,
        details: { returncode: 1, stdout: "", stderr: message },
      });
    } finally {
      setPendingAction(null);
    }
  }

  async function handleDirectBrowserDownload(item: BrowserCatalogItem) {
    setPendingAction(`download-${item.id}`);
    setResult({
      status: "pending",
      action: "browser-download",
      summary: `Pokrećem preuzimanje za ${item.model}...`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });

    try {
      const downloadResult = await downloadBrowserCatalogModel({
        source: item.source,
        repoId: item.repo,
        filename: item.filename,
        label: item.model,
        family: item.family,
      });
      const finalResult = await awaitModelActionResult(downloadResult, setResult);
      setResult(finalResult);
      setDownloadOffer(null);
      await loadCatalog();
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Preuzimanje nije uspelo.";
      setResult({
        status: "error",
        action: "browser-download",
        summary: message,
        details: { returncode: 1, stdout: "", stderr: message },
      });
    } finally {
      setPendingAction(null);
    }
  }

  async function handleCompatibility(item: BrowserCatalogItem) {
    setCompatibilityRequest({ catalogModelId: item.id });
  }

  if (!catalog) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam Browser katalog..."
        onRetry={() => {
          setError(null);
          void refreshCatalogViewFromCache({ syncTable: true });
        }}
      />
    );
  }

  const sourceOptions = [
    { value: "all", label: "Svi izvori" },
    { value: "huggingface", label: "Hugging Face" },
    { value: "unsloth", label: "Unsloth" },
    { value: "other", label: "Drugo" },
  ];
  const familySelectOptions = [
    { value: "all", label: "Sve familije" },
    ...familyOptions.map((family) => ({ value: family, label: family })),
  ];
  const quantSelectOptions = [
    { value: "all", label: "Sve kvantizacije" },
    ...quantOptions.map((quantization) => ({ value: quantization, label: quantization })),
  ];
  const sizeOptions = [
    { value: "all", label: "Sve veličine" },
    { value: "small", label: "Malo (<4 GiB)" },
    { value: "medium", label: "Srednje (4-16 GiB)" },
    { value: "large", label: "Veliko (>16 GiB)" },
  ];
  const mtpOptions = [
    { value: "all", label: "Bilo koji MTP" },
    { value: "has-mtp", label: "Ima MTP" },
    { value: "no-mtp", label: "Nema MTP" },
    { value: "unknown", label: "Nepoznato" },
  ];
  const dateOptions = [
    { value: "all", label: "Bilo kada" },
    { value: "7d", label: "Poslednjih 7 dana" },
    { value: "30d", label: "Poslednjih 30 dana" },
    { value: "90d", label: "Poslednjih 90 dana" },
  ];
  const sortOptions = [
    { value: "quant-asc", label: "Manji quant prvo" },
    { value: "quant-desc", label: "Veći quant prvo" },
    { value: "updated-desc", label: "Najnovije prvo" },
    { value: "updated-asc", label: "Najstarije prvo" },
    { value: "fit-desc", label: "Najbolji fit prvo" },
    { value: "size-desc", label: "Najveće prvo" },
    { value: "size-asc", label: "Najmanje prvo" },
    { value: "family-asc", label: "Familija A-Š" },
    { value: "source-asc", label: "Izvor A-Š" },
  ];

  const refreshCounts = catalog.refresh.counts || {};
  const warningCount = catalog.refresh.warnings.length;
  const errorCount = catalog.refresh.errors.length;
  const refreshInProgress = Boolean(pendingAction?.startsWith("refresh-"));

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <SupportPageDeck
        eyebrow="Browser katalog"
        title="Osveži, filtriraj, pa odluči"
        summary="Najzdraviji redosled je da prvo osvežiš katalog, zatim filtriraš modele, pa tek onda dodaješ lokalno ili proveravaš fit za svoju mašinu."
        actionsBelowTitle={true}
        actionsClassName="browser-support-actions"
        steps={[
          {
            title: "Osveži katalog",
            detail: "Ako sumnjaš da su brojači zastareli, prvo povuci sveže modele sa interneta.",
          },
          {
            title: "Filtriraj model",
            detail: "Suzi izbor po source, family, quant, veličini i datumu pre nego što otvoriš detalje.",
          },
          {
            title: "Dodaj lokalno ili proveri fit",
            detail: "Kada nađeš kandidata, dodaj ga u lokalni katalog ili idi na tab kompatibilnosti za potvrdu.",
          },
        ]}
        actions={
          <>
            <button type="button" className="secondary-button" onClick={() => void handleRefresh()}>
              Osveži katalog
            </button>
            <button type="button" className="secondary-button" onClick={() => void handleRefresh("huggingface")}>
              Osveži HF
            </button>
            <button type="button" className="secondary-button" onClick={() => void handleRefresh("unsloth")}>
              Osveži Unsloth
            </button>
          </>
        }
        resultHint={
          <>
            <span className="status-label">Gde vidiš rezultat</span>
            <strong className="status-value">Tabela, detalj panela i status preuzimanja</strong>
            <p className="helper-text">
              Posle osvežavanja ili dodavanja modela, rezultat se vidi odmah niže kroz brojke kataloga,
              listu modela i download status.
            </p>
          </>
        }
      />
      <section className="status-card wide-card runtimepilot-faceplate-module">
        <div className="section-header">
          <div>
            <span className="status-label">Browser</span>
            <strong className="status-value">Udaljeni GGUF katalog</strong>
            <p className="helper-text">
              Jedna tabela za Hugging Face i Unsloth GGUF modele. Izvor ostaje filter i bedž, dok
              Modeli ostaje lokalni katalog.
            </p>
          </div>
          <div className="inline-actions compact-actions browser-refresh-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={!selectedItem}
              onClick={() => {
                if (!selectedItem) {
                  return;
                }
                onOpenCompatibilityTab?.({
                  title: selectedItem.model,
                  request: { catalogModelId: selectedItem.id },
                });
              }}
            >
              Tab kompatibilnosti
            </button>
          </div>
        </div>
        <div className="browser-toolbar">
          <label className="browser-field">
            <span>Pretraga</span>
            <input
              type="text"
              placeholder="Pretraži model, familiju, repo i kvantizaciju..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="browser-field">
            <span>Izvor</span>
            <CustomSelect value={sourceFilter} options={sourceOptions} onChange={setSourceFilter} ariaLabel="Source filter" />
          </label>
          <label className="browser-field">
            <span>Familija modela</span>
            <CustomSelect value={familyFilter} options={familySelectOptions} onChange={setFamilyFilter} ariaLabel="Family filter" />
          </label>
          <label className="browser-field">
            <span>Quant</span>
            <CustomSelect value={quantFilter} options={quantSelectOptions} onChange={setQuantFilter} ariaLabel="Quant filter" />
          </label>
          <label className="browser-field">
            <span>Veličina</span>
            <CustomSelect value={sizeFilter} options={sizeOptions} onChange={setSizeFilter} ariaLabel="Size filter" />
          </label>
          <label className="browser-field">
            <span>MTP status</span>
            <CustomSelect value={mtpFilter} options={mtpOptions} onChange={setMtpFilter} ariaLabel="MTP filter" />
          </label>
          <label className="browser-field">
            <span>Datum</span>
            <CustomSelect value={dateFilter} options={dateOptions} onChange={setDateFilter} ariaLabel="Date filter" />
          </label>
          <label className="browser-field">
            <span>Sort</span>
            <CustomSelect value={sortKey} options={sortOptions} onChange={(value) => setSortKey(value as SortKey)} ariaLabel="Sort browser table" />
          </label>
        </div>
        <section className="browser-overview">
          <div className="browser-overview-main">
            <strong>
              Prikazano {filteredItems.length} od {refreshCounts.all ?? filteredItems.length} modela
            </strong>
            <span>Poslednje osvežavanje kataloga: {formatDate(catalog.refresh.lastRefresh || null)}</span>
          </div>
          <div className="browser-overview-meta">
            <span>HF: {refreshCounts.huggingface ?? 0}</span>
            <span>Unsloth: {refreshCounts.unsloth ?? 0}</span>
            {warningCount ? <span>Upozorenja: {warningCount}</span> : null}
            {errorCount ? <span>Greške: {errorCount}</span> : null}
          </div>
        </section>
        {refreshInProgress ? (
          <section className="browser-notice browser-notice-info">
            <div className="browser-notice-header">
              <div>
                <strong>Osvežavanje kataloga je u toku</strong>
                <p className="helper-text">
                  Prvo punjenje može da traje oko minut jer RuntimePilot proverava Hugging Face i Unsloth izvore.
                  Čim odgovor stigne, tabela i brojači se osvežavaju automatski.
                </p>
              </div>
            </div>
          </section>
        ) : null}
        {warningCount ? (
          <section className="browser-notice browser-notice-warning">
            <div className="browser-notice-header">
              <div>
                <strong>Upozorenja kataloga</strong>
                <p className="helper-text">
                  Neki repozitorijumi imaju više GGUF fajlova nego što je trenutno prikazano. Ovo
                  ne blokira Browser, ali znači da je pregled skraćen.
                </p>
              </div>
              <button type="button" className="secondary-button" onClick={() => setWarningsExpanded((current) => !current)}>
                {warningsExpanded ? "Skupi upozorenja" : `Proširi upozorenja (${warningCount})`}
              </button>
            </div>
            {warningsExpanded ? (
              <div className="browser-notice-list">
                {catalog.refresh.warnings.map((warning) => (
                  <div className="browser-notice-item" key={warning}>
                    {warning}
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}
        {errorCount ? (
          <section className="browser-notice browser-notice-error">
            <div className="browser-notice-header">
              <div>
                <strong>Greške kataloga</strong>
                <p className="helper-text">
                  Ove greške su sačuvane iz poslednjeg osvežavanja i mogu da objasne zašto deo kataloga nije kompletan.
                </p>
              </div>
              <button type="button" className="secondary-button" onClick={() => setErrorsExpanded((current) => !current)}>
                {errorsExpanded ? "Skupi greške" : `Proširi greške (${errorCount})`}
              </button>
            </div>
            {errorsExpanded ? (
              <div className="browser-notice-list">
                {catalog.refresh.errors.map((catalogError) => (
                  <div className="browser-notice-item" key={catalogError}>
                    {catalogError}
                  </div>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module browser-results-stack">
        {selectedItem ? (
          <section className="browser-detail-top runtimepilot-faceplate-module">
            <div className="browser-detail-rack">
              <section className="browser-detail-hero runtime-faceplate-support">
                <div className="runtime-faceplate-head">
                  <div className="runtime-faceplate-headline">
                    <span className="runtime-faceplate-module-glyph" aria-hidden="true">
                      <RuntimePilotIcon className="runtime-faceplate-module-icon" name="browser" />
                    </span>
                    <div className="runtime-faceplate-module-copy">
                      <span className="status-label">Panel detalja</span>
                      <strong className="status-value">{selectedItem.model}</strong>
                      <p className="muted-line">
                        {selectedItem.family} | {selectedItem.quantization}
                      </p>
                    </div>
                  </div>
                  <div className="runtime-faceplate-status-lights" aria-hidden="true">
                    <span className="runtime-faceplate-status-light runtime-faceplate-status-light-active" />
                    <span
                      className={`runtime-faceplate-status-light ${
                        selectedItem.fitStatus !== "nije provereno" ? "runtime-faceplate-status-light-active-soft" : ""
                      }`}
                    />
                    <span
                      className={`runtime-faceplate-status-light ${
                        selectedItem.mtpStatus === "has-mtp" ? "runtime-faceplate-status-light-active-soft" : ""
                      }`}
                    />
                  </div>
                </div>

                <div className="runtime-faceplate-copy browser-detail-copy">
                  <div className="browser-detail-pill-row">
                    <span
                      className={`browser-badge browser-source-${selectedItem.source}`}
                      title={sourceLabel(selectedItem.source)}
                    >
                      {sourceLabel(selectedItem.source)}
                    </span>
                    <span
                      className={`browser-badge browser-fit-${selectedItem.fitStatus.replace(/\s+/g, "-")}`}
                      title={selectedItem.fitLabel}
                    >
                      Fit · {selectedItem.fitLabel}
                    </span>
                    <span className={`browser-badge browser-mtp-${selectedItem.mtpStatus}`} title={selectedItem.mtpLabel}>
                      MTP · {selectedItem.mtpLabel}
                    </span>
                  </div>
                  <p className="helper-text">
                    {selectedItem.summary || "Izabrani katalog modela je spreman za proveru, dodavanje u lokalni katalog ili direktno preuzimanje."}
                  </p>
                  {mtpDownloadOnlyGuidance(selectedItem) ? (
                    <p className="helper-text">{mtpDownloadOnlyGuidance(selectedItem)}</p>
                  ) : null}
                </div>

                <div className="runtime-faceplate-rail browser-detail-action-rail browser-detail-action-row">
                  <span className="status-label">Komande</span>
                  <button
                    type="button"
                    className="action-button-soft deck-control-button deck-control-button-primary"
                    disabled={Boolean(pendingAction)}
                    onClick={() => void handleDirectBrowserDownload(selectedItem)}
                  >
                    <span className="deck-control-symbol" aria-hidden="true">
                      <RuntimePilotIcon name="play" />
                    </span>
                    <span className="deck-control-copy">Preuzmi</span>
                  </button>
                  <button
                    type="button"
                    className="action-button-soft deck-control-button deck-control-button-secondary"
                    disabled={Boolean(pendingAction)}
                    onClick={() => void handleAddToLocal(selectedItem)}
                  >
                    <span className="deck-control-symbol" aria-hidden="true">
                      <RuntimePilotIcon name="models" />
                    </span>
                    <span className="deck-control-copy">Dodaj u lokalni katalog</span>
                  </button>
                  <button
                    type="button"
                    className="action-button-soft deck-control-button deck-control-button-secondary"
                    disabled={Boolean(pendingAction)}
                    onClick={() => void handleCompatibility(selectedItem)}
                  >
                    <span className="deck-control-symbol" aria-hidden="true">
                      <RuntimePilotIcon name="compatibility" />
                    </span>
                    <span className="deck-control-copy">Proveri kompatibilnost</span>
                  </button>
                  <button
                    type="button"
                    className="action-button-soft deck-control-button deck-control-button-secondary"
                    disabled={!selectedItem.sourceUrl}
                    onClick={() => window.open(selectedItem.sourceUrl, "_blank", "noopener,noreferrer")}
                  >
                    <span className="deck-control-symbol" aria-hidden="true">
                      <RuntimePilotIcon name="browser" />
                    </span>
                    <span className="deck-control-copy">Otvori izvornu stranicu</span>
                  </button>
                </div>
              </section>

              <div className="browser-detail-module-grid">
                <section className="browser-detail-module browser-detail-specs browser-detail-specs-wide">
                  <div className="browser-detail-module-header">
                    <span className="status-label">Signal i specifikacije</span>
                    <strong className="status-value">Šta vidiš pre nego što krene download</strong>
                  </div>
                  <div className="browser-detail-specs-note">
                    <strong>Kompatibilnost pa lokalni katalog.</strong>
                    <p className="helper-text">
                      Koristi <strong>Proveri kompatibilnost</strong> da otvoriš kalkulator kompatibilnosti pre nego što
                      dodaš model u lokalni katalog.
                    </p>
                  </div>
                  <div className="browser-metadata-grid browser-metadata-grid-hifi">
                    <article className="browser-readout-card">
                      <span className="status-label">Veličina</span>
                      <strong className="status-value">{formatSize(selectedItem)}</strong>
                    </article>
                    <article className="browser-readout-card">
                      <span className="status-label">Poslednje ažuriranje</span>
                      <strong className="status-value">{formatDate(selectedItem.updatedAt)}</strong>
                    </article>
                    <article className="browser-readout-card">
                      <span className="status-label">Repo</span>
                      <strong className="status-value">{selectedItem.repo || "Nepoznato"}</strong>
                    </article>
                    <article className="browser-readout-card">
                      <span className="status-label">Preuzimanja</span>
                      <strong className="status-value">{formatCount(selectedItem.downloads)}</strong>
                    </article>
                  </div>
                  {selectedItem.tags.length ? (
                    <div className="browser-chip-row browser-detail-chip-row">
                      {selectedItem.tags.map((tag) => (
                        <span key={tag} className="browser-chip">
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {downloadOffer && downloadOffer.label === selectedItem.model ? (
                    <div className="browser-callout">
                      <strong>Dodato u lokalni katalog.</strong> Preuzimanje je i dalje ručno. Ako želiš fajl odmah, pokreni ga sada.
                      <div className="inline-actions compact-actions">
                        <button type="button" onClick={() => void handleDownload(downloadOffer.modelId, downloadOffer.label)}>
                          Preuzmi sada
                        </button>
                        <button type="button" className="secondary-button" onClick={() => setDownloadOffer(null)}>
                          Kasnije
                        </button>
                      </div>
                    </div>
                  ) : null}
                </section>
              </div>

              <ModelDownloadProgressCard progress={downloadProgress} />

              {result ? <ActionResultPanel result={result} /> : null}
            </div>
          </section>
        ) : (
          <div className="helper-text">Izaberi red u Browser tabeli da vidiš detalje i akcije.</div>
        )}

        <div className="browser-table-panel">
          <div className="browser-table-wrap">
            <table className="browser-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Family</th>
                  <th>Izvor</th>
                  <th>
                    <button
                      type="button"
                      className={`browser-sort-button ${sortKey === "quant-asc" || sortKey === "quant-desc" ? "browser-sort-button-active" : ""}`}
                      onClick={() => setSortKey((current) => nextSortKey(current, "quant"))}
                    >
                      Quant
                      <span className="browser-sort-indicator">
                        {sortKey === "quant-asc" ? "↑" : sortKey === "quant-desc" ? "↓" : "↕"}
                      </span>
                    </button>
                  </th>
                  <th>
                    <button
                      type="button"
                      className={`browser-sort-button ${sortKey === "size-desc" || sortKey === "size-asc" ? "browser-sort-button-active" : ""}`}
                      onClick={() => setSortKey((current) => nextSortKey(current, "size"))}
                    >
                      Veličina
                      <span className="browser-sort-indicator">
                        {sortKey === "size-desc" ? "↓" : sortKey === "size-asc" ? "↑" : "↕"}
                      </span>
                    </button>
                  </th>
                  <th>
                    <button
                      type="button"
                      className={`browser-sort-button ${sortKey === "updated-desc" || sortKey === "updated-asc" ? "browser-sort-button-active" : ""}`}
                      onClick={() => setSortKey((current) => nextSortKey(current, "updated"))}
                    >
                      Poslednje ažuriranje
                      <span className="browser-sort-indicator">
                        {sortKey === "updated-desc" ? "↓" : sortKey === "updated-asc" ? "↑" : "↕"}
                      </span>
                    </button>
                  </th>
                  <th>MTP</th>
                  <th>Fit</th>
                </tr>
              </thead>
              <tbody>
                {paginatedItems.map((item) => (
                  <tr
                    key={item.id}
                    className={selectedId === item.id ? "browser-row-selected" : ""}
                    onClick={() => {
                      setSelectedId(item.id);
                      setCompatibilityRequest(null);
                    }}
                  >
                    <td>
                      <strong>{item.model}</strong>
                      <div className="browser-subline">{item.filename || item.repo || item.id}</div>
                      <div className="inline-actions compact-actions">
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={Boolean(pendingAction)}
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedId(item.id);
                            void handleDirectBrowserDownload(item);
                          }}
                        >
                          Preuzmi
                        </button>
                        {item.sourceUrl ? (
                          <a
                            className="secondary-button browser-model-link-button"
                            href={item.sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(event) => event.stopPropagation()}
                          >
                            Otvori stranicu modela
                          </a>
                        ) : null}
                      </div>
                    </td>
                    <td>{item.family}</td>
                    <td className="browser-source-cell">
                      <span className="browser-source-text" title={sourceLabel(item.source)}>
                        {sourceLabel(item.source)}
                      </span>
                    </td>
                    <td title={item.quantization}>{item.quantization}</td>
                    <td>{formatSize(item)}</td>
                    <td>{formatDate(item.updatedAt)}</td>
                    <td>
                      <span className={`browser-badge browser-badge-compact browser-mtp-${item.mtpStatus}`} title={item.mtpLabel} aria-label={item.mtpLabel}>
                        {compactMtpLabel(item.mtpStatus)}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`browser-badge browser-badge-compact browser-fit-${item.fitStatus.replace(/\s+/g, "-")}`}
                        title={item.fitLabel}
                        aria-label={item.fitLabel}
                      >
                        {compactFitLabel(item.fitStatus)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!filteredItems.length ? <div className="helper-text">Nema modela koji odgovaraju trenutnim filterima u Browser katalogu.</div> : null}
          </div>
          {filteredItems.length ? (
            <div className="browser-pagination">
              <span>
                Strana {currentPage} / {totalPages} | Redovi {pageStart + 1}-{Math.min(pageStart + rowsPerPage, filteredItems.length)} od {filteredItems.length}
              </span>
              <div className="browser-pagination-controls browser-pagination-inline">
                <button type="button" className="secondary-button" disabled={currentPage <= 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}>
                  Prethodna
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                >
                  Sledeća
                </button>
                <form
                  className="browser-page-jump-form browser-pagination-inline"
                  onSubmit={(event) => {
                    event.preventDefault();
                    jumpToCatalogPage(pageJumpValue);
                  }}
                >
                  <label className="browser-page-jump-label">
                    <span>Idi na stranu</span>
                    <input
                      className="browser-page-jump-input"
                      type="number"
                      min={1}
                      max={totalPages}
                      inputMode="numeric"
                      value={pageJumpValue}
                      onChange={(event) => setPageJumpValue(event.target.value)}
                      aria-label="Idi direktno na stranu Browser kataloga"
                    />
                  </label>
                  <button type="submit" className="secondary-button">
                    Idi
                  </button>
                </form>
              </div>
            </div>
          ) : null}
        </div>
      </section>
      <CompatibilityCalculatorModal
        isOpen={Boolean(compatibilityRequest)}
        title={selectedItem?.model || "Model"}
        request={compatibilityRequest}
        onClose={() => setCompatibilityRequest(null)}
        headerActions={
          compatibilityRequest && selectedItem ? (
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                onOpenCompatibilityTab?.({
                  title: selectedItem.model,
                  request: compatibilityRequest,
                });
                setCompatibilityRequest(null);
              }}
            >
              Tab kompatibilnosti
            </button>
          ) : null
        }
      />

      {result && result.action !== "browser-download" ? <ActionResultPanel result={result} /> : null}
    </>
  );
}
