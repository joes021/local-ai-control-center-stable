import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import { RuntimePilotIcon } from "../components/RuntimePilotIcon";
import {
  RuntimePilotActionDeck,
  type RuntimePilotActionDeckItem,
} from "../components/shell/RuntimePilotActionDeck";
import {
  RuntimePilotStatusDeck,
  type RuntimePilotStatusDeckItem,
} from "../components/shell/RuntimePilotStatusDeck";
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

function lastPathSegment(path: string | null | undefined) {
  if (!path) {
    return "Nije postavljen";
  }
  const trimmed = path.replace(/[\\/]+$/, "");
  if (!trimmed) {
    return path;
  }
  const segments = trimmed.split(/[\\/]+/).filter(Boolean);
  return segments[segments.length - 1] || trimmed;
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

  function loadStepPreset(preset: OpenCodeStepPreset) {
    setStepEditor({ ...preset.steps });
    setResult({
      status: "ok",
      action: "load-opencode-step-preset",
      summary: `OpenCode preset ${preset.name} je učitan u editor.`,
      details: { returncode: 0, stdout: "", stderr: "" },
    });
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
  const currentInstance = opencode.instances?.[0];
  const directActionLabel = opencode.openActionLabel || "Otvori OpenCode";
  const bootstrapActionLabel = opencode.bootstrapActionLabel || "Instaliraj ili popravi OpenCode";
  const workspaceLabel = lastPathSegment(opencode.workingDirectory || opencode.launchPreview.workingDirectory);
  const managedModelLabel = opencode.launchPreview.managedConfig.model || "Model nije postavljen";
  const managedProviderLabel = opencode.launchPreview.managedConfig.selectedProvider || "nije prepoznat";
  const managedBaseUrlLabel = opencode.launchPreview.managedConfig.localProviderBaseUrl || "nije pronađen";
  const instanceLabel = currentInstance?.name || "Sesija još nije otvorena";
  const instancePidLabel = currentInstance?.pid ?? "nepoznat";
  const sessionSignalTitle = opencode.runtimeConnected ? "Povezano sa runtime-om" : openCodeStateTitle;
  const sessionSignalSummary = opencode.runtimeConnected
    ? "Korisnik odmah vidi da li je agent stvarno spreman za rad."
    : opencode.runtimeLiveReason || "OpenCode još čeka zdrav runtime signal.";
  const resultSignalTitle = result?.status === "ok" ? "Otvaranje potvrđeno" : "Desktop app + portal signal";
  const resultSignalSummary = result?.summary || "Otvaranje ne sme biti gluvo; status mora da potvrdi ishod.";

  const openAdvancedTools = () => {
    const details = document.getElementById("opencode-advanced-tools");
    if (details instanceof HTMLDetailsElement) {
      details.open = true;
      details.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const scrollToActionResult = () => {
    const panel = document.getElementById("opencode-action-result");
    if (panel) {
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const openCodeStatusItems: RuntimePilotStatusDeckItem[] = [
    {
      id: "session",
      label: "Sesija",
      value: openCodeStateTitle,
      detail: openCodeStateSummary,
      action: "CLI i GUI signal",
      icon: "opencode",
      accent: "rgba(242, 184, 75, 0.36)",
    },
    {
      id: "runtime",
      label: "Runtime",
      value: sessionSignalTitle,
      detail: sessionSignalSummary,
      action: "Veza sa engine-om",
      icon: "runtime",
      accent: "rgba(109, 172, 255, 0.34)",
    },
    {
      id: "workspace",
      label: "Workspace",
      value: workspaceLabel,
      detail: opencode.workingDirectory || opencode.launchPreview.workingDirectory,
      action: "Radni direktorijum",
      icon: "workflows",
      accent: "rgba(88, 222, 193, 0.34)",
    },
    {
      id: "managed-config",
      label: "Managed config sažetak",
      value: managedModelLabel,
      detail: `Provider ${managedProviderLabel} | Base URL ${managedBaseUrlLabel}`,
      action: "Model i provider",
      icon: "models",
      accent: "rgba(205, 162, 255, 0.34)",
    },
    {
      id: "last-result",
      label: "Poslednja akcija",
      value: resultSignalTitle,
      detail: resultSignalSummary,
      action: "Skok na rezultat",
      icon: "logs",
      accent: "rgba(255, 129, 177, 0.34)",
      onClick: scrollToActionResult,
    },
  ];

  const openCodeActionItems: RuntimePilotActionDeckItem[] = [
    {
      id: "open-direct",
      code: "GUI",
      title: directActionLabel,
      subtitle: "OTVORI DESKTOP APP",
      icon: "opencode",
      tone: "primary",
      detail: opencode.openBlockedReason || "Koristi aktivni managed config i trenutni workspace.",
      disabled: opencode.canOpen === false,
      onClick: () =>
        void runOpenCodeAction(() => openOpenCode(opencode.profile || "balanced", "direct")),
    },
    {
      id: "open-isolated",
      code: "ISO",
      title: "Izolovan workspace",
      subtitle: "OTVORI U IZOLOVANOM WORKSPACE-U",
      icon: "workflows",
      detail: "Odvojen probni workspace bez gaženja glavnog radnog foldera.",
      disabled: opencode.canOpen === false,
      onClick: () =>
        void runOpenCodeAction(() => openOpenCode(opencode.profile || "balanced", "isolated")),
    },
    {
      id: "bootstrap",
      code: "FIX",
      title: bootstrapActionLabel,
      subtitle: "SERVIS + BOOTSTRAP",
      icon: "repair",
      detail: opencode.bootstrapBlockedReason || "Kad GUI ili launcher nisu spremni, ovde kreće popravka.",
      disabled: opencode.canBootstrap === false,
      onClick: () => void runOpenCodeAction(bootstrapOpenCode),
    },
    {
      id: "jump-result",
      code: "LOG",
      title: "Skok na rezultat",
      subtitle: "POSLEDNJA AKCIJA",
      icon: "logs",
      detail: "Posle klika prvo ovde čitaš da li je otvaranje uspelo i šta je sledeći korak.",
      onClick: scrollToActionResult,
    },
    {
      id: "advanced-tools",
      code: "CLI",
      title: "Napredni alati",
      subtitle: "KOMANDA + SIGURNOST",
      icon: "settings",
      detail: "Launcher preview, env, presetovi koraka i lista instanci ostaju ispod.",
      onClick: openAdvancedTools,
    },
  ];

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <PageFlowCard
        title="OpenCode radni tok"
        summary="Prvo potvrdi sesiju i runtime signal, zatim otvori GUI ili izolovan workspace, pa rezultat odmah pročitaj u panelu ispod bez lutanja kroz sporedne kartice."
        steps={[
          {
            title: "Proveri da li je sesija spremna",
            detail: "Status deck odmah pokazuje da li je OpenCode dostupan, da li vidi runtime i koji workspace koristi.",
          },
          {
            title: "Otvori GUI ili izolovan workspace",
            detail: "Direktni GUI koristi glavni workspace, a izolovan tok pali odvojen probni prostor za bezbedan rad.",
          },
          {
            title: "Pročitaj rezultat ili otvori servis",
            detail: "Poslednja akcija i napredni alati ostaju odmah ispod kao jasno mesto za ishod i dijagnostiku.",
          },
        ]}
      />

      <RuntimePilotStatusDeck
        eyebrow="Status dashboard"
        title="Sesija, workspace i managed config"
        helper="Pet kartica odmah kaže da li je OpenCode spreman, gde radi, koji model koristi i šta se desilo posle poslednjeg klika."
        items={openCodeStatusItems}
      />

      <RuntimePilotActionDeck
        eyebrow="Akcije"
        title="Otvori GUI, rezultat ili servis"
        helper="Ovde su samo stvarni klikovi: direktan GUI, izolovan workspace, popravka, rezultat i servisni alati."
        items={openCodeActionItems}
      />

      <section className="status-card wide-card runtimepilot-faceplate-module runtimepilot-opencode-shell">
        <div className="section-header">
          <div>
            <span className="status-label">Managed config i sesija</span>
            <strong className="status-value">Glavni OpenCode readout bez starog trokolonskog rack-a</strong>
          </div>
        </div>
        <p className="helper-text">
          Ovo je centralni pregled za OpenCode: jedna zona za stanje sesije, druga za managed config, a treća za poslednju potvrdu posle klika.
        </p>
        <div className="runtimepilot-opencode-summary-grid">
          <article className="runtimepilot-opencode-summary-card">
            <span className="status-label">Sesija i runtime</span>
            <strong className="status-value">{sessionSignalTitle}</strong>
            <p className="helper-text">{sessionSignalSummary}</p>
            <div className="summary-metrics">
              <span>Sesija: {opencode.sessionState}</span>
              <span>Runtime: {opencode.runtimeConnected ? "povezan" : opencode.runtimeLiveStatus || "--"}</span>
              <span>PID i instanca: {instancePidLabel} · {instanceLabel}</span>
            </div>
          </article>
          <article className="runtimepilot-opencode-summary-card">
            <span className="status-label">Managed config sažetak</span>
            <strong className="status-value">{managedModelLabel}</strong>
            <p className="helper-text">
              Provider: {managedProviderLabel} · Base URL: {managedBaseUrlLabel}
            </p>
            <div className="summary-metrics">
              <span>Workspace: {workspaceLabel}</span>
              <span>Profil: {opencode.profile || "--"}</span>
              <span>Instanci: {opencode.instanceCount ?? 0}</span>
            </div>
          </article>
          <article className="runtimepilot-opencode-summary-card">
            <span className="status-label">Poslednja akcija</span>
            <strong className="status-value">{resultSignalTitle}</strong>
            <p className="helper-text">
              Posle klika prvo ovde čitaš da li je otvaranje uspelo i šta je sledeći korak.
            </p>
            <p className="helper-text">{resultSignalSummary}</p>
          </article>
        </div>
      </section>

      <div id="opencode-action-result">
        <ActionResultPanel result={result} />
      </div>

      <details
        id="opencode-advanced-tools"
        className="status-card wide-card runtimepilot-section-shell runtimepilot-advanced-disclosure"
      >
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
            <p className="helper-text runtimepilot-opencode-generation-strip">
              Efektivna local-lacc inference podrazumevana podešavanja: {opencode.launchPreview.generationSummary}
            </p>
          ) : null}
          <div className="runtimepilot-opencode-service-bay">
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-opencode-service-panel">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">FLOW</span>
                <span className="status-label">Servisni tok OpenCode-a</span>
              </div>
              <strong className="status-value">Komande i launcher</strong>
              <p className="helper-text">
                Ovde dobijaš ručni ekvivalent otvaranja OpenCode-a bez razvlačenja komandi preko cele
                širine. Prvo vidiš launcher tok, pa tek onda precizne varijante za kopiranje.
              </p>
              {opencode.launchPreview.generationSummary ? (
                <p className="helper-text">
                  Efektivna local-lacc inference podrazumevana podešavanja: {opencode.launchPreview.generationSummary}
                </p>
              ) : null}
              <div className="summary-metrics">
                <span>Launcher: spreman</span>
                <span>Provider: {managedProviderLabel}</span>
                <span>Model: {managedModelLabel}</span>
              </div>
            </article>
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-opencode-service-panel">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">ACT</span>
                <span className="status-label">Transport</span>
              </div>
              <strong className="status-value">Kopiranje bez gužve</strong>
              <p className="helper-text">
                Dugmad su ovde kratka i jasna: klik odmah daje komandu u clipboard, a rezultat se vidi u
                panelu ispod glavnog OpenCode toka.
              </p>
              <div className="runtimepilot-opencode-transport-rail">
                <button
                  type="button"
                  className="action-button-soft deck-control-button deck-control-button-secondary"
                  onClick={() => void copyText(opencode.launchPreview.launcherCommand, "Launcher komanda")}
                >
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="logs" />
                  </span>
                  <span className="deck-control-copy">Kopiraj launcher</span>
                </button>
                <button
                  type="button"
                  className="action-button-soft deck-control-button deck-control-button-secondary"
                  onClick={() => void copyText(opencode.launchPreview.powershellCommand, "PowerShell prikaz")}
                >
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="opencode" />
                  </span>
                  <span className="deck-control-copy">Kopiraj PowerShell</span>
                </button>
              </div>
            </article>
          </div>
          <div className="command-preview-grid runtimepilot-opencode-command-grid">
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
                Preset menja samo OpenCode korake. Bezbednosni režim, autonomija i radni
                direktorijum ostaju odvojena podešavanja.
              </p>
            </div>
            <div className="runtime-faceplate-rail runtime-faceplate-rail-stack">
              <span className="status-label">Šta menjaš</span>
              <p className="helper-text runtime-faceplate-note">
                Ovde oblikuješ ponašanje agenta, ne runtime server. Zato su stepovi, sigurnost i autonomija grupisani zajedno.
              </p>
            </div>
          </div>

          <div className="runtimepilot-opencode-service-bay">
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-opencode-service-panel">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">STEP</span>
                <span className="status-label">Servisni tok OpenCode-a</span>
              </div>
              <strong className="status-value">Presetovi i ponašanje agenta</strong>
              <p className="helper-text">
                Presetovi služe da brzo vratiš provereni OpenCode radni tok, a brojčana polja ispod da ga
                fino doteraš bez traženja po celoj strani.
              </p>
            </article>
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-opencode-service-panel">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">SAFE</span>
                <span className="status-label">Kontrolni kanal</span>
              </div>
              <strong className="status-value">Bezbednost i autonomija</strong>
              <p className="helper-text">
                Režim bezbednosti i autonomije su odmah uz presetove da korisnik bez lutanja vidi šta
                menja ponašanje agenta, a šta njegov nivo slobode.
              </p>
            </article>
          </div>

          <div className="model-list runtimepilot-opencode-preset-grid">
            {stepSchema.builtInPresets.map((preset) => (
              <article className="model-item runtimepilot-opencode-preset-card" key={preset.id}>
                <div className="model-item-header">
                  <div>
                    <strong>{formatPresetLabel(preset)}</strong>
                  </div>
                  <div className="inline-actions runtimepilot-opencode-preset-actions">
                    <button
                      type="button"
                      className="action-button-soft deck-control-button deck-control-button-secondary"
                      onClick={() => loadStepPreset(preset)}
                    >
                      <span className="deck-control-symbol" aria-hidden="true">
                        <RuntimePilotIcon name="play" />
                      </span>
                      <span className="deck-control-copy">Učitaj preset</span>
                    </button>
                  </div>
                </div>
              </article>
            ))}
            {stepSchema.userPresets.map((preset) => (
              <article className="model-item runtimepilot-opencode-preset-card" key={preset.id}>
                <div className="model-item-header">
                  <div>
                    <strong>{formatPresetLabel(preset)}</strong>
                  </div>
                  <div className="inline-actions runtimepilot-opencode-preset-actions">
                    <button
                      type="button"
                      className="action-button-soft deck-control-button deck-control-button-secondary"
                      onClick={() => loadStepPreset(preset)}
                    >
                      <span className="deck-control-symbol" aria-hidden="true">
                        <RuntimePilotIcon name="play" />
                      </span>
                      <span className="deck-control-copy">Učitaj preset</span>
                    </button>
                    <button
                      type="button"
                      className="danger-button deck-control-button deck-control-button-secondary runtimepilot-opencode-danger-button"
                      onClick={() => void runOpenCodeAction(() => deleteOpenCodeStepPreset(preset.id))}
                    >
                      <span className="deck-control-symbol" aria-hidden="true">
                        <RuntimePilotIcon name="stop" />
                      </span>
                      <span className="deck-control-copy">Obriši preset</span>
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="runtimepilot-opencode-field-stack runtimepilot-opencode-control-rack">
            <section className="form-grid runtimepilot-opencode-control-card runtimepilot-opencode-step-card">
              <div className="runtimepilot-opencode-control-head">
                <span className="runtimepilot-opencode-control-code">STEP</span>
                <span className="status-label">Koraci po toku</span>
                <strong className="runtimepilot-opencode-control-title">Koliko koraka agent dobija za svaki tip posla</strong>
              </div>
              <p className="helper-text">
                Ovde podešavaš OpenCode step budžet: koliko agent sme da troši na izradu, plan,
                opšti tok i istraživanje.
              </p>
              <div className="form-grid runtimepilot-opencode-step-grid">
                <label className="runtimepilot-opencode-compact-field runtimepilot-opencode-step-field">
                  <span className="runtimepilot-opencode-step-field-label">Izrada</span>
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
                  <span className="runtimepilot-opencode-step-field-note">
                    Kod, implementacija i završavanje konkretnog zadatka.
                  </span>
                </label>
                <label className="runtimepilot-opencode-compact-field runtimepilot-opencode-step-field">
                  <span className="runtimepilot-opencode-step-field-label">Plan</span>
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
                  <span className="runtimepilot-opencode-step-field-note">
                    Razlaganje posla, plan rada i sledeći koraci.
                  </span>
                </label>
                <label className="runtimepilot-opencode-compact-field runtimepilot-opencode-step-field">
                  <span className="runtimepilot-opencode-step-field-label">Opšte</span>
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
                  <span className="runtimepilot-opencode-step-field-note">
                    Standardan rad kad zadatak nije čisto build ili plan.
                  </span>
                </label>
                <label className="runtimepilot-opencode-compact-field runtimepilot-opencode-step-field">
                  <span className="runtimepilot-opencode-step-field-label">Istraživanje</span>
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
                  <span className="runtimepilot-opencode-step-field-note">
                    Dublje kopanje, analiza opcija i skupljanje konteksta.
                  </span>
                </label>
              </div>
            </section>

            <section className="form-grid runtimepilot-opencode-control-card runtimepilot-opencode-form-cluster">
              <div className="runtimepilot-opencode-control-head">
                <span className="runtimepilot-opencode-control-code">PSET</span>
                <span className="status-label">Preset kanal</span>
                <strong className="runtimepilot-opencode-control-title">Sačuvaj ovu kombinaciju kao preset</strong>
              </div>
              <p className="helper-text">
                Upiši ime preset-a, pa ovaj raspored stepova možeš kasnije odmah da vratiš bez
                ponovnog ručnog nameštanja.
              </p>
              <label className="runtimepilot-opencode-compact-field">
                Ime preset-a
                <input
                  placeholder="Ime OpenCode preset-a"
                  value={presetName}
                  onChange={(event) => setPresetName(event.target.value)}
                />
              </label>
              <div className="runtimepilot-opencode-transport-rail runtimepilot-opencode-inline-transport runtimepilot-opencode-form-actions">
                <button
                  type="button"
                  className="action-button deck-control-button deck-control-button-primary"
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
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="memory" />
                  </span>
                  <span className="deck-control-copy">Sačuvaj preset</span>
                </button>
                <button
                  type="button"
                  className="action-button-soft deck-control-button deck-control-button-secondary"
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
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="reload" />
                  </span>
                  <span className="deck-control-copy">Vrati podrazumevano</span>
                </button>
              </div>
            </section>

            <section className="form-grid runtimepilot-opencode-control-card runtimepilot-opencode-settings-grid">
              <div className="runtimepilot-opencode-control-head">
                <span className="runtimepilot-opencode-control-code">SAFE</span>
                <span className="status-label">Bezbednosni kanal</span>
                <strong className="runtimepilot-opencode-control-title">Sloboda i ograničenja OpenCode agenta</strong>
              </div>
              <p className="helper-text">
                Ovaj deo određuje šta agent sme da dira i koliko autonomno sme da izvršava komande
                bez dodatne potvrde.
              </p>
              <div className="runtimepilot-opencode-settings-row">
                <label className="runtimepilot-opencode-compact-field">
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
                <label className="runtimepilot-opencode-compact-field">
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
              </div>
              <div className="runtimepilot-opencode-transport-rail runtimepilot-opencode-inline-transport runtimepilot-opencode-settings-actions">
                <button
                  type="button"
                  className="action-button deck-control-button deck-control-button-primary"
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
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="control" />
                  </span>
                  <span className="deck-control-copy">Sačuvaj OpenCode podešavanja</span>
                </button>
              </div>
            </section>
          </div>
        </section>

        <section className="status-card wide-card runtimepilot-faceplate-module runtimepilot-advanced-module">
          <div className="runtimepilot-advanced-module-shell">
            <div className="runtime-faceplate-head">
              <span className="status-label">OpenCode sesije</span>
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
          <div className="runtimepilot-opencode-service-bay">
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-opencode-service-panel">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">INST</span>
                <span className="status-label">Pregled procesa</span>
              </div>
              <strong className="status-value">Ko je stvarno otvoren</strong>
              <p className="helper-text">
                Ovaj deo služi za brz odgovor na pitanje da li zaista postoji jedna, više ili nijedna
                OpenCode sesija.
              </p>
            </article>
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-opencode-service-panel">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">PID</span>
                <span className="status-label">Čitanje rezultata</span>
              </div>
              <strong className="status-value">Instance i komandna linija</strong>
              <p className="helper-text">
                Ako primetiš duplo otvaranje ili zaglavljenu sesiju, ovde najbrže vidiš PID i komandu
                pod kojom je proces pokrenut.
              </p>
            </article>
          </div>
          {opencode.instances?.length ? (
            <div className="model-list runtimepilot-opencode-instance-grid">
              {opencode.instances.map((instance, index) => (
                <article className="model-item runtimepilot-opencode-instance-card" key={`${instance.pid ?? "instance"}-${index}`}>
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
