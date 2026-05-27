import type { BenchmarkPayload } from "../lib/types";

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
  const liveStateLabel = telemetry?.flowStateLabel || "quiet";
  const liveStateClass = telemetry?.flowState || "quiet";
  const input24h = formatTokenCount(telemetry?.input24hTokens);
  const output24h = formatTokenCount(telemetry?.output24hTokens);
  const total24h = formatTokenCount(telemetry?.total24hTokens);
  const activeRoutes = formatTokenCount(telemetry?.activeRoutes);
  const cost24h = formatTelemetryCost(telemetry?.estimatedCost24hUsd);
  const liveNow = formatTelemetryThroughput(telemetry?.liveNowTokensPerSecond);
  const lastUpdate = formatTelemetryDate(telemetry?.lastUpdate);
  const splitText = `${telemetry?.inputSharePercent?.toFixed(1) ?? "0.0"}% / ${
    telemetry?.outputSharePercent?.toFixed(1) ?? "0.0"
  }%`;
  const inputSplitWidth = telemetry?.inputSharePercent ?? 0;
  const outputSplitWidth = telemetry?.outputSharePercent ?? 0;

  return (
    <section className={`status-card wide-card telemetry-panel telemetry-panel-${variant}`}>
      {variant === "benchmark" ? (
        <div className="telemetry-page-header">
          <div>
            <span className="status-label">Telemetry</span>
            <strong className="telemetry-page-title">Live token flow, sync i launch queue signal</strong>
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
          <span className="status-label">Token Pulse</span>
          <div className="telemetry-hero-state-row">
            <span className={`telemetry-state-badge telemetry-state-${liveStateClass}`}>{liveStateLabel}</span>
            <span className="telemetry-state-caption">Live signal</span>
          </div>
          <div className="telemetry-metric-grid">
            <MetricCard
              label="Input 24h"
              value={input24h}
              copy="Prompt tokeni za poslednja 24 sata."
            />
            <MetricCard
              label="Output 24h"
              value={output24h}
              copy="Generisani tokeni za poslednja 24 sata."
            />
            <MetricCard
              label="Active routes"
              value={activeRoutes}
              copy={routeSummary(telemetry?.activeRoutesLabel)}
            />
            <MetricCard
              label="Cost 24h"
              value={cost24h}
              copy="Proxy procena za poslednja 24 sata."
            />
          </div>
        </div>

        <div className="telemetry-live-panel">
          <span className="telemetry-live-label">Live now</span>
          <strong className="telemetry-live-value">{liveNow}</strong>
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
            {telemetry?.flowStateReason || "Telemetry jos nema live signal sa runtime-a."}
          </p>
        </div>
      </div>

      <div className="telemetry-footer-grid">
        <article className="telemetry-footer-card">
          <span className="telemetry-footer-label">Flow state</span>
          <strong>{liveStateLabel}</strong>
        </article>
        <article className="telemetry-footer-card">
          <span className="telemetry-footer-label">Last update</span>
          <strong>{lastUpdate}</strong>
        </article>
        <article className="telemetry-footer-card">
          <span className="telemetry-footer-label">24h total</span>
          <strong>{total24h}</strong>
        </article>
        <article className="telemetry-footer-card telemetry-footer-card-split">
          <span className="telemetry-footer-label">Input / output split</span>
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
            <span className="telemetry-footer-label">Sync signal</span>
            <strong>
              {benchmark?.activity.throughputTrend.signal || "--"} {benchmark?.activity.throughputTrend.label || "--"}
            </strong>
            <p className="helper-text">
              Latency: {benchmark?.activity.latencyTrend.signal || "--"} {benchmark?.activity.latencyTrend.label || "--"}
            </p>
          </article>
          <article className="telemetry-support-card">
            <span className="telemetry-footer-label">Launch queue signal</span>
            <strong>{telemetry?.launchQueueSignal.label || "launch queue quiet"}</strong>
            <p className="helper-text">
              {telemetry?.launchQueueSignal.summary || "Nema aktivnog benchmark launch reda."}
            </p>
          </article>
          <article className="telemetry-support-card">
            <span className="telemetry-footer-label">Route focus</span>
            <strong>{activeRoutes}</strong>
            <p className="helper-text">{routeSummary(telemetry?.activeRoutesLabel)}</p>
          </article>
        </div>
      ) : null}
    </section>
  );
}
