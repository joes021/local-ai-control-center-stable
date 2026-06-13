import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import {
  applySettings,
  deleteWorkflowPreset,
  fetchSettings,
  saveWorkflowPreset,
} from "../lib/api";
import {
  resolveSelectedWorkflowPreset,
  resolveWorkflowPresets,
} from "../lib/workflowPresets";
import type { ActionResult, SettingsPayload, WorkflowPreset } from "../lib/types";

type WorkflowPresetDraft = {
  name: string;
  summary: string;
  badgesText: string;
  profile: string;
  context: number;
  outputTokens: number;
  thinkingMode: string;
  temperature: number;
  topK: number;
  topP: number;
  minP: number;
  repeatPenalty: number;
  repeatLastN: number;
  presencePenalty: number;
  frequencyPenalty: number;
  seed: number;
  webSearchMode: string;
  webSearchProvider: string;
  searchProvider: string;
  searchSuggestedAction: "search" | "answer" | "compare";
  searchQueryHint: string;
  knowledgeMode: "documents-only" | "documents+web" | "web-only";
  knowledgeQueryHint: string;
  benchmarkBatteryId: string;
  benchmarkLaunchTarget: "selected" | "battery";
  benchmarkRunLabel: string;
};

const PROFILE_OPTIONS = [
  { value: "balanced", label: "balansirano" },
  { value: "speed", label: "brzina" },
  { value: "video", label: "video" },
];

const THINKING_MODE_OPTIONS = [
  { value: "no-thinking", label: "bez razmišljanja" },
  { value: "low", label: "nisko" },
  { value: "mid", label: "srednje" },
  { value: "high", label: "visoko" },
  { value: "extra-high", label: "vrlo visoko" },
];

const WEB_SEARCH_MODE_OPTIONS = [
  { value: "off", label: "Isključeno" },
  { value: "on-demand", label: "Na zahtev" },
  { value: "always", label: "Uvek" },
];

const SEARCH_ACTION_OPTIONS = [
  { value: "search", label: "Prikaži izvore" },
  { value: "answer", label: "Odgovori lokalno" },
  { value: "compare", label: "Uporedi provajdere" },
];

const KNOWLEDGE_MODE_OPTIONS = [
  { value: "documents-only", label: "Samo dokumenti" },
  { value: "documents+web", label: "Dokumenti + veb" },
  { value: "web-only", label: "Samo veb" },
];

const BENCHMARK_TARGET_OPTIONS = [
  { value: "selected", label: "Pokreni izabrani scenario" },
  { value: "battery", label: "Pokreni celu sekvencu baterije" },
];

const WORKFLOW_PRESET_SUMMARY_MAX_LENGTH = 220;
const WORKFLOW_PRESET_BADGE_MAX_COUNT = 6;
const WORKFLOW_PRESET_BADGE_MAX_LENGTH = 20;

function formatInferenceMetric(value: number, fractionDigits = 2): string {
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(fractionDigits).replace(/\.?0+$/, "");
}

function buildWorkflowInferenceSummary(preset: WorkflowPreset) {
  const temperature = preset.settingsPatch.temperature ?? 0.8;
  const topK = preset.settingsPatch.topK ?? 40;
  const topP = preset.settingsPatch.topP ?? 0.95;
  const seed = preset.settingsPatch.seed ?? -1;

  return [
    `temp ${formatInferenceMetric(temperature)}`,
    `top-k ${formatInferenceMetric(topK, 0)}`,
    `top-p ${formatInferenceMetric(topP)}`,
    `seed ${formatInferenceMetric(seed, 0)}`,
  ].join(" | ");
}

function createDraftFromPreset(preset: WorkflowPreset): WorkflowPresetDraft {
  return {
    name: preset.name || preset.label,
    summary: preset.summary,
    badgesText: preset.badges.join(", "),
    profile: preset.settingsPatch.profile ?? "balanced",
    context: preset.settingsPatch.context ?? 262144,
    outputTokens: preset.settingsPatch.outputTokens ?? 8192,
    thinkingMode: preset.settingsPatch.thinkingMode ?? "mid",
    temperature: preset.settingsPatch.temperature ?? 0.8,
    topK: preset.settingsPatch.topK ?? 40,
    topP: preset.settingsPatch.topP ?? 0.95,
    minP: preset.settingsPatch.minP ?? 0.05,
    repeatPenalty: preset.settingsPatch.repeatPenalty ?? 1,
    repeatLastN: preset.settingsPatch.repeatLastN ?? 64,
    presencePenalty: preset.settingsPatch.presencePenalty ?? 0,
    frequencyPenalty: preset.settingsPatch.frequencyPenalty ?? 0,
    seed: preset.settingsPatch.seed ?? -1,
    webSearchMode: preset.settingsPatch.webSearchMode ?? "off",
    webSearchProvider: preset.settingsPatch.webSearchProvider ?? "searxng",
    searchProvider: preset.searchDefaults.provider,
    searchSuggestedAction: preset.searchDefaults.suggestedAction,
    searchQueryHint: preset.searchDefaults.queryHint,
    knowledgeMode: preset.knowledgeDefaults.mode,
    knowledgeQueryHint: preset.knowledgeDefaults.queryHint,
    benchmarkBatteryId: preset.benchmarkDefaults.batteryId,
    benchmarkLaunchTarget: preset.benchmarkDefaults.launchTarget,
    benchmarkRunLabel: preset.benchmarkDefaults.runLabel,
  };
}

function cloneDraft(draft: WorkflowPresetDraft): WorkflowPresetDraft {
  return { ...draft };
}

function areDraftsEqual(left: WorkflowPresetDraft | null, right: WorkflowPresetDraft | null): boolean {
  if (!left || !right) {
    return false;
  }
  return JSON.stringify(left) === JSON.stringify(right);
}

function buildClonedPresetName(name: string, presets: WorkflowPreset[]): string {
  const existingNames = new Set(
    presets.map((preset) => preset.name.trim().toLowerCase()).filter(Boolean),
  );
  const baseName = `Kopija - ${name.trim() || "Novi preset"}`;
  if (!existingNames.has(baseName.toLowerCase())) {
    return baseName;
  }
  let suffix = 2;
  while (existingNames.has(`${baseName} ${suffix}`.toLowerCase())) {
    suffix += 1;
  }
  return `${baseName} ${suffix}`;
}

function buildClonedDraft(
  draft: WorkflowPresetDraft,
  presets: WorkflowPreset[],
): WorkflowPresetDraft {
  return {
    ...cloneDraft(draft),
    name: buildClonedPresetName(draft.name, presets),
  };
}

function validateWorkflowPresetDraft(
  draft: WorkflowPresetDraft | null,
  presets: WorkflowPreset[],
  updatePresetId: string,
): string[] {
  if (!draft) {
    return [];
  }
  const errors: string[] = [];
  const normalizedName = draft.name.trim().toLowerCase();
  if (!normalizedName) {
    errors.push("Ime preseta je obavezno.");
  }
  const duplicate = presets.find((preset) => {
    if (updatePresetId && preset.id === updatePresetId) {
      return false;
    }
    return preset.name.trim().toLowerCase() === normalizedName;
  });
  if (normalizedName && duplicate) {
    errors.push("Preset sa tim imenom već postoji.");
  }
  if (draft.summary.trim().length > WORKFLOW_PRESET_SUMMARY_MAX_LENGTH) {
    errors.push(
      `Kratak opis može da ima najviše ${WORKFLOW_PRESET_SUMMARY_MAX_LENGTH} karaktera.`,
    );
  }
  const badges = draft.badgesText
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (badges.length > WORKFLOW_PRESET_BADGE_MAX_COUNT) {
    errors.push(`Možeš da koristiš najviše ${WORKFLOW_PRESET_BADGE_MAX_COUNT} badge oznaka.`);
  }
  if (badges.some((badge) => badge.length > WORKFLOW_PRESET_BADGE_MAX_LENGTH)) {
    errors.push(
      `Jedna badge oznaka može da ima najviše ${WORKFLOW_PRESET_BADGE_MAX_LENGTH} karaktera.`,
    );
  }
  return errors;
}

function buildWorkflowPresetPayload(
  draft: WorkflowPresetDraft,
  options?: { presetId?: string },
) {
  const badges = draft.badgesText
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return {
    presetId: options?.presetId,
    name: draft.name.trim(),
    summary: draft.summary.trim(),
    badges,
    settingsPatch: {
      profile: draft.profile,
      context: draft.context,
      outputTokens: draft.outputTokens,
      thinkingMode: draft.thinkingMode,
      temperature: draft.temperature,
      topK: draft.topK,
      topP: draft.topP,
      minP: draft.minP,
      repeatPenalty: draft.repeatPenalty,
      repeatLastN: draft.repeatLastN,
      presencePenalty: draft.presencePenalty,
      frequencyPenalty: draft.frequencyPenalty,
      seed: draft.seed,
      webSearchMode: draft.webSearchMode,
      webSearchProvider: draft.webSearchProvider,
    },
    searchDefaults: {
      provider: draft.searchProvider,
      suggestedAction: draft.searchSuggestedAction,
      queryHint: draft.searchQueryHint.trim(),
    },
    knowledgeDefaults: {
      mode: draft.knowledgeMode,
      queryHint: draft.knowledgeQueryHint.trim(),
    },
    benchmarkDefaults: {
      batteryId: draft.benchmarkBatteryId.trim() || "default",
      launchTarget: draft.benchmarkLaunchTarget,
      runLabel: draft.benchmarkRunLabel.trim(),
    },
  };
}

function chooseEditorPreset(
  payload: SettingsPayload,
  options?: { preferredPresetId?: string; preferredPresetName?: string },
): WorkflowPreset | null {
  const presets = resolveWorkflowPresets(payload);
  if (!presets.length) {
    return null;
  }
  if (options?.preferredPresetId) {
    const matchedById = presets.find((preset) => preset.id === options.preferredPresetId);
    if (matchedById) {
      return matchedById;
    }
  }
  if (options?.preferredPresetName) {
    const normalizedName = options.preferredPresetName.trim().toLowerCase();
    const matchedByName = presets.find(
      (preset) =>
        preset.name.trim().toLowerCase() === normalizedName ||
        preset.label.trim().toLowerCase() === normalizedName,
    );
    if (matchedByName) {
      return matchedByName;
    }
  }
  return resolveSelectedWorkflowPreset(payload) ?? presets[0] ?? null;
}

export function WorkflowsPage({
  onOpenSearch,
  onOpenKnowledge,
  onOpenBenchmark,
}: {
  onOpenSearch: () => void;
  onOpenKnowledge: () => void;
  onOpenBenchmark: () => void;
}) {
  const [settingsPayload, setSettingsPayload] = useState<SettingsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyPresetId, setBusyPresetId] = useState("");
  const [editorPresetId, setEditorPresetId] = useState("");
  const [editorUpdatePresetId, setEditorUpdatePresetId] = useState("");
  const [editorBaseline, setEditorBaseline] = useState<WorkflowPresetDraft | null>(null);
  const [editorDraft, setEditorDraft] = useState<WorkflowPresetDraft | null>(null);
  const [editorBusy, setEditorBusy] = useState<
    "" | "save-new" | "save-update" | "delete" | "reset"
  >("");
  const [result, setResult] = useState<ActionResult | null>(null);

  async function load(options?: {
    preferredPresetId?: string;
    preferredPresetName?: string;
  }) {
    try {
      const payload = await fetchSettings();
      const chosenPreset = chooseEditorPreset(payload, options);

      setSettingsPayload(payload);
      setError(null);

      if (chosenPreset) {
        const nextBaseline = createDraftFromPreset(chosenPreset);
        setEditorPresetId(chosenPreset.id);
        setEditorUpdatePresetId(chosenPreset.kind === "user" ? chosenPreset.id : "");
        setEditorBaseline(nextBaseline);
        setEditorDraft(cloneDraft(nextBaseline));
      }
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Radni prostor za radne tokove nije mogao da se učita.",
      );
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const presets = useMemo(
    () => resolveWorkflowPresets(settingsPayload),
    [settingsPayload],
  );
  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === editorPresetId) ?? null,
    [editorPresetId, presets],
  );
  const editorIsDirty = useMemo(
    () => !areDraftsEqual(editorDraft, editorBaseline),
    [editorBaseline, editorDraft],
  );
  const editorValidationErrors = useMemo(
    () => validateWorkflowPresetDraft(editorDraft, presets, editorUpdatePresetId),
    [editorDraft, editorUpdatePresetId, presets],
  );
  const searchProviderOptions = useMemo(
    () =>
      settingsPayload?.availableSearchProviders.map((provider) => ({
        value: provider.id,
        label: provider.label,
      })) ?? [],
    [settingsPayload],
  );

  const inlineError = error;

  if (!settingsPayload || !editorDraft) {
    return (
      <PageDataStateCard
        error={inlineError}
        loadingText="Učitavam radni prostor za radne tokove..."
        onRetry={() => {
          setError(null);
          void load();
        }}
      />
    );
  }

  if (!settingsPayload || !editorDraft) {
    return (
      <section className="status-card wide-card runtimepilot-faceplate-module">
        Učitavam radni prostor za radne tokove...
      </section>
    );
  }

  const selectedWorkflowPresetId =
    settingsPayload.selectedWorkflowPresetId || settingsPayload.workflowPresetId;
  const isEditingUserPreset =
    selectedPreset?.kind === "user" && editorUpdatePresetId === selectedPreset.id;

  return (
    <>
      {inlineError ? <div className="error-panel wide-card">{inlineError}</div> : null}
      <PageFlowCard
        title="Tok radnih tokova"
        summary="Ova strana je najjasnija kada je koristiš redom: prvo izaberi preset, zatim ga učitaj u editor, pa ga aktiviraj ili sačuvaj kao svoju varijantu."
        steps={[
          {
            title: "Izaberi preset",
            detail: "Katalog služi da odmah vidiš šta već postoji i koji preset je trenutno aktivan.",
          },
          {
            title: "Učitaj u editor",
            detail: "Editor je mesto za kloniranje, doterivanje i razumevanje preseta bez lutanja kroz više strana.",
          },
          {
            title: "Aktiviraj ili sačuvaj",
            detail: "Aktiviraj kada hoćeš da preset vodi RuntimePilot odmah, ili ga sačuvaj kao novu korisničku varijantu.",
          },
        ]}
        actions={
          <>
            <button type="button" className="secondary-button" onClick={onOpenSearch}>
              Otvori pretragu
            </button>
            <button type="button" className="secondary-button" onClick={onOpenKnowledge}>
              Otvori znanje
            </button>
            <button type="button" className="secondary-button" onClick={onOpenBenchmark}>
              Otvori benchmark
            </button>
          </>
        }
      />
      <section className="status-card wide-card runtimepilot-faceplate-module">
        <span className="status-label">Radni tokovi</span>
        <strong className="status-value">Radni prostor za radne tokove</strong>
        <p className="helper-text">
          Ovde vidiš ugrađene presete radnog toka, a svaki preset radnog toka možeš da aktiviraš za ceo RuntimePilot i da
          napraviš svoje korisničke varijante bez ručnog lutanja kroz Podešavanja.
        </p>
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module">
        <span className="status-label">Katalog preseta</span>
        <div className="workflow-preset-grid">
          {presets.map((preset) => {
            const isActive = selectedWorkflowPresetId === preset.id;
            const isLoadedInEditor = editorPresetId === preset.id;
            return (
              <article
                className={`theme-option-card ${isActive ? "theme-option-card-active" : ""}`}
                key={preset.id}
              >
                <strong className="theme-option-name">{preset.label}</strong>
                <p className="theme-option-copy">{preset.summary}</p>
                <div className="summary-metrics">
                  <span>{preset.kind === "user" ? "korisnički preset" : "ugrađeni preset"}</span>
                  {preset.badges.map((badge) => (
                    <span key={`${preset.id}-${badge}`}>{badge}</span>
                  ))}
                </div>
                <p className="helper-text">
                  Pretraga: {preset.searchDefaults.provider} | Znanje:{" "}
                  {preset.knowledgeDefaults.mode} | Benchmark:{" "}
                  {preset.benchmarkDefaults.runLabel}
                </p>
                <p className="helper-text">
                  Sažetak inferencije: {buildWorkflowInferenceSummary(preset)}
                </p>
                <div className="inline-actions">
                  <button
                    type="button"
                    className="action-button"
                    disabled={busyPresetId === preset.id}
                    onClick={async () => {
                      setBusyPresetId(preset.id);
                      try {
                        const payload: SettingsPayload = {
                          ...settingsPayload,
                          ...preset.settingsPatch,
                          workflowPresetId: preset.id,
                          selectedWorkflowPresetId: preset.id,
                        };
                        const action = await applySettings(payload);
                        setResult(action);
                        await load({ preferredPresetId: preset.id });
                      } catch (reason: unknown) {
                        setError(
                          reason instanceof Error
                            ? reason.message
                            : "Aktivacija preseta radnog toka nije uspela.",
                        );
                      } finally {
                        setBusyPresetId("");
                      }
                    }}
                  >
                    Aktiviraj preset
                  </button>
                  <button
                    type="button"
                    className={isLoadedInEditor ? "secondary-button" : "secondary-button"}
                    onClick={() => {
                      const nextBaseline = createDraftFromPreset(preset);
                      setEditorPresetId(preset.id);
                      setEditorUpdatePresetId(preset.kind === "user" ? preset.id : "");
                      setEditorBaseline(nextBaseline);
                      setEditorDraft(cloneDraft(nextBaseline));
                      setResult({
                        status: "ok",
                        action: "load-workflow-preset-editor",
                        summary: `Preset ${preset.label} je učitan u editor.`,
                        details: { returncode: 0, stdout: "", stderr: "" },
                      });
                    }}
                  >
                    Učitaj u editor
                  </button>
                  <button type="button" className="secondary-button" onClick={onOpenSearch}>
                    Otvori pretragu
                  </button>
                  <button type="button" className="secondary-button" onClick={onOpenKnowledge}>
                    Otvori znanje
                  </button>
                  <button type="button" className="secondary-button" onClick={onOpenBenchmark}>
                    Otvori benchmark
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module">
        <span className="status-label">Editor preseta radnog toka</span>
        <strong className="status-value">{editorDraft.name || "Novi korisnički preset"}</strong>
        <div className="summary-metrics">
          <span>
            Izvor:{" "}
            {selectedPreset
              ? `${selectedPreset.label} (${selectedPreset.kind === "user" ? "korisnički preset" : "ugrađeni preset"})`
              : "nema učitanog izvora"}
          </span>
          <span>
            {editorUpdatePresetId
              ? "Sačuvavanje menja postojeći korisnički preset."
              : "Sačuvavanje pravi novi korisnički preset."}
          </span>
          <span>{editorIsDirty ? "Nesačuvane izmene" : "Editor je usklađen."}</span>
        </div>
        <p className="helper-text">
          Ugrađeni preset možeš da iskoristiš kao osnovu i da ga sačuvaš kao novi korisnički
          preset. Korisnički preset možeš da menjaš, kloniraš i brišeš.
        </p>
        {editorIsDirty ? (
          <div className="warning-badge">Nesačuvane izmene čekaju čuvanje ili poništavanje.</div>
        ) : null}

        <div className="workflow-editor-grid">
          <article className="settings-field">
            <span className="settings-field-label">Ime preseta</span>
            <input
              type="text"
              value={editorDraft.name}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  name: event.target.value,
                })
              }
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Kratak opis</span>
            <textarea
              value={editorDraft.summary}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  summary: event.target.value,
                })
              }
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Oznake</span>
            <input
              type="text"
              value={editorDraft.badgesText}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  badgesText: event.target.value,
                })
              }
            />
            <p className="helper-text">
              Upiši oznake razdvojene zarezima, na primer: kod, veb, prilagođeno. Najviše{" "}
              {WORKFLOW_PRESET_BADGE_MAX_COUNT} oznaka, do {WORKFLOW_PRESET_BADGE_MAX_LENGTH} karaktera po oznaci.
            </p>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Profil</span>
            <CustomSelect
              value={editorDraft.profile}
              options={PROFILE_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  profile: value,
                })
              }
              ariaLabel="Izaberi profil preseta radnog toka"
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Kontekst</span>
            <input
              type="number"
              value={editorDraft.context}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  context: Number(event.target.value || 0),
                })
              }
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Izlazni tokeni</span>
            <input
              type="number"
              value={editorDraft.outputTokens}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  outputTokens: Number(event.target.value || 0),
                })
              }
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Režim razmišljanja</span>
            <CustomSelect
              value={editorDraft.thinkingMode}
              options={THINKING_MODE_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  thinkingMode: value,
                })
              }
              ariaLabel="Izaberi režim razmišljanja preseta radnog toka"
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Inferencija i uzorkovanje</span>
            <p className="helper-text">
              Ove vrednosti se čuvaju unutar preseta radnog toka i mogu da preuzmu runtime komande,
              lokalni model i `OpenCode local-lacc` fallback kada preset aktiviraš kroz RuntimePilot.
            </p>
            <div className="workflow-editor-grid">
              <article className="settings-field">
                <span className="settings-field-label">Temperature</span>
                <input
                  type="number"
                  step="0.05"
                  value={editorDraft.temperature}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      temperature: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
              <article className="settings-field">
                <span className="settings-field-label">Top-k</span>
                <input
                  type="number"
                  step="1"
                  value={editorDraft.topK}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      topK: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
              <article className="settings-field">
                <span className="settings-field-label">Top-p</span>
                <input
                  type="number"
                  step="0.01"
                  value={editorDraft.topP}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      topP: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
              <article className="settings-field">
                <span className="settings-field-label">Min-p</span>
                <input
                  type="number"
                  step="0.01"
                  value={editorDraft.minP}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      minP: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
              <article className="settings-field">
                <span className="settings-field-label">Repeat penalty</span>
                <input
                  type="number"
                  step="0.05"
                  value={editorDraft.repeatPenalty}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      repeatPenalty: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
              <article className="settings-field">
                <span className="settings-field-label">Repeat last N</span>
                <input
                  type="number"
                  step="1"
                  value={editorDraft.repeatLastN}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      repeatLastN: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
              <article className="settings-field">
                <span className="settings-field-label">Presence penalty</span>
                <input
                  type="number"
                  step="0.05"
                  value={editorDraft.presencePenalty}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      presencePenalty: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
              <article className="settings-field">
                <span className="settings-field-label">Frequency penalty</span>
                <input
                  type="number"
                  step="0.05"
                  value={editorDraft.frequencyPenalty}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      frequencyPenalty: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
              <article className="settings-field">
                <span className="settings-field-label">Seed</span>
                <input
                  type="number"
                  step="1"
                  value={editorDraft.seed}
                  onChange={(event) =>
                    setEditorDraft({
                      ...editorDraft,
                      seed: Number(event.target.value || 0),
                    })
                  }
                />
              </article>
            </div>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Veb režim pretrage</span>
            <CustomSelect
              value={editorDraft.webSearchMode}
              options={WEB_SEARCH_MODE_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  webSearchMode: value,
                })
              }
              ariaLabel="Izaberi veb režim pretrage preseta radnog toka"
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Provider pretrage u podešavanjima</span>
            <CustomSelect
              value={editorDraft.webSearchProvider}
              options={searchProviderOptions}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  webSearchProvider: value,
                  searchProvider: value,
                })
              }
              ariaLabel="Izaberi podrazumevani provajder preseta radnog toka"
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Provider pretrage</span>
            <CustomSelect
              value={editorDraft.searchProvider}
              options={searchProviderOptions}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  searchProvider: value,
                })
              }
              ariaLabel="Izaberi provajder za tab Pretraga"
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Akcija pretrage</span>
            <CustomSelect
              value={editorDraft.searchSuggestedAction}
              options={SEARCH_ACTION_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  searchSuggestedAction: value as WorkflowPresetDraft["searchSuggestedAction"],
                })
              }
              ariaLabel="Izaberi podrazumevanu akciju pretrage"
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Nagoveštaj upita za pretragu</span>
            <textarea
              value={editorDraft.searchQueryHint}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  searchQueryHint: event.target.value,
                })
              }
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Režim znanja</span>
            <CustomSelect
              value={editorDraft.knowledgeMode}
              options={KNOWLEDGE_MODE_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  knowledgeMode: value as WorkflowPresetDraft["knowledgeMode"],
                })
              }
              ariaLabel="Izaberi režim znanja"
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Nagoveštaj upita za znanje</span>
            <textarea
              value={editorDraft.knowledgeQueryHint}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  knowledgeQueryHint: event.target.value,
                })
              }
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">ID benchmark baterije</span>
            <input
              type="text"
              value={editorDraft.benchmarkBatteryId}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  benchmarkBatteryId: event.target.value,
                })
              }
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Cilj pokretanja benchmark-a</span>
            <CustomSelect
              value={editorDraft.benchmarkLaunchTarget}
              options={BENCHMARK_TARGET_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  benchmarkLaunchTarget: value as WorkflowPresetDraft["benchmarkLaunchTarget"],
                })
              }
              ariaLabel="Izaberi cilj pokretanja benchmark-a"
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Oznaka benchmark pokretanja</span>
            <input
              type="text"
              value={editorDraft.benchmarkRunLabel}
              onChange={(event) =>
                setEditorDraft({
                  ...editorDraft,
                  benchmarkRunLabel: event.target.value,
                })
              }
            />
          </article>
        </div>

        <div className="workflow-editor-feedback">
          <p className="helper-text">
            Kratak opis: {editorDraft.summary.trim().length} / {WORKFLOW_PRESET_SUMMARY_MAX_LENGTH}
          </p>
          <p className="helper-text">
            Poništi izmene u editoru vraća editor na poslednju učitanu verziju preseta ili na
            početnu kloniranu kopiju.
          </p>
          {editorValidationErrors.length ? (
            <div className="error-panel">
              {editorValidationErrors.map((item) => (
                <div key={item}>{item}</div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="inline-actions workflow-editor-actions">
          <button
            type="button"
            className="secondary-button"
            disabled={!editorBaseline || !editorIsDirty || editorBusy !== ""}
            onClick={() => {
              if (!editorBaseline) {
                return;
              }
              setEditorBusy("reset");
              setEditorDraft(cloneDraft(editorBaseline));
              setResult({
                status: "ok",
                action: "reset-workflow-preset-editor",
                summary: "Editor preseta radnog toka je vraćen na poslednju učitanu verziju.",
                details: { returncode: 0, stdout: "", stderr: "" },
              });
              setEditorBusy("");
            }}
          >
            Poništi izmene u editoru
          </button>

          <button
            type="button"
            className="secondary-button"
            disabled={editorBusy !== ""}
            onClick={() => {
              const clonedDraft = buildClonedDraft(editorDraft, presets);
              setEditorUpdatePresetId("");
              setEditorBaseline(cloneDraft(clonedDraft));
              setEditorDraft(cloneDraft(clonedDraft));
              setResult({
                status: "ok",
                action: "clone-workflow-preset-editor",
                summary: "Napravljen je klon preseta u editoru. Sačuvaj ga kao novi preset kada budeš zadovoljan.",
                details: { returncode: 0, stdout: "", stderr: "" },
              });
            }}
          >
            Kloniraj preset
          </button>

          <button
            type="button"
            className="action-button"
            disabled={editorBusy !== "" || editorValidationErrors.length > 0}
            onClick={async () => {
              setEditorBusy("save-new");
              try {
                const action = await saveWorkflowPreset(buildWorkflowPresetPayload(editorDraft));
                setResult(action);
                await load({ preferredPresetName: editorDraft.name });
              } catch (reason: unknown) {
                setError(
                  reason instanceof Error
                    ? reason.message
                    : "Čuvanje novog preseta radnog toka nije uspelo.",
                );
              } finally {
                setEditorBusy("");
              }
            }}
          >
            Sačuvaj kao novi preset
          </button>

          <button
            type="button"
            className="action-button"
            disabled={!isEditingUserPreset || editorBusy !== "" || editorValidationErrors.length > 0}
            onClick={async () => {
              if (!selectedPreset) {
                return;
              }
              setEditorBusy("save-update");
              try {
                const action = await saveWorkflowPreset(
                  buildWorkflowPresetPayload(editorDraft, { presetId: selectedPreset.id }),
                );
                setResult(action);
                await load({ preferredPresetId: selectedPreset.id });
              } catch (reason: unknown) {
                setError(
                  reason instanceof Error
                    ? reason.message
                    : "Ažuriranje preseta radnog toka nije uspelo.",
                );
              } finally {
                setEditorBusy("");
              }
            }}
          >
            Sačuvaj izmene preseta
          </button>

          <button
            type="button"
            className="danger-button"
            disabled={!isEditingUserPreset || editorBusy !== ""}
            onClick={async () => {
              if (!selectedPreset) {
                return;
              }
              setEditorBusy("delete");
              try {
                const action = await deleteWorkflowPreset(selectedPreset.id);
                setResult(action);
                await load();
              } catch (reason: unknown) {
                setError(
                  reason instanceof Error
                    ? reason.message
                    : "Brisanje korisničkog preseta radnog toka nije uspelo.",
                );
              } finally {
                setEditorBusy("");
              }
            }}
          >
            Obriši korisnički preset
          </button>
        </div>
      </section>

      <ActionResultPanel result={result} />
    </>
  );
}
