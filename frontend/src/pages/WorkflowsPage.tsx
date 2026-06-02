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
  { value: "balanced", label: "balanced" },
  { value: "speed", label: "speed" },
  { value: "video", label: "video" },
];

const THINKING_MODE_OPTIONS = [
  { value: "no-thinking", label: "no-thinking" },
  { value: "low", label: "low" },
  { value: "mid", label: "mid" },
  { value: "high", label: "high" },
  { value: "extra-high", label: "extra-high" },
];

const WEB_SEARCH_MODE_OPTIONS = [
  { value: "off", label: "Off" },
  { value: "on-demand", label: "On-demand" },
  { value: "always", label: "Always" },
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
  { value: "selected", label: "Pokreni selected scenario" },
  { value: "battery", label: "Pokreni celu battery sekvencu" },
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
        loadingText="U\u010ditavam radni prostor za radne tokove..."
        onRetry={() => {
          setError(null);
          void load();
        }}
      />
    );
  }

  if (!settingsPayload || !editorDraft) {
    return (
      <section className="status-card wide-card">
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
        title="Workflows tok"
        summary="Ova strana je najjasnija kada je koristi\u0161 redom: prvo izaberi preset, zatim ga u\u010ditaj u editor, pa ga aktiviraj ili sa\u010duvaj kao svoju varijantu."
        steps={[
          {
            title: "Izaberi preset",
            detail: "Katalog slu\u017ei da odmah vidi\u0161 \u0161ta ve\u0107 postoji i koji preset je trenutno aktivan.",
          },
          {
            title: "U\u010ditaj u editor",
            detail: "Editor je mesto za kloniranje, doterivanje i razumevanje preseta bez lutanja kroz vi\u0161e strana.",
          },
          {
            title: "Aktiviraj ili sa\u010duvaj",
            detail: "Aktiviraj kada ho\u0107e\u0161 da preset vodi RuntimePilot odmah, ili ga sa\u010duvaj kao novu korisni\u010dku varijantu.",
          },
        ]}
        actions={
          <>
            <button type="button" className="secondary-button" onClick={onOpenSearch}>
              Otvori Search
            </button>
            <button type="button" className="secondary-button" onClick={onOpenKnowledge}>
              Otvori Knowledge
            </button>
            <button type="button" className="secondary-button" onClick={onOpenBenchmark}>
              Otvori Benchmark
            </button>
          </>
        }
      />
      <section className="status-card wide-card">
        <span className="status-label">Radni tokovi</span>
        <strong className="status-value">Radni prostor za radne tokove</strong>
        <p className="helper-text">
          Ovde vidiš ugrađene workflow preset-e, možeš da ih aktiviraš za ceo RuntimePilot i da
          napraviš svoje korisničke varijante bez ručnog lutanja kroz Podešavanja.
        </p>
      </section>

      <section className="status-card wide-card">
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
                  Inference sažetak: {buildWorkflowInferenceSummary(preset)}
                </p>
                <div className="inline-actions">
                  <button
                    type="button"
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
                            : "Aktivacija workflow preseta nije uspela.",
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
                    className={isLoadedInEditor ? "secondary-button" : undefined}
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
                  <button type="button" onClick={onOpenSearch}>
                    Otvori pretragu
                  </button>
                  <button type="button" onClick={onOpenKnowledge}>
                    Otvori znanje
                  </button>
                  <button type="button" onClick={onOpenBenchmark}>
                    Otvori benchmark
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Editor workflow preseta</span>
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
            <span className="settings-field-label">Badge oznake</span>
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
              Upiši oznake razdvojene zarezima, na primer: code, web, custom. Najviše{" "}
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
              ariaLabel="Izaberi profil workflow preseta"
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Context</span>
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
            <span className="settings-field-label">Output tokens</span>
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
            <span className="settings-field-label">Thinking mode</span>
            <CustomSelect
              value={editorDraft.thinkingMode}
              options={THINKING_MODE_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  thinkingMode: value,
                })
              }
              ariaLabel="Izaberi thinking režim workflow preseta"
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Inference i sampling</span>
            <p className="helper-text">
              Ove vrednosti se čuvaju unutar workflow preseta i mogu da preuzmu runtime komande,
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
            <span className="settings-field-label">Web search mode</span>
            <CustomSelect
              value={editorDraft.webSearchMode}
              options={WEB_SEARCH_MODE_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  webSearchMode: value,
                })
              }
              ariaLabel="Izaberi web search mode workflow preseta"
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
              ariaLabel="Izaberi podrazumevani provider workflow preseta"
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
              ariaLabel="Izaberi provider za Search tab"
            />
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Search akcija</span>
            <CustomSelect
              value={editorDraft.searchSuggestedAction}
              options={SEARCH_ACTION_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  searchSuggestedAction: value as WorkflowPresetDraft["searchSuggestedAction"],
                })
              }
              ariaLabel="Izaberi podrazumevanu Search akciju"
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Hint upita za pretragu</span>
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
            <span className="settings-field-label">Knowledge režim</span>
            <CustomSelect
              value={editorDraft.knowledgeMode}
              options={KNOWLEDGE_MODE_OPTIONS}
              onChange={(value) =>
                setEditorDraft({
                  ...editorDraft,
                  knowledgeMode: value as WorkflowPresetDraft["knowledgeMode"],
                })
              }
              ariaLabel="Izaberi Knowledge režim"
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Knowledge query hint</span>
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
              ariaLabel="Izaberi benchmark launch target"
            />
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Oznaka benchmark run-a</span>
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
                summary: "Editor workflow preseta je vraćen na poslednju učitanu verziju.",
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
                    : "Čuvanje novog workflow preseta nije uspelo.",
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
                    : "Ažuriranje workflow preseta nije uspelo.",
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
                    : "Brisanje korisničkog workflow preseta nije uspelo.",
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
