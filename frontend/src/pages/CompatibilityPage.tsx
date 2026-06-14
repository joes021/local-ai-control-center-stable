import { useEffect, useMemo, useState } from "react";

import { CompatibilityCalculatorPanel } from "../components/CompatibilityCalculatorPanel";
import { CustomSelect } from "../components/CustomSelect";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import {
  SecondaryActionRail,
  type SecondaryActionRailItem,
} from "../components/shell/SecondaryActionRail";
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
  const upper = readString(value, "Nepoznato").trim().toUpperCase();
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

function buildBrowserCatalogItem(record: Record<string, unknown>): BrowserCatalogItem {
  const source = normalizeSource(
    readString(
      record.source || record.provider || record.catalogSource || record.origin,
      "other",
    ),
  );
  const model = readString(
    record.model || record.label || record.name || record.title,
    "Nepoznat model",
  );
  const family = readString(
    record.family || record.modelFamily || record.architecture,
    "Nepoznato",
  );
  const quantization = readString(
    record.quantization || record.quant || record.gguf || record.variant,
    "Nepoznato",
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
    (sizeBytes === null ? "Nepoznato" : `${(sizeBytes / 1024 ** 3).toFixed(1)} GiB`);
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
              : "Podaci o kompatibilnosti nisu mogli da se učitaju.",
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
      return activeModel ? `Aktivni model: ${activeModel.label}` : "Aktivni model";
    }
    if (scope === "local") {
      return selectedLocalModel
        ? `Lokalni katalog: ${selectedLocalModel.label}`
        : "Lokalni katalog";
    }
    return selectedRemoteModel
      ? `Udaljeni katalog: ${selectedRemoteModel.model}`
      : "Udaljeni katalog";
  }, [activeModel, scope, selectedLocalModel, selectedRemoteModel]);

  const localModelOptions = useMemo(
    () =>
      localCandidates.map((item) => ({
        value: item.id,
        label: `${item.label} | ${formatModelSource(item)}${item.active ? " | Aktivni model" : ""}`,
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

  const inlineError = error;

  if (!models || !catalog) {
    return (
      <PageDataStateCard
        error={inlineError}
        loadingText="Učitavam radni prostor kompatibilnosti..."
        onRetry={() => window.location.reload()}
      />
    );
  }

  if (!models || !catalog) {
    return <div className="status-card wide-card">Učitavam radni prostor kompatibilnosti...</div>;
  }

  function openSelectedRemoteSource() {
    if (!selectedRemoteModel?.sourceUrl) {
      return;
    }
    window.open(selectedRemoteModel.sourceUrl, "_blank", "noopener,noreferrer");
  }

  const compatibilityRailItems: SecondaryActionRailItem[] = [
    {
      code: "LIVE",
      title: "Koristi aktivni model",
      subtitle: activeModel?.label ?? "AKTIVNI MODEL",
      icon: "models",
      tone: "primary",
      onClick: () => setScope("active"),
    },
    {
      code: "MODEL",
      title: "Otvori Modele",
      subtitle: "LOKALNI KATALOG",
      icon: "models",
      onClick: onOpenModels,
    },
    {
      code: "CAT",
      title: "Otvori katalog",
      subtitle: "BROWSER + IZVORI",
      icon: "browser",
      onClick: onOpenBrowser,
    },
    {
      code: "SRC",
      title: "Otvori izvornu stranicu",
      subtitle: selectedRemoteModel?.model ?? "IZABERI UDALJENI MODEL",
      icon: "search",
      detail: selectedRemoteModel?.sourceUrl || "Link se pali kada udaljeni model ima izvorni URL.",
      disabled: !selectedRemoteModel?.sourceUrl,
      onClick: openSelectedRemoteSource,
    },
  ];

  return (
    <div className="compatibility-page runtimepilot-rack-page">
      {inlineError ? <div className="error-panel wide-card">{inlineError}</div> : null}
      <div className="runtimepilot-secondary-hub">
        <div className="runtimepilot-secondary-hub-main">
          <PageFlowCard
            title="Tok kompatibilnosti"
            summary="Levo ostaju izbor opsega i kalkulator, a desni rail drži samo stvarne ulaze za aktivni model, lokalni katalog, Browser katalog i izvorni link."
            steps={[
              {
                title: "Izaberi aktivni, lokalni ili udaljeni model",
                detail: "Opseg određuje da li proveravaš ono što već koristiš, lokalni katalog ili kandidat iz kataloga.",
              },
              {
                title: "Pogledaj fit i runtime preporuku",
                detail: "Kalkulator sam ponavlja proveru kad promeniš model, pa je fokus na tumačenju rezultata umesto na ručnom startovanju.",
              },
              {
                title: "Vrati se u Modele ili katalog",
                detail: "Kada vidiš šta radi na mašini, odmah se vrati na pravo mesto i potvrdi model ili izvor.",
              },
            ]}
          />
          <div className="compatibility-hifi-stack">
      <div className="compatibility-mixer-deck">
      <section className="status-card wide-card compatibility-workspace runtimepilot-faceplate-module compat-rack-module">
        <div className="section-header">
          <div>
            <span className="status-label">Radni prostor kompatibilnosti</span>
            <strong className="status-value">
              Vidljiv kalkulator za fit modela i izbor runtime-a
            </strong>
            <p className="helper-text">
              Ovde možeš da proveriš kako model stoji na lokalnom hardveru, da
              uporediš llama.cpp i TurboQuant put i da odmah primeniš preporuke.
            </p>
            <p className="helper-text">
              Provera kompatibilnosti se na ovoj stranici pokreće automatski čim
              promeniš izabrani model.
            </p>
          </div>
        </div>
        <div className="compatibility-snapshot-grid">
          <div className="compatibility-snapshot-card">
            <span className="status-label">Aktivni model</span>
            <strong className="status-value">
              {activeModel?.label ?? "Nema aktivnog modela"}
            </strong>
            <div className="helper-text">
              {activeModel
                ? `${formatModelSource(activeModel)} | ${activeModel.family ?? "Nepoznato"}`
                : "Izaberi lokalni ili udaljeni model da bi kalkulator radio."}
            </div>
          </div>
          <div className="compatibility-snapshot-card">
            <span className="status-label">Lokalni katalog</span>
            <strong className="status-value">{localCandidates.length}</strong>
            <div className="helper-text">Ukupno modela poznatih instaliranoj aplikaciji.</div>
          </div>
          <div className="compatibility-snapshot-card">
            <span className="status-label">Udaljeni katalog</span>
            <strong className="status-value">{remoteCandidates.length}</strong>
            <div className="helper-text">
              Katalog modela koji kalkulator može odmah da proveri.
            </div>
          </div>
          <div className="compatibility-snapshot-card">
            <span className="status-label">Snimak sistema</span>
            <strong className="status-value">
              {lastPayload?.systemSnapshot?.vramGiB ?? "--"} GiB VRAM
            </strong>
            <div className="helper-text">
              RAM {lastPayload?.systemSnapshot?.ramGiB ?? "--"} GiB | kontekst{" "}
              {lastPayload?.systemSnapshot?.context ?? "--"} | izlaz{" "}
              {lastPayload?.systemSnapshot?.outputTokens ?? "--"}
            </div>
            <div className="helper-text">
              TurboQuant{" "}
              {lastPayload?.systemSnapshot?.turboQuantAvailable ? "dostupan" : "nije potvrđen"}
            </div>
          </div>
          <div className="compatibility-snapshot-card">
            <span className="status-label">Trenutni fit</span>
            <strong className="status-value">
              {lastPayload?.overallFitLabel ?? "--"}
            </strong>
            <div className="helper-text">
              Najbolji runtime {lastPayload?.bestRuntimeLabel ?? "--"} | brzina{" "}
              {lastPayload?.speedLabel ?? "--"}
            </div>
          </div>
        </div>
      </section>

      <section className="status-card wide-card compatibility-picker-card runtimepilot-faceplate-module compat-rack-module">
        <div className="section-header">
          <div>
            <span className="status-label">Izvor modela</span>
            <strong className="status-value">Izaberi šta proveravaš</strong>
          </div>
        </div>

        <div className="compatibility-scope-row">
          <button
            type="button"
            className={`secondary-button ${scope === "active" ? "nav-button-active" : ""}`}
            onClick={() => setScope("active")}
          >
            Aktivni model
          </button>
          <button
            type="button"
            className={`secondary-button ${scope === "local" ? "nav-button-active" : ""}`}
            onClick={() => setScope("local")}
          >
            Lokalni katalog
          </button>
          <button
            type="button"
            className={`secondary-button ${scope === "remote" ? "nav-button-active" : ""}`}
            onClick={() => setScope("remote")}
          >
            Udaljeni katalog
          </button>
        </div>

        {scope === "active" ? (
          <div className="compatibility-choice-grid">
            <div className="compatibility-choice-card">
              <span className="status-label">Aktivni model</span>
              <strong className="status-value">
                {activeModel?.label ?? "Nema aktivnog modela"}
              </strong>
              <div className="helper-text">
                {activeModel
                  ? `Izvor: ${formatModelSource(activeModel)} | MTP: ${activeModel.mtpStatusLabel ?? "nepoznato"}`
                  : "Prvo aktiviraj ili izaberi model iz lokalnog kataloga."}
              </div>
            </div>
          </div>
        ) : null}

        {scope === "local" ? (
          <div className="compatibility-choice-grid">
            <label className="browser-field">
              <span>Lokalni katalog</span>
              <CustomSelect
                value={selectedLocalModel?.id ?? ""}
                options={localModelOptions}
                onChange={setLocalModelId}
                ariaLabel="Birač modela lokalnog kataloga"
              />
            </label>
            <div className="compatibility-choice-card">
              <span className="status-label">Trenutni lokalni izbor</span>
              <strong className="status-value">
                {selectedLocalModel?.label ?? "Nije izabran model"}
              </strong>
              <div className="helper-text">
                {selectedLocalModel
                  ? `${formatModelSource(selectedLocalModel)} | ${selectedLocalModel.family ?? "Nepoznato"} | ${selectedLocalModel.lifecycleLabel ?? "Status nepoznat"}`
                  : "Izaberi model iz lokalnog kataloga."}
              </div>
            </div>
          </div>
        ) : null}

        {scope === "remote" ? (
          <div className="compatibility-choice-grid compatibility-choice-grid-remote">
            <label className="browser-field">
              <span>Pretraga udaljenog kataloga</span>
              <input
                type="text"
                placeholder="Pretraži model, repo, kvantizaciju..."
                value={remoteSearch}
                onChange={(event) => setRemoteSearch(event.target.value)}
              />
            </label>
            <label className="browser-field">
              <span>Udaljeni izvor</span>
              <CustomSelect
                value={remoteSource}
                options={[
                  { value: "all", label: "Svi izvori" },
                  { value: "huggingface", label: "Hugging Face" },
                  { value: "unsloth", label: "Unsloth" },
                  { value: "other", label: "Drugo" },
                ]}
                onChange={setRemoteSource}
                ariaLabel="Filter udaljenog izvora"
              />
            </label>
            <label className="browser-field compatibility-remote-picker">
              <span>Udaljeni katalog</span>
              <CustomSelect
                value={selectedRemoteModel?.id ?? ""}
                options={remoteModelOptions}
                onChange={setRemoteModelId}
                ariaLabel="Birač modela udaljenog kataloga"
              />
            </label>
            <div className="compatibility-choice-card">
              <span className="status-label">Trenutni udaljeni izbor</span>
              <strong className="status-value">
                {selectedRemoteModel?.model ?? "Nije izabran model"}
              </strong>
              <div className="helper-text">
                {selectedRemoteModel
                  ? `${sourceLabel(String(selectedRemoteModel.source))} | ${selectedRemoteModel.quantization} | ${selectedRemoteModel.fitLabel}`
                  : "Nema pogodaka za trenutni filter udaljenog kataloga."}
              </div>
              <div className="helper-text">
                Filter trenutno vraća {filteredRemoteCandidates.length} modela.
              </div>
            </div>
          </div>
        ) : null}
      </section>
      </div>

      <CompatibilityCalculatorPanel
        className="compat-surface compat-page-surface"
        title={compatibilityTitle}
        request={compatibilityRequest}
        onPayloadChange={setLastPayload}
        emptyState={
          <div className="compat-empty-state">
            <strong>Nema izabranog modela za proveru.</strong>
            <div className="helper-text">
              Izaberi aktivni model, lokalni katalog ili udaljeni katalog da bi kalkulator
              mogao da izračuna fit.
            </div>
          </div>
        }
      />

          </div>
        </div>

        <SecondaryActionRail
          eyebrow="Action rail"
          title="Ulazi i prečice"
          summary="Desno ostaju samo ulazi koji vode na aktivni model, lokalni katalog, Browser katalog ili izvorni link kada postoji."
          items={compatibilityRailItems}
        />
      </div>
    </div>
  );
}
