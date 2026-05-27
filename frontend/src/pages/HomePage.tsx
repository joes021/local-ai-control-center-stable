import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import {
  fetchOpenCodeStatus,
  fetchServerStatus,
  fetchStatus,
  openOpenCode,
  selectRuntime,
} from "../lib/api";
import type {
  ActionResult,
  OpenCodeStatusPayload,
  ServerStatusPayload,
  StatusPayload,
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

export function HomePage() {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [serverStatus, setServerStatus] = useState<ServerStatusPayload | null>(null);
  const [opencode, setOpencode] = useState<OpenCodeStatusPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);

  async function loadStatus() {
    try {
      const [statusPayload, serverPayload, opencodePayload] = await Promise.all([
        fetchStatus(),
        fetchServerStatus(),
        fetchOpenCodeStatus(),
      ]);
      setStatus(statusPayload);
      setServerStatus(serverPayload);
      setOpencode(opencodePayload);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greska");
    }
  }

  async function runAction(action: () => Promise<ActionResult>) {
    try {
      const actionResult = await action();
      setResult(actionResult);
      await loadStatus();
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

  const serverWarning = serverStatus?.warningSummary || "";

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <div className="home-layout wide-card">
        <div className="home-top-grid">
          <section className="status-card system-overview-card">
            <span className="status-label">System overview</span>
            <div className="system-overview-grid">
              <article className="system-overview-item">
                <span className="system-overview-label">Control Center health</span>
                <strong className="system-overview-value">{status?.health ?? "--"}</strong>
              </article>
              <article className="system-overview-item">
                <span className="system-overview-label">Aktivan runtime</span>
                <strong className="system-overview-value">{status?.activeRuntimeLabel ?? "--"}</strong>
              </article>
              <article className="system-overview-item">
                <span className="system-overview-label">Status runtime servera</span>
                <strong className="system-overview-value">{status?.runtimeLiveStatus ?? "--"}</strong>
              </article>
              <article className="system-overview-item">
                <span className="system-overview-label">Aktivni model</span>
                <strong className="system-overview-value">{status?.activeModel ?? "--"}</strong>
              </article>
              <article className="system-overview-item">
                <span className="system-overview-label">Profil</span>
                <strong className="system-overview-value">{status?.profile ?? "--"}</strong>
              </article>
              <article className="system-overview-item">
                <span className="system-overview-label">Dostupni runtime-i</span>
                <strong className="system-overview-value">
                  {status?.availableRuntimes?.length ? status.availableRuntimes.join(", ") : "--"}
                </strong>
              </article>
            </div>
          </section>

          <section className="status-card">
            <span className="status-label">Server</span>
            <strong className="status-value">{serverStatus?.status ?? "--"}</strong>
            <div className="summary-metrics">
              <span>Port: {serverStatus ? String(serverStatus.port) : "--"}</span>
              <span>Health: {serverStatus?.health ?? "--"}</span>
              <span>Runtime: {serverStatus?.activeRuntimeLabel ?? "--"}</span>
            </div>
            {serverStatus?.requestedRuntimeLabel ? (
              <p className="helper-text">
                Izabrani runtime: {serverStatus.requestedRuntimeLabel} |{" "}
                {serverStatus.runtimeSelectionSummary || "Nema dodatnih detalja o izboru runtime-a."}
              </p>
            ) : null}
            {serverWarning ? <div className="warning-badge">Server warning: {serverWarning}</div> : null}
          </section>

          <section className="status-card">
            <span className="status-label">OpenCode</span>
            <strong className="status-value">{renderOpenCodeState(opencode)}</strong>
            <div className="summary-metrics">
              <span>Instanci: {opencode?.instanceCount ?? 0}</span>
              <span>Profil: {opencode?.profile || "--"}</span>
              <span>
                Backend: {opencode?.runtimeConnected ? "povezan" : opencode?.runtimeLiveStatus || "--"}
              </span>
            </div>
            <p className="helper-text">
              {opencode?.sessionSummary || "Promena modela vazi za novi OpenCode session."}
            </p>
            <div className="inline-actions compact-actions">
              <button
                type="button"
                disabled={opencode?.canOpen === false}
                title={opencode?.openBlockedReason || undefined}
                onClick={() => void runAction(() => openOpenCode(status?.profile || opencode?.profile || "balanced"))}
              >
                {opencode?.openActionLabel || "Open OpenCode"}
              </button>
            </div>
          </section>
        </div>

        <div className="home-detail-grid">
          <section className="status-card">
            <span className="status-label">Server summary</span>
            <strong className="status-value">
              {serverStatus?.lastReason || "Ucitavam server lifecycle status..."}
            </strong>
            <p className="helper-text">
              Status: {serverStatus?.status || "--"} | Health: {serverStatus?.health || "--"} | Port:{" "}
              {serverStatus ? String(serverStatus.port) : "--"} | Runtime: {serverStatus?.activeRuntimeLabel || "--"}
            </p>
          </section>

          <section className="status-card">
            <span className="status-label">Runtime summary</span>
            <strong className="status-value">
              {status?.runtimeSummary ?? "Ucitavam runtime status..."}
            </strong>
          </section>

          <section className="status-card">
            <span className="status-label">Binar u upotrebi</span>
            <strong className="status-value">
              {status?.activeRuntimeBinary || "Nije potvrdeno."}
            </strong>
            <p className="helper-text">
              Izvor potvrde: {status?.activeRuntimeBinarySource || "nema potvrde"}
            </p>
            <p className="helper-text">
              Izabrani runtime: {status?.requestedRuntimeLabel || "--"} |{" "}
              {status?.runtimeSelectionSummary || "Nema dodatnih detalja o izboru runtime-a."}
            </p>
            <p className="helper-text">
              Runtime health: {status?.runtimeLiveReason || "Nema dodatnih detalja."}
            </p>
          </section>

          <section className="status-card">
            <span className="status-label">TurboQuant stanje</span>
            <strong className="status-value">
              {status?.turboQuantSummary ?? "Ucitavam TurboQuant stanje..."}
            </strong>
            <p className="helper-text">
              {status?.turboQuantGuidance || "Ucitavam TurboQuant smernice..."}
            </p>
            <p className="helper-text">
              Tehnicki razlog: {status?.turboQuantReason || "nema dodatnih detalja."}
            </p>
            <div className="inline-actions">
              <button
                type="button"
                onClick={async () => {
                  const actionResult = await selectRuntime("llama.cpp");
                  setResult(actionResult);
                  await loadStatus();
                }}
              >
                Koristi llama.cpp
              </button>
              <button
                type="button"
                disabled={!status?.turboQuantRuntimeAvailable}
                onClick={async () => {
                  const actionResult = await selectRuntime("turboquant");
                  setResult(actionResult);
                  await loadStatus();
                }}
              >
                Koristi TurboQuant
              </button>
            </div>
          </section>

          <section className="status-card">
            <span className="status-label">Local URL</span>
            <strong className="status-value">
              {status ? status.localUrl : "Ucitavam lokalni backend status..."}
            </strong>
          </section>

          <section className="status-card">
            <span className="status-label">Tailscale URL</span>
            <strong className="status-value">
              {status?.tailscaleUrl || "Tailscale nije aktivan ili UI nije izlozen kroz Tailscale."}
            </strong>
          </section>
        </div>

        <section className="status-card">
          <span className="status-label">OpenCode</span>
          <strong className="status-value">
            {opencode?.available ? "Dostupan" : "Nije dostupan"}
          </strong>
          <p className="helper-text">OpenCode config: {opencode?.configPath || "nije pronadjen"}</p>
          <p className="helper-text">
            Backend veza: {opencode?.runtimeConnected ? "spremna" : "nije spremna"} |{" "}
            {opencode?.runtimeLiveReason || "Nema dodatnih runtime detalja."}
          </p>
          <p className="helper-text">
            Security rezim: {opencode?.securityModeLabel || "--"} | Autonomija:{" "}
            {opencode?.capabilityModeLabel || "--"}
          </p>
          <p className="helper-text">
            Audit: {opencode?.auditSummary || "Nema dodatnih OpenCode detalja."}
          </p>
          <p className="helper-text">
            Ako promenis aktivni model u Control Center-u, zatvori i otvori OpenCode ponovo da bi
            novi session preuzeo taj model.
          </p>
        </section>
      </div>
      <ActionResultPanel result={result} />
    </>
  );
}
