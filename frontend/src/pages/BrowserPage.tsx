import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CompatibilityCalculatorModal } from "../components/CompatibilityCalculatorModal";
import { CustomSelect } from "../components/CustomSelect";
import { ModelDownloadProgressCard } from "../components/ModelDownloadProgressCard";
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
  return "Unknown";
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
  const upper = readString(value, "Unknown").trim().toUpperCase();
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
    return "MTP modeli koriste llama.cpp draft-mtp put. Ako je TurboQuant izabran, panel ce za takav model pasti nazad na llama.cpp.";
  }
  return null;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Unknown";
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
    return "Unknown";
  }
  return `${(item.sizeBytes / 1024 ** 3).toFixed(1)} GiB`;
}

function formatCount(value: number | null): string {
  if (value === null) {
    return "Unknown";
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
  const model = readString(record.model || record.label || record.name || record.title, "Unknown model");
  const family = readString(record.family || record.modelFamily || record.architecture, "Unknown");
  const quantization = readString(record.quantization || record.quant || record.gguf || record.variant, "Unknown");
  const sizeBytesGiB = readNumber(record.approxSizeGiB || record.sizeGiB);
  const sizeBytes =
    readNumber(record.sizeBytes || record.fileSizeBytes || record.bytes || record.approxSizeBytes) ??
    (sizeBytesGiB === null ? null : Math.round(sizeBytesGiB * 1024 ** 3));
  const sizeLabel =
    readString(record.sizeLabel || record.fileSizeLabel || record.approxSize || record.size, "") ||
    (sizeBytes === null ? "Unknown" : `${(sizeBytes / 1024 ** 3).toFixed(1)} GiB`);
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
  const summaryParts = [`Catalog refresh zavrsen za ${sourceLabelText}.`, `Modela: ${count}.`];
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

export function BrowserPage() {
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

  async function loadCatalog(query: BrowserCatalogQuery = browserQuery) {
    const requestId = ++catalogRequestRef.current;
    try {
      const payload = await fetchBrowserCatalog(query);
      const normalized = normalizeCatalogPayload(payload as BrowserCatalogEnvelope);
      if (requestId != catalogRequestRef.current) {
        return null;
      }
      setCatalog(normalized);
      setError(null);
      const models = normalized.models.map((item) => buildItem(asRecord(item)));
      setSelectedId((current) => current ?? models[0]?.id ?? null);
      return normalized;
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Browser catalog request failed.";
      setError(message);
      return null;
    }
  }

  async function loadCatalogIndex() {
    const requestId = ++catalogIndexRequestRef.current;
    try {
      const payload = await fetchBrowserCatalog();
      const normalized = normalizeCatalogPayload(payload as BrowserCatalogEnvelope);
      if (requestId != catalogIndexRequestRef.current) {
        return null;
      }
      setCatalogIndex(normalized);
      setError(null);
      return normalized;
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Browser catalog request failed.";
      setError(message);
      return null;
    }
  }

  useEffect(() => {
    void Promise.all([loadCatalogIndex(), loadCatalog()]);
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
    void loadCatalog();
  }, [browserQuery, catalogIndex]);

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
          await Promise.all([loadCatalogIndex(), loadCatalog()]);
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

  useEffect(() => {
    setCurrentPage(1);
  }, [deferredSearch, sourceFilter, familyFilter, quantFilter, sizeFilter, mtpFilter, dateFilter, sortKey]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

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
      summary: source ? `Refreshing ${source} catalog...` : "Refresh from internet...",
      details: { returncode: 0, stdout: "", stderr: "" },
    });

    try {
      const refreshPayload = normalizeCatalogPayload((await refreshBrowserCatalog(source)) as BrowserCatalogEnvelope);
      await Promise.all([loadCatalogIndex(), loadCatalog()]);
      setResult(buildRefreshActionResult(source, refreshPayload));
      setError(null);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Refresh from internet failed.";
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
      summary: `Adding ${item.model} to local catalog...`,
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
      const message = reason instanceof Error ? reason.message : "Add to local catalog failed.";
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
      summary: `Starting download for ${label}...`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });

    try {
      const downloadResult = await downloadBrowserModel(modelId);
      const finalResult = await awaitModelActionResult(downloadResult, setResult);
      setResult(finalResult);
      setDownloadOffer(null);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Download failed.";
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
      summary: `Starting download for ${item.model}...`,
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
      const message = reason instanceof Error ? reason.message : "Download failed.";
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

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!catalog) {
    return <div className="status-card wide-card">Loading Browser catalog...</div>;
  }

  const sourceOptions = [
    { value: "all", label: "All sources" },
    { value: "huggingface", label: "Hugging Face" },
    { value: "unsloth", label: "Unsloth" },
    { value: "other", label: "Other" },
  ];
  const familySelectOptions = [
    { value: "all", label: "All families" },
    ...familyOptions.map((family) => ({ value: family, label: family })),
  ];
  const quantSelectOptions = [
    { value: "all", label: "All quantizations" },
    ...quantOptions.map((quantization) => ({ value: quantization, label: quantization })),
  ];
  const sizeOptions = [
    { value: "all", label: "All sizes" },
    { value: "small", label: "Small (<4 GiB)" },
    { value: "medium", label: "Medium (4-16 GiB)" },
    { value: "large", label: "Large (>16 GiB)" },
  ];
  const mtpOptions = [
    { value: "all", label: "Any MTP" },
    { value: "has-mtp", label: "Has MTP" },
    { value: "no-mtp", label: "No MTP" },
    { value: "unknown", label: "Unknown" },
  ];
  const dateOptions = [
    { value: "all", label: "Any time" },
    { value: "7d", label: "Last 7 days" },
    { value: "30d", label: "Last 30 days" },
    { value: "90d", label: "Last 90 days" },
  ];
  const sortOptions = [
    { value: "quant-asc", label: "Quant smallest first" },
    { value: "quant-desc", label: "Quant largest first" },
    { value: "updated-desc", label: "Latest first" },
    { value: "updated-asc", label: "Oldest first" },
    { value: "fit-desc", label: "Best Fit first" },
    { value: "size-desc", label: "Largest first" },
    { value: "size-asc", label: "Smallest first" },
    { value: "family-asc", label: "Family A-Z" },
    { value: "source-asc", label: "Source A-Z" },
  ];

  const refreshCounts = catalog.refresh.counts || {};
  const warningCount = catalog.refresh.warnings.length;
  const errorCount = catalog.refresh.errors.length;

  return (
    <>
      <section className="status-card wide-card">
        <div className="section-header">
          <div>
            <span className="status-label">Browser</span>
            <strong className="status-value">Remote GGUF catalog</strong>
            <p className="helper-text">
              One table for Hugging Face and Unsloth GGUF models. Source stays a filter and badge, while Models remains the local catalog.
            </p>
          </div>
          <div className="inline-actions compact-actions browser-refresh-actions">
            <button type="button" className="secondary-button" disabled={Boolean(pendingAction)} onClick={() => void handleRefresh()}>
              Refresh from internet
            </button>
            <button type="button" className="secondary-button" disabled={Boolean(pendingAction)} onClick={() => void handleRefresh("huggingface")}>
              Refresh Hugging Face
            </button>
            <button type="button" className="secondary-button" disabled={Boolean(pendingAction)} onClick={() => void handleRefresh("unsloth")}>
              Refresh Unsloth
            </button>
          </div>
        </div>
        <div className="browser-toolbar">
          <label className="browser-field">
            <span>Search</span>
            <input
              type="text"
              placeholder="Search model, family, repo, quant..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <label className="browser-field">
            <span>Source</span>
            <CustomSelect value={sourceFilter} options={sourceOptions} onChange={setSourceFilter} ariaLabel="Source filter" />
          </label>
          <label className="browser-field">
            <span>Model family</span>
            <CustomSelect value={familyFilter} options={familySelectOptions} onChange={setFamilyFilter} ariaLabel="Family filter" />
          </label>
          <label className="browser-field">
            <span>Quant</span>
            <CustomSelect value={quantFilter} options={quantSelectOptions} onChange={setQuantFilter} ariaLabel="Quant filter" />
          </label>
          <label className="browser-field">
            <span>Size</span>
            <CustomSelect value={sizeFilter} options={sizeOptions} onChange={setSizeFilter} ariaLabel="Size filter" />
          </label>
          <label className="browser-field">
            <span>MTP status</span>
            <CustomSelect value={mtpFilter} options={mtpOptions} onChange={setMtpFilter} ariaLabel="MTP filter" />
          </label>
          <label className="browser-field">
            <span>Date</span>
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
              Showing {filteredItems.length} of {refreshCounts.all ?? filteredItems.length} models
            </strong>
            <span>Last catalog update: {formatDate(catalog.refresh.lastRefresh || null)}</span>
          </div>
          <div className="browser-overview-meta">
            <span>HF: {refreshCounts.huggingface ?? 0}</span>
            <span>Unsloth: {refreshCounts.unsloth ?? 0}</span>
            {warningCount ? <span>Warnings: {warningCount}</span> : null}
            {errorCount ? <span>Errors: {errorCount}</span> : null}
          </div>
        </section>
        {warningCount ? (
          <section className="browser-notice browser-notice-warning">
            <div className="browser-notice-header">
              <div>
                <strong>Catalog warnings</strong>
                <p className="helper-text">
                  Neki repozitorijumi imaju vise GGUF fajlova nego sto je trenutno prikazano. Ovo ne blokira browser, ali znaci da je pregled skracen.
                </p>
              </div>
              <button type="button" className="secondary-button" onClick={() => setWarningsExpanded((current) => !current)}>
                {warningsExpanded ? "Collapse warnings" : `Expand warnings (${warningCount})`}
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
                <strong>Catalog errors</strong>
                <p className="helper-text">
                  Ove greske su sacuvane iz poslednjeg osvezavanja i mogu da objasne zasto deo kataloga nije kompletan.
                </p>
              </div>
              <button type="button" className="secondary-button" onClick={() => setErrorsExpanded((current) => !current)}>
                {errorsExpanded ? "Collapse errors" : `Expand errors (${errorCount})`}
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

      <section className="status-card wide-card browser-results-stack">
        {selectedItem ? (
          <section className="browser-detail-top">
            <div className="browser-detail-header">
              <div>
                <span className="status-label">Detail panel</span>
                <h2>{selectedItem.model}</h2>
                <p className="muted-line">
                  {selectedItem.family} | {selectedItem.quantization}
                </p>
              </div>
              <span className={`browser-badge browser-source-${selectedItem.source}`} title={sourceLabel(selectedItem.source)}>
                {sourceLabel(selectedItem.source)}
              </span>
            </div>

            <div className="browser-metadata-grid">
              <div>
                <span className="status-label">Fit</span>
                <strong className="status-value">Fit: {selectedItem.fitLabel}</strong>
              </div>
              <div>
                <span className="status-label">MTP</span>
                <strong className="status-value">{selectedItem.mtpLabel}</strong>
              </div>
              <div>
                <span className="status-label">Size</span>
                <strong className="status-value">{formatSize(selectedItem)}</strong>
              </div>
              <div>
                <span className="status-label">Last update</span>
                <strong className="status-value">{formatDate(selectedItem.updatedAt)}</strong>
              </div>
              <div>
                <span className="status-label">Repo</span>
                <strong className="status-value">{selectedItem.repo || "Unknown"}</strong>
              </div>
              <div>
                <span className="status-label">Downloads</span>
                <strong className="status-value">{formatCount(selectedItem.downloads)}</strong>
              </div>
            </div>

            {selectedItem.summary ? <p className="helper-text">{selectedItem.summary}</p> : null}
            {mtpDownloadOnlyGuidance(selectedItem) ? (
              <p className="helper-text">{mtpDownloadOnlyGuidance(selectedItem)}</p>
            ) : null}

            {selectedItem.tags.length ? (
              <div className="browser-chip-row">
                {selectedItem.tags.map((tag) => (
                  <span key={tag} className="browser-chip">
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="inline-actions">
              <button
                type="button"
                disabled={Boolean(pendingAction)}
                onClick={() => void handleDirectBrowserDownload(selectedItem)}
              >
                Download
              </button>
              <button type="button" disabled={Boolean(pendingAction)} onClick={() => void handleAddToLocal(selectedItem)}>
                Add to local catalog
              </button>
              <button
                type="button"
                disabled={!selectedItem.sourceUrl}
                onClick={() => window.open(selectedItem.sourceUrl, "_blank", "noopener,noreferrer")}
              >
                Open source page
              </button>
                      <button type="button" disabled={Boolean(pendingAction)} onClick={() => void handleCompatibility(selectedItem)}>
                        Check compatibility
                      </button>
            </div>

            {downloadOffer && downloadOffer.label === selectedItem.model ? (
              <div className="browser-callout">
                <strong>Added to local catalog.</strong> Download is still manual. If you want the file immediately, start it now.
                <div className="inline-actions compact-actions">
                  <button type="button" onClick={() => void handleDownload(downloadOffer.modelId, downloadOffer.label)}>
                    Download now
                  </button>
                  <button type="button" className="secondary-button" onClick={() => setDownloadOffer(null)}>
                    Later
                  </button>
                </div>
              </div>
            ) : null}

            <p className="helper-text">
              Use <strong>Check compatibility</strong> to open the compatibility calculator before you add the model to the local catalog.
            </p>

            <ModelDownloadProgressCard progress={downloadProgress} />

            {result && result.action === "browser-download" ? <ActionResultPanel result={result} /> : null}
          </section>
        ) : (
          <div className="helper-text">Select a Browser row to inspect details and actions.</div>
        )}

        <div className="browser-table-panel">
          <div className="browser-table-wrap">
            <table className="browser-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Family</th>
                  <th>Source</th>
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
                      Size
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
                      Last update
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
                          Download
                        </button>
                        {item.sourceUrl ? (
                          <a
                            href={item.sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(event) => event.stopPropagation()}
                          >
                            Open model page
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
            {!filteredItems.length ? <div className="helper-text">No matching models in the Browser catalog.</div> : null}
          </div>
          {filteredItems.length ? (
            <div className="browser-pagination">
              <span>
                Page {currentPage} / {totalPages} | Rows {pageStart + 1}-{Math.min(pageStart + rowsPerPage, filteredItems.length)} of {filteredItems.length}
              </span>
              <div className="inline-actions compact-actions">
                <button type="button" className="secondary-button" disabled={currentPage <= 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}>
                  Previous
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                >
                  Next
                </button>
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
      />

      {result && result.action !== "browser-download" ? <ActionResultPanel result={result} /> : null}
    </>
  );
}
