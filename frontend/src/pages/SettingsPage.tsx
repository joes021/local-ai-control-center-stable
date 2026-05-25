import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import {
  applySettings,
  deleteSettingsProfile,
  deleteTurboQuantPreset,
  fetchSettings,
  fetchTurboQuantSchema,
  pickWorkingDirectory,
  saveSettingsProfile,
  saveTurboQuantConfig,
  saveTurboQuantPreset,
} from "../lib/api";
import type {
  ActionResult,
  SettingsPayload,
  SettingsProfilePreset,
  SettingsProfileValues,
  TurboQuantConfig,
  TurboQuantPreset,
  TurboQuantSchemaPayload,
} from "../lib/types";

const TURBOQUANT_DRAFT_STORAGE_KEY = "local-ai-control-center:turboquant-draft";
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
      setError(reason instanceof Error ? reason.message : "Nepoznata greska");
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

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!settings || !schema || !turboConfig) {
    return <div className="status-card wide-card">Ucitavam settings...</div>;
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

  return (
    <div className="settings-page">
      <section className="status-card wide-card settings-cluster-card">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Profiles & scope</span>
            <strong className="status-value">
              Aktivni model: {settings.activeModelLabel || "nema"} ({settings.activeModelId || "--"})
            </strong>
          </div>
        </div>
        <div className="settings-cluster-grid settings-cluster-grid-profiles">
          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Settings scope</span>
            <p className="helper-text">
              Global defaults vaze za sve modele bez posebnog override-a. Active model override vazi
              samo za trenutno aktivni model.
            </p>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.settingsScope}
                options={[
                  { value: "global", label: "Global defaults" },
                  { value: "model", label: "Active model override" },
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
                ? "Za aktivni model vec postoji poseban override."
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
                    summary: `Profil ${profile.name} je ucitan u editor.`,
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
            <span className="settings-field-label">Sacuvaj trenutni custom profil</span>
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
                Sacuvaj profil
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
                  Obrisi izabrani profil
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
                ariaLabel="Izaberi context velicinu"
              />
              {contextChoice === "custom" ? (
                <input
                  type="number"
                  value={settings.context}
                  aria-label="Unesi context velicinu"
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
            <span className="settings-field-label">Working directory</span>
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
                Browse
              </button>
            </div>
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
              Ovo vazi za Search tab i za OpenCode kada koristi lokalni `local-lacc` provider.
              Cloud `opencode` modeli ne prolaze kroz ovaj lokalni search sloj.
            </p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">SearxNG base URL</span>
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
          </article>

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
                summary: "Model settings su vraceni na poslednje sacuvane vrednosti.",
                details: { returncode: 0, stdout: "", stderr: "" },
              });
            }}
          >
            Restore default
          </button>
        </div>
        <p className="helper-text">
          Glavne promene postaju stvarno aktivne tek kada kliknes Save model settings.
        </p>
      </section>

      <section className="status-card wide-card">
        <div className="section-header">
          <span className="status-label">TurboQuant preseti</span>
        </div>
        <p className="helper-text">
          safe je najbezbedniji, daily je preporuceni balans, a max-context je agresivniji kada
          juris sto duzi context.
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
                        summary: `Preset ${preset.name} je ucitan u editor.`,
                        details: { returncode: 0, stdout: "", stderr: "" },
                      });
                    }}
                  >
                    Load preset
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
                      Obrisi
                    </button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Sacuvaj trenutni preset</span>
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
            Sacuvaj preset
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
                      ukljuceno
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
