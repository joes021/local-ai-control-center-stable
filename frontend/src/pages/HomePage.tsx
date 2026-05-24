import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { StatusCard } from "../components/StatusCard";
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

function renderOpenCodeActionLabel(opencode: OpenCodeStatusPayload | null) {
  if (opencode?.sessionState === "app-only") {
    return "Pripremi backend za OpenCode";
  }
  if (opencode?.sessionState === "connected") {
    return "OpenCode je vec otvoren";
  }
  return "Open OpenCode";
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
      {error ? <div className="error-panel">{error}</div> : null}
      <StatusCard label="Control Center health" value={status?.health ?? "--"} />
      <StatusCard label="Aktivni model" value={status?.activeModel ?? "--"} />
      <StatusCard label="Profil" value={status?.profile ?? "--"} />
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
      <StatusCard label="Aktivan runtime" value={status?.activeRuntimeLabel ?? "--"} />
      <StatusCard
        label="Dostupni runtime-i"
        value={status?.availableRuntimes?.length ? status.availableRuntimes.join(", ") : "--"}
      />
      <StatusCard label="Status runtime servera" value={status?.runtimeLiveStatus ?? "--"} />
      <section className="status-card">
        <span className="status-label">OpenCode</span>
        <strong className="status-value">{renderOpenCodeState(opencode)}</strong>
        <div className="summary-metrics">
          <span>Instanci: {opencode?.instanceCount ?? 0}</span>
          <span>Profil: {opencode?.profile || "--"}</span>
          <span>Backend: {opencode?.runtimeConnected ? "povezan" : opencode?.runtimeLiveStatus || "--"}</span>
        </div>
        <p className="helper-text">
          {opencode?.sessionSummary || "Promena modela vazi za novi OpenCode session."}
        </p>
        <div className="inline-actions compact-actions">
          <button
            type="button"
            onClick={() => void runAction(() => openOpenCode(status?.profile || opencode?.profile || "balanced"))}
          >
            {renderOpenCodeActionLabel(opencode)}
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Server summary</span>
        <strong className="status-value">
          {serverStatus?.lastReason || "Ucitavam server lifecycle status..."}
        </strong>
        <p className="helper-text">
          Status: {serverStatus?.status || "--"} | Health: {serverStatus?.health || "--"} | Port:{" "}
          {serverStatus ? String(serverStatus.port) : "--"} | Runtime: {serverStatus?.activeRuntimeLabel || "--"}
        </p>
      </section>
      <section className="status-card wide-card">
        <span className="status-label">Runtime summary</span>
        <strong className="status-value">
          {status?.runtimeSummary ?? "Ucitavam runtime status..."}
        </strong>
      </section>
      <section className="status-card wide-card">
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
      <section className="status-card wide-card">
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
      <section className="status-card wide-card">
        <span className="status-label">Local URL</span>
        <strong className="status-value">
          {status ? status.localUrl : "Ucitavam lokalni backend status..."}
        </strong>
      </section>
      <section className="status-card wide-card">
        <span className="status-label">Tailscale URL</span>
        <strong className="status-value">
          {status?.tailscaleUrl || "Tailscale nije aktivan ili UI nije izlozen kroz Tailscale."}
        </strong>
      </section>
      <section className="status-card wide-card">
        <span className="status-label">OpenCode</span>
        <strong className="status-value">
          {opencode?.available ? "Dostupan" : "Nije dostupan"}
        </strong>
        <p className="helper-text">
          OpenCode config: {opencode?.configPath || "nije pronadjen"}
        </p>
        <p className="helper-text">
          Backend veza: {opencode?.runtimeConnected ? "spremna" : "nije spremna"} |{" "}
          {opencode?.runtimeLiveReason || "Nema dodatnih runtime detalja."}
        </p>
        <p className="helper-text">
          Security režim: {opencode?.securityModeLabel || "--"} | Autonomija:{" "}
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
      <ActionResultPanel result={result} />
    </>
  );
}
