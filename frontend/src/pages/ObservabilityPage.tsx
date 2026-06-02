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
  const [observability, setObservability] = useState<ObservabilityPayload | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [observabilityPayload, benchmarkPayload] = await Promise.all([
          fetchObservability(),
          fetchBenchmark(),
        ]);
        if (cancelled) {
          return;
        }
        setObservability(observabilityPayload);
        setBenchmark(benchmarkPayload);
        setError(null);
      } catch (reason: unknown) {
        if (cancelled) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Observability nije mogao da se učita.");
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

  if (!observability || !benchmark) {
    return (
      <PageDataStateCard
        error={inlineError}
        loadingText="U\u010ditavam observability..."
        onRetry={() => window.location.reload()}
      />
    );
  }

  if (!observability || !benchmark) {
    return <section className="status-card wide-card">Učitavam observability...</section>;
  }

  return (
    <>
      {inlineError ? <div className="error-panel wide-card">{inlineError}</div> : null}
      <PageFlowCard
        title="Observability tok"
        summary="Najlak\u0161e je da prvo pogleda\u0161 \u017eivu telemetriju, zatim runtime signal i tek onda dublje sistemske metrike i logove."
        steps={[
          {
            title: "Pogledaj token signal",
            detail: "Telemetry blok najbr\u017ee pokazuje da li sistem zaista radi i koliki je \u017eivi protok.",
          },
          {
            title: "Proveri runtime i sistem",
            detail: "CPU, RAM, GPU i runtime status potvr\u0111uju da signal dolazi iz stvarnog rada ma\u0161ine, a ne iz starog traga.",
          },
          {
            title: "Spusti se na logove",
            detail: "Ako brojke izgledaju \u010dudno, log signali su slede\u0107e najkorisnije mesto za dijagnostiku.",
          },
        ]}
      />
      <TelemetryPanel benchmark={benchmark} variant="benchmark" />
      <RuntimeResourcePanel observability={observability} />

      <section className="status-card wide-card">
        <span className="status-label">Telemetrija</span>
        <strong className="status-value">GPU, RAM, runtime i log signal uživo na jednom mestu</strong>
        <p className="helper-text">
          Ovaj pogled skuplja best-effort sistemske metrike, runtime status i benchmark telemetry bez
          skrivanja kada neki signal nije dostupan.
        </p>
      </section>

      <section className="status-card wide-card">
        <div className="system-overview-grid">
          <article className="system-overview-item">
            <span className="system-overview-label">Host</span>
            <strong className="system-overview-value">
              {observability.system.hostname} | {observability.system.platformLabel}
            </strong>
          </article>
          <article className="system-overview-item">
            <span className="system-overview-label">CPU uživo</span>
            <strong className="system-overview-value">{formatPercent(observability.system.cpuPercent)}</strong>
          </article>
          <article className="system-overview-item">
            <span className="system-overview-label">RAM uživo</span>
            <strong className="system-overview-value">
              {formatGiB(observability.system.ramUsedGiB)} / {formatGiB(observability.system.ramTotalGiB)}
            </strong>
          </article>
          <article className="system-overview-item">
            <span className="system-overview-label">GPU uživo</span>
            <strong className="system-overview-value">{observability.system.gpuName}</strong>
            <div className="muted-line">
              {formatGiB(observability.system.vramUsedGiB)} / {formatGiB(observability.system.vramTotalGiB)}
            </div>
          </article>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Runtime signal</span>
        <strong className="status-value">
          {observability.runtime.activeRuntime} | {observability.runtime.activeModel}
        </strong>
        <div className="summary-metrics">
          <span>Health: {observability.runtime.runtimeLiveStatus}</span>
          <span>Endpoint: {observability.runtime.baseUrl || "--"}</span>
          <span>Port: {observability.runtime.port ?? "--"}</span>
          <span>Uživo sada: {formatTok(observability.telemetry.liveNowTokensPerSecond)}</span>
        </div>
        <p className="helper-text">{observability.runtime.runtimeLiveReason || "Nema dodatnog runtime signala."}</p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Skorašnji log signali</span>
        {observability.logSignals.length ? (
          <div className="model-list">
            {observability.logSignals.map((item, index) => (
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
          <p className="helper-text">Još nema znacajnih log signala u zadnjim installer-managed logovima.</p>
        )}
      </section>
    </>
  );
}
