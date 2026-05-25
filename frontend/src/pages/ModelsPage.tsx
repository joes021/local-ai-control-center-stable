import { useEffect, useMemo, useRef, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CompatibilityCalculatorModal } from "../components/CompatibilityCalculatorModal";
import { ModelDownloadProgressCard } from "../components/ModelDownloadProgressCard";
import {
  activateModel,
  addHfModel,
  addLocalModel,
  addUnslothModel,
  awaitModelActionResult,
  deleteModel,
  downloadModel,
  fetchDownloadProgress,
  fetchModels,
  fetchTurboQuantSchema,
  pickLocalGguf,
} from "../lib/api";
import {
  buildCompatibilityRequestFromModelEntry,
  type CompatibilityLaunchTarget,
} from "../lib/compatibility";
import type {
  ActionResult,
  CompatibilityCheckRequest,
  DownloadProgressPayload,
  ModelEntry,
  ModelsPayload,
  RecommendedModel,
} from "../lib/types";

type GroupKey = "curated" | "local" | "huggingFace" | "unsloth";
type ModelsFilter = "all" | "installed" | "active" | "no-mtp" | "has-mtp" | "unknown-mtp";
type ForceActivationPromptState = string | null;

function formatGiB(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "nepoznato";
  }
  return `${value.toFixed(2)} GiB`;
}

function formatSpeed(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "nepoznato";
  }
  return `${value.toFixed(1)} MB/s`;
}

function formatEta(seconds: number | null) {
  if (seconds === null || seconds < 0) {
    return "nepoznato";
  }
  if (seconds === 0) {
    return "0s";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  const parts: string[] = [];
  if (hours) {
    parts.push(`${hours}h`);
  }
  if (minutes) {
    parts.push(`${minutes}m`);
  }
  if (secs && hours === 0) {
    parts.push(`${secs}s`);
  }
  return parts.join(" ") || "0s";
}

function formatMiB(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "nepoznato";
  }
  return `${value} MiB`;
}

function supportsRuntimeActivation(item: ModelEntry): boolean {
  return item.supportsActivation ?? item.mtpStatus !== "has-mtp";
}

function mtpActivationGuidance(item: ModelEntry): string | null {
  if (item.activationSummary && !supportsRuntimeActivation(item)) {
    return item.activationSummary;
  }
  if (item.mtpStatus === "has-mtp") {
    return "MTP modeli koriste llama.cpp draft-mtp put. Ako je TurboQuant izabran, panel ce za takav model automatski pasti nazad na llama.cpp.";
  }
  if (!supportsRuntimeActivation(item)) {
    return "Model trenutno nije spreman za aktivaciju. Proveri lifecycle status i runtime razlog iznad.";
  }
  return null;
}

function lifecycleTone(status: string | undefined): string {
  switch (status) {
    case "active":
      return "compat-badge compat-badge-ok";
    case "ready":
      return "compat-badge";
    case "downloading":
      return "compat-badge compat-badge-warn";
    case "unsupported":
    case "missing":
    case "unavailable":
      return "compat-badge compat-badge-error";
    default:
      return "compat-badge";
  }
}

function downloadActionLabel(item: ModelEntry): string {
  if (item.downloadActive) {
    return "Downloading...";
  }
  if (item.installed && item.canDownload) {
    return "Re-download";
  }
  if (item.canDownload) {
    return "Download";
  }
  return "Nema download";
}

function requiresForceActivationConfirmation(item: ModelEntry): boolean {
  return Boolean(item.requiresForceConfirmation && item.activationRiskSummary);
}

function activationRiskSummary(item: ModelEntry): string {
  return item.activationRiskSummary ?? "Compatibility procena kaze da ovaj model verovatno nece raditi na ovoj masini.";
}

function ActivationRiskCallout({
  item,
  confirmationOpen,
  pendingAction,
  onConfirm,
  onCancel,
  onOpenCompatibility,
}: {
  item: ModelEntry;
  confirmationOpen: boolean;
  pendingAction: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onOpenCompatibility: () => void;
}) {
  if (!requiresForceActivationConfirmation(item)) {
    return null;
  }

  return (
    <div className="model-activation-warning">
      <div className="model-activation-warning-title">
        Ovaj model verovatno nece moci da radi ili ce raditi lose na ovoj masini.
      </div>
      <div className="helper-text">{activationRiskSummary(item)}</div>
      {confirmationOpen ? (
        <>
          <div className="helper-text">Da li zelis ipak da pokusas aktivaciju?</div>
          <div className="inline-actions compact-actions">
            <button
              type="button"
              className="danger-button"
              disabled={pendingAction}
              onClick={onConfirm}
            >
              Ipak pokusaj aktivaciju
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={pendingAction}
              onClick={onCancel}
            >
              Otkazi
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={pendingAction}
              onClick={onOpenCompatibility}
            >
              Compatibility tab
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

function FilterResultsCard({
  filter,
  items,
  onChanged,
  onCheckCompatibility,
}: {
  filter: ModelsFilter;
  items: ModelEntry[];
  onChanged: () => Promise<unknown>;
  onCheckCompatibility: (item: ModelEntry) => void;
}) {
  const [result, setResult] = useState<ActionResult | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [removeFile, setRemoveFile] = useState(true);
  const [removeRegistry, setRemoveRegistry] = useState(true);
  const [forceActivationPrompt, setForceActivationPrompt] = useState<ForceActivationPromptState>(null);

  async function handleAction(label: string, run: () => Promise<ActionResult>) {
    setPendingAction(label);
    setResult({
      status: "pending",
      action: "models",
      summary: `Pokrecem model akciju: ${label}`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });
    try {
      const actionResult = await run();
      const finalResult = await awaitModelActionResult(actionResult, setResult);
      setResult(finalResult);
      await onChanged();
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Model akcija nije uspela.";
      setResult({
        status: "error",
        action: "models",
        summary: message,
        details: { returncode: 1, stdout: "", stderr: message },
      });
    } finally {
      setPendingAction(null);
    }
  }

  async function handleActivate(item: ModelEntry) {
    if (requiresForceActivationConfirmation(item)) {
      setForceActivationPrompt(item.id);
      setResult({
        status: "warning",
        action: "activate-model-precheck",
        summary: "Ovaj model verovatno nece moci da radi ili ce raditi lose na ovoj masini.",
        details: {
          returncode: 1,
          stdout: activationRiskSummary(item),
          stderr: activationRiskSummary(item),
        },
      });
      return;
    }
    setForceActivationPrompt(null);
    await handleAction(`activate ${item.id}`, () => activateModel(item.id));
  }

  return (
    <section className="status-card wide-card">
      <div className="section-header">
        <span className="status-label">Rezultati filtera</span>
        <strong className="status-value">
          {filter === "all"
            ? "Svi modeli"
            : filter === "installed"
              ? "Skinuti modeli"
              : filter === "active"
                ? "Aktivni modeli"
                : filter === "no-mtp"
                  ? "Modeli bez MTP"
                  : filter === "has-mtp"
                    ? "Modeli sa MTP"
                    : "Modeli sa nepoznatim MTP statusom"}
        </strong>
      </div>
      {items.length ? (
        <div className="model-list">
          {items.map((item) => (
            <article className="model-item" key={`filtered-${item.id}`}>
              <div className="model-item-header">
                <div>
                  <div className="model-title-row">
                    <strong>{item.label}</strong>
                    <span className={lifecycleTone(item.lifecycleStatus)}>{item.lifecycleLabel ?? "Status"}</span>
                  </div>
                  <div className="muted-line">
                    {item.active ? "Aktivan" : "Nije aktivan"} |{" "}
                    {item.installed ? "Skinut" : "Nije skinut"} | {item.source}
                  </div>
                  <div className="muted-line">
                    ID: <code>{item.id}</code>
                  </div>
                  {item.lifecycleSummary ? (
                    <div className="helper-text">{item.lifecycleSummary}</div>
                  ) : null}
                  <div className="helper-text">
                    Velicina: {formatGiB(item.approxSizeGiB ?? null)} | Instalirano:{" "}
                    {item.installed ? formatGiB(item.installedSizeGiB ?? null) : "nije skinut"}
                  </div>
                  <div className="helper-text">
                    Potreban disk: {formatGiB(item.diskNeededGiB ?? null)} | Slobodan disk:{" "}
                    {formatGiB(item.freeDiskGiB ?? null)}
                  </div>
                  <div className="helper-text">
                    GPU prag: {formatMiB(item.minimumGpuMiB)} | Preporuceni GPU:{" "}
                    {formatMiB(item.recommendedGpuMiB)} | RAM: {formatGiB(item.minimumRamGiB ?? null)}
                  </div>
                  <div className="helper-text">MTP status: {item.mtpStatusLabel ?? "nepoznato"}</div>
                  {mtpActivationGuidance(item) ? (
                    <div className="helper-text">{mtpActivationGuidance(item)}</div>
                  ) : null}
                  <ActivationRiskCallout
                    item={item}
                    confirmationOpen={forceActivationPrompt === item.id}
                    pendingAction={Boolean(pendingAction)}
                    onConfirm={() =>
                      void (async () => {
                        setForceActivationPrompt(null);
                        await handleAction(`activate ${item.id} (force)`, () =>
                          activateModel(item.id, { force: true }),
                        );
                      })()
                    }
                    onCancel={() => setForceActivationPrompt(null)}
                    onOpenCompatibility={() => onCheckCompatibility(item)}
                  />
                  {item.description ? <p className="helper-text">{item.description}</p> : null}
                </div>
                <div className="inline-actions">
                  <button
                    disabled={Boolean(pendingAction) || !supportsRuntimeActivation(item) || Boolean(item.downloadActive)}
                    title={
                      requiresForceActivationConfirmation(item)
                        ? activationRiskSummary(item)
                        : (mtpActivationGuidance(item) ?? undefined)
                    }
                    onClick={() => {
                      void handleActivate(item);
                    }}
                    type="button"
                  >
                    Activate
                  </button>
                  <button
                    disabled={Boolean(pendingAction) || !item.canDownload || Boolean(item.downloadActive)}
                    title={item.downloadSummary ?? undefined}
                    onClick={() => handleAction(`download ${item.id}`, () => downloadModel(item.id))}
                    type="button"
                  >
                    {downloadActionLabel(item)}
                  </button>
                  <button
                    disabled={Boolean(pendingAction)}
                    onClick={() => onCheckCompatibility(item)}
                    type="button"
                  >
                    Check compatibility
                  </button>
                  <button
                    className="danger-button"
                    disabled={Boolean(pendingAction) || Boolean(item.downloadActive)}
                    onClick={() => {
                      setDeleteTargetId(item.id);
                      setRemoveFile(true);
                      setRemoveRegistry(Boolean(item.isCustom));
                    }}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {deleteTargetId === item.id ? (
                <div className="helper-text">
                  <strong>Potvrdi delete:</strong>
                  <div className="inline-actions compact-actions">
                    <label>
                      <input
                        type="checkbox"
                        checked={removeRegistry}
                        onChange={(event) => setRemoveRegistry(event.target.checked)}
                      />{" "}
                      Ukloni iz liste
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={removeFile}
                        onChange={(event) => setRemoveFile(event.target.checked)}
                      />{" "}
                      Obrisi sa diska
                    </label>
                    <button
                      type="button"
                      className="danger-button"
                      disabled={Boolean(pendingAction)}
                      onClick={async () => {
                        await handleAction(`delete ${item.id}`, () =>
                          deleteModel(item.id, removeFile, removeRegistry),
                        );
                        setDeleteTargetId(null);
                      }}
                    >
                      Potvrdi delete
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => setDeleteTargetId(null)}
                    >
                      Otkazi
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="helper-text">Nema modela za izabrani filter.</div>
      )}
      <ActionResultPanel result={result} />
    </section>
  );
}

function ModelGroup({
  title,
  groupKey,
  items,
  collapsed,
  onToggle,
  onChanged,
  onCheckCompatibility,
}: {
  title: string;
  groupKey: GroupKey;
  items: ModelEntry[];
  collapsed: boolean;
  onToggle: (group: GroupKey) => void;
  onChanged: () => Promise<unknown>;
  onCheckCompatibility: (item: ModelEntry) => void;
}) {
  const [result, setResult] = useState<ActionResult | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [removeFile, setRemoveFile] = useState(true);
  const [removeRegistry, setRemoveRegistry] = useState(true);
  const [forceActivationPrompt, setForceActivationPrompt] = useState<ForceActivationPromptState>(null);

  async function handleAction(label: string, run: () => Promise<ActionResult>) {
    setPendingAction(label);
    setResult({
      status: "pending",
      action: "models",
      summary: `Pokrecem model akciju: ${label}`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });
    try {
      const actionResult = await run();
      const finalResult = await awaitModelActionResult(actionResult, setResult);
      setResult(finalResult);
      await onChanged();
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Model akcija nije uspela.";
      setResult({
        status: "error",
        action: "models",
        summary: message,
        details: { returncode: 1, stdout: "", stderr: message },
      });
    } finally {
      setPendingAction(null);
    }
  }

  async function handleActivate(item: ModelEntry) {
    if (requiresForceActivationConfirmation(item)) {
      setForceActivationPrompt(item.id);
      setResult({
        status: "warning",
        action: "activate-model-precheck",
        summary: "Ovaj model verovatno nece moci da radi ili ce raditi lose na ovoj masini.",
        details: {
          returncode: 1,
          stdout: activationRiskSummary(item),
          stderr: activationRiskSummary(item),
        },
      });
      return;
    }
    setForceActivationPrompt(null);
    await handleAction(`activate ${item.id}`, () => activateModel(item.id));
  }

  return (
    <section className="status-card wide-card">
      <div className="section-header">
        <span className="status-label">{title}</span>
        <button type="button" className="secondary-button" onClick={() => onToggle(groupKey)}>
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>
      {!collapsed ? (
        items.length ? (
          <div className="model-list">
            {items.map((item) => (
              <article className="model-item" key={item.id}>
                <div className="model-item-header">
                  <div>
                    <div className="model-title-row">
                      <strong>{item.label}</strong>
                      <span className={lifecycleTone(item.lifecycleStatus)}>{item.lifecycleLabel ?? "Status"}</span>
                    </div>
                    <div className="muted-line">
                      {item.active ? "Aktivan" : "Nije aktivan"} |{" "}
                      {item.installed ? "Skinut" : "Nije skinut"} | {item.family ?? "Unknown"}
                    </div>
                  <div className="muted-line">
                    ID: <code>{item.id}</code>
                  </div>
                  {item.lifecycleSummary ? (
                    <div className="helper-text">{item.lifecycleSummary}</div>
                  ) : null}
                  <div className="helper-text">
                    Velicina: {formatGiB(item.approxSizeGiB ?? null)} | Instalirano:{" "}
                    {item.installed ? formatGiB(item.installedSizeGiB ?? null) : "nije skinut"}
                  </div>
                  <div className="helper-text">
                    Potreban disk: {formatGiB(item.diskNeededGiB ?? null)} | Slobodan disk:{" "}
                    {formatGiB(item.freeDiskGiB ?? null)} | Dovoljno diska:{" "}
                    {item.hasEnoughDisk === null || item.hasEnoughDisk === undefined
                      ? "nepoznato"
                      : item.hasEnoughDisk
                        ? "da"
                        : "ne"}
                  </div>
                  <div className="helper-text">
                    GPU prag: {formatMiB(item.minimumGpuMiB)} | Preporuceni GPU:{" "}
                    {formatMiB(item.recommendedGpuMiB)} | RAM: {formatGiB(item.minimumRamGiB ?? null)}
                  </div>
                  <div className="helper-text">MTP status: {item.mtpStatusLabel ?? "nepoznato"}</div>
                  {mtpActivationGuidance(item) ? (
                    <div className="helper-text">{mtpActivationGuidance(item)}</div>
                  ) : null}
                  <ActivationRiskCallout
                    item={item}
                    confirmationOpen={forceActivationPrompt === item.id}
                    pendingAction={Boolean(pendingAction)}
                    onConfirm={() =>
                      void (async () => {
                        setForceActivationPrompt(null);
                        await handleAction(`activate ${item.id} (force)`, () =>
                          activateModel(item.id, { force: true }),
                        );
                      })()
                    }
                    onCancel={() => setForceActivationPrompt(null)}
                    onOpenCompatibility={() => onCheckCompatibility(item)}
                  />
                  {item.description ? <p className="helper-text">{item.description}</p> : null}
                </div>
                  <div className="inline-actions">
                    <button
                      disabled={Boolean(pendingAction) || !supportsRuntimeActivation(item) || Boolean(item.downloadActive)}
                      title={
                        requiresForceActivationConfirmation(item)
                          ? activationRiskSummary(item)
                          : (mtpActivationGuidance(item) ?? undefined)
                      }
                      onClick={() => {
                        void handleActivate(item);
                      }}
                      type="button"
                    >
                      Activate
                    </button>
                    <button
                      disabled={Boolean(pendingAction) || !item.canDownload || Boolean(item.downloadActive)}
                      title={item.downloadSummary ?? undefined}
                      onClick={() => handleAction(`download ${item.id}`, () => downloadModel(item.id))}
                      type="button"
                    >
                      {downloadActionLabel(item)}
                    </button>
                    <button
                      disabled={Boolean(pendingAction)}
                      onClick={() => onCheckCompatibility(item)}
                      type="button"
                    >
                      Check compatibility
                    </button>
                    <button
                      className="danger-button"
                      disabled={Boolean(pendingAction) || Boolean(item.downloadActive)}
                      onClick={() => {
                        setDeleteTargetId(item.id);
                        setRemoveFile(true);
                        setRemoveRegistry(Boolean(item.isCustom));
                      }}
                      type="button"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                {deleteTargetId === item.id ? (
                  <div className="helper-text">
                    <strong>Potvrdi delete:</strong>
                    <div className="inline-actions compact-actions">
                      <label>
                        <input
                          type="checkbox"
                          checked={removeRegistry}
                          onChange={(event) => setRemoveRegistry(event.target.checked)}
                        />{" "}
                        Ukloni iz liste
                      </label>
                      <label>
                        <input
                          type="checkbox"
                          checked={removeFile}
                          onChange={(event) => setRemoveFile(event.target.checked)}
                        />{" "}
                        Obriši sa diska
                      </label>
                      <button
                        type="button"
                        className="danger-button"
                        disabled={Boolean(pendingAction)}
                        onClick={async () => {
                          await handleAction(`delete ${item.id}`, () =>
                            deleteModel(item.id, removeFile, removeRegistry),
                          );
                          setDeleteTargetId(null);
                        }}
                      >
                        Potvrdi delete
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => setDeleteTargetId(null)}
                      >
                        Otkazi
                      </button>
                    </div>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="helper-text">Nema modela za izabrani filter u ovoj grupi.</div>
        )
      ) : (
        <div className="helper-text">Sekcija je sklopljena.</div>
      )}
      <ActionResultPanel result={result} />
    </section>
  );
}

export function ModelsPage({
  onOpenCompatibilityTab,
}: {
  onOpenCompatibilityTab?: (target: CompatibilityLaunchTarget) => void;
}) {
  const [models, setModels] = useState<ModelsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [localPath, setLocalPath] = useState("");
  const [unslothRepo, setUnslothRepo] = useState("");
  const [unslothFilename, setUnslothFilename] = useState("");
  const [hfRepo, setHfRepo] = useState("");
  const [hfFilename, setHfFilename] = useState("");
  const [result, setResult] = useState<ActionResult | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [recommendedModels, setRecommendedModels] = useState<RecommendedModel[]>([]);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgressPayload | null>(null);
  const [modelsFilter, setModelsFilter] = useState<ModelsFilter>("all");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<GroupKey, boolean>>({
    curated: false,
    local: false,
    huggingFace: false,
    unsloth: false,
  });
  const [compatibilityRequest, setCompatibilityRequest] = useState<CompatibilityCheckRequest | null>(null);
  const [compatibilityTitle, setCompatibilityTitle] = useState("Model");
  const progressStatusRef = useRef<string>("idle");

  function showClientError(summary: string) {
    setResult({
      status: "error",
      action: "models-ui",
      summary,
      details: { returncode: 1, stdout: "", stderr: summary },
    });
  }

  function showPendingAction(label: string) {
    setPendingAction(label);
    setResult({
      status: "pending",
      action: "models",
      summary: `Pokrecem model akciju: ${label}`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });
  }

  async function reloadModels() {
    try {
      const payload = await fetchModels();
      setModels(payload);
      setError(null);
      return payload;
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greska");
      return null;
    }
  }

  useEffect(() => {
    void reloadModels();
    void fetchDownloadProgress()
      .then((payload) => {
        setDownloadProgress(payload);
        progressStatusRef.current = payload.status;
      })
      .catch(() => null);
    fetchTurboQuantSchema()
      .then((payload) => setRecommendedModels(payload.recommendedModels))
      .catch(() => setRecommendedModels([]));
  }, []);

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
          void reloadModels();
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

  const summary = useMemo(() => {
    if (!models) {
      return { total: 0, installed: 0 };
    }
    const items = [...models.curated, ...models.local, ...models.huggingFace, ...models.unsloth];
    return {
      total: items.length,
      installed: items.filter((item) => item.installed).length,
    };
  }, [models]);

  const filteredModels = useMemo(() => {
    if (!models) {
      return null;
    }

    function matchesFilter(item: ModelEntry) {
      if (modelsFilter === "installed") {
        return item.installed;
      }
      if (modelsFilter === "active") {
        return item.active;
      }
      if (modelsFilter === "no-mtp") {
        return item.mtpStatus === "no-mtp";
      }
      if (modelsFilter === "has-mtp") {
        return item.mtpStatus === "has-mtp";
      }
      if (modelsFilter === "unknown-mtp") {
        return item.mtpStatus === "unknown";
      }
      return true;
    }

    return {
      curated: models.curated.filter(matchesFilter),
      local: models.local.filter(matchesFilter),
      huggingFace: models.huggingFace.filter(matchesFilter),
      unsloth: models.unsloth.filter(matchesFilter),
    };
  }, [models, modelsFilter]);

  const filteredItems = useMemo(() => {
    if (!filteredModels) {
      return [];
    }
    return [
      ...filteredModels.curated,
      ...filteredModels.local,
      ...filteredModels.huggingFace,
      ...filteredModels.unsloth,
    ];
  }, [filteredModels]);

  const filteredSummary = useMemo(() => {
    return {
      total: filteredItems.length,
      installed: filteredItems.filter((item) => item.installed).length,
      active: filteredItems.filter((item) => item.active).length,
    };
  }, [filteredItems]);

  async function runTopLevelAction(label: string, run: () => Promise<ActionResult>) {
    try {
      showPendingAction(label);
      const actionResult = await run();
      const finalResult = await awaitModelActionResult(actionResult, setResult);
      setResult(finalResult);
      await reloadModels();
    } catch (reason: unknown) {
      showClientError(reason instanceof Error ? reason.message : "Model akcija nije uspela.");
    } finally {
      setPendingAction(null);
    }
  }

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!models || !filteredModels) {
    return <div className="status-card wide-card">Ucitavam modele...</div>;
  }

  return (
    <>
      <section className="status-card wide-card">
        <div className="section-header">
          <span className="status-label">Model browser</span>
          <div className="inline-actions compact-actions">
            <button
              type="button"
              className={`secondary-button ${modelsFilter === "all" ? "nav-button-active" : ""}`}
              onClick={() => setModelsFilter("all")}
            >
              Svi
            </button>
            <button
              type="button"
              className={`secondary-button ${modelsFilter === "installed" ? "nav-button-active" : ""}`}
              onClick={() => setModelsFilter("installed")}
            >
              Skinuti
            </button>
            <button
              type="button"
              className={`secondary-button ${modelsFilter === "active" ? "nav-button-active" : ""}`}
              onClick={() => setModelsFilter("active")}
            >
              Aktivni
            </button>
            <button
              type="button"
              className={`secondary-button ${modelsFilter === "no-mtp" ? "nav-button-active" : ""}`}
              onClick={() => setModelsFilter("no-mtp")}
            >
              Bez MTP
            </button>
            <button
              type="button"
              className={`secondary-button ${modelsFilter === "has-mtp" ? "nav-button-active" : ""}`}
              onClick={() => setModelsFilter("has-mtp")}
            >
              Ima MTP
            </button>
            <button
              type="button"
              className={`secondary-button ${modelsFilter === "unknown-mtp" ? "nav-button-active" : ""}`}
              onClick={() => setModelsFilter("unknown-mtp")}
            >
              Nepoznato MTP
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                setCollapsedGroups({
                  curated: false,
                  local: false,
                  huggingFace: false,
                  unsloth: false,
                })
              }
            >
              Expand all
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                setCollapsedGroups({
                  curated: true,
                  local: true,
                  huggingFace: true,
                  unsloth: true,
                })
              }
            >
              Collapse all
            </button>
          </div>
        </div>
        <strong className="status-value">
          Prikaz: {modelsFilter === "all"
            ? "Svi"
            : modelsFilter === "installed"
              ? "Skinuti"
              : modelsFilter === "active"
                ? "Aktivni"
                : modelsFilter === "no-mtp"
                  ? "Bez MTP"
                  : modelsFilter === "has-mtp"
                    ? "Ima MTP"
                    : "Nepoznato MTP"} |
          Ukupno: {filteredSummary.total} | Skinuto: {filteredSummary.installed} | Aktivno: {filteredSummary.active}
        </strong>
        {modelsFilter !== "all" ? (
          <p className="helper-text">
            Ukupno u katalogu: {summary.total} | Ukupno skinuto: {summary.installed}
          </p>
        ) : null}
        <p className="helper-text">
          Activate menja aktivni Local Qwen model odmah, ali OpenCode taj novi model preuzima tek
          u novom session-u. Ako je OpenCode vec otvoren, zatvori ga i otvori ponovo.
        </p>
        <p className="helper-text">
          MTP modeli sada koriste llama.cpp draft-mtp put. Ako je TurboQuant izabran, panel ce
          za takav model automatski pasti nazad na llama.cpp.
        </p>
        <div className="inline-actions compact-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              if (!models.local.length && !models.curated.length && !models.huggingFace.length && !models.unsloth.length) {
                return;
              }
              const firstModel = filteredItems[0] ?? models.curated[0] ?? models.local[0] ?? models.huggingFace[0] ?? models.unsloth[0];
              if (!firstModel) {
                return;
              }
              onOpenCompatibilityTab?.({
                title: firstModel.label,
                request: buildCompatibilityRequestFromModelEntry(firstModel),
              });
            }}
          >
            Compatibility tab
          </button>
        </div>
      </section>

        <FilterResultsCard
          filter={modelsFilter}
          items={filteredItems}
          onChanged={reloadModels}
          onCheckCompatibility={(item) => {
            setCompatibilityTitle(item.label);
            setCompatibilityRequest(buildCompatibilityRequestFromModelEntry(item));
          }}
        />
      <CompatibilityCalculatorModal
        isOpen={Boolean(compatibilityRequest)}
        title={compatibilityTitle}
        request={compatibilityRequest}
        onClose={() => setCompatibilityRequest(null)}
        headerActions={
          compatibilityRequest ? (
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                onOpenCompatibilityTab?.({
                  title: compatibilityTitle,
                  request: compatibilityRequest,
                });
                setCompatibilityRequest(null);
              }}
            >
              Compatibility tab
            </button>
          ) : null
        }
      />
      <ModelDownloadProgressCard progress={downloadProgress} />

      <section className="status-card wide-card">
        <span className="status-label">Dodaj lokalni GGUF</span>
        <p className="helper-text">
          Dodavanje lokalnog GGUF-a odmah kopira fajl u model folder, pa nema posebnog Download koraka.
        </p>
        <div className="form-grid">
          <input
            placeholder="/putanja/do/model.gguf"
            value={localPath}
            onChange={(event) => setLocalPath(event.target.value)}
          />
          <button
            type="button"
            disabled={Boolean(pendingAction)}
            onClick={() =>
              pickLocalGguf().then((payload) => {
                if (payload.path) {
                  setLocalPath(payload.path);
                  setResult({
                    status: "ok",
                    action: "pick-local-gguf",
                    summary: payload.summary,
                    details: { returncode: 0, stdout: payload.path, stderr: "" },
                  });
                } else {
                  setResult({
                    status: payload.status === "cancelled" ? "cancelled" : "error",
                    action: "pick-local-gguf",
                    summary: payload.summary,
                    details: {
                      returncode: payload.status === "cancelled" ? 0 : 1,
                      stdout: "",
                      stderr: payload.summary,
                    },
                  });
                }
              })
            }
          >
            Browse
          </button>
          <button
            type="button"
            disabled={Boolean(pendingAction)}
            onClick={async () => {
              if (!localPath.trim()) {
                showClientError("Izaberi lokalni GGUF fajl pre dodavanja.");
                return;
              }
              await runTopLevelAction("add local", () => addLocalModel(localPath.trim(), "", "Custom"));
            }}
          >
            Add local
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Dodaj Unsloth model</span>
        <p className="helper-text">
          Ovaj korak samo dodaje model u spisak. Posle toga idi na <strong>Download</strong>.
        </p>
        <div className="form-grid">
          <input
            placeholder="unsloth/Qwen3.6-35B-A3B-GGUF"
            value={unslothRepo}
            onChange={(event) => setUnslothRepo(event.target.value)}
          />
          <input
            placeholder="Qwen3.6-35B-A3B-UD-IQ2_M.gguf"
            value={unslothFilename}
            onChange={(event) => setUnslothFilename(event.target.value)}
          />
          <button
            type="button"
            disabled={Boolean(pendingAction)}
            onClick={async () => {
              if (!unslothRepo.trim() || !unslothFilename.trim()) {
                showClientError("Popuni Unsloth repo i tacan GGUF filename sa kvantizacijom.");
                return;
              }
              await runTopLevelAction("add unsloth", () =>
                addUnslothModel(unslothRepo.trim(), unslothFilename.trim(), "", "Unsloth"),
              );
            }}
          >
            Add Unsloth
          </button>
        </div>
        <p className="helper-text">
          Unsloth je poseban izvor modela. Unesi tacan GGUF filename sa kvantizacijom.
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Dodaj Hugging Face model</span>
        <p className="helper-text">
          Ovaj korak samo dodaje model u spisak. Posle toga idi na <strong>Download</strong>.
        </p>
        <div className="form-grid">
          <input
            placeholder="Qwen/Qwen3-0.6B-GGUF"
            value={hfRepo}
            onChange={(event) => setHfRepo(event.target.value)}
          />
          <input
            placeholder="Qwen3-0.6B-Q8_0.gguf"
            value={hfFilename}
            onChange={(event) => setHfFilename(event.target.value)}
          />
          <button
            type="button"
            disabled={Boolean(pendingAction)}
            onClick={async () => {
              if (!hfRepo.trim() || !hfFilename.trim()) {
                showClientError("Popuni repo i tacan GGUF filename sa kvantizacijom.");
                return;
              }
              await runTopLevelAction("add hf", () =>
                addHfModel(hfRepo.trim(), hfFilename.trim(), "", "Custom"),
              );
            }}
          >
            Add HF
          </button>
        </div>
        <p className="helper-text">
          Unesi tacan GGUF filename sa kvantizacijom, na primer <code>Qwen3-0.6B-Q8_0.gguf</code>.
        </p>
      </section>

      <ActionResultPanel result={result} />

      <section className="status-card wide-card">
        <span className="status-label">Unsloth GGUF preporuke</span>
        <p className="helper-text">
          Ovo su preporuceni non-MTP GGUF izbori za RTX 3060 12 GB + llama.cpp + TurboQuant.
        </p>
        <p className="helper-text">
          Fokus je na Qwen3.6 35B A3B i Qwen3.6 27B varijantama kao sto su UD-IQ2_M i UD-IQ3_XXS.
        </p>
        <div className="model-list">
          {recommendedModels.map((item) => (
            <article className="model-item" key={item.id}>
              <div className="model-item-header">
                <div>
                  <strong>
                    {item.label} | {item.quantization}
                  </strong>
                  <div className="muted-line">{item.repo}</div>
                  <div className="muted-line">{item.filename}</div>
                  <p className="helper-text">{item.fitNote}</p>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    disabled={Boolean(pendingAction)}
                    onClick={async () => {
                      setUnslothRepo(item.repo);
                      setUnslothFilename(item.filename);
                      await runTopLevelAction(`add unsloth ${item.filename}`, () =>
                        addUnslothModel(item.repo, item.filename, item.label, "Unsloth"),
                      );
                    }}
                  >
                    Dodaj Unsloth model
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <ModelGroup
        title="Kurirani modeli"
        groupKey="curated"
        items={filteredModels.curated}
        collapsed={collapsedGroups.curated}
        onToggle={(group) =>
          setCollapsedGroups((current) => ({ ...current, [group]: !current[group] }))
        }
        onChanged={reloadModels}
        onCheckCompatibility={(item) => {
          setCompatibilityTitle(item.label);
          setCompatibilityRequest(buildCompatibilityRequestFromModelEntry(item));
        }}
      />
      <ModelGroup
        title="Lokalni modeli"
        groupKey="local"
        items={filteredModels.local}
        collapsed={collapsedGroups.local}
        onToggle={(group) =>
          setCollapsedGroups((current) => ({ ...current, [group]: !current[group] }))
        }
        onChanged={reloadModels}
        onCheckCompatibility={(item) => {
          setCompatibilityTitle(item.label);
          setCompatibilityRequest(buildCompatibilityRequestFromModelEntry(item));
        }}
      />
      <ModelGroup
        title="Hugging Face modeli"
        groupKey="huggingFace"
        items={filteredModels.huggingFace}
        collapsed={collapsedGroups.huggingFace}
        onToggle={(group) =>
          setCollapsedGroups((current) => ({ ...current, [group]: !current[group] }))
        }
        onChanged={reloadModels}
        onCheckCompatibility={(item) => {
          setCompatibilityTitle(item.label);
          setCompatibilityRequest(buildCompatibilityRequestFromModelEntry(item));
        }}
      />
      <ModelGroup
        title="Unsloth modeli"
        groupKey="unsloth"
        items={filteredModels.unsloth}
        collapsed={collapsedGroups.unsloth}
        onToggle={(group) =>
          setCollapsedGroups((current) => ({ ...current, [group]: !current[group] }))
        }
        onChanged={reloadModels}
        onCheckCompatibility={(item) => {
          setCompatibilityTitle(item.label);
          setCompatibilityRequest(buildCompatibilityRequestFromModelEntry(item));
        }}
      />
    </>
  );
}
