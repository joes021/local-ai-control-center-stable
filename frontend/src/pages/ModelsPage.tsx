import { useEffect, useMemo, useRef, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CompatibilityCalculatorModal } from "../components/CompatibilityCalculatorModal";
import { ModelDownloadProgressCard } from "../components/ModelDownloadProgressCard";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
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
  peekModelsCache,
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

function buildModelsFilterLabel(filter: ModelsFilter) {
  if (filter === "all") {
    return "Svi";
  }
  if (filter === "installed") {
    return "Skinuti";
  }
  if (filter === "active") {
    return "Aktivni";
  }
  if (filter === "no-mtp") {
    return "Bez MTP";
  }
  if (filter === "has-mtp") {
    return "Ima MTP";
  }
  return "Nepoznato MTP";
}

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
    return "MTP modeli koriste llama.cpp draft-mtp put. Ako je TurboQuant izabran, panel će za takav model automatski pasti nazad na llama.cpp.";
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
    return "Preuzimanje...";
  }
  if (item.installed && item.canDownload) {
    return "Preuzmi ponovo";
  }
  if (item.canDownload) {
    return "Preuzmi";
  }
  return "Nema preuzimanja";
}

function requiresForceActivationConfirmation(item: ModelEntry): boolean {
  return Boolean(item.requiresForceConfirmation && item.activationRiskSummary);
}

function activationRiskSummary(item: ModelEntry): string {
  return item.activationRiskSummary ?? "Procena kompatibilnosti kaže da ovaj model verovatno neće raditi na ovoj mašini.";
}

function canRemoveModelFile(item: ModelEntry): boolean {
  return Boolean(item.installed) && !Boolean(item.active);
}

function canRemoveModelRegistry(item: ModelEntry): boolean {
  return Boolean(item.isCustom) || (item.source === "curated" && !Boolean(item.active));
}

function hasAnyDeleteAction(item: ModelEntry): boolean {
  return canRemoveModelFile(item) || canRemoveModelRegistry(item);
}

function deleteActionHint(item: ModelEntry): string | undefined {
  if (canRemoveModelFile(item) || canRemoveModelRegistry(item)) {
    return undefined;
  }
  if (item.active && item.installed) {
    return "Aktivni model ne može da se obriše sa diska dok je aktivan.";
  }
  if (item.source === "curated" && !item.active) {
    return "Kurirani model možeš da sakriješ iz liste da ne zauzima prostor, čak i kada nije skinut na disk.";
  }
  if (!item.installed) {
    return "Model nije skinut na disk, pa nema fajla za brisanje.";
  }
  return "Za ovaj model trenutno nema dostupne delete akcije.";
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
        Ovaj model verovatno neće moći da radi ili će raditi loše na ovoj mašini.
      </div>
      <div className="helper-text">{activationRiskSummary(item)}</div>
      {confirmationOpen ? (
        <>
          <div className="helper-text">Da li želiš ipak da pokušaš aktivaciju?</div>
          <div className="inline-actions compact-actions">
            <button
              type="button"
              className="danger-button"
              disabled={pendingAction}
              onClick={onConfirm}
            >
              Ipak pokušaj aktivaciju
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={pendingAction}
              onClick={onCancel}
            >
              Otkaži
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={pendingAction}
              onClick={onOpenCompatibility}
            >
              Tab kompatibilnosti
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

function ModelGroupHeaderMeta({ items }: { items: ModelEntry[] }) {
  const installedCount = items.filter((item) => item.installed).length;
  const activeCount = items.filter((item) => item.active).length;
  const downloadReadyCount = items.filter((item) => item.canDownload && !item.installed).length;

  return (
    <div className="model-group-header-meta">
      <span>{items.length} modela</span>
      <span>{installedCount} skinuto</span>
      <span>{activeCount} aktivno</span>
      <span>{downloadReadyCount} spremno za download</span>
    </div>
  );
}

function ModelFactGrid({ item }: { item: ModelEntry }) {
  const readinessValue = item.active ? "Aktivan" : item.installed ? "Spreman" : "Nije skinut";
  const sourceValue = item.isCustom
    ? "Lokalni GGUF"
    : item.source === "curated"
      ? "Kurirani katalog"
      : item.source;
  const lifecycleDetail = item.lifecycleLabel ?? "Status";
  const fitValue = `${formatMiB(item.minimumGpuMiB)} GPU`;
  const fitDetail = `RAM ${formatGiB(item.minimumRamGiB ?? null)}`;
  const sizeValue = formatGiB(item.approxSizeGiB ?? null);
  const sizeDetail = item.installed
    ? `Instalirano ${formatGiB(item.installedSizeGiB ?? null)}`
    : "Još nije lokalno skinut";
  const diskValue = formatGiB(item.diskNeededGiB ?? null);
  const diskDetail = `Slobodno ${formatGiB(item.freeDiskGiB ?? null)}`;

  return (
    <div className="model-fact-grid">
      <article className="model-fact-card">
        <span className="model-fact-label">Stanje</span>
        <strong className="model-fact-value">{readinessValue}</strong>
        <span className="helper-text">{lifecycleDetail}</span>
      </article>
      <article className="model-fact-card">
        <span className="model-fact-label">Poreklo</span>
        <strong className="model-fact-value">{sourceValue}</strong>
        <span className="helper-text">{item.family ?? "Porodica nije prijavljena"}</span>
      </article>
      <article className="model-fact-card">
        <span className="model-fact-label">Veličina</span>
        <strong className="model-fact-value">{sizeValue}</strong>
        <span className="helper-text">{sizeDetail}</span>
      </article>
      <article className="model-fact-card">
        <span className="model-fact-label">Fit prag</span>
        <strong className="model-fact-value">{fitValue}</strong>
        <span className="helper-text">{fitDetail}</span>
      </article>
      <article className="model-fact-card">
        <span className="model-fact-label">Disk</span>
        <strong className="model-fact-value">{diskValue}</strong>
        <span className="helper-text">
          {diskDetail} ·{" "}
          {item.hasEnoughDisk === null || item.hasEnoughDisk === undefined
            ? "provera nije završena"
            : item.hasEnoughDisk
              ? "dovoljno"
              : "nema dovoljno"}
        </span>
      </article>
      <article className="model-fact-card">
        <span className="model-fact-label">MTP</span>
        <strong className="model-fact-value">{item.mtpStatusLabel ?? "nepoznato"}</strong>
        <span className="helper-text">
          {supportsRuntimeActivation(item) ? "može u runtime tok" : "traži draft-mtp fallback"}
        </span>
      </article>
    </div>
  );
}

function ModelDeletePanel({
  item,
  pendingAction,
  removeFile,
  removeRegistry,
  onToggleRemoveFile,
  onToggleRemoveRegistry,
  onConfirm,
  onCancel,
}: {
  item: ModelEntry;
  pendingAction: boolean;
  removeFile: boolean;
  removeRegistry: boolean;
  onToggleRemoveFile: (checked: boolean) => void;
  onToggleRemoveRegistry: (checked: boolean) => void;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}) {
  return (
    <div className="model-delete-panel">
      <strong>Potvrdi brisanje</strong>
      <p className="helper-text">
        Izaberi da li želiš da ukloniš stavku iz prikaza, obrišeš lokalni fajl ili uradiš oba koraka
        odjednom.
      </p>
      <div className="model-delete-options">
        {canRemoveModelRegistry(item) ? (
          <label className="model-delete-option">
            <input
              type="checkbox"
              checked={removeRegistry}
              onChange={(event) => onToggleRemoveRegistry(event.target.checked)}
            />{" "}
            {item.isCustom ? "Ukloni iz liste" : "Sakrij sa liste"}
          </label>
        ) : (
          <span className="helper-text">Ovaj model ostaje u katalogu i ne može da se ukloni iz liste.</span>
        )}
        {canRemoveModelFile(item) ? (
          <label className="model-delete-option">
            <input
              type="checkbox"
              checked={removeFile}
              onChange={(event) => onToggleRemoveFile(event.target.checked)}
            />{" "}
            Obriši sa diska
          </label>
        ) : item.active && item.installed ? (
          <span className="helper-text">Aktivni model ne može da se obriše sa diska dok je aktivan.</span>
        ) : (
          <span className="helper-text">Model trenutno nema fajl na disku za brisanje.</span>
        )}
      </div>
      <div className="inline-actions compact-actions">
        <button
          type="button"
          className="danger-button"
          disabled={pendingAction || (!removeFile && !removeRegistry)}
          onClick={() => void onConfirm()}
        >
          Potvrdi brisanje
        </button>
        <button type="button" className="secondary-button" onClick={onCancel}>
          Otkaži
        </button>
      </div>
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
      summary: `Pokrećem model akciju: ${label}`,
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
        summary: "Ovaj model verovatno neće moći da radi ili će raditi loše na ovoj mašini.",
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
        <div>
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
          <ModelGroupHeaderMeta items={items} />
        </div>
      </div>
      {items.length ? (
        <div className="model-list">
            {items.map((item) => (
              <article className="model-item" key={`filtered-${item.id}`}>
                <div className="model-item-header">
                  <div className="model-item-copy">
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
                  <ModelFactGrid item={item} />
                  {item.lifecycleSummary || mtpActivationGuidance(item) || item.description ? (
                    <div className="model-guidance-panel">
                      {item.lifecycleSummary ? <div className="helper-text">{item.lifecycleSummary}</div> : null}
                      {mtpActivationGuidance(item) ? (
                        <div className="helper-text">{mtpActivationGuidance(item)}</div>
                      ) : null}
                      {item.description ? <p className="helper-text">{item.description}</p> : null}
                    </div>
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
                  </div>
                <div className="inline-actions model-action-rail">
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
                    Aktiviraj
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
                    Proveri kompatibilnost
                  </button>
                  <button
                    className="danger-button"
                    disabled={Boolean(pendingAction) || Boolean(item.downloadActive) || !hasAnyDeleteAction(item)}
                    title={deleteActionHint(item)}
                    onClick={() => {
                      setDeleteTargetId(item.id);
                      setRemoveFile(canRemoveModelFile(item));
                      setRemoveRegistry(canRemoveModelRegistry(item));
                    }}
                    type="button"
                  >
                    Obriši
                  </button>
                </div>
              </div>
              {deleteTargetId === item.id ? (
                <ModelDeletePanel
                  item={item}
                  pendingAction={Boolean(pendingAction)}
                  removeFile={removeFile}
                  removeRegistry={removeRegistry}
                  onToggleRemoveFile={setRemoveFile}
                  onToggleRemoveRegistry={setRemoveRegistry}
                  onConfirm={async () => {
                    await handleAction(`delete ${item.id}`, () =>
                      deleteModel(item.id, removeFile, removeRegistry),
                    );
                    setDeleteTargetId(null);
                  }}
                  onCancel={() => setDeleteTargetId(null)}
                />
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
  showWhenEmpty = false,
  highlightedModelId,
  onToggle,
  onChanged,
  onCheckCompatibility,
}: {
  title: string;
  groupKey: GroupKey;
  items: ModelEntry[];
  collapsed: boolean;
  showWhenEmpty?: boolean;
  highlightedModelId?: string | null;
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
      summary: `Pokrećem model akciju: ${label}`,
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
        summary: "Ovaj model verovatno neće moći da radi ili će raditi loše na ovoj mašini.",
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

  if (!items.length && !showWhenEmpty) {
    return null;
  }

  return (
    <section className="status-card wide-card">
      <div className="section-header">
        <div>
          <span className="status-label">{title}</span>
          <ModelGroupHeaderMeta items={items} />
        </div>
        <button type="button" className="secondary-button" onClick={() => onToggle(groupKey)}>
          {collapsed ? "Proširi" : "Skupi"}
        </button>
      </div>
      {!collapsed ? (
        items.length ? (
          <div className="model-list">
            {items.map((item) => (
              <article
                className={`model-item ${highlightedModelId === item.id ? "model-item-highlighted" : ""}`}
                key={item.id}
              >
                <div className="model-item-header">
                  <div className="model-item-copy">
                    <div className="model-title-row">
                      <strong>{item.label}</strong>
                      <span className={lifecycleTone(item.lifecycleStatus)}>{item.lifecycleLabel ?? "Status"}</span>
                    </div>
                    {highlightedModelId === item.id ? (
                      <div className="helper-text">
                        Novo dodato. Ako želiš da ga pokreneš odmah, idi na <strong>Aktiviraj</strong>.
                        Ako procena kaže da je model pretežak za ovu mašinu, klikni{" "}
                        <strong>Ipak pokušaj aktivaciju</strong>.
                      </div>
                    ) : null}
                    <div className="muted-line">
                      {item.active ? "Aktivan" : "Nije aktivan"} |{" "}
                      {item.installed ? "Skinut" : "Nije skinut"} | {item.family ?? "nepoznato"}
                    </div>
                  <div className="muted-line">
                    ID: <code>{item.id}</code>
                  </div>
                  <ModelFactGrid item={item} />
                  {item.lifecycleSummary || mtpActivationGuidance(item) || item.description ? (
                    <div className="model-guidance-panel">
                      {item.lifecycleSummary ? <div className="helper-text">{item.lifecycleSummary}</div> : null}
                      {mtpActivationGuidance(item) ? (
                        <div className="helper-text">{mtpActivationGuidance(item)}</div>
                      ) : null}
                      {item.description ? <p className="helper-text">{item.description}</p> : null}
                    </div>
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
                  </div>
                  <div className="inline-actions model-action-rail">
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
                      Aktiviraj
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
                      Proveri kompatibilnost
                    </button>
                    <button
                      className="danger-button"
                      disabled={Boolean(pendingAction) || Boolean(item.downloadActive) || !hasAnyDeleteAction(item)}
                      title={deleteActionHint(item)}
                      onClick={() => {
                        setDeleteTargetId(item.id);
                        setRemoveFile(canRemoveModelFile(item));
                        setRemoveRegistry(canRemoveModelRegistry(item));
                      }}
                      type="button"
                    >
                      Obriši
                    </button>
                  </div>
                </div>
                {deleteTargetId === item.id ? (
                  <ModelDeletePanel
                    item={item}
                    pendingAction={Boolean(pendingAction)}
                    removeFile={removeFile}
                    removeRegistry={removeRegistry}
                    onToggleRemoveFile={setRemoveFile}
                    onToggleRemoveRegistry={setRemoveRegistry}
                    onConfirm={async () => {
                      await handleAction(`delete ${item.id}`, () =>
                        deleteModel(item.id, removeFile, removeRegistry),
                      );
                      setDeleteTargetId(null);
                    }}
                    onCancel={() => setDeleteTargetId(null)}
                  />
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
  const [models, setModels] = useState<ModelsPayload | null>(() => peekModelsCache());
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
  const [lastAddedLocalModelId, setLastAddedLocalModelId] = useState<string | null>(null);
  const [lastAddedLocalLabel, setLastAddedLocalLabel] = useState<string | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<GroupKey, boolean>>({
    curated: false,
    local: false,
    huggingFace: false,
    unsloth: false,
  });
  const [compatibilityRequest, setCompatibilityRequest] = useState<CompatibilityCheckRequest | null>(null);
  const [compatibilityTitle, setCompatibilityTitle] = useState("Model");
  const progressStatusRef = useRef<string>("idle");
  const localGroupRef = useRef<HTMLDivElement | null>(null);

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
      summary: `Pokrećem model akciju: ${label}`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });
  }

  function revealLocalModels() {
    requestAnimationFrame(() => {
      localGroupRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  async function reloadModels() {
    try {
      const payload = await fetchModels();
      setModels(payload);
      setError(null);
      return payload;
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
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

  if (!models || !filteredModels) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam modele..."
        onRetry={() => {
          setError(null);
          void reloadModels();
        }}
      />
    );
  }

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Model tok"
        summary="Najprirodniji tok je da prvo dodaš ili preuzmeš model, zatim ga aktiviraš, pa po potrebi proveriš kompatibilnost pre starta runtime-a."
        steps={[
          {
            title: "Dodaj ili preuzmi model",
            detail: "Kreni od curated, local ili remote izvora i prvo obezbedi da model stvarno postoji lokalno.",
          },
          {
            title: "Aktiviraj model",
            detail: "Tek kada je model spreman lokalno, aktiviraj ga i obrati pažnju na lifecycle i MTP napomene.",
          },
          {
            title: "Proveri kompatibilnost ili pokreni runtime",
            detail: "Ako imaš sumnju oko memorije i fit-a, idi na Compatibility tok pre nego što kreneš u rad.",
          },
        ]}
      />
      <section className="status-card wide-card models-browser-shell">
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
              Proširi sve
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
              Skupi sve
            </button>
          </div>
        </div>
        <strong className="status-value">Pregled model kataloga i aktivacije</strong>
        <div className="models-summary-grid">
          <article className="models-summary-card">
            <span className="status-label">Trenutni prikaz</span>
            <strong>{buildModelsFilterLabel(modelsFilter)}</strong>
            <p className="helper-text">
              {modelsFilter === "all"
                ? "Gledaš ceo katalog bez dodatnog filtriranja."
                : "Filtrirani prikaz ti sužava fokus pre aktivacije ili čišćenja liste."}
            </p>
          </article>
          <article className="models-summary-card">
            <span className="status-label">U ovom prikazu</span>
            <strong>{filteredSummary.total} modela</strong>
            <p className="helper-text">
              Skinuto: {filteredSummary.installed} · Aktivno: {filteredSummary.active}
            </p>
          </article>
          <article className="models-summary-card">
            <span className="status-label">Ukupan katalog</span>
            <strong>{summary.total} modela</strong>
            <p className="helper-text">
              Ukupno skinuto: {summary.installed}. To ti govori koliki je stvarni lokalni fond.
            </p>
          </article>
          <article className="models-summary-card">
            <span className="status-label">Brzi savet</span>
            <strong>Model pa nova sesija</strong>
            <p className="helper-text">
              Kad promeniš aktivni model, otvori novu OpenCode sesiju da agent stvarno preuzme novu postavku.
            </p>
          </article>
        </div>
        <div className="models-toolbar-note-grid">
          <article className="models-toolbar-note">
            <strong>OpenCode i aktivacija</strong>
            <p className="helper-text">
              Aktiviraj menja aktivni lokalni model odmah, ali OpenCode taj novi model preuzima tek
              u novoj sesiji. Ako je OpenCode već otvoren, zatvori ga i otvori ponovo.
            </p>
          </article>
          <article className="models-toolbar-note">
            <strong>MTP i runtime fallback</strong>
            <p className="helper-text">
              MTP modeli sada koriste llama.cpp draft-mtp put. Ako je TurboQuant izabran, panel će
              za takav model automatski pasti nazad na llama.cpp.
            </p>
          </article>
        </div>
        <div className="inline-actions compact-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              if (!models.local.length && !models.curated.length && !models.huggingFace.length && !models.unsloth.length) {
                return;
              }
              const firstModel =
                filteredItems[0] ??
                models.curated[0] ??
                models.local[0] ??
                models.huggingFace[0] ??
                models.unsloth[0];
              if (!firstModel) {
                return;
              }
              onOpenCompatibilityTab?.({
                title: firstModel.label,
                request: buildCompatibilityRequestFromModelEntry(firstModel),
              });
            }}
          >
            Tab kompatibilnosti
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
              Tab kompatibilnosti
            </button>
          ) : null
        }
      />
      <ModelDownloadProgressCard progress={downloadProgress} />

      <section className="status-card wide-card">
        <span className="status-label">Dodavanje modela</span>
        <strong className="status-value">Lokalni GGUF, Unsloth i Hugging Face ulazna tačka</strong>
        <p className="helper-text">
          Sve tri opcije rade različitu stvar: lokalni GGUF odmah kopira fajl u model folder, dok
          Unsloth i Hugging Face prvo dodaju zapis u katalog pa tek onda ide preuzimanje.
        </p>
        <div className="models-import-grid">
          <article className="models-import-card">
            <span className="status-label">Dodaj lokalni GGUF</span>
            <strong>Direktno kopiranje u lokalni model folder</strong>
            <p className="helper-text">
              Dodavanje lokalnog GGUF-a odmah kopira fajl u model folder, pa nema posebnog koraka za preuzimanje.
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
                Izaberi fajl
              </button>
              <button
                type="button"
                disabled={Boolean(pendingAction)}
                onClick={async () => {
                  if (!localPath.trim()) {
                    showClientError("Izaberi lokalni GGUF fajl pre dodavanja.");
                    return;
                  }
                  const localPathValue = localPath.trim();
                  try {
                    showPendingAction("add local");
                    const actionResult = await addLocalModel(localPathValue, "", "Custom");
                    const finalResult = await awaitModelActionResult(actionResult, setResult);
                    const reloadedModels = await reloadModels();
                    const localModelId = String(
                      (finalResult as { localModelId?: string }).localModelId ??
                        (actionResult as { localModelId?: string }).localModelId ??
                        "",
                    ).trim();
                    if (finalResult.status === "ok" && localModelId) {
                      const addedItem =
                        reloadedModels?.local?.find((item) => item.id === localModelId) ?? null;
                      setLastAddedLocalModelId(localModelId);
                      setLastAddedLocalLabel(
                        addedItem?.label ||
                          localPathValue.split(/[\\/]/).pop()?.replace(/\.gguf$/i, "") ||
                          "lokalni model",
                      );
                      setModelsFilter("installed");
                      setCollapsedGroups((current) => ({ ...current, local: false }));
                      setLocalPath("");
                      setResult({
                        ...finalResult,
                        summary:
                          `${finalResult.summary} Model je dodat u \`Lokalni modeli\`. ` +
                          "Ako ga ne vidiš odmah, grupa niže na strani će se otvoriti. " +
                          "Ako fit procena kaže da je model pretežak, klikni Aktiviraj pa `Ipak pokušaj aktivaciju`.",
                      });
                      revealLocalModels();
                    } else {
                      setResult(finalResult);
                    }
                  } catch (reason: unknown) {
                    showClientError(reason instanceof Error ? reason.message : "Model akcija nije uspela.");
                  } finally {
                    setPendingAction(null);
                  }
                }}
              >
                Dodaj lokalni
              </button>
            </div>
            {pendingAction === "add local" ? (
              <div className="model-import-callout">
                <strong>Kopiram lokalni GGUF u model folder.</strong>
                <p className="helper-text">
                  Za velike modele ovo može da traje neko vreme. Kada se kopiranje završi, RuntimePilot će
                  otvoriti grupu <strong>Lokalni modeli</strong> niže na strani.
                </p>
              </div>
            ) : null}
            {lastAddedLocalModelId ? (
              <div className="model-import-callout">
                <strong>Model je dodat u `Lokalni modeli`.</strong>
                <p className="helper-text">
                  {lastAddedLocalLabel || "Lokalni model"} je uspešno kopiran u installer-managed model folder.
                  Ako želiš da ga pronađeš odmah, koristi dugme ispod. Ako aktivacija pokaže da je model
                  pretežak za ovu mašinu, nastavi preko <strong>Aktiviraj</strong> pa{" "}
                  <strong>Ipak pokušaj aktivaciju</strong>.
                </p>
                <div className="inline-actions compact-actions">
                  <button type="button" className="secondary-button" onClick={revealLocalModels}>
                    Prikaži u Lokalni modeli
                  </button>
                </div>
              </div>
            ) : null}
          </article>

          <article className="models-import-card">
            <span className="status-label">Dodaj Unsloth model</span>
            <strong>Prvo unos u katalog, pa preuzimanje</strong>
            <p className="helper-text">
              Ovaj korak samo dodaje model u spisak. Posle toga idi na <strong>Preuzmi</strong>.
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
                    showClientError("Popuni Unsloth repo i tačan GGUF filename sa kvantizacijom.");
                    return;
                  }
                  await runTopLevelAction("add unsloth", () =>
                    addUnslothModel(unslothRepo.trim(), unslothFilename.trim(), "", "Unsloth"),
                  );
                }}
              >
                Dodaj Unsloth
              </button>
            </div>
            <p className="helper-text">
              Unsloth je poseban izvor modela. Unesi tačan GGUF filename sa kvantizacijom.
            </p>
          </article>

          <article className="models-import-card">
            <span className="status-label">Dodaj Hugging Face model</span>
            <strong>Repo + tačan GGUF filename</strong>
            <p className="helper-text">
              Ovaj korak samo dodaje model u spisak. Posle toga idi na <strong>Preuzmi</strong>.
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
                    showClientError("Popuni repo i tačan GGUF filename sa kvantizacijom.");
                    return;
                  }
                  await runTopLevelAction("add hf", () =>
                    addHfModel(hfRepo.trim(), hfFilename.trim(), "", "Custom"),
                  );
                }}
              >
                Dodaj HF
              </button>
            </div>
            <p className="helper-text">
              Unesi tačan GGUF filename sa kvantizacijom, na primer <code>Qwen3-0.6B-Q8_0.gguf</code>.
            </p>
          </article>
        </div>
      </section>

      <ActionResultPanel result={result} />

      <section className="status-card wide-card">
        <span className="status-label">Unsloth GGUF preporuke</span>
        <p className="helper-text">
          Ovo su preporučeni non-MTP GGUF izbori za RTX 3060 12 GB + llama.cpp + TurboQuant.
        </p>
        <p className="helper-text">
          Fokus je na Qwen3.6 35B A3B i Qwen3.6 27B varijantama kao što su UD-IQ2_M i UD-IQ3_XXS.
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
        showWhenEmpty
        onToggle={(group) =>
          setCollapsedGroups((current) => ({ ...current, [group]: !current[group] }))
        }
        onChanged={reloadModels}
        onCheckCompatibility={(item) => {
          setCompatibilityTitle(item.label);
          setCompatibilityRequest(buildCompatibilityRequestFromModelEntry(item));
        }}
      />
      <div className="models-local-group-anchor wide-card" ref={localGroupRef}>
        <ModelGroup
          title="Lokalni modeli"
          groupKey="local"
          items={filteredModels.local}
          collapsed={collapsedGroups.local}
          showWhenEmpty
          highlightedModelId={lastAddedLocalModelId}
          onToggle={(group) =>
            setCollapsedGroups((current) => ({ ...current, [group]: !current[group] }))
          }
          onChanged={reloadModels}
          onCheckCompatibility={(item) => {
            setCompatibilityTitle(item.label);
            setCompatibilityRequest(buildCompatibilityRequestFromModelEntry(item));
          }}
        />
      </div>
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
