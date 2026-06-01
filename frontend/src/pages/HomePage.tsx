import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageFlowCard } from "../components/PageFlowCard";
import { TelemetryPanel } from "../components/TelemetryPanel";
import {
  fetchBenchmark,
  fetchOpenCodeStatus,
  fetchServerStatus,
  fetchStatus,
  openOpenCode,
  selectRuntime,
} from "../lib/api";
import type {
  ActionResult,
  BenchmarkPayload,
  OpenCodeStatusPayload,
  ServerStatusPayload,
  StatusPayload,
} from "../lib/types";

const GENERAL_REFRESH_MS = 5000;
const BENCHMARK_REALTIME_REFRESH_MS = 1000;

function renderOpenCodeState(opencode: OpenCodeStatusPayload | null) {
  if (!opencode?.available) {
    return "Nedostupan";
  }
  if (opencode.sessionState === "launching") {
    return "Pokretanje u toku";
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

function describeRuntimeBinaryPath(binaryPath: string | null | undefined) {
  const normalized = String(binaryPath || "").trim().replace(/\//g, "\\");
  if (!normalized) {
    return null;
  }
  const parts = normalized.split("\\").filter(Boolean);
  if (!parts.length) {
    return {
      fileName: normalized,
      compactDirectory: "",
      fullPath: normalized,
    };
  }

  const fileName = parts[parts.length - 1] || normalized;
  const directoryParts = parts.slice(0, -1);
  const compactDirectory =
    directoryParts.length <= 4
      ? directoryParts.join("\\")
      : `${directoryParts.slice(0, 2).join("\\")}\\…\\${directoryParts
          .slice(-2)
          .join("\\")}`;

  return {
    fileName,
    compactDirectory,
    fullPath: normalized,
  };
}

export function HomePage({
  onOpenModels,
  onOpenOpenCode,
  onOpenServer,
  onOpenTuningLab,
}: {
  onOpenModels?: () => void;
  onOpenOpenCode?: () => void;
  onOpenServer?: () => void;
  onOpenTuningLab?: () => void;
}) {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [serverStatus, setServerStatus] = useState<ServerStatusPayload | null>(null);
  const [opencode, setOpencode] = useState<OpenCodeStatusPayload | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkPayload | null>(null);
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
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    }
  }

  async function loadBenchmarkOnly() {
    try {
      const benchmarkPayload = await fetchBenchmark();
      setBenchmark(benchmarkPayload);
    } catch {
      setBenchmark(null);
    }
  }

  async function runAction(action: () => Promise<ActionResult>) {
    try {
      const actionResult = await action();
      setResult(actionResult);
      await loadStatus();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    }
  }

  useEffect(() => {
    let active = true;
    void loadStatus();
    void loadBenchmarkOnly();

    const timer = window.setInterval(() => {
      if (active) {
        void loadStatus();
      }
    }, GENERAL_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let active = true;

    const timer = window.setInterval(() => {
      if (active) {
        void loadBenchmarkOnly();
      }
    }, BENCHMARK_REALTIME_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const serverWarning = serverStatus?.warningSummary || "";
  const runtimeBinary = describeRuntimeBinaryPath(status?.activeRuntimeBinary);

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Najbrži sledeći korak"
        summary="Početna treba da ti odmah kaže gde da nastaviš bez kopanja po tabovima. Kreni od stanja runtime-a, pa pređi na model, OpenCode ili Tuning Lab."
        steps={[
          {
            title: "Proveri runtime i model",
            detail: "Pogledaj da li su runtime server i aktivni model u zdravom stanju pre nego što kreneš dalje.",
          },
          {
            title: "Ako treba, idi na Server ili Modele",
            detail: "Server koristiš za start/stop i ručnu CLI proveru, a Modeli za download, aktivaciju i kompatibilnost.",
          },
          {
            title: "Otvori OpenCode ili Tuning Lab",
            detail: "Kad je runtime zdrav, pređi na pravi rad u OpenCode-u ili na poređenje podešavanja u Tuning Lab-u.",
          },
        ]}
        actions={
          <>
            <button type="button" className="secondary-button" onClick={onOpenServer}>
              Otvori Server
            </button>
            <button type="button" className="secondary-button" onClick={onOpenModels}>
              Otvori Modele
            </button>
            <button type="button" className="secondary-button" onClick={onOpenOpenCode}>
              Otvori OpenCode
            </button>
            <button type="button" onClick={onOpenTuningLab}>
              Otvori Tuning Lab
            </button>
          </>
        }
      />
      <div className="home-layout wide-card">
        <TelemetryPanel benchmark={benchmark} variant="home" />
        <section className="status-card system-overview-card wide-card">
          <span className="status-label">Pregled sistema</span>
          <div className="system-overview-grid">
            <article className="system-overview-item">
              <span className="system-overview-label">Stanje RuntimePilot-a</span>
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

        <div className="home-server-grid">
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
            {serverWarning ? <div className="warning-badge">Upozorenje servera: {serverWarning}</div> : null}
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
              {opencode?.sessionSummary || "Promena modela važi za novu OpenCode sesiju."}
            </p>
            <div className="inline-actions compact-actions">
              <button
                type="button"
                disabled={opencode?.canOpen === false}
                title={opencode?.openBlockedReason || undefined}
                onClick={() => void runAction(() => openOpenCode(status?.profile || opencode?.profile || "balanced"))}
              >
                {opencode?.openActionLabel || "Otvori OpenCode"}
              </button>
            </div>
          </section>
        </div>

        <div className="home-detail-grid">
          <section className="status-card">
            <span className="status-label">Sažetak servera</span>
            <strong className="status-value">
              {serverStatus?.lastReason || "Učitavam lifecycle status servera..."}
            </strong>
            <p className="helper-text">
              Status: {serverStatus?.status || "--"} | Health: {serverStatus?.health || "--"} | Port:{" "}
              {serverStatus ? String(serverStatus.port) : "--"} | Runtime: {serverStatus?.activeRuntimeLabel || "--"}
            </p>
          </section>

          <section className="status-card">
            <span className="status-label">Sažetak runtime-a</span>
            <strong className="status-value">
              {status?.runtimeSummary ?? "Učitavam runtime status..."}
            </strong>
          </section>

          <section className="status-card">
            <span className="status-label">Binar u upotrebi</span>
            <div className="runtime-binary-card">
              <strong className="status-value runtime-binary-file">
                {runtimeBinary?.fileName || "Nije potvrđeno."}
              </strong>
              {runtimeBinary?.compactDirectory ? (
                <div className="runtime-binary-location-block" title={runtimeBinary.fullPath}>
                  <span className="runtime-binary-location-label">Lokacija binara</span>
                  <span className="runtime-binary-location">{runtimeBinary.compactDirectory}</span>
                </div>
              ) : null}
            </div>
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
              {status?.turboQuantSummary ?? "Učitavam TurboQuant stanje..."}
            </strong>
            <p className="helper-text">
              {status?.turboQuantGuidance || "Učitavam TurboQuant smernice..."}
            </p>
            <p className="helper-text">
              Tehnički razlog: {status?.turboQuantReason || "nema dodatnih detalja."}
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
            <span className="status-label">Lokalni URL</span>
            <strong className="status-value">
              {status ? status.localUrl : "Učitavam lokalni backend status..."}
            </strong>
          </section>

          <section className="status-card">
            <span className="status-label">Tailscale URL</span>
            <strong className="status-value">
              {status?.tailscaleUrl || "Tailscale nije aktivan ili interfejs nije izložen kroz Tailscale."}
            </strong>
          </section>
        </div>

        <section className="status-card">
          <span className="status-label">OpenCode</span>
          <strong className="status-value">
            {opencode?.available ? "Dostupan" : "Nije dostupan"}
          </strong>
          <p className="helper-text">OpenCode config: {opencode?.configPath || "nije pronađen"}</p>
          <p className="helper-text">
            Backend veza: {opencode?.runtimeConnected ? "spremna" : "nije spremna"} |{" "}
            {opencode?.runtimeLiveReason || "Nema dodatnih runtime detalja."}
          </p>
          <p className="helper-text">
            Bezbednosni režim: {opencode?.securityModeLabel || "--"} | Autonomija:{" "}
            {opencode?.capabilityModeLabel || "--"}
          </p>
          <p className="helper-text">
            Audit: {opencode?.auditSummary || "Nema dodatnih OpenCode detalja."}
          </p>
          <p className="helper-text">
            Ako promeniš aktivni model u RuntimePilot-u, zatvori i otvori OpenCode ponovo da bi
            nova sesija preuzela taj model.
          </p>
        </section>
      </div>
      <ActionResultPanel result={result} />
    </>
  );
}
