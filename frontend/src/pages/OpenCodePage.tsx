import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PrimaryFlowCard } from "../components/PrimaryFlowCard";
import { RuntimePilotIcon } from "../components/RuntimePilotIcon";
import {
  applyOpenCodeSettings,
  bootstrapOpenCode,
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
  if (opencode.sessionState === "launching") {
    return "Pokretanje CLI sesije";
  }
  if (opencode.sessionState === "connected") {
    return "CLI sesija aktivna";
  }
  if (opencode.sessionState === "app-only") {
    return "CLI sesija bez backend veze";
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
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
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

  async function copyText(text: string, label: string) {
    if (!text.trim()) {
      setError(`Nema sadržaja za kopiranje: ${label}.`);
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setResult({
        status: "ok",
        action: "copy-opencode-preview",
        summary: `${label} je kopiran u clipboard.`,
        details: { returncode: 0, stdout: text, stderr: "" },
      });
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : `Kopiranje nije uspelo: ${label}.`,
      );
    }
  }

  async function runOpenCodeAction(action: () => Promise<ActionResult>) {
    try {
      const actionResult = await action();
      setResult(actionResult);
      await loadStatus();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    }
  }

  if (!opencode || !settings || !stepSchema || !stepEditor) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam OpenCode status..."
        onRetry={() => {
          setError(null);
          void loadStatus();
        }}
      />
    );
  }

  const openCodeStateTitle = renderOpenCodeState(opencode);
  const openCodeStateSummary =
    opencode.sessionSummary ||
    "Kada su runtime i model zdravi, ovde prelaziš na konkretan rad, taskove i rezultate.";
  const actionSummary = result
    ? result.summary
    : "Posle klika odmah vidiš da li je otvoren direktan rad nad pravim projektom ili izolovani workspace za bezbedan probni tok.";
  const currentInstance = opencode.instances?.[0];

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <div className="primary-page-top-grid runtime-page-top-grid wide-card">
        <PrimaryFlowCard
          className="runtime-faceplate-card"
          eyebrow="OpenCode"
          title="OpenCode radni tok"
          stateTitle={openCodeStateTitle}
          stateSummary={openCodeStateSummary}
          icon="opencode"
          primaryLabel="Glavna akcija"
          primaryActionLabel={opencode.openActionLabel || "Otvori OpenCode"}
          primaryActionIcon="play"
          onPrimaryAction={() =>
            void runOpenCodeAction(() => openOpenCode(opencode.profile || "balanced", "direct"))
          }
          primaryDisabled={opencode.canOpen === false}
          primaryTitle={opencode.openBlockedReason || undefined}
          secondaryLabel="Sekundarna akcija"
          secondaryActionLabel="Otvori u izolovanom workspace-u"
          secondaryActionIcon="reload"
          onSecondaryAction={() =>
            void runOpenCodeAction(() => openOpenCode(opencode.profile || "balanced", "isolated"))
          }
          secondaryDisabled={opencode.canOpen === false}
          secondaryTitle={opencode.openBlockedReason || undefined}
          resultLabel="Rezultat posle klika"
          resultSummary={actionSummary}
          stateMeta={
            <>
              <span>Instanci: {opencode.instanceCount ?? 0}</span>
              <span>Profil: {opencode.profile || "--"}</span>
              <span>Backend: {opencode.runtimeConnected ? "povezan" : opencode.runtimeLiveStatus || "--"}</span>
            </>
          }
          liveResult={
            <div className="primary-flow-inline-result">
              <strong>Desktop GUI kada je dostupan</strong>
              <p className="helper-text">
                RuntimePilot sada prvo pokušava da otvori desktop OpenCode prozor nad pravim projektom
                ili nad izolovanim workspace-om. Ako GUI nije dostupan, koristi CLI fallback.
              </p>
              <p className="helper-text">Otvorena CLI sesija i sledeći klik ostaju vidljivi u sesijskom deck-u ispod.</p>
            </div>
          }
        />

        <section className="status-card runtimepilot-section-shell primary-page-support-card runtime-faceplate-support">
          <div className="runtime-faceplate-head">
            <span className="status-label">Sesija sada</span>
            <strong className="status-value">
              {currentInstance?.name || (opencode.active ? "Sesija je aktivna" : "Sesija još nije otvorena")}
            </strong>
          </div>
          <div className="runtime-faceplate-copy">
            <p className="helper-text">
              {opencode.runtimeConnected
                ? "OpenCode je povezan sa runtime-om i može odmah da koristi aktivni model."
                : opencode.runtimeLiveReason || "OpenCode još čeka zdrav runtime signal."}
            </p>
            <div className="summary-metrics">
              <span>PID: {currentInstance?.pid ?? "nepoznat"}</span>
              <span>State: {opencode.sessionState}</span>
              <span>Search proxy: {opencode.localProviderUsesSearchProxy ? "uključen" : "isključen"}</span>
            </div>
          </div>
          <div className="runtime-faceplate-rail">
            <span className="status-label">Veza i održavanje</span>
            <p className="helper-text runtime-faceplate-note">
              {opencode.localProviderSearchSummary ||
                "local-lacc koristi isti RuntimePilot search sloj kao i Search tab kada je to uključeno."}
            </p>
            <button
              type="button"
              className="action-button-soft deck-control-button deck-control-button-secondary"
              onClick={() => void runOpenCodeAction(bootstrapOpenCode)}
              disabled={opencode.canBootstrap === false}
              title={opencode.bootstrapBlockedReason || undefined}
            >
              <span className="deck-control-symbol" aria-hidden="true">
                <RuntimePilotIcon name="reload" />
              </span>
              <span className="deck-control-copy">
                {opencode.bootstrapActionLabel || "Instaliraj ili popravi OpenCode"}
              </span>
            </button>
          </div>
        </section>

        <section className="status-card runtimepilot-section-shell primary-page-support-card runtime-faceplate-support">
          <div className="runtime-faceplate-head">
            <div className="runtime-faceplate-headline">
              <span className="runtime-faceplate-module-glyph" aria-hidden="true">
                <RuntimePilotIcon className="runtime-faceplate-module-icon" name="settings" />
              </span>
              <div className="runtime-faceplate-module-copy">
                <span className="status-label">Managed config i runtime veza</span>
                <strong className="status-value">
                  {opencode.launchPreview.managedConfig.model || "Model nije postavljen"}
                </strong>
              </div>
            </div>
            <div className="runtime-faceplate-status-lights" aria-hidden="true">
              <span className="runtime-faceplate-status-light runtime-faceplate-status-light-active" />
              <span className="runtime-faceplate-status-light" />
              <span className="runtime-faceplate-status-light" />
            </div>
          </div>
          <div className="runtime-faceplate-copy">
            <p className="helper-text">
              Provider: {opencode.launchPreview.managedConfig.selectedProvider || "nije prepoznat"} · Base URL:{" "}
              {opencode.launchPreview.managedConfig.localProviderBaseUrl || "nije pronađen"}
            </p>
            <div className="summary-metrics">
              <span>Config: {opencode.configExists ? "pronađen" : "nedostaje"}</span>
              <span>Radni direktorijum: {opencode.workingDirectory || "--"}</span>
            </div>
          </div>
          <div className="runtime-faceplate-rail">
            <span className="status-label">Launcher</span>
            <button
              type="button"
              className="action-button-soft deck-control-button deck-control-button-secondary"
              onClick={() => void copyText(opencode.launchPreview.launcherCommand, "Launcher komanda")}
            >
              <span className="deck-control-symbol" aria-hidden="true">
                <RuntimePilotIcon name="play" />
              </span>
              <span className="deck-control-copy">Kopiraj launcher</span>
            </button>
          </div>
        </section>
      </div>

      <ActionResultPanel result={result} />

      <details className="status-card wide-card runtimepilot-section-shell runtimepilot-advanced-disclosure">
        <summary>Napredni OpenCode alati</summary>
        <p className="helper-text runtimepilot-advanced-summary">
          Ovde ostaju launcher preview, managed config detalji, env promenljive, presetovi koraka,
          sigurnosni režimi i lista instanci. Vrh strane sada služi za direktan rad, a ovo otvaraš
          kada ti stvarno treba fino podešavanje ili dijagnostika.
        </p>

        <section className="status-card wide-card runtimepilot-faceplate-module runtimepilot-command-module">
          <div className="runtimepilot-advanced-module-shell">
            <div className="runtime-faceplate-head">
              <span className="status-label">Ekvivalentna OpenCode komanda</span>
              <strong className="status-value">{opencode.launchPreview.shellLabel}</strong>
            </div>
            <div className="runtime-faceplate-copy">
              <p className="helper-text">
                Ovo je najbliži ručni prikaz onoga što RuntimePilot radi kada otvara OpenCode. Managed config
                određuje provider i model, a `local-lacc` zatim koristi trenutni runtime i aktivni model iz trenutnog RuntimePilot okruženja.
              </p>
              <p className="helper-text">
                Kada klikneš `Otvori OpenCode`, RuntimePilot prvo pokušava da otvori desktop GUI kada je dostupan.
                `Otvori u izolovanom workspace-u` radi isto, ali nad odvojenim probnim folderom. CLI fallback ostaje
                samo kao rezervni tok kada GUI nije dostupan.
              </p>
              <p className="helper-text">
                Ako želiš ručno da ga startuješ iz običnog `cmd.exe`, koristi launcher `.cmd`. PowerShell
                prikaz ispod samo razlaže iste korake u čitljiv niz `Set-Location` + `env` + `opencode.exe`.
              </p>
            </div>
            <div className="runtime-faceplate-rail runtime-faceplate-rail-stack">
              <span className="status-label">Signal</span>
              <p className="helper-text runtime-faceplate-note">Launcher .cmd: {opencode.launchPreview.launcherPath}</p>
              <p className="helper-text runtime-faceplate-note">Radni direktorijum: {opencode.launchPreview.workingDirectory}</p>
              <p className="helper-text runtime-faceplate-note">{opencode.launchPreview.summary}</p>
            </div>
          </div>
          {opencode.launchPreview.generationSummary ? (
            <p className="helper-text">
              Efektivna local-lacc inference podrazumevana podešavanja: {opencode.launchPreview.generationSummary}
            </p>
          ) : null}
          <div className="inline-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => void copyText(opencode.launchPreview.launcherCommand, "Launcher komanda")}
            >
              Kopiraj launcher
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => void copyText(opencode.launchPreview.powershellCommand, "PowerShell prikaz")}
            >
              Kopiraj PowerShell
            </button>
          </div>
          <div className="command-preview-grid">
            <div className="command-preview-card">
              <span className="status-label">Launcher .cmd</span>
              <div className="details-block">
                <pre>{opencode.launchPreview.launcherCommand}</pre>
              </div>
            </div>
            <div className="command-preview-card">
              <span className="status-label">PowerShell prikaz</span>
              <div className="details-block">
                <pre>{opencode.launchPreview.powershellCommand}</pre>
              </div>
            </div>
            <div className="command-preview-card">
              <span className="status-label">Managed config ulazi</span>
              <div className="opencode-config-grid">
                <article className="opencode-config-item">
                  <span className="opencode-config-label">Provider</span>
                  <strong className="opencode-config-value">
                    {opencode.launchPreview.managedConfig.selectedProvider || "nije prepoznat"}
                  </strong>
                </article>
                <article className="opencode-config-item">
                  <span className="opencode-config-label">Model</span>
                  <strong className="opencode-config-value opencode-config-value-break">
                    {opencode.launchPreview.managedConfig.model || "nije postavljen"}
                  </strong>
                </article>
                <article className="opencode-config-item">
                  <span className="opencode-config-label">Osnovni URL</span>
                  <strong className="opencode-config-value opencode-config-value-break">
                    {opencode.launchPreview.managedConfig.localProviderBaseUrl || "nije pronađen"}
                  </strong>
                </article>
                <article className="opencode-config-item">
                  <span className="opencode-config-label">Omogućeni provider-i</span>
                  <strong className="opencode-config-value opencode-config-value-break">
                    {opencode.launchPreview.managedConfig.enabledProviders.length
                      ? opencode.launchPreview.managedConfig.enabledProviders.join(", ")
                      : "nisu prijavljeni"}
                  </strong>
                </article>
              </div>
              <p className="helper-text">
                Model i provider dolaze iz `managed-config.json`, a `baseURL` pokazuje gde OpenCode traži
                lokalni runtime proxy.
              </p>
            </div>
            <div className="command-preview-card">
              <span className="status-label">Env promenljive</span>
              <p className="helper-text">
                Ovo su promenljive koje launcher postavlja pre nego što pokrene `opencode.exe`.
              </p>
              {opencode.launchPreview.environment.length ? (
                <div className="opencode-env-grid">
                  {opencode.launchPreview.environment.map((item) => (
                    <article className="opencode-env-item" key={item.key}>
                      <span className="opencode-env-key">{item.key}</span>
                      <code className="opencode-env-value">{item.value}</code>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="details-block">
                  <pre>Nema dodatnih env promenljivih.</pre>
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="status-card wide-card runtimepilot-faceplate-module runtimepilot-advanced-module">
          <div className="runtimepilot-advanced-module-shell">
            <div className="runtime-faceplate-head">
              <span className="status-label">Preseti koraka i podešavanja</span>
              <strong className="status-value">Aktivni preset: {activePresetLabel}</strong>
            </div>
            <div className="runtime-faceplate-copy">
              <div className="summary-metrics">
                <span>Izrada: {stepEditor.buildSteps}</span>
                <span>Plan: {stepEditor.planSteps}</span>
                <span>Opšte: {stepEditor.generalSteps}</span>
                <span>Istraživanje: {stepEditor.exploreSteps}</span>
              </div>
              <p className="helper-text">
                Preset menja samo OpenCode stepove. Security, autonomija i working directory ostaju
                odvojena podešavanja.
              </p>
            </div>
            <div className="runtime-faceplate-rail runtime-faceplate-rail-stack">
              <span className="status-label">Šta menjaš</span>
              <p className="helper-text runtime-faceplate-note">
                Ovde oblikuješ ponašanje agenta, ne runtime server. Zato su stepovi, sigurnost i autonomija grupisani zajedno.
              </p>
            </div>
          </div>

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
                          summary: `OpenCode preset ${preset.name} je učitan u editor.`,
                          details: { returncode: 0, stdout: "", stderr: "" },
                        });
                      }}
                    >
                      Učitaj preset
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
                          summary: `OpenCode preset ${preset.name} je učitan u editor.`,
                          details: { returncode: 0, stdout: "", stderr: "" },
                        });
                      }}
                    >
                      Učitaj preset
                    </button>
                    <button
                      type="button"
                      className="danger-button"
                      onClick={() => void runOpenCodeAction(() => deleteOpenCodeStepPreset(preset.id))}
                    >
                      Obriši preset
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="form-grid">
            <label>
              Izrada
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
              Opšte
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
              Istraživanje
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
              Sačuvaj preset
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setStepEditor({ ...stepSchema.defaultSteps });
                setResult({
                  status: "ok",
                  action: "restore-opencode-step-defaults",
                  summary: "OpenCode stepovi su vraćeni na podrazumevani preset.",
                  details: { returncode: 0, stdout: "", stderr: "" },
                });
              }}
            >
              Vrati podrazumevano
            </button>
          </div>

          <div className="form-grid">
            <label>
              Bezbednosni režim
              <CustomSelect
                value={opencode.securityMode}
                options={[
                  { value: "strict", label: "Strogo ograničen agent" },
                  { value: "workspace-write", label: "Ograničen agent sa blacklist pravilima" },
                  { value: "open", label: "Potpuno otvoren agent" },
                ]}
                onChange={(value) =>
                  setOpencode({
                    ...opencode,
                    securityMode: value,
                    securityModeLabel:
                      value === "workspace-write"
                        ? "Ograničen agent sa blacklist pravilima"
                        : value === "open"
                          ? "Potpuno otvoren agent"
                          : "Strogo ograničen agent",
                  })
                }
                ariaLabel="Izaberi bezbednosni režim OpenCode-a"
              />
            </label>
            <label>
              Autonomija
              <CustomSelect
                value={opencode.capabilityMode}
                options={[
                  { value: "read-only", label: "1. Samo čitanje fajlova" },
                  { value: "read-write", label: "2. Čitanje + izmena fajlova" },
                  { value: "confirm-commands", label: "3. Čitanje + izmena + komande uz potvrdu" },
                  { value: "auto-commands", label: "4. Čitanje + izmena + komande bez potvrde" },
                ]}
                onChange={(value) =>
                  setOpencode({
                    ...opencode,
                    capabilityMode: value,
                    capabilityModeLabel:
                      value === "read-only"
                        ? "1. Samo čitanje fajlova"
                        : value === "read-write"
                          ? "2. Čitanje + izmena fajlova"
                          : value === "auto-commands"
                            ? "4. Čitanje + izmena + komande bez potvrde"
                            : "3. Čitanje + izmena + komande uz potvrdu",
                  })
                }
                ariaLabel="Izaberi režim autonomije OpenCode-a"
              />
            </label>
            <button
              type="button"
              onClick={() =>
                void runOpenCodeAction(() =>
                  applyOpenCodeSettings({
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
                  }),
                )
              }
            >
              Sačuvaj OpenCode podešavanja
            </button>
          </div>
        </section>

        <section className="status-card wide-card runtimepilot-faceplate-module runtimepilot-advanced-module">
          <div className="runtimepilot-advanced-module-shell">
            <div className="runtime-faceplate-head">
              <span className="status-label">OpenCode instance</span>
              <strong className="status-value">{opencode.instances?.length ? `${opencode.instances.length} aktivnih instanci` : "Broj instanci nije dostupan"}</strong>
            </div>
            <div className="runtime-faceplate-copy">
              <p className="helper-text">
                Ovaj pregled koristiš kada proveravaš koliko CLI sesija stvarno radi i pod kojim PID-om.
              </p>
            </div>
            <div className="runtime-faceplate-rail runtime-faceplate-rail-stack">
              <span className="status-label">Dijagnostika</span>
              <p className="helper-text runtime-faceplate-note">
                Ako ti nešto deluje duplo otvoreno ili zaglavljeno, ovde brzo vidiš da li postoji više instanci.
              </p>
            </div>
          </div>
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
      </details>
    </>
  );
}
