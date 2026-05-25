import { useEffect, useMemo, useState } from "react";

import { CompatibilityCalculatorPanel } from "../components/CompatibilityCalculatorPanel";
import { CustomSelect } from "../components/CustomSelect";
import { fetchBrowserCatalog, fetchModels } from "../lib/api";
import {
  buildCompatibilityRequestFromModelEntry,
  type CompatibilityLaunchTarget,
  flattenModelsPayload,
} from "../lib/compatibility";
import type {
  BrowserCatalogItem,
  BrowserCatalogPayload,
  BrowserCompatibilityPayload,
  BrowserFitStatus,
  BrowserMtpStatus,
  ModelsPayload,
  ModelEntry,
} from "../lib/types";

type Props = {
  onOpenModels: () => void;
  onOpenBrowser: () => void;
  launchTarget?: CompatibilityLaunchTarget | null;
};

type CompatibilityScope = "active" | "local" | "remote";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
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

function normalizeQuantFilterKey(value: string): string {
  const upper = readString(value, "Unknown").trim().toUpperCase();
  if (!upper) {
    return "UNKNOWN";
  }
  const segments = upper.split("-");
  const quantIndex = segments.findIndex((segment) =>
    /^(IQ\d|Q\d|BF16|F16|MXFP|NVFP)/.test(segment),
  );
  if (quantIndex > 0) {
    return segments.slice(quantIndex).join("-");
  }
  return upper;
}

function normalizeMtpStatus(value: unknown): BrowserMtpStatus {
  const lowered = readString(value, "unknown").trim().toLowerCase();
  if (lowered.includes("has") || lowered.includes("mtp")) {
    return lowered.includes("no") || lowered.includes("bez")
      ? "no-mtp"
      : "has-mtp";
  }
  return lowered.includes("no") || lowered.includes("bez")
    ? "no-mtp"
    : "unknown";
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

function buildBrowserCatalogItem(record: Record<string, unknown>): BrowserCatalogItem {
  const source = normalizeSource(
    readString(
      record.source || record.provider || record.catalogSource || record.origin,
      "other",
    ),
  );
  const model = readString(
    record.model || record.label || record.name || record.title,
    "Unknown model",
  );
  const family = readString(
    record.family || record.modelFamily || record.architecture,
    "Unknown",
  );
  const quantization = readString(
    record.quantization || record.quant || record.gguf || record.variant,
    "Unknown",
  );
  const sizeBytesGiB = readNumber(record.approxSizeGiB || record.sizeGiB);
  const sizeBytes =
    readNumber(
      record.sizeBytes ||
        record.fileSizeBytes ||
        record.bytes ||
        record.approxSizeBytes,
    ) ??
    (sizeBytesGiB === null ? null : Math.round(sizeBytesGiB * 1024 ** 3));
  const sizeLabel =
    readString(
      record.sizeLabel ||
        record.fileSizeLabel ||
        record.approxSize ||
        record.size,
      "",
    ) ||
    (sizeBytes === null ? "Unknown" : `${(sizeBytes / 1024 ** 3).toFixed(1)} GiB`);
  const mtpStatus = normalizeMtpStatus(record.mtpStatus || record.mtp || record.mtp_state);
  const fitStatus = normalizeFitStatus(record.fitStatus || asRecord(record.fit).status || record.compatibility);
  const repo = readString(record.repo || record.repoId || record.repository || record.slug);
  const filename = readString(record.filename || record.fileName || record.ggufFilename);
  const id =
    readString(record.id) ||
    [source, repo || model, filename || quantization]
      .filter(Boolean)
      .join(":")
      .replace(/\s+/g, "-");

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
    updatedAt:
      readString(
        record.updatedAt ||
          record.lastUpdated ||
          record.publishedAt ||
          record.date,
      ) || null,
    mtpStatus,
    mtpLabel: readString(record.mtpLabel) || mtpLabel(mtpStatus),
    fitStatus,
    fitLabel:
      readString(record.fitLabel || asRecord(record.fit).fitLabel) ||
      fitLabel(fitStatus),
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

function formatModelSource(item: ModelEntry): string {
  if (item.source === "huggingface") {
    return "Hugging Face";
  }
  if (item.source === "unsloth") {
    return "Unsloth";
  }
  if (item.source === "curated") {
    return "Curated";
  }
  if (item.source === "local") {
    return "Local";
  }
  return item.source;
}

function sortModelCandidates(items: ModelEntry[]): ModelEntry[] {
  return [...items].sort((left, right) => {
    if (left.active !== right.active) {
      return left.active ? -1 : 1;
    }
    if (left.installed !== right.installed) {
      return left.installed ? -1 : 1;
    }
    return left.label.localeCompare(right.label);
  });
}

export function CompatibilityPage({
  onOpenModels,
  onOpenBrowser,
  launchTarget,
}: Props) {
  const [models, setModels] = useState<ModelsPayload | null>(null);
  const [catalog, setCatalog] = useState<BrowserCatalogPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScope] = useState<CompatibilityScope>("active");
  const [localModelId, setLocalModelId] = useState("");
  const [remoteSearch, setRemoteSearch] = useState("");
  const [remoteSource, setRemoteSource] = useState("all");
  const [remoteModelId, setRemoteModelId] = useState("");
  const [lastPayload, setLastPayload] =
    useState<BrowserCompatibilityPayload | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [modelsPayload, catalogPayload] = await Promise.all([
          fetchModels(),
          fetchBrowserCatalog(),
        ]);
        if (cancelled) {
          return;
        }
        setModels(modelsPayload);
        setCatalog(catalogPayload);
        setError(null);
      } catch (reason: unknown) {
        if (!cancelled) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Compatibility podaci nisu mogli da se ucitaju.",
          );
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const localCandidates = useMemo(() => {
    if (!models) {
      return [];
    }
    return sortModelCandidates(flattenModelsPayload(models));
  }, [models]);

  const activeModel = useMemo(
    () => localCandidates.find((item) => item.active) ?? null,
    [localCandidates],
  );

  useEffect(() => {
    if (!localCandidates.length) {
      return;
    }
    if (!localModelId || !localCandidates.some((item) => item.id === localModelId)) {
      setLocalModelId(activeModel?.id ?? localCandidates[0].id);
    }
  }, [activeModel, localCandidates, localModelId]);

  useEffect(() => {
    if (!launchTarget?.request?.model?.id) {
      return;
    }
    setScope("local");
    setRemoteSearch("");
    setRemoteSource("all");
    setLocalModelId(String(launchTarget.request.model.id));
  }, [launchTarget]);

  const remoteCandidates = useMemo(() => {
    if (!catalog) {
      return [];
    }
    return catalog.models.map((entry) => buildBrowserCatalogItem(asRecord(entry)));
  }, [catalog]);

  const filteredRemoteCandidates = useMemo(() => {
    const normalizedSearch = remoteSearch.trim().toLowerCase();
    return remoteCandidates.filter((item) => {
      if (remoteSource !== "all" && item.source !== remoteSource) {
        return false;
      }
      if (!normalizedSearch) {
        return true;
      }
      const haystack = [
        item.model,
        item.family,
        item.repo,
        item.filename,
        item.quantization,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [remoteCandidates, remoteSearch, remoteSource]);

  useEffect(() => {
    if (!filteredRemoteCandidates.length) {
      setRemoteModelId("");
      return;
    }
    if (
      !remoteModelId ||
      !filteredRemoteCandidates.some((item) => item.id === remoteModelId)
    ) {
      setRemoteModelId(filteredRemoteCandidates[0].id);
    }
  }, [filteredRemoteCandidates, remoteModelId]);

  useEffect(() => {
    if (!launchTarget?.request?.catalogModelId) {
      return;
    }
    setScope("remote");
    setRemoteSearch("");
    setRemoteSource("all");
    setRemoteModelId(String(launchTarget.request.catalogModelId));
  }, [launchTarget]);

  const selectedLocalModel = useMemo(
    () => localCandidates.find((item) => item.id === localModelId) ?? null,
    [localCandidates, localModelId],
  );

  const selectedRemoteModel = useMemo(
    () => filteredRemoteCandidates.find((item) => item.id === remoteModelId) ?? null,
    [filteredRemoteCandidates, remoteModelId],
  );

  const compatibilityRequest = useMemo(() => {
    if (scope === "active") {
      return activeModel ? buildCompatibilityRequestFromModelEntry(activeModel) : null;
    }
    if (scope === "local") {
      return selectedLocalModel
        ? buildCompatibilityRequestFromModelEntry(selectedLocalModel)
        : null;
    }
    return selectedRemoteModel ? { catalogModelId: selectedRemoteModel.id } : null;
  }, [activeModel, scope, selectedLocalModel, selectedRemoteModel]);

  const compatibilityTitle = useMemo(() => {
    if (launchTarget?.title) {
      if (scope === "remote" && launchTarget.request.catalogModelId) {
        return launchTarget.title;
      }
      if (scope === "local" && launchTarget.request.model?.id) {
        return launchTarget.title;
      }
    }
    if (scope === "active") {
      return activeModel ? `Active model: ${activeModel.label}` : "Active model";
    }
    if (scope === "local") {
      return selectedLocalModel
        ? `Local catalog: ${selectedLocalModel.label}`
        : "Local catalog";
    }
    return selectedRemoteModel
      ? `Remote catalog: ${selectedRemoteModel.model}`
      : "Remote catalog";
  }, [activeModel, scope, selectedLocalModel, selectedRemoteModel]);

  const localModelOptions = useMemo(
    () =>
      localCandidates.map((item) => ({
        value: item.id,
        label: `${item.label} | ${formatModelSource(item)}${item.active ? " | Active model" : ""}`,
      })),
    [localCandidates],
  );

  const remoteModelOptions = useMemo(
    () =>
      filteredRemoteCandidates.slice(0, 200).map((item) => ({
        value: item.id,
        label: `${item.model} | ${item.quantization} | ${sourceLabel(String(item.source))}`,
      })),
    [filteredRemoteCandidates],
  );

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!models || !catalog) {
    return <div className="status-card wide-card">Ucitavam Compatibility workspace...</div>;
  }

  return (
    <div className="compatibility-page">
      <section className="status-card wide-card compatibility-workspace">
        <div className="section-header">
          <div>
            <span className="status-label">Compatibility workspace</span>
            <strong className="status-value">
              Vidljiv calculator za fit modela i runtime izbora
            </strong>
            <p className="helper-text">
              Ovde mozes da proveris kako model stoji na lokalnom hardveru, da
              uporedis llama.cpp i TurboQuant put i da odmah primenis preporuke.
            </p>
            <p className="helper-text">
              Check compatibility se na ovoj stranici pokrece automatski cim
              promenis izabrani model.
            </p>
          </div>
          <div className="inline-actions compact-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => setScope("active")}
            >
              Use active model
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={onOpenModels}
            >
              Open Models
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={onOpenBrowser}
            >
              Open Browser
            </button>
          </div>
        </div>
        <div className="compatibility-snapshot-grid">
          <div className="compatibility-snapshot-card">
            <span className="status-label">Active model</span>
            <strong className="status-value">
              {activeModel?.label ?? "Nema aktivnog modela"}
            </strong>
            <div className="helper-text">
              {activeModel
                ? `${formatModelSource(activeModel)} | ${activeModel.family ?? "Unknown"}`
                : "Izaberi lokalni ili remote model da bi calculator radio."}
            </div>
          </div>
          <div className="compatibility-snapshot-card">
            <span className="status-label">Local catalog</span>
            <strong className="status-value">{localCandidates.length}</strong>
            <div className="helper-text">Ukupno modela poznatih instaliranoj aplikaciji.</div>
          </div>
          <div className="compatibility-snapshot-card">
            <span className="status-label">Remote catalog</span>
            <strong className="status-value">{remoteCandidates.length}</strong>
            <div className="helper-text">
              Browser indeks koji calculator moze odmah da proveri.
            </div>
          </div>
          <div className="compatibility-snapshot-card">
            <span className="status-label">System snapshot</span>
            <strong className="status-value">
              {lastPayload?.systemSnapshot?.vramGiB ?? "--"} GiB VRAM
            </strong>
            <div className="helper-text">
              RAM {lastPayload?.systemSnapshot?.ramGiB ?? "--"} GiB | context{" "}
              {lastPayload?.systemSnapshot?.context ?? "--"} | output{" "}
              {lastPayload?.systemSnapshot?.outputTokens ?? "--"}
            </div>
            <div className="helper-text">
              TurboQuant{" "}
              {lastPayload?.systemSnapshot?.turboQuantAvailable ? "dostupan" : "nije potvrden"}
            </div>
          </div>
          <div className="compatibility-snapshot-card">
            <span className="status-label">Current fit</span>
            <strong className="status-value">
              {lastPayload?.overallFitLabel ?? "--"}
            </strong>
            <div className="helper-text">
              Best runtime {lastPayload?.bestRuntimeLabel ?? "--"} | speed{" "}
              {lastPayload?.speedLabel ?? "--"}
            </div>
          </div>
        </div>
      </section>

      <section className="status-card wide-card compatibility-picker-card">
        <div className="section-header">
          <div>
            <span className="status-label">Model source</span>
            <strong className="status-value">Izaberi sta proveravas</strong>
          </div>
        </div>

        <div className="compatibility-scope-row">
          <button
            type="button"
            className={`secondary-button ${scope === "active" ? "nav-button-active" : ""}`}
            onClick={() => setScope("active")}
          >
            Active model
          </button>
          <button
            type="button"
            className={`secondary-button ${scope === "local" ? "nav-button-active" : ""}`}
            onClick={() => setScope("local")}
          >
            Local catalog
          </button>
          <button
            type="button"
            className={`secondary-button ${scope === "remote" ? "nav-button-active" : ""}`}
            onClick={() => setScope("remote")}
          >
            Remote catalog
          </button>
        </div>

        {scope === "active" ? (
          <div className="compatibility-choice-grid">
            <div className="compatibility-choice-card">
              <span className="status-label">Active model</span>
              <strong className="status-value">
                {activeModel?.label ?? "Nema aktivnog modela"}
              </strong>
              <div className="helper-text">
                {activeModel
                  ? `Izvor: ${formatModelSource(activeModel)} | MTP: ${activeModel.mtpStatusLabel ?? "nepoznato"}`
                  : "Prvo aktiviraj ili izaberi model iz lokalnog kataloga."}
              </div>
              <div className="inline-actions compact-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={onOpenModels}
                >
                  Open Models
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {scope === "local" ? (
          <div className="compatibility-choice-grid">
            <label className="browser-field">
              <span>Local catalog</span>
              <CustomSelect
                value={selectedLocalModel?.id ?? ""}
                options={localModelOptions}
                onChange={setLocalModelId}
                ariaLabel="Local catalog model picker"
              />
            </label>
            <div className="compatibility-choice-card">
              <span className="status-label">Current local selection</span>
              <strong className="status-value">
                {selectedLocalModel?.label ?? "Nije izabran model"}
              </strong>
              <div className="helper-text">
                {selectedLocalModel
                  ? `${formatModelSource(selectedLocalModel)} | ${selectedLocalModel.family ?? "Unknown"} | ${selectedLocalModel.lifecycleLabel ?? "Status nepoznat"}`
                  : "Izaberi model iz lokalnog kataloga."}
              </div>
              <div className="inline-actions compact-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={onOpenModels}
                >
                  Open Models
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {scope === "remote" ? (
          <div className="compatibility-choice-grid compatibility-choice-grid-remote">
            <label className="browser-field">
              <span>Remote search</span>
              <input
                type="text"
                placeholder="Search model, repo, quant..."
                value={remoteSearch}
                onChange={(event) => setRemoteSearch(event.target.value)}
              />
            </label>
            <label className="browser-field">
              <span>Remote source</span>
              <CustomSelect
                value={remoteSource}
                options={[
                  { value: "all", label: "All sources" },
                  { value: "huggingface", label: "Hugging Face" },
                  { value: "unsloth", label: "Unsloth" },
                  { value: "other", label: "Other" },
                ]}
                onChange={setRemoteSource}
                ariaLabel="Remote source filter"
              />
            </label>
            <label className="browser-field compatibility-remote-picker">
              <span>Remote catalog</span>
              <CustomSelect
                value={selectedRemoteModel?.id ?? ""}
                options={remoteModelOptions}
                onChange={setRemoteModelId}
                ariaLabel="Remote catalog model picker"
              />
            </label>
            <div className="compatibility-choice-card">
              <span className="status-label">Current remote selection</span>
              <strong className="status-value">
                {selectedRemoteModel?.model ?? "Nije izabran model"}
              </strong>
              <div className="helper-text">
                {selectedRemoteModel
                  ? `${sourceLabel(String(selectedRemoteModel.source))} | ${selectedRemoteModel.quantization} | ${selectedRemoteModel.fitLabel}`
                  : "Nema pogodaka za trenutni remote filter."}
              </div>
              <div className="helper-text">
                Filter trenutno vraca {filteredRemoteCandidates.length} modela.
              </div>
              <div className="inline-actions compact-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={onOpenBrowser}
                >
                  Open Browser
                </button>
                {selectedRemoteModel?.sourceUrl ? (
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() =>
                      window.open(
                        selectedRemoteModel.sourceUrl,
                        "_blank",
                        "noopener,noreferrer",
                      )
                    }
                  >
                    Open source page
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <CompatibilityCalculatorPanel
        className="compat-surface compat-page-surface"
        title={compatibilityTitle}
        request={compatibilityRequest}
        onPayloadChange={setLastPayload}
        emptyState={
          <div className="compat-empty-state">
            <strong>Nema izabranog modela za proveru.</strong>
            <div className="helper-text">
              Izaberi Active model, Local catalog ili Remote catalog da bi calculator
              mogao da izracuna fit.
            </div>
          </div>
        }
      />
    </div>
  );
}
