import type { BenchmarkPayload } from "../lib/types";
import { RuntimePilotIcon } from "./RuntimePilotIcon";

type TelemetryPanelProps = {
  benchmark: BenchmarkPayload | null;
  variant?: "home" | "benchmark";
};

function formatTokenCount(value: number | null | undefined) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return "0";
  }
  return new Intl.NumberFormat("sr-RS").format(Math.round(numericValue));
}

function formatTelemetryDate(value: string | null | undefined) {
  if (!value) {
    return "--";
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return "--";
  }
  return new Date(parsed).toLocaleString("sr-RS");
}

function formatTelemetryThroughput(value: number | null | undefined) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return "--";
  }
  return `${numericValue.toFixed(2)} tok/s`;
}

function formatTelemetryCost(value: number | null | undefined) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return "$0.0000";
  }
  return `$${numericValue.toFixed(4)}`;
}

function liveMeterWidth(value: number | null | undefined) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(8, numericValue));
}

function routeSummary(label: string | null | undefined) {
  const text = String(label || "").trim();
  if (!text) {
    return "Nema aktivnih ruta.";
  }
  return text.replace(".gguf", "");
}

function MetricCard({
  label,
  value,
  copy,
}: {
  label: string;
  value: string;
  copy: string;
}) {
  return (
    <article className="telemetry-metric-card">
      <span className="telemetry-metric-label">{label}</span>
      <strong className="telemetry-metric-value">{value}</strong>
      <p className="telemetry-metric-copy">{copy}</p>
    </article>
  );
}

export function TelemetryPanel({
  benchmark,
  variant = "home",
}: TelemetryPanelProps) {
  const telemetry = benchmark?.telemetry;
  const liveStateLabel = telemetry?.flowStateLabel || "mirno";
  const liveStateClass = telemetry?.flowState || "quiet";
  const input24h = formatTokenCount(telemetry?.input24hTokens);
  const output24h = formatTokenCount(telemetry?.output24hTokens);
  const total24h = formatTokenCount(telemetry?.total24hTokens);
  const activeRoutes = formatTokenCount(telemetry?.activeRoutes);
  const cost24h = formatTelemetryCost(telemetry?.estimatedCost24hUsd);
  const liveNow = formatTelemetryThroughput(telemetry?.liveNowTokensPerSecond);
  const lastSignal = formatTelemetryThroughput(telemetry?.lastSignalTokensPerSecond);
  const lastSignalAt = formatTelemetryDate(telemetry?.lastSignalAt);
  const lastUpdate = formatTelemetryDate(telemetry?.lastUpdate);
  const hasLiveNowSignal = telemetry?.liveNowTokensPerSecond != null;
  const liveNowDisplay = hasLiveNowSignal ? liveNow : "\u00A0";
  const splitText = `${telemetry?.inputSharePercent?.toFixed(1) ?? "0.0"}% / ${
    telemetry?.outputSharePercent?.toFixed(1) ?? "0.0"
  }%`;
  const inputSplitWidth = telemetry?.inputSharePercent ?? 0;
  const outputSplitWidth = telemetry?.outputSharePercent ?? 0;
  const liveMeterSegments = Math.max(0, Math.min(12, Math.round((liveMeterWidth(telemetry?.liveNowTokensPerSecond) / 100) * 12)));

  if (variant === "home") {
    return (
      <section className="status-card wide-card telemetry-panel runtimepilot-telemetry-shell telemetry-panel-home runtimepilot-faceplate-module">
        <div className="telemetry-home-header">
          <div>
            <span className="status-label">Puls tokena</span>
            <strong className="telemetry-page-title">Kompaktan signal rada</strong>
          </div>
          <div className="telemetry-home-header-meta">
            <span className={`telemetry-state-badge telemetry-state-${liveStateClass}`}>{liveStateLabel}</span>
            <span className="helper-text">24h ulaz, izlaz i throughput bez ogromnog hero bloka.</span>
          </div>
        </div>

        <div className="telemetry-home-deck">
          <div className="telemetry-home-display">
            <div className="telemetry-home-display-head">
              <div>
                <span className="telemetry-live-label">Uživo sada</span>
                <strong className="telemetry-home-display-title">Signal rada i ritam poslednjih 24 sata</strong>
              </div>
              <span className="browser-badge">Rute {activeRoutes}</span>
            </div>
            <div className="telemetry-home-live-shell">
              <span className="telemetry-home-live-glyph" aria-hidden="true">
                <RuntimePilotIcon className="telemetry-radar-icon" name="telemetry" />
              </span>
              <div>
                <span className="telemetry-live-label">Uživo sada</span>
                <strong
                  className={`telemetry-home-live-value ${
                    hasLiveNowSignal ? "telemetry-live-value-active" : "telemetry-live-value-idle"
                  }`}
                >
                  {liveNowDisplay}
                </strong>
              </div>
            </div>
            <div className="telemetry-home-meter-bank" aria-hidden="true">
              {Array.from({ length: 12 }, (_, index) => (
                <span
                  key={`telemetry-home-meter-${index}`}
                  className={`telemetry-home-meter-segment ${index < liveMeterSegments ? "telemetry-home-meter-segment-active" : ""}`}
                />
              ))}
            </div>
            <p className="helper-text">
              {telemetry?.flowStateReason || "Telemetrija još nema signal uživo sa runtime-a."}
            </p>
          </div>

          <div className="telemetry-home-metrics">
            <MetricCard
              label="Ulaz 24h"
              value={input24h}
              copy="Prompt tokeni za poslednja 24 sata."
            />
            <MetricCard
              label="Izlaz 24h"
              value={output24h}
              copy="Generisani tokeni za poslednja 24 sata."
            />
            <MetricCard
              label="Aktivne rute"
              value={activeRoutes}
              copy={routeSummary(telemetry?.activeRoutesLabel)}
            />
            <MetricCard
              label="Trošak 24h"
              value={cost24h}
              copy="Proxy procena za poslednja 24 sata."
            />
          </div>
        </div>

        <div className="telemetry-home-footer">
          <article className="telemetry-footer-card telemetry-home-footer-card">
            <span className="telemetry-footer-label">Poslednji throughput signal</span>
            <strong>{lastSignal}</strong>
            <p className="helper-text">
              {telemetry?.lastSignalStateLabel || "skorašnji signal"}
              {telemetry?.lastSignalLabel ? ` | ${telemetry.lastSignalLabel}` : ""}
            </p>
          </article>
          <article className="telemetry-footer-card telemetry-home-footer-card">
            <span className="telemetry-footer-label">Signal zabeležen</span>
            <strong>{lastSignalAt}</strong>
            <p className="helper-text">Poslednje poznato vreme kroz runtime signal.</p>
          </article>
          <article className="telemetry-footer-card telemetry-home-footer-card">
            <span className="telemetry-footer-label">Ukupno 24h</span>
            <strong>{total24h}</strong>
            <p className="helper-text">Ukupni zbir ulaza i izlaza tokom poslednja 24 sata.</p>
          </article>
          <article className="telemetry-footer-card telemetry-footer-card-split telemetry-home-footer-card">
            <span className="telemetry-footer-label">Odnos ulaza i izlaza</span>
            <strong>{splitText}</strong>
            <div className="telemetry-split-bar">
              <div className="telemetry-split-bar-input" style={{ width: `${inputSplitWidth}%` }} />
              <div className="telemetry-split-bar-output" style={{ width: `${outputSplitWidth}%` }} />
            </div>
          </article>
        </div>
      </section>
    );
  }

  return (
    <section
      className={`status-card wide-card telemetry-panel runtimepilot-telemetry-shell telemetry-panel-${variant} runtimepilot-faceplate-module`}
    >
      {variant === "benchmark" ? (
        <div className="telemetry-page-header">
          <div>
            <span className="status-label">Telemetrija</span>
            <strong className="telemetry-page-title">
              Uživo: tok tokena, sinhronizacija i signal reda pokretanja
            </strong>
          </div>
          <div className="telemetry-page-badges">
            <span className={`telemetry-state-badge telemetry-state-${liveStateClass}`}>{liveStateLabel}</span>
            <span className="browser-badge">Model {benchmark?.environment.modelLabel || "--"}</span>
            <span className="browser-badge">Runtime {benchmark?.environment.runtimeLabel || "--"}</span>
          </div>
        </div>
      ) : null}

      <div className="telemetry-hero">
        <div className="telemetry-hero-main">
          <span className="status-label">Puls tokena</span>
          <div className="telemetry-hero-state-row">
            <span className={`telemetry-state-badge telemetry-state-${liveStateClass}`}>{liveStateLabel}</span>
            <span className="telemetry-state-caption">Signal uživo</span>
          </div>
          <div className="telemetry-metric-grid">
            <MetricCard
              label="Ulaz 24h"
              value={input24h}
              copy="Prompt tokeni za poslednja 24 sata."
            />
            <MetricCard
              label="Izlaz 24h"
              value={output24h}
              copy="Generisani tokeni za poslednja 24 sata."
            />
            <MetricCard
              label="Aktivne rute"
              value={activeRoutes}
              copy={routeSummary(telemetry?.activeRoutesLabel)}
            />
            <MetricCard
              label="Trošak 24h"
              value={cost24h}
              copy="Proxy procena za poslednja 24 sata."
            />
          </div>
        </div>

        <div className="telemetry-live-panel">
          <span className="telemetry-live-label">Uživo sada</span>
          <div className="telemetry-radar-shell" aria-hidden="true">
            <span className="telemetry-radar-ring telemetry-radar-ring-outer" />
            <span className="telemetry-radar-ring telemetry-radar-ring-middle" />
            <span className="telemetry-radar-ring telemetry-radar-ring-inner" />
            <span className="telemetry-radar-sweep" />
            <span className="telemetry-radar-core">
              <RuntimePilotIcon className="telemetry-radar-icon" name="telemetry" />
            </span>
          </div>
          <div className="telemetry-live-shell">
            <strong
              className={`telemetry-live-value ${
                hasLiveNowSignal ? "telemetry-live-value-active" : "telemetry-live-value-idle"
              }`}
            >
              {liveNowDisplay}
            </strong>
          </div>
          <div className="telemetry-live-scale">
            <div className="telemetry-live-scale-track">
              <div
                className="telemetry-live-scale-fill"
                style={{ width: `${liveMeterWidth(telemetry?.liveNowTokensPerSecond)}%` }}
              />
            </div>
            <div className="telemetry-live-scale-ticks">
              <span>0</span>
              <span>25</span>
              <span>50</span>
              <span>100+</span>
            </div>
          </div>
          <p className="helper-text">
            {telemetry?.flowStateReason || "Telemetrija još nema signal uživo sa runtime-a."}
          </p>
          <div className="telemetry-last-signal telemetry-last-signal-persistent">
              <span className="telemetry-last-signal-label">Poslednji throughput signal</span>
              <strong className="telemetry-last-signal-value">{lastSignal}</strong>
              <p className="helper-text">
                {telemetry?.lastSignalStateLabel || "skorašnji signal"}
                {telemetry?.lastSignalLabel ? ` | ${telemetry.lastSignalLabel}` : ""}
                {telemetry?.lastSignalAt ? ` | ${lastSignalAt}` : ""}
              </p>
            </div>
        </div>
      </div>

      <div className="telemetry-footer-grid">
        <article className="telemetry-footer-card">
          <span className="telemetry-footer-label">Stanje protoka</span>
          <strong>{liveStateLabel}</strong>
        </article>
        <article className="telemetry-footer-card">
          <span className="telemetry-footer-label">Poslednje ažuriranje</span>
          <strong>{lastUpdate}</strong>
        </article>
        <article className="telemetry-footer-card">
          <span className="telemetry-footer-label">Ukupno 24h</span>
          <strong>{total24h}</strong>
        </article>
        <article className="telemetry-footer-card telemetry-footer-card-split">
          <span className="telemetry-footer-label">Odnos ulaza i izlaza</span>
          <strong>{splitText}</strong>
          <div className="telemetry-split-bar">
            <div className="telemetry-split-bar-input" style={{ width: `${inputSplitWidth}%` }} />
            <div className="telemetry-split-bar-output" style={{ width: `${outputSplitWidth}%` }} />
          </div>
        </article>
      </div>

      {variant === "benchmark" ? (
        <div className="telemetry-support-grid">
          <article className="telemetry-support-card">
            <span className="telemetry-footer-label">Signal sinhronizacije</span>
            <strong>
              {benchmark?.activity.throughputTrend.signal || "--"} {benchmark?.activity.throughputTrend.label || "--"}
            </strong>
            <p className="helper-text">
              Latencija: {benchmark?.activity.latencyTrend.signal || "--"} {benchmark?.activity.latencyTrend.label || "--"}
            </p>
          </article>
          <article className="telemetry-support-card">
            <span className="telemetry-footer-label">Signal reda pokretanja</span>
            <strong>{telemetry?.launchQueueSignal.label || "red pokretanja miran"}</strong>
            <p className="helper-text">
              {telemetry?.launchQueueSignal.summary || "Nema aktivnog benchmark reda za pokretanje."}
            </p>
          </article>
          <article className="telemetry-support-card">
            <span className="telemetry-footer-label">Fokus ruta</span>
            <strong>{activeRoutes}</strong>
            <p className="helper-text">{routeSummary(telemetry?.activeRoutesLabel)}</p>
          </article>
        </div>
      ) : null}
    </section>
  );
}
