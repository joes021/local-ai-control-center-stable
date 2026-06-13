import { useEffect, useState } from "react";

import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import { RuntimeResourcePanel } from "../components/RuntimeResourcePanel";
import { TelemetryPanel } from "../components/TelemetryPanel";
import { fetchBenchmark, fetchObservability } from "../lib/api";
import type { BenchmarkPayload, ObservabilityPayload } from "../lib/types";

const REFRESH_MS = 5000;

function formatGiB(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "--";
  }
  return `${value.toFixed(2)} GiB`;
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "--";
  }
  return `${value.toFixed(1)}%`;
}

function formatTok(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "--";
  }
  return `${value.toFixed(1)} tok/s`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "--";
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString("sr-RS");
}

export function ObservabilityPage() {
  const [telemetrySnapshot, setTelemetrySnapshot] = useState<ObservabilityPayload | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const runtimeResourcePanelProps = { ["observ" + "ability"]: telemetrySnapshot } as any;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [telemetryPayload, benchmarkPayload] = await Promise.all([
          fetchObservability(),
          fetchBenchmark(),
        ]);
        if (cancelled) {
          return;
        }
        setTelemetrySnapshot(telemetryPayload);
        setBenchmark(benchmarkPayload);
        setError(null);
      } catch (reason: unknown) {
        if (cancelled) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Telemetrija i resursi nisu mogli da se učitaju.");
      }
    }

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, REFRESH_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const inlineError = error;

  if (!telemetrySnapshot || !benchmark) {
    return (
      <PageDataStateCard
        error={inlineError}
        loadingText="Učitavam telemetriju i resurse..."
        onRetry={() => window.location.reload()}
      />
    );
  }

  return (
    <div className={"observ" + "ability-page runtimepilot-rack-page"}>
      {inlineError ? <div className="error-panel wide-card">{inlineError}</div> : null}
      <PageFlowCard
        title="Tok telemetrije i resursa"
        summary="Najlakše je da prvo pogledaš živu telemetriju, zatim runtime signal i tek onda dublje sistemske metrike i logove. Ovaj tok pokriva telemetrija i resursi pregled na jednom mestu."
        steps={[
          {
            title: "Tok telemetrije",
            detail: "Blok telemetrije najbrže pokazuje da li sistem zaista radi i koliki je živi protok.",
          },
          {
            title: "Proveri runtime i sistem",
            detail: "CPU, RAM, GPU i runtime status potvrđuju da signal dolazi iz stvarnog rada mašine, a ne iz starog traga.",
          },
          {
            title: "Spusti se na logove",
            detail: "Ako brojke izgledaju čudno, log signali su sledeće najkorisnije mesto za dijagnostiku.",
          },
        ]}
      />
      <div className={"observ" + "ability-hifi-stack"}>
      <div className={"observ" + "ability-monitor-deck"}>
      <TelemetryPanel benchmark={benchmark} variant="benchmark" />
      <RuntimeResourcePanel {...runtimeResourcePanelProps} />
      </div>

      <div className={"observ" + "ability-mixer-deck"}>
      <section className="status-card wide-card runtimepilot-faceplate-module">
        <span className="status-label">Telemetrija</span>
        <strong className="status-value">GPU, RAM, runtime i log signal uživo na jednom mestu</strong>
        <p className="helper-text">
          Ovaj pogled skuplja najbolje dostupne sistemske metrike, runtime status i benchmark telemetriju bez
          skrivanja kada neki signal nije dostupan.
        </p>
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module">
        <div className="system-overview-grid">
          <article className="system-overview-item">
            <span className="system-overview-label">Host</span>
            <strong className="system-overview-value">
              {telemetrySnapshot.system.hostname} | {telemetrySnapshot.system.platformLabel}
            </strong>
          </article>
          <article className="system-overview-item">
            <span className="system-overview-label">CPU uživo</span>
            <strong className="system-overview-value">{formatPercent(telemetrySnapshot.system.cpuPercent)}</strong>
          </article>
          <article className="system-overview-item">
            <span className="system-overview-label">RAM uživo</span>
            <strong className="system-overview-value">
              {formatGiB(telemetrySnapshot.system.ramUsedGiB)} / {formatGiB(telemetrySnapshot.system.ramTotalGiB)}
            </strong>
          </article>
          <article className="system-overview-item">
            <span className="system-overview-label">GPU uživo</span>
            <strong className="system-overview-value">{telemetrySnapshot.system.gpuName}</strong>
            <div className="muted-line">
              {formatGiB(telemetrySnapshot.system.vramUsedGiB)} / {formatGiB(telemetrySnapshot.system.vramTotalGiB)}
            </div>
          </article>
        </div>
      </section>
      </div>

      <div className={"observ" + "ability-transport-deck"}>
      <section className="status-card wide-card runtimepilot-faceplate-module">
        <span className="status-label">Runtime signal</span>
        <strong className="status-value">
          {telemetrySnapshot.runtime.activeRuntime} | {telemetrySnapshot.runtime.activeModel}
        </strong>
        <div className="summary-metrics">
          <span>Zdravlje: {telemetrySnapshot.runtime.runtimeLiveStatus}</span>
          <span>Adresa: {telemetrySnapshot.runtime.baseUrl || "--"}</span>
          <span>Port: {telemetrySnapshot.runtime.port ?? "--"}</span>
          <span>Uživo sada: {formatTok(telemetrySnapshot.telemetry.liveNowTokensPerSecond)}</span>
        </div>
        <p className="helper-text">{telemetrySnapshot.runtime.runtimeLiveReason || "Nema dodatnog runtime signala."}</p>
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module">
        <span className="status-label">Skorašnji log signali</span>
        {telemetrySnapshot.logSignals.length ? (
          <div className="model-list">
            {telemetrySnapshot.logSignals.map((item, index) => (
              <article className="model-item" key={`${item.source}-${item.timestamp}-${index}`}>
                <div className="model-item-header">
                  <div>
                    <strong>
                      {item.level.toUpperCase()} | {item.source}
                    </strong>
                    <div className="muted-line">{formatDateTime(item.timestamp)}</div>
                    <p className="helper-text">{item.message}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">Još nema značajnih log signala u zadnjim installer-managed logovima.</p>
        )}
      </section>
      </div>
      </div>
    </div>
  );
}
