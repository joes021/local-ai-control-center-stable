import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import {
  applyOpenCodeSettings,
  deleteOpenCodeStepPreset,
  fetchOpenCodeStatus,
  fetchOpenCodeStepSchema,
  fetchSettings,
  openOpenCode,
  saveOpenCodeStepPreset,
} from "../lib/api";
import type {
  ActionResult,
  OpenCodeStatusPayload,
  OpenCodeStepPreset,
  OpenCodeStepSchemaPayload,
  OpenCodeStepValues,
  SettingsPayload,
} from "../lib/types";

function renderOpenCodeState(opencode: OpenCodeStatusPayload | null) {
  if (!opencode?.available) {
    return "Nedostupan";
  }
  if (opencode.sessionState === "connected") {
    return "Aktivan";
  }
  if (opencode.sessionState === "app-only") {
    return "Otvoren bez backend veze";
  }
  if (opencode.sessionState === "runtime-ready") {
    return "Runtime spreman";
  }
  return "Dostupan";
}

function formatPresetLabel(preset: OpenCodeStepPreset) {
  return `${preset.name} (${preset.summary})`;
}

function isSameStepPreset(left: OpenCodeStepValues, right: OpenCodeStepValues) {
  return (
    left.buildSteps === right.buildSteps &&
    left.planSteps === right.planSteps &&
    left.generalSteps === right.generalSteps &&
    left.exploreSteps === right.exploreSteps
  );
}

export function OpenCodePage() {
  const [opencode, setOpencode] = useState<OpenCodeStatusPayload | null>(null);
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [stepSchema, setStepSchema] = useState<OpenCodeStepSchemaPayload | null>(null);
  const [stepEditor, setStepEditor] = useState<OpenCodeStepValues | null>(null);
  const [presetName, setPresetName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);

  async function loadStatus() {
    try {
      const [opencodePayload, settingsPayload, stepSchemaPayload] = await Promise.all([
        fetchOpenCodeStatus(),
        fetchSettings(),
        fetchOpenCodeStepSchema(),
      ]);
      setOpencode(opencodePayload);
      setSettings(settingsPayload);
      setStepSchema(stepSchemaPayload);
      setStepEditor(stepSchemaPayload.currentSteps);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greska");
    }
  }

  useEffect(() => {
    let active = true;
    void loadStatus();

    const timer = window.setInterval(() => {
      if (active) {
        void loadStatus();
      }
    }, 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const activePresetLabel = useMemo(() => {
    if (!stepSchema || !stepEditor) {
      return "Custom values";
    }
    const matchedPreset = [...stepSchema.builtInPresets, ...stepSchema.userPresets].find((preset) =>
      isSameStepPreset(preset.steps, stepEditor),
    );
    return matchedPreset ? formatPresetLabel(matchedPreset) : "Custom values";
  }, [stepEditor, stepSchema]);

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!opencode || !settings || !stepSchema || !stepEditor) {
    return <section className="status-card wide-card">Ucitavam OpenCode status...</section>;
  }

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">OpenCode stanje</span>
        <strong className="status-value">{renderOpenCodeState(opencode)}</strong>
        <div className="summary-metrics">
          <span>Instanci: {opencode.instanceCount ?? 0}</span>
          <span>Profil: {opencode.profile || "--"}</span>
          <span>Backend: {opencode.runtimeConnected ? "povezan" : opencode.runtimeLiveStatus || "--"}</span>
          <span>Security režim: {opencode.securityModeLabel || "--"}</span>
          <span>Autonomija: {opencode.capabilityModeLabel || "--"}</span>
        </div>
        <div className="inline-actions">
          <button
            type="button"
            disabled={opencode.canOpen === false}
            title={opencode.openBlockedReason || undefined}
            onClick={async () => {
              try {
                const actionResult = await openOpenCode(opencode.profile || "balanced");
                setResult(actionResult);
                await loadStatus();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Nepoznata greska");
              }
            }}
          >
            {opencode.openActionLabel || "Open OpenCode"}
          </button>
        </div>
        <p className="helper-text">
          {opencode.sessionSummary ||
            "Promena modela vazi za novi OpenCode session. Vec otvoren OpenCode prozor ne menja model usred sesije."}
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">OpenCode config</span>
        <strong className="status-value">{opencode.configPath || "nije pronadjen"}</strong>
        <p className="helper-text">Executable: {opencode.executablePath || "nije pronadjen"}</p>
        <p className="helper-text">Working directory: {opencode.workingDirectory || "--"}</p>
        <p className="helper-text">
          Backend veza: {opencode.runtimeConnected ? "spremna" : "nije spremna"} |{" "}
          {opencode.runtimeLiveReason || "Nema dodatnih runtime detalja."}
        </p>
        <p className="helper-text">Audit: {opencode.auditSummary || "Nema dodatnih OpenCode detalja."}</p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">OpenCode steps</span>
        <strong className="status-value">Aktivni preset: {activePresetLabel}</strong>
        <div className="summary-metrics">
          <span>Build: {stepEditor.buildSteps}</span>
          <span>Plan: {stepEditor.planSteps}</span>
          <span>General: {stepEditor.generalSteps}</span>
          <span>Explore: {stepEditor.exploreSteps}</span>
        </div>
        <p className="helper-text">
          Preset menja samo OpenCode stepove. Security, autonomija i working directory ostaju
          odvojena podesavanja.
        </p>

        <div className="model-list">
          {stepSchema.builtInPresets.map((preset) => (
            <article className="model-item" key={preset.id}>
              <div className="model-item-header">
                <div>
                  <strong>{formatPresetLabel(preset)}</strong>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => {
                      setStepEditor({ ...preset.steps });
                      setResult({
                        status: "ok",
                        action: "load-opencode-step-preset",
                        summary: `OpenCode preset ${preset.name} je ucitan u editor.`,
                        details: { returncode: 0, stdout: "", stderr: "" },
                      });
                    }}
                  >
                    Load preset
                  </button>
                </div>
              </div>
            </article>
          ))}
          {stepSchema.userPresets.map((preset) => (
            <article className="model-item" key={preset.id}>
              <div className="model-item-header">
                <div>
                  <strong>{formatPresetLabel(preset)}</strong>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    onClick={() => {
                      setStepEditor({ ...preset.steps });
                      setResult({
                        status: "ok",
                        action: "load-opencode-step-preset",
                        summary: `OpenCode preset ${preset.name} je ucitan u editor.`,
                        details: { returncode: 0, stdout: "", stderr: "" },
                      });
                    }}
                  >
                    Load preset
                  </button>
                  <button
                    type="button"
                    className="danger-button"
                    onClick={async () => {
                      const actionResult = await deleteOpenCodeStepPreset(preset.id);
                      setResult(actionResult);
                      await loadStatus();
                    }}
                  >
                    Delete preset
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>

        <div className="form-grid">
          <label>
            Build
            <input
              type="number"
              value={stepEditor.buildSteps}
              onChange={(event) =>
                setStepEditor({
                  ...stepEditor,
                  buildSteps: Number(event.target.value || 0),
                })
              }
            />
          </label>
          <label>
            Plan
            <input
              type="number"
              value={stepEditor.planSteps}
              onChange={(event) =>
                setStepEditor({
                  ...stepEditor,
                  planSteps: Number(event.target.value || 0),
                })
              }
            />
          </label>
          <label>
            General
            <input
              type="number"
              value={stepEditor.generalSteps}
              onChange={(event) =>
                setStepEditor({
                  ...stepEditor,
                  generalSteps: Number(event.target.value || 0),
                })
              }
            />
          </label>
          <label>
            Explore
            <input
              type="number"
              value={stepEditor.exploreSteps}
              onChange={(event) =>
                setStepEditor({
                  ...stepEditor,
                  exploreSteps: Number(event.target.value || 0),
                })
              }
            />
          </label>
        </div>

        <div className="form-grid">
          <input
            placeholder="Ime OpenCode preset-a"
            value={presetName}
            onChange={(event) => setPresetName(event.target.value)}
          />
          <button
            type="button"
            onClick={async () => {
              const actionResult = await saveOpenCodeStepPreset({
                name: presetName,
                steps: stepEditor,
              });
              setResult(actionResult);
              if (actionResult.status === "ok") {
                setPresetName("");
              }
              await loadStatus();
            }}
          >
            Save preset
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              setStepEditor({ ...stepSchema.defaultSteps });
              setResult({
                status: "ok",
                action: "restore-opencode-step-defaults",
                summary: "OpenCode stepovi su vraceni na podrazumevani preset.",
                details: { returncode: 0, stdout: "", stderr: "" },
              });
            }}
          >
            Restore default
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">OpenCode settings</span>
        <div className="form-grid">
          <label>
            Security režim
            <CustomSelect
              value={opencode.securityMode}
              options={[
                { value: "strict", label: "Strogo ogranicen agent" },
                { value: "workspace-write", label: "Ogranicen agent sa blacklist pravilima" },
                { value: "open", label: "Potpuno otvoren agent" },
              ]}
              onChange={(value) =>
                setOpencode({
                  ...opencode,
                  securityMode: value,
                  securityModeLabel:
                    value === "workspace-write"
                      ? "Ogranicen agent sa blacklist pravilima"
                      : value === "open"
                        ? "Potpuno otvoren agent"
                        : "Strogo ogranicen agent",
                })
              }
              ariaLabel="Izaberi OpenCode security mode"
            />
          </label>
          <label>
            Autonomija
            <CustomSelect
              value={opencode.capabilityMode}
              options={[
                { value: "read-only", label: "1. Samo citanje fajlova" },
                { value: "read-write", label: "2. Citanje + izmena fajlova" },
                { value: "confirm-commands", label: "3. Citanje + izmena + komande uz potvrdu" },
                { value: "auto-commands", label: "4. Citanje + izmena + komande bez potvrde" },
              ]}
              onChange={(value) =>
                setOpencode({
                  ...opencode,
                  capabilityMode: value,
                  capabilityModeLabel:
                    value === "read-only"
                      ? "1. Samo citanje fajlova"
                      : value === "read-write"
                        ? "2. Citanje + izmena fajlova"
                        : value === "auto-commands"
                          ? "4. Citanje + izmena + komande bez potvrde"
                          : "3. Citanje + izmena + komande uz potvrdu",
                })
              }
              ariaLabel="Izaberi OpenCode capability mode"
            />
          </label>
          <button
            type="button"
            onClick={async () => {
              const actionResult = await applyOpenCodeSettings({
                profile: settings.profile,
                context: settings.context,
                outputTokens: settings.outputTokens,
                workingDirectory: settings.workingDirectory,
                buildSteps: stepEditor.buildSteps,
                planSteps: stepEditor.planSteps,
                generalSteps: stepEditor.generalSteps,
                exploreSteps: stepEditor.exploreSteps,
                securityMode: opencode.securityMode,
                capabilityMode: opencode.capabilityMode,
              });
              setResult(actionResult);
              await loadStatus();
            }}
          >
            Save OpenCode settings
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">OpenCode instances</span>
        {opencode.instances?.length ? (
          <div className="model-list">
            {opencode.instances.map((instance, index) => (
              <article className="model-item" key={`${instance.pid ?? "instance"}-${index}`}>
                <strong>{instance.name || `Instanca ${index + 1}`}</strong>
                <div className="muted-line">PID: {instance.pid ?? "nepoznat"}</div>
                {instance.commandLine ? <div className="muted-line">{instance.commandLine}</div> : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">
            Lista OpenCode procesa nije dostupna na ovom sistemu, pa se za sada prikazuje samo broj
            instanci.
          </p>
        )}
      </section>

      <ActionResultPanel result={result} />
    </>
  );
}
