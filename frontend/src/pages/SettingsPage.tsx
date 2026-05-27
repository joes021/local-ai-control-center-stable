import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import {
  applySettings,
  bootstrapManagedSearchProvider,
  deleteSettingsProfile,
  deleteTurboQuantPreset,
  fetchSearchProviderStatus,
  fetchSettings,
  fetchTurboQuantSchema,
  pickWorkingDirectory,
  saveSettingsProfile,
  saveTurboQuantConfig,
  saveTurboQuantPreset,
} from "../lib/api";
import { applyTheme } from "../lib/theme";
import { resolveSelectedWorkflowPreset, resolveWorkflowPresets } from "../lib/workflowPresets";
import type {
  ActionResult,
  SearchProviderStatusPayload,
  SettingsPayload,
  SettingsProfilePreset,
  SettingsProfileValues,
  ThemeOption,
  TurboQuantConfig,
  TurboQuantPreset,
  TurboQuantSchemaPayload,
  WorkflowPreset,
} from "../lib/types";

const TURBOQUANT_DRAFT_STORAGE_KEY = "local-ai-control-center:turboquant-draft";
const FALLBACK_THEME_OPTIONS: ThemeOption[] = [
  {
    id: "dark-chocolate",
    label: "Dark Chocolate",
    summary: "Topla tamna podloga sa bronzanim i cijan akcentima.",
    accent: "#f2b84b",
    textColor: "#f7dfb0",
  },
  {
    id: "light",
    label: "Light",
    summary: "Svetla radna tema sa toplim zlatnim akcentom.",
    accent: "#d59b2f",
    textColor: "#7f5a12",
  },
  {
    id: "dark",
    label: "Dark",
    summary: "Neutralna tamna tema sa hladnijim plavo-sivim tonom.",
    accent: "#6f8fd8",
    textColor: "#bfd4ff",
  },
  {
    id: "neon-green",
    label: "Neon Green",
    summary: "Visokokontrastna terminalsko-neonska tema za jak signal.",
    accent: "#58ff8f",
    textColor: "#c8ffd9",
  },
  {
    id: "marine-blue",
    label: "Marine Blue",
    summary: "Duboki plavi komandni most sa morskim cijan akcentom.",
    accent: "#39b7ff",
    textColor: "#cbe8ff",
  },
];
const TOKEN_STEP_OPTIONS = [
  { value: "1024", label: "1024" },
  { value: "2048", label: "2048" },
  { value: "4096", label: "4096" },
  { value: "8192", label: "8192" },
  { value: "16384", label: "16384" },
  { value: "32768", label: "32768" },
  { value: "65536", label: "65536" },
  { value: "131072", label: "131072" },
  { value: "262144", label: "262144" },
] as const;
const SETTINGS_PROFILE_COMPARE_KEYS: Array<keyof SettingsProfileValues> = [
  "profile",
  "context",
  "outputTokens",
  "workingDirectory",
  "thinkingMode",
  "buildSteps",
  "planSteps",
  "generalSteps",
  "exploreSteps",
  "accessMode",
];

function applyPresetToConfig(preset: TurboQuantPreset): TurboQuantConfig {
  return { ...preset.settings };
}

function readDraft<T>(key: string): Partial<T> | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<T>;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function writeDraft<T>(key: string, value: T | null) {
  if (typeof window === "undefined") {
    return;
  }
  if (!value) {
    window.localStorage.removeItem(key);
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}

function clearDraft(key: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(key);
}

function resolveTokenChoice(value: number): string {
  const matched = TOKEN_STEP_OPTIONS.find((option) => Number(option.value) === value);
  return matched?.value ?? "custom";
}

function matchesSettingsProfile(
  settings: SettingsPayload,
  profile: SettingsProfilePreset,
): boolean {
  return SETTINGS_PROFILE_COMPARE_KEYS.every(
    (key) => settings[key] === profile.settings[key],
  );
}

function mergeSettingsProfile(
  settings: SettingsPayload,
  profile: SettingsProfilePreset,
): SettingsPayload {
  return {
    ...settings,
    ...profile.settings,
  };
}

function buildSettingsProfileDraft(settings: SettingsPayload): SettingsProfileValues {
  return {
    profile: settings.profile,
    context: settings.context,
    outputTokens: settings.outputTokens,
    workingDirectory: settings.workingDirectory,
    thinkingMode: settings.thinkingMode,
    buildSteps: settings.buildSteps,
    planSteps: settings.planSteps,
    generalSteps: settings.generalSteps,
    exploreSteps: settings.exploreSteps,
    accessMode: settings.accessMode,
  };
}

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsPayload | null>(null);
  const [schema, setSchema] = useState<TurboQuantSchemaPayload | null>(null);
  const [turboConfig, setTurboConfig] = useState<TurboQuantConfig | null>(null);
  const [settingsProfileName, setSettingsProfileName] = useState("");
  const [presetName, setPresetName] = useState("");
  const [presetDescription, setPresetDescription] = useState("");
  const [presetTargetPattern, setPresetTargetPattern] = useState("");
  const [presetNotes, setPresetNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [providerBusy, setProviderBusy] = useState<"" | "check" | "setup">("");

  async function reload() {
    const [settingsPayload, schemaPayload] = await Promise.all([
      fetchSettings(),
      fetchTurboQuantSchema(),
    ]);
    const turboDraft = readDraft<TurboQuantConfig>(TURBOQUANT_DRAFT_STORAGE_KEY);

    setSettings(settingsPayload);
    setSettingsDefaults(settingsPayload);
    setSchema(schemaPayload);
    setTurboConfig(turboDraft ? { ...schemaPayload.currentConfig, ...turboDraft } : schemaPayload.currentConfig);
  }

  useEffect(() => {
    reload().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    });
  }, []);

  useEffect(() => {
    if (turboConfig) {
      writeDraft(TURBOQUANT_DRAFT_STORAGE_KEY, turboConfig);
    }
  }, [turboConfig]);

  const settingsProfiles = useMemo(
    () => (settings ? [...settings.builtInSettingsProfiles, ...settings.userSettingsProfiles] : []),
    [settings],
  );
  const selectedSettingsProfileId = useMemo(() => {
    if (!settings) {
      return "custom";
    }
    const matched = settingsProfiles.find((profile) => matchesSettingsProfile(settings, profile));
    return matched?.id ?? "custom";
  }, [settings, settingsProfiles]);
  const selectedSettingsProfile = useMemo(
    () => settingsProfiles.find((profile) => profile.id === selectedSettingsProfileId) ?? null,
    [selectedSettingsProfileId, settingsProfiles],
  );
  const currentSearchProviderOption = useMemo(
    () =>
      settings
        ? settings.availableSearchProviders.find((provider) => provider.id === settings.webSearchProvider) ??
          null
        : null,
    [settings],
  );
  const availableThemeOptions = useMemo<ThemeOption[]>(
    () => (settings?.availableThemes?.length ? settings.availableThemes : FALLBACK_THEME_OPTIONS),
    [settings],
  );
  const currentThemeOption = useMemo<ThemeOption | null>(
    () => (settings ? availableThemeOptions.find((theme) => theme.id === settings.themeId) ?? null : null),
    [availableThemeOptions, settings],
  );
  const workflowPresets = useMemo<WorkflowPreset[]>(
    () => resolveWorkflowPresets(settings),
    [settings],
  );
  const currentWorkflowPreset = useMemo<WorkflowPreset | null>(
    () => resolveSelectedWorkflowPreset(settings),
    [settings],
  );

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!settings || !schema || !turboConfig) {
    return <div className="status-card wide-card">Učitavam settings...</div>;
  }

  const allTurboPresets = [...schema.builtInPresets, ...schema.userPresets];
  const profileOptions = [
    ...settings.builtInSettingsProfiles.map((profile) => ({
      value: profile.id,
      label: `${profile.name} (${profile.summary})`,
    })),
    ...settings.userSettingsProfiles.map((profile) => ({
      value: profile.id,
      label: `${profile.name} (${profile.summary})`,
    })),
    { value: "custom", label: "custom (trenutne vrednosti)" },
  ];
  const contextChoice = resolveTokenChoice(settings.context);
  const outputTokensChoice = resolveTokenChoice(settings.outputTokens);
  const activeSettings = settings;

  function applyWorkflowPreset(preset: WorkflowPreset) {
    setSettings({
      ...activeSettings,
      workflowPresetId: preset.id,
      profile: preset.settingsPatch.profile ?? activeSettings.profile,
      context: preset.settingsPatch.context ?? activeSettings.context,
      outputTokens: preset.settingsPatch.outputTokens ?? activeSettings.outputTokens,
      thinkingMode: preset.settingsPatch.thinkingMode ?? activeSettings.thinkingMode,
      webSearchMode: preset.settingsPatch.webSearchMode ?? activeSettings.webSearchMode,
      webSearchProvider: preset.settingsPatch.webSearchProvider ?? activeSettings.webSearchProvider,
    });
  }

  function updateProviderStatus(nextStatus: SearchProviderStatusPayload) {
    setSettings((current) =>
      current
        ? {
            ...current,
            searchProviderStatus: nextStatus,
          }
        : current,
    );
  }

  return (
    <div className="settings-page">
      <section className="status-card wide-card settings-cluster-card">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Profili i opseg</span>
            <strong className="status-value">
              Aktivni model: {settings.activeModelLabel || "nema"} ({settings.activeModelId || "--"})
            </strong>
          </div>
        </div>
        <div className="settings-cluster-grid settings-cluster-grid-profiles">
          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Opseg podešavanja</span>
            <p className="helper-text">
              Globalna podrazumevana važe za sve modele bez posebnog override-a. Override aktivnog modela važi
              samo za trenutno aktivni model.
            </p>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.settingsScope}
                options={[
                  { value: "global", label: "Globalna podrazumevana" },
                  { value: "model", label: "Override aktivnog modela" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    settingsScope: value,
                  })
                }
                ariaLabel="Izaberi settings scope"
              />
            </div>
            <p className="helper-text">
              {settings.modelOverrideExists
                ? "Za aktivni model već postoji poseban override."
                : "Za aktivni model trenutno nema posebnog override-a."}
            </p>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Profil</span>
            <div className="settings-control-block settings-control-block-wide">
              <CustomSelect
                value={selectedSettingsProfileId}
                options={profileOptions}
                onChange={(value) => {
                  if (value === "custom") {
                    setResult({
                      status: "ok",
                      action: "select-settings-profile",
                      summary: "Editor je ostao na custom vrednostima.",
                      details: { returncode: 0, stdout: "", stderr: "" },
                    });
                    return;
                  }
                  const profile = settingsProfiles.find((item) => item.id === value);
                  if (!profile) {
                    return;
                  }
                  setSettings(mergeSettingsProfile(settings, profile));
                  setResult({
                    status: "ok",
                    action: "load-settings-profile",
                    summary: `Profil ${profile.name} je učitan u editor.`,
                    details: { returncode: 0, stdout: "", stderr: "" },
                  });
                }}
                ariaLabel="Izaberi settings profil"
              />
            </div>
            <p className="helper-text">
              Profil puni editor za context, output tokens, access mode i OpenCode profil.
            </p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Workflow presets</span>
            <div className="settings-option-grid">
              {workflowPresets.map((preset) => {
                const active = currentWorkflowPreset?.id === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    className={`theme-option-card ${active ? "theme-option-card-active" : ""}`}
                    onClick={() => applyWorkflowPreset(preset)}
                  >
                    <span className="theme-option-name">{preset.label}</span>
                    <span className="theme-option-copy">{preset.summary}</span>
                    <span className="muted-line">{preset.badges.join(" | ")}</span>
                  </button>
                );
              })}
            </div>
            <p className="helper-text">
              Aktivni workflow preset: {currentWorkflowPreset?.label || "Research"}.
            </p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Sačuvaj trenutni custom profil</span>
            <div className="settings-action-row">
              <input
                className="settings-profile-name-input"
                placeholder="Ime novog profila"
                value={settingsProfileName}
                onChange={(event) => setSettingsProfileName(event.target.value)}
              />
              <button
                type="button"
                onClick={async () => {
                  const actionResult = await saveSettingsProfile({
                    name: settingsProfileName,
                    settings: buildSettingsProfileDraft(settings),
                  });
                  setResult(actionResult);
                  if (actionResult.status === "ok") {
                    setSettingsProfileName("");
                  }
                  await reload();
                }}
              >
                Sačuvaj profil
              </button>
              {selectedSettingsProfile && selectedSettingsProfile.kind === "user" ? (
                <button
                  type="button"
                  className="danger-button"
                  onClick={async () => {
                    const actionResult = await deleteSettingsProfile(selectedSettingsProfile.id);
                    setResult(actionResult);
                    await reload();
                  }}
                >
                  Obriši izabrani profil
                </button>
              ) : null}
            </div>
            <p className="helper-text">
              Trenutno aktivan izbor:{" "}
              {selectedSettingsProfile
                ? `${selectedSettingsProfile.name} (${selectedSettingsProfile.summary})`
                : "custom"}
            </p>
          </article>
        </div>
      </section>

      <section className="status-card wide-card settings-cluster-card">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Core settings</span>
          </div>
        </div>
        <div className="settings-cluster-grid settings-cluster-grid-core">
          <article className="settings-field">
            <span className="settings-field-label">Access mode</span>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.accessMode}
                options={[
                  { value: "local-only", label: "Local only" },
                  { value: "tailscale", label: "Tailscale" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    accessMode: value,
                  })
                }
                ariaLabel="Izaberi access mode"
              />
            </div>
            <p className="helper-text">Lokalno ili Tailscale izlaganje backend-a.</p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Color theme</span>
            <div className="settings-option-grid">
              {availableThemeOptions.map((theme) => {
                const active = settings.themeId === theme.id;
                return (
                  <button
                    key={theme.id}
                    type="button"
                    className={`theme-option-card ${active ? "theme-option-card-active" : ""}`}
                    onClick={() => {
                      setSettings({
                        ...settings,
                        themeId: theme.id,
                      });
                      applyTheme(theme.id);
                    }}
                  >
                    <span
                      className="theme-option-name"
                      style={{ color: theme.textColor, borderColor: `${theme.accent}55`, background: `${theme.accent}18` }}
                    >
                      {theme.label}
                    </span>
                    <span className="theme-option-copy">{theme.summary}</span>
                  </button>
                );
              })}
            </div>
            <p className="helper-text">
              Trenutna tema: {currentThemeOption?.label || "Dark Chocolate"}.
            </p>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">OpenCode profil</span>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.profile}
                options={[
                  { value: "speed", label: "speed" },
                  { value: "balanced", label: "balanced" },
                  { value: "video", label: "video" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    profile: value,
                  })
                }
                ariaLabel="Izaberi OpenCode profil"
              />
            </div>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Thinking mode</span>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.thinkingMode}
                options={[
                  { value: "no-thinking", label: "No thinking" },
                  { value: "low", label: "Low" },
                  { value: "mid", label: "Mid" },
                  { value: "high", label: "High" },
                  { value: "extra-high", label: "Extra high" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    thinkingMode: value,
                  })
                }
                ariaLabel="Izaberi thinking mode"
              />
            </div>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Context</span>
            <div className="settings-number-row">
              <CustomSelect
                value={contextChoice}
                options={[
                  ...TOKEN_STEP_OPTIONS.map((option) => ({
                    value: option.value,
                    label: option.label,
                  })),
                  { value: "custom", label: "custom" },
                ]}
                onChange={(value) => {
                  if (value === "custom") {
                    return;
                  }
                  setSettings({
                    ...settings,
                    context: Number(value),
                  });
                }}
                ariaLabel="Izaberi context veličinu"
              />
              {contextChoice === "custom" ? (
                <input
                  type="number"
                  value={settings.context}
                  aria-label="Unesi context veličinu"
                  onChange={(event) =>
                    setSettings({
                      ...settings,
                      context: Number(event.target.value || 0),
                    })
                  }
                />
              ) : null}
            </div>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Output tokens</span>
            <div className="settings-number-row">
              <CustomSelect
                value={outputTokensChoice}
                options={[
                  ...TOKEN_STEP_OPTIONS.map((option) => ({
                    value: option.value,
                    label: option.label,
                  })),
                  { value: "custom", label: "custom" },
                ]}
                onChange={(value) => {
                  if (value === "custom") {
                    return;
                  }
                  setSettings({
                    ...settings,
                    outputTokens: Number(value),
                  });
                }}
                ariaLabel="Izaberi output token limit"
              />
              {outputTokensChoice === "custom" ? (
                <input
                  type="number"
                  value={settings.outputTokens}
                  aria-label="Unesi output token limit"
                  onChange={(event) =>
                    setSettings({
                      ...settings,
                      outputTokens: Number(event.target.value || 0),
                    })
                  }
                />
              ) : null}
            </div>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Radni direktorijum</span>
            <div className="settings-path-row">
              <input
                className="settings-path-input"
                value={settings.workingDirectory}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    workingDirectory: event.target.value,
                  })
                }
              />
              <button
                type="button"
                onClick={() =>
                  pickWorkingDirectory().then((payload) => {
                    if (payload.path) {
                      setSettings({
                        ...settings,
                        workingDirectory: payload.path,
                      });
                    }
                  })
                }
              >
                Pregledaj
              </button>
            </div>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Provider pretrage</span>
            <div className="settings-control-block settings-control-block-wide">
              <CustomSelect
                value={settings.webSearchProvider}
                options={settings.availableSearchProviders.map((provider) => ({
                  value: provider.id,
                  label: provider.label,
                }))}
                onChange={(value) => {
                  const nextSettings = {
                    ...settings,
                    webSearchProvider: value,
                    webSearchBaseUrl: value === "searxng" ? settings.webSearchBaseUrl : "",
                  };
                  setSettings(nextSettings);
                  void fetchSearchProviderStatus(value).then(updateProviderStatus);
                }}
                ariaLabel="Izaberi search provider"
              />
            </div>
            <p className="helper-text">
              {currentSearchProviderOption?.summary || "Izaberi provider za Search, Knowledge i local-lacc search augmentation."}
            </p>
            <p className="helper-text">
              Ako hoćeš javni provider bez API ključa, biraj DuckDuckGo (public web, no key).
            </p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">
              {settings.webSearchProvider === "searxng"
                ? "Managed local SearxNG (Windows + WSL)"
                : "DuckDuckGo public web (no key)"}
            </span>
            <strong className="status-value">
              {settings.searchProviderStatus.providerLabel}: {settings.searchProviderStatus.label}
            </strong>
            <p className="helper-text">{settings.searchProviderStatus.summary}</p>
            <div className="summary-metrics">
              <span>Source: {settings.searchProviderStatus.source || "--"}</span>
              <span>Configured URL: {settings.searchProviderStatus.configuredBaseUrl || "--"}</span>
              <span>Effective URL: {settings.searchProviderStatus.effectiveBaseUrl || "--"}</span>
              <span>Service: {settings.searchProviderStatus.serviceLabel || "--"}</span>
            </div>
            <div className="settings-action-row">
              <button
                type="button"
                disabled={providerBusy !== ""}
                onClick={async () => {
                  setProviderBusy("check");
                  try {
                    const providerStatus = await fetchSearchProviderStatus(settings.webSearchProvider);
                    updateProviderStatus(providerStatus);
                    setResult({
                      status: providerStatus.status === "healthy" ? "ok" : "error",
                      action: "check-search-provider",
                      summary: providerStatus.summary,
                      details: {
                        returncode: providerStatus.status === "healthy" ? 0 : 1,
                        stdout: providerStatus.status === "healthy" ? providerStatus.summary : "",
                        stderr: providerStatus.status === "healthy" ? "" : providerStatus.summary,
                      },
                    });
                  } finally {
                    setProviderBusy("");
                  }
                }}
              >
                {providerBusy === "check" ? "Checking..." : "Check health"}
              </button>
              {settings.webSearchProvider === "searxng" ? (
                <button
                  type="button"
                  disabled={providerBusy !== "" || settings.searchProviderStatus.canBootstrap === false}
                  title={
                    settings.searchProviderStatus.canBootstrap
                      ? undefined
                      : settings.searchProviderStatus.bootstrapSummary
                  }
                  onClick={async () => {
                    setProviderBusy("setup");
                    try {
                      const payload = await bootstrapManagedSearchProvider(settings.webSearchProvider);
                      updateProviderStatus(payload.providerStatus);
                      setResult(payload.result);
                      await reload();
                    } finally {
                      setProviderBusy("");
                    }
                  }}
                >
                  {providerBusy === "setup"
                    ? "Setting up managed SearxNG..."
                    : "Setup managed SearxNG (Windows + WSL)"}
                </button>
              ) : null}
            </div>
            {settings.webSearchProvider === "searxng" ? (
              <p className="helper-text">
                Ovaj automatski setup koristi WSL da lokalno podigne SearxNG. Manualni URL ispod je
                odvojeni rezim i ne zahteva WSL.
              </p>
            ) : (
              <p className="helper-text">
                DuckDuckGo radi kao javni provider i ne traži WSL, bootstrap ni manualni endpoint.
              </p>
            )}
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Web search mode</span>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.webSearchMode}
                options={[
                  { value: "off", label: "Off" },
                  { value: "on-demand", label: "On-demand" },
                  { value: "always", label: "Always" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    webSearchMode: value,
                  })
                }
                ariaLabel="Izaberi web search mode"
              />
            </div>
            <p className="helper-text">
              Ovo važi za Search tab i za OpenCode kada koristi lokalni `local-lacc` provider.
              Cloud `opencode` modeli ne prolaze kroz ovaj lokalni search sloj.
            </p>
          </article>

          {settings.webSearchProvider === "searxng" ? (
            <article className="settings-field settings-field-wide">
              <span className="settings-field-label">Manual SearxNG base URL (optional, no WSL)</span>
              <div className="settings-path-row">
                <input
                  className="settings-path-input"
                  value={settings.webSearchBaseUrl}
                  onChange={(event) =>
                    setSettings({
                      ...settings,
                      webSearchBaseUrl: event.target.value,
                    })
                  }
                />
              </div>
              <p className="helper-text">
                Ostavi prazno ako hoćeš da Search koristi managed lokalni SearxNG koji aplikacija sama
                podigne preko WSL-a.
              </p>
            </article>
          ) : null}

          <article className="settings-field">
            <span className="settings-field-label">Search results limit</span>
            <div className="settings-number-row">
              <input
                type="number"
                value={settings.webSearchMaxResults}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    webSearchMaxResults: Number(event.target.value || 0),
                  })
                }
              />
            </div>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Search timeout (s)</span>
            <div className="settings-number-row">
              <input
                type="number"
                value={settings.webSearchTimeoutSeconds}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    webSearchTimeoutSeconds: Number(event.target.value || 0),
                  })
                }
              />
            </div>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">On-demand prefix</span>
            <div className="settings-number-row">
              <input
                value={settings.webSearchPromptPrefix}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    webSearchPromptPrefix: event.target.value,
                  })
                }
              />
            </div>
          </article>
        </div>
        <div className="inline-actions settings-footer-actions">
          <button
            type="button"
            onClick={async () => {
              const actionResult = await applySettings(settings);
              setResult(actionResult);
              await reload();
            }}
          >
            Save model settings
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              if (!settingsDefaults) {
                return;
              }
              setSettings({ ...settingsDefaults });
              setResult({
                status: "ok",
                action: "restore-model-settings",
                summary: "Model settings su vraćeni na poslednje sačuvane vrednosti.",
                details: { returncode: 0, stdout: "", stderr: "" },
              });
            }}
          >
            Vrati podrazumevano
          </button>
        </div>
        <p className="helper-text">
          Glavne promene postaju stvarno aktivne tek kada klikneš na `Save model settings`.
        </p>
      </section>

      <section className="status-card wide-card">
        <div className="section-header">
          <span className="status-label">TurboQuant preseti</span>
        </div>
        <p className="helper-text">
          `safe` je najbezbedniji, `daily` je preporučeni balans, a `max-context` je agresivniji
          kada juriš što duži kontekst.
        </p>
        <div className="model-list">
          {allTurboPresets.map((preset) => (
            <article className="model-item" key={preset.id}>
              <div className="model-item-header">
                <div>
                  <strong>{preset.name}</strong>
                  <div className="muted-line">{preset.description}</div>
                  <div className="muted-line">
                    Context {preset.settings.context} | ctk {preset.settings.ctk} | ctv{" "}
                    {preset.settings.ctv} | ncmoe {preset.settings.ncmoe}
                  </div>
                  {preset.notes ? <p className="helper-text">{preset.notes}</p> : null}
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => {
                      setTurboConfig(applyPresetToConfig(preset));
                      setResult({
                        status: "ok",
                        action: "apply-preset-local",
                        summary: `Preset ${preset.name} je učitan u editor.`,
                        details: { returncode: 0, stdout: "", stderr: "" },
                      });
                    }}
                  >
                    Učitaj preset
                  </button>
                  {schema.userPresets.some((item) => item.id === preset.id) ? (
                    <button
                      type="button"
                      className="danger-button"
                      onClick={async () => {
                        const actionResult = await deleteTurboQuantPreset(preset.id);
                        setResult(actionResult);
                        await reload();
                      }}
                    >
                      Obriši
                    </button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Sačuvaj trenutni preset</span>
        <div className="form-grid">
          <input
            placeholder="Ime preset-a"
            value={presetName}
            onChange={(event) => setPresetName(event.target.value)}
          />
          <input
            placeholder="Kratak opis"
            value={presetDescription}
            onChange={(event) => setPresetDescription(event.target.value)}
          />
          <input
            placeholder="Model pattern, npr qwen36-*"
            value={presetTargetPattern}
            onChange={(event) => setPresetTargetPattern(event.target.value)}
          />
          <input
            placeholder="Napomena"
            value={presetNotes}
            onChange={(event) => setPresetNotes(event.target.value)}
          />
          <button
            type="button"
            onClick={async () => {
              const actionResult = await saveTurboQuantPreset({
                name: presetName,
                description: presetDescription,
                targetModelPattern: presetTargetPattern,
                notes: presetNotes,
                settings: turboConfig,
              });
              setResult(actionResult);
              setPresetName("");
              setPresetDescription("");
              setPresetTargetPattern("");
              setPresetNotes("");
              await reload();
            }}
          >
            Sačuvaj preset
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">TurboQuant parametri</span>
        <div className="model-list">
          {schema.parameters.map((parameter) => (
            <article className="model-item" key={parameter.id}>
              <div className="model-item-header">
                <div>
                  <strong>{parameter.label}</strong>
                  <p className="helper-text">{parameter.whatIsIt}</p>
                  <p className="helper-text">Ucinak: {parameter.effect}</p>
                  <p className="helper-text">Preporuka: {parameter.recommendation}</p>
                  <div className="muted-line">
                    Safe: {parameter.safeChoices.join(", ") || "--"} | Advanced:{" "}
                    {parameter.advancedChoices.join(", ") || "--"}
                  </div>
                </div>
                <div className="inline-actions">
                  {parameter.id === "context" || parameter.id === "ncmoe" ? (
                    <input
                      type="number"
                      value={Number(turboConfig[parameter.id as keyof TurboQuantConfig])}
                      onChange={(event) =>
                        setTurboConfig({
                          ...turboConfig,
                          [parameter.id]: Number(event.target.value || 0),
                        })
                      }
                    />
                  ) : parameter.id === "flashAttention" || parameter.id === "mlock" ? (
                    <label>
                      <input
                        type="checkbox"
                        checked={Boolean(turboConfig[parameter.id as keyof TurboQuantConfig])}
                        onChange={(event) =>
                          setTurboConfig({
                            ...turboConfig,
                            [parameter.id]: event.target.checked,
                          })
                        }
                      />{" "}
                      uključeno
                    </label>
                  ) : (
                    <CustomSelect
                      value={String(turboConfig[parameter.id as keyof TurboQuantConfig])}
                      options={[...parameter.safeChoices, ...parameter.advancedChoices].map((choice) => ({
                        value: choice,
                        label: choice,
                      }))}
                      onChange={(value) =>
                        setTurboConfig({
                          ...turboConfig,
                          [parameter.id]: value,
                        })
                      }
                      ariaLabel={`Izaberi ${parameter.label}`}
                    />
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="status-card wide-card">
        <div className="inline-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={async () => {
              const actionResult = await saveTurboQuantConfig(turboConfig);
              setResult(actionResult);
              if (actionResult.status === "ok") {
                clearDraft(TURBOQUANT_DRAFT_STORAGE_KEY);
              }
              await reload();
            }}
          >
            Save TurboQuant config
          </button>
        </div>
      </section>
      <ActionResultPanel result={result} />
    </div>
  );
}
