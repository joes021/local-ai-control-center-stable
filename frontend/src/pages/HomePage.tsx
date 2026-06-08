import { useEffect, useState } from "react";

import { PrimaryFlowCard } from "../components/PrimaryFlowCard";
import { RuntimePilotIcon } from "../components/RuntimePilotIcon";
import { TelemetryPanel } from "../components/TelemetryPanel";
import { fetchBenchmark, fetchOpenCodeStatus, fetchServerStatus, fetchStatus, openOpenCode } from "../lib/api";
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

export function HomePage({
  onOpenBenchmark,
  onOpenCompatibility,
  onOpenModels,
  onOpenOpenCode,
  onOpenProjectMemory,
  onOpenServer,
  onOpenTuningLab,
  onStartGuidedFlow,
}: {
  onOpenBenchmark?: () => void;
  onOpenCompatibility?: () => void;
  onOpenModels?: () => void;
  onOpenOpenCode?: () => void;
  onOpenProjectMemory?: () => void;
  onOpenServer?: () => void;
  onOpenTuningLab?: () => void;
  onStartGuidedFlow?: () => void;
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

  const runtimeStateTitle = status?.activeRuntimeLabel || serverStatus?.activeRuntimeLabel || "Runtime nije izabran";
  const runtimeStateSummary =
    status?.runtimeSummary ||
    serverStatus?.lastReason ||
    "Prvo proveri runtime stanje pre izbora modela i pre pokretanja OpenCode rada.";
  const modelStateTitle =
    status?.activeModel && status.activeModel.trim() && status.activeModel.trim() !== "--"
      ? status.activeModel.trim()
      : "Nema aktivnog modela";
  const modelStateSummary =
    modelStateTitle === "Nema aktivnog modela"
      ? "Prvo izaberi ili dodaj lokalni model, pa tek onda pređi na OpenCode rad."
      : `Runtime: ${status?.activeRuntimeLabel || "--"} | Profil: ${status?.profile || "--"}.`;
  const openCodeStateTitle = renderOpenCodeState(opencode);
  const openCodeStateSummary =
    opencode?.sessionSummary ||
    "Kada su runtime i model zdravi, ovde prelaziš na konkretan rad, taskove i rezultate.";

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <section className="status-card wide-card runtimepilot-home-intro runtimepilot-section-shell runtimepilot-faceplate-module">
        <div className="section-header">
          <div>
            <span className="status-label">Komandni pregled</span>
            <strong className="status-value">Nastavi direktan rad</strong>
            <p className="helper-text">Komandni ekran za tri glavna toka: Runtime, Lokalni model i OpenCode.</p>
          </div>
          <div className="inline-actions compact-actions">
            <button type="button" className="action-button" onClick={onStartGuidedFlow}>
              Vodi me redom
            </button>
            <button type="button" className="action-button-soft" onClick={onOpenTuningLab}>
              Otvori Tuning Lab
            </button>
          </div>
        </div>
        <p className="helper-text">
          Početna sada služi samo za tri glavna toka: prvo proveri runtime, zatim promeni lokalni model,
          pa pređi u OpenCode. Sve drugo je sekundarni alat kada ti zaista zatreba.
        </p>
        <div className="runtimepilot-home-signal-row">
          <article className="runtimepilot-home-signal-chip">
            <span className="status-label">Runtime</span>
            <strong>{runtimeStateTitle}</strong>
            <p className="helper-text">{status?.runtimeLiveStatus || serverStatus?.status || "Čeka signal"}</p>
          </article>
          <article className="runtimepilot-home-signal-chip">
            <span className="status-label">Lokalni model</span>
            <strong>{modelStateTitle}</strong>
            <p className="helper-text">{status?.profile || "Profil još nije potvrđen"}</p>
          </article>
          <article className="runtimepilot-home-signal-chip">
            <span className="status-label">OpenCode</span>
            <strong>{openCodeStateTitle}</strong>
            <p className="helper-text">{opencode?.runtimeConnected ? "CLI povezan sa runtime-om" : "Čeka otvaranje sesije"}</p>
          </article>
        </div>
      </section>

      <section className="status-card wide-card primary-flow-sequence-rail runtimepilot-section-shell runtimepilot-faceplate-module">
        <div className="primary-flow-sequence-head">
          <span className="status-label">Redosled glavnog rada</span>
          <span className="primary-flow-sequence-copy">Runtime → Lokalni model → OpenCode</span>
        </div>
        <div className="primary-flow-sequence-row" aria-label="Glavni tok rada">
          <span className="primary-flow-sequence-chip">
            <strong>1</strong>
            <span>Runtime</span>
          </span>
          <span className="primary-flow-sequence-chip">
            <strong>2</strong>
            <span>Lokalni model</span>
          </span>
          <span className="primary-flow-sequence-chip">
            <strong>3</strong>
            <span>OpenCode</span>
          </span>
        </div>
      </section>

      <div className="primary-flow-grid wide-card">
        <PrimaryFlowCard
          eyebrow="Runtime"
          title="Pokreni ili proveri engine"
          stateTitle={runtimeStateTitle}
          stateSummary={runtimeStateSummary}
          icon="server"
          primaryLabel="Glavna akcija"
          primaryActionLabel="Otvori Runtime"
          primaryActionIcon="play"
          onPrimaryAction={() => onOpenServer?.()}
          secondaryLabel="Sekundarna akcija"
          secondaryActionLabel="Promeni runtime"
          secondaryActionIcon="play"
          onSecondaryAction={() => onOpenServer?.()}
          resultLabel="Rezultat posle klika"
          resultSummary="Otvara se Runtime ekran sa health signalom, start/restart kontrolama i naprednim runtime podešavanjima."
          stateMeta={
            <>
              <span>Health: {serverStatus?.health || status?.health || "--"}</span>
              <span>Server: {serverStatus?.status || "--"}</span>
              <span>Runtime signal: {status?.runtimeLiveStatus || "--"}</span>
            </>
          }
        />

        <PrimaryFlowCard
          eyebrow="Lokalni model"
          title="Izaberi model za rad"
          stateTitle={modelStateTitle}
          stateSummary={modelStateSummary}
          icon="models"
          primaryLabel="Glavna akcija"
          primaryActionLabel="Otvori Modele"
          primaryActionIcon="play"
          onPrimaryAction={() => onOpenModels?.()}
          secondaryLabel="Sekundarna akcija"
          secondaryActionLabel="Proveri kompatibilnost"
          secondaryActionIcon="play"
          onSecondaryAction={() => onOpenCompatibility?.()}
          resultLabel="Rezultat posle klika"
          resultSummary="Otvara se fokusirani picker sa aktivnim modelom, lokalnim GGUF-ovima i proverom da li model staje u mašinu."
          stateMeta={
            <>
              <span>Runtime: {status?.activeRuntimeLabel || "--"}</span>
              <span>Profil: {status?.profile || "--"}</span>
              <span>Katalog: lokalni + spremni za download</span>
            </>
          }
        />

        <PrimaryFlowCard
          eyebrow="OpenCode"
          title="Pređi na konkretan rad"
          stateTitle={openCodeStateTitle}
          stateSummary={openCodeStateSummary}
          icon="opencode"
          primaryLabel="Glavna akcija"
          primaryActionLabel={opencode?.openActionLabel || "Otvori OpenCode"}
          primaryActionIcon="play"
          onPrimaryAction={() =>
            void runAction(async () => {
              const actionResult = await openOpenCode(
                status?.profile || opencode?.profile || "balanced",
                "direct",
              );
              if (actionResult.status === "ok") {
                onOpenOpenCode?.();
              }
              return actionResult;
            })
          }
          primaryDisabled={opencode?.canOpen === false}
          primaryTitle={opencode?.openBlockedReason || undefined}
          secondaryLabel="Sekundarna akcija"
          secondaryActionLabel="Otvori u izolovanom workspace-u"
          secondaryActionIcon="play"
          onSecondaryAction={() =>
            void runAction(async () => {
              const actionResult = await openOpenCode(
                status?.profile || opencode?.profile || "balanced",
                "isolated",
              );
              if (actionResult.status === "ok") {
                onOpenOpenCode?.();
              }
              return actionResult;
            })
          }
          secondaryDisabled={opencode?.canOpen === false}
          secondaryTitle={opencode?.openBlockedReason || undefined}
          resultLabel="Rezultat posle klika"
          resultSummary="Otvaraš ili direktan OpenCode nad pravim projektom, ili izolovani workspace za bezbedan probni rad bez diranja glavnog foldera."
          stateMeta={
            <>
              <span>Instanci: {opencode?.instanceCount ?? 0}</span>
              <span>Profil: {opencode?.profile || status?.profile || "--"}</span>
              <span>Backend: {opencode?.runtimeConnected ? "povezan" : "nije povezan"}</span>
            </>
          }
          liveResult={
            result ? (
              <div className="primary-flow-inline-result">
                <strong>{result.status === "ok" ? "Poslednja OpenCode akcija" : "Poslednji signal"}</strong>
                <p className="helper-text">{result.summary}</p>
              </div>
            ) : null
          }
        />
      </div>

      <div className="runtimepilot-home-support-stack wide-card">
        <TelemetryPanel benchmark={benchmark} variant="home" />

        <section className="status-card runtimepilot-home-support-card runtimepilot-section-shell runtimepilot-faceplate-module">
          <div className="runtimepilot-secondary-tools-layout">
            <div className="runtimepilot-secondary-tools-copy">
              <span className="status-label">Sekundarni alati</span>
              <strong className="status-value">Kad osnovni tok radi, dalje ideš kroz Više</strong>
              <p className="helper-text">
                Benchmark, Telemetrija, Tuning Lab, Project Memory, Kompatibilnost i ostali alati ostaju tu,
                ali više ne guše prvi ekran. Otvaraj ih tek kada ti stvarno trebaju analiza, poređenje ili fino podešavanje.
              </p>
            </div>
            <div className="runtimepilot-secondary-tools-bay">
              <article className="runtimepilot-secondary-tool-chip">
                <span className="status-label">Benchmark</span>
                <strong>Izmeri brzinu i uporedi run-ove</strong>
                <p className="helper-text">Za throughput, latenciju i istoriju rezultata.</p>
                <button type="button" className="runtimepilot-secondary-tool-link" onClick={onOpenBenchmark}>
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="play" />
                  </span>
                  <span className="deck-control-copy">Otvori Benchmark</span>
                </button>
              </article>
              <article className="runtimepilot-secondary-tool-chip">
                <span className="status-label">Tuning Lab</span>
                <strong>Traži bolju kombinaciju parametara</strong>
                <p className="helper-text">Za batch testove, slotove i izbor pobedničkog seta.</p>
                <button type="button" className="runtimepilot-secondary-tool-link" onClick={onOpenTuningLab}>
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="play" />
                  </span>
                  <span className="deck-control-copy">Otvori Tuning Lab</span>
                </button>
              </article>
              <article className="runtimepilot-secondary-tool-chip">
                <span className="status-label">Project Memory</span>
                <strong>Sačuvaj fokus zadatka</strong>
                <p className="helper-text">Za cilj, pravila i sledeće korake koje agent ne sme da izgubi.</p>
                <button type="button" className="runtimepilot-secondary-tool-link" onClick={onOpenProjectMemory}>
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="play" />
                  </span>
                  <span className="deck-control-copy">Otvori Project Memory</span>
                </button>
              </article>
              <article className="runtimepilot-secondary-tool-chip">
                <span className="status-label">Kompatibilnost</span>
                <strong>Proveri da li model staje</strong>
                <p className="helper-text">Za VRAM fit, kontekst i izbor bez nagađanja.</p>
                <button type="button" className="runtimepilot-secondary-tool-link" onClick={onOpenCompatibility}>
                  <span className="deck-control-symbol" aria-hidden="true">
                    <RuntimePilotIcon name="play" />
                  </span>
                  <span className="deck-control-copy">Otvori kompatibilnost</span>
                </button>
              </article>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
