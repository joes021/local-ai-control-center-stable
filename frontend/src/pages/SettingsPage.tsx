import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import {
  applySettings,
  deleteTurboQuantPreset,
  fetchSettings,
  fetchTurboQuantSchema,
  pickWorkingDirectory,
  saveTurboQuantConfig,
  saveTurboQuantPreset,
} from "../lib/api";
import type {
  ActionResult,
  SettingsPayload,
  TurboQuantConfig,
  TurboQuantPreset,
  TurboQuantSchemaPayload,
} from "../lib/types";

const TURBOQUANT_DRAFT_STORAGE_KEY = "local-ai-control-center:turboquant-draft";

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

export function SettingsPage() {
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsPayload | null>(null);
  const [schema, setSchema] = useState<TurboQuantSchemaPayload | null>(null);
  const [turboConfig, setTurboConfig] = useState<TurboQuantConfig | null>(null);
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

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!settings || !schema || !turboConfig) {
    return <div className="status-card wide-card">Ucitavam settings...</div>;
  }

  const allPresets = [...schema.builtInPresets, ...schema.userPresets];

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Settings scope</span>
        <strong className="status-value">
          Aktivni model: {settings.activeModelLabel || "nema"} ({settings.activeModelId || "--"})
        </strong>
        <p className="helper-text">
          Global defaults vaze za sve modele bez posebnog override-a. Active model override vazi
          samo za trenutno aktivni model.
        </p>
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
        <p className="helper-text">
          {settings.modelOverrideExists
            ? "Za aktivni model vec postoji poseban override."
            : "Za aktivni model trenutno nema posebnog override-a."}
        </p>
      </section>

      <section className="status-card">
        <span className="status-label">Access mode</span>
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
        <p className="helper-text">
          Tailscale rezim podize backend tako da moze da se otvori i preko Tailscale adrese.
        </p>
      </section>

      <section className="status-card">
        <span className="status-label">Profil</span>
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
          ariaLabel="Izaberi profil"
        />
      </section>

      <section className="status-card">
        <span className="status-label">Thinking mode</span>
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
      </section>

      <section className="status-card">
        <span className="status-label">Context</span>
        <input
          type="number"
          value={settings.context}
          onChange={(event) =>
            setSettings({
              ...settings,
              context: Number(event.target.value || 0),
            })
          }
        />
      </section>

      <section className="status-card">
        <span className="status-label">Output tokens</span>
        <input
          type="number"
          value={settings.outputTokens}
          onChange={(event) =>
            setSettings({
              ...settings,
              outputTokens: Number(event.target.value || 0),
            })
          }
        />
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Working directory</span>
        <div className="form-grid">
          <input
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
      </section>

      <section className="status-card wide-card">
        <div className="inline-actions">
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
          Dropdown izbori i ostale glavne promene postaju stvarno aktivni tek kada kliknes Save model settings.
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
          {allPresets.map((preset) => (
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
    </>
  );
}
