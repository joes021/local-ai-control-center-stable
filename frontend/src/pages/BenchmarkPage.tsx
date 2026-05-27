import { useEffect, useMemo, useRef, useState } from "react";

import { CustomSelect } from "../components/CustomSelect";
import { TelemetryPanel } from "../components/TelemetryPanel";
import {
  clearBenchmarkHistory,
  exportBenchmarkRuns,
  fetchBenchmark,
  fetchSettings,
  fetchBenchmarkCompare,
  loadBenchmarkBattery,
  restoreDefaultBenchmarkTests,
  runBatteryBenchmark,
  runSelectedBenchmark,
  saveBenchmarkBattery,
} from "../lib/api";
import { resolveSelectedWorkflowPreset } from "../lib/workflowPresets";
import type {
  BenchmarkComparePayload,
  BenchmarkHistoryItem,
  BenchmarkPayload,
  BenchmarkScenario,
  SettingsPayload,
} from "../lib/types";

const REALTIME_REFRESH_MS = 5000;
const CHART_GAP_MS = REALTIME_REFRESH_MS + 1500;
const CHART_WIDTH = 640;
const CHART_HEIGHT = 180;
const CHART_OFFSET_X = 48;
const CHART_OFFSET_Y = 10;

const RANGE_OPTIONS = [
  { key: "1m", label: "1m", durationMs: 60_000 },
  { key: "5m", label: "5m", durationMs: 5 * 60_000 },
  { key: "15m", label: "15m", durationMs: 15 * 60_000 },
  { key: "1h", label: "1h", durationMs: 60 * 60_000 },
] as const;

type RangeKey = (typeof RANGE_OPTIONS)[number]["key"];
type MetricKey =
  | "promptTokensPerSecond"
  | "completionTokensPerSecond"
  | "totalTokensPerSecond";

type HistoryPoint = BenchmarkHistoryItem & {
  timestampMs: number;
};

type MetricPoint = {
  key: string;
  timestampMs: number;
  value: number;
  x: number;
  y: number;
};

function parseMetricValue(value: number | null | undefined) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function parseTimestamp(value: string | undefined | null) {
  const parsed = Date.parse(value ?? "");
  return Number.isFinite(parsed) ? parsed : null;
}

function formatClockTime(timestampMs: number) {
  const date = new Date(timestampMs);
  return [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
}

function formatDurationLabel(durationMs: number) {
  const totalSeconds = Math.max(0, Math.floor(durationMs / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  if (minutes > 0) {
    return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
  }
  return `${seconds}s`;
}

function formatThroughput(value: number | undefined | null) {
  const numericValue = parseMetricValue(value);
  if (numericValue === null) {
    return "--";
  }
  return `${numericValue.toFixed(1)} tok/s`;
}

function formatCompactTokens(value: number | undefined | null) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return "--";
  }
  if (numericValue % 1024 === 0) {
    return `${numericValue / 1024}k`;
  }
  return `${numericValue}`;
}

function formatDateTimeLabel(value: string | undefined | null) {
  const timestamp = parseTimestamp(value);
  if (timestamp === null) {
    return "--";
  }
  const date = new Date(timestamp);
  return `${date.toLocaleDateString("sr-RS")} ${date.toLocaleTimeString("sr-RS", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })}`;
}

function formatYAxisLabel(value: number) {
  return `${Math.round(value)} tok/s`;
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}

function pointToString(point: Pick<MetricPoint, "x" | "y">) {
  return `${point.x},${point.y}`;
}

function buildMetricPoints(
  samples: HistoryPoint[],
  metricKey: MetricKey,
  rangeStartMs: number,
  rangeEndMs: number,
  maxValue: number,
) {
  const timeWindowMs = Math.max(rangeEndMs - rangeStartMs, 1);
  const safeMaxValue = Math.max(maxValue, 1);

  return samples.flatMap((sample) => {
    const rawValue = parseMetricValue(sample[metricKey]);
    if (rawValue === null) {
      return [];
    }
    const x = clamp(((sample.timestampMs - rangeStartMs) / timeWindowMs) * (CHART_WIDTH - 8), 0, CHART_WIDTH - 8);
    const y = CHART_HEIGHT - (rawValue / safeMaxValue) * (CHART_HEIGHT - 10);

    return [
      {
        key: `${metricKey}-${sample.timestampMs}`,
        timestampMs: sample.timestampMs,
        value: rawValue,
        x: x + CHART_OFFSET_X,
        y: y + CHART_OFFSET_Y,
      },
    ];
  });
}

function buildSolidSegments(points: MetricPoint[]) {
  if (!points.length) {
    return [];
  }

  const segments: string[] = [];
  let currentSegment: string[] = [pointToString(points[0])];

  for (let index = 1; index < points.length; index += 1) {
    const previousPoint = points[index - 1];
    const currentPoint = points[index];

    if (currentPoint.timestampMs - previousPoint.timestampMs > CHART_GAP_MS) {
      segments.push(currentSegment.join(" "));
      currentSegment = [pointToString(currentPoint)];
      continue;
    }

    currentSegment.push(pointToString(currentPoint));
  }

  segments.push(currentSegment.join(" "));
  return segments;
}

function buildGapSegments(points: MetricPoint[], rangeEndMs: number) {
  if (!points.length) {
    return [];
  }

  const segments: Array<{ key: string; x1: number; y1: number; x2: number; y2: number }> = [];

  for (let index = 1; index < points.length; index += 1) {
    const previousPoint = points[index - 1];
    const currentPoint = points[index];

    if (currentPoint.timestampMs - previousPoint.timestampMs <= CHART_GAP_MS) {
      continue;
    }

    segments.push({
      key: `gap-${previousPoint.timestampMs}-${currentPoint.timestampMs}`,
      x1: previousPoint.x,
      y1: previousPoint.y,
      x2: currentPoint.x,
      y2: currentPoint.y,
    });
  }

  const lastPoint = points[points.length - 1];
  if (rangeEndMs - lastPoint.timestampMs > CHART_GAP_MS) {
    const rangeEndX = CHART_OFFSET_X + (CHART_WIDTH - 8);
    segments.push({
      key: `gap-tail-${lastPoint.timestampMs}-${rangeEndMs}`,
      x1: lastPoint.x,
      y1: lastPoint.y,
      x2: rangeEndX,
      y2: lastPoint.y,
    });
  }

  return segments;
}

function buildMetricY(value: number, maxValue: number) {
  const safeMaxValue = Math.max(maxValue, 1);
  return CHART_HEIGHT - (Math.max(value, 0) / safeMaxValue) * (CHART_HEIGHT - 10) + CHART_OFFSET_Y;
}

function buildInactivitySegments(
  points: MetricPoint[],
  rangeStartMs: number,
  rangeEndMs: number,
  maxValue: number,
  fallbackBeforeRangeValue: number | null,
) {
  const segments = buildGapSegments(points, rangeEndMs);
  const rangeStartX = CHART_OFFSET_X;
  const rangeEndX = CHART_OFFSET_X + (CHART_WIDTH - 8);

  if (!points.length) {
    if (fallbackBeforeRangeValue === null) {
      return segments;
    }

    const fallbackY = buildMetricY(fallbackBeforeRangeValue, maxValue);
    return [
      {
        key: `gap-empty-${rangeStartMs}-${rangeEndMs}`,
        x1: rangeStartX,
        y1: fallbackY,
        x2: rangeEndX,
        y2: fallbackY,
      },
    ];
  }

  const firstPoint = points[0];
  if (firstPoint.timestampMs - rangeStartMs > CHART_GAP_MS) {
    const headY = fallbackBeforeRangeValue === null ? firstPoint.y : buildMetricY(fallbackBeforeRangeValue, maxValue);
    segments.unshift({
      key: `gap-head-${rangeStartMs}-${firstPoint.timestampMs}`,
      x1: rangeStartX,
      y1: headY,
      x2: firstPoint.x,
      y2: firstPoint.y,
    });
  }

  return segments;
}

function buildTimeTicks(rangeStartMs: number, rangeEndMs: number, selectedRangeKey: RangeKey) {
  const tickCount = selectedRangeKey === "1h" ? 5 : 6;

  return Array.from({ length: tickCount }, (_, index) => {
    const ratio = index / (tickCount - 1);
    const timestampMs = rangeStartMs + (rangeEndMs - rangeStartMs) * ratio;
    const x = CHART_OFFSET_X + ratio * (CHART_WIDTH - 8);

    return {
      key: `${selectedRangeKey}-${timestampMs}`,
      label: formatClockTime(timestampMs),
      x,
    };
  });
}

function buildChartStatus(lastSample: HistoryPoint | null, nowTickMs: number) {
  if (!lastSample) {
    return "cekam prve benchmark uzorke | poslednji throughput: --";
  }

  const inactiveForMs = Math.max(0, nowTickMs - lastSample.timestampMs);
  const lastThroughput = formatThroughput(lastSample.totalTokensPerSecond);

  if (inactiveForMs <= CHART_GAP_MS) {
    return `live | poslednji throughput: ${lastThroughput} | pre ${formatDurationLabel(inactiveForMs)}`;
  }

  return `nema novih zahteva u poslednjih ${formatDurationLabel(inactiveForMs)} | poslednji throughput: ${lastThroughput}`;
}

function findRangeByKey(rangeKey: RangeKey) {
  return RANGE_OPTIONS.find((option) => option.key === rangeKey) ?? RANGE_OPTIONS[0];
}

export function BenchmarkPage({ onOpenLogs }: { onOpenLogs: () => void }) {
  const [benchmark, setBenchmark] = useState<BenchmarkPayload | null>(null);
  const [comparePayload, setComparePayload] = useState<BenchmarkComparePayload | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [selectedCompareRunIds, setSelectedCompareRunIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [batteryName, setBatteryName] = useState("");
  const [scenariosDraft, setScenariosDraft] = useState<BenchmarkScenario[]>([]);
  const [actionMessage, setActionMessage] = useState("");
  const [settingsPayload, setSettingsPayload] = useState<SettingsPayload | null>(null);
  const [selectedRangeKey, setSelectedRangeKey] = useState<RangeKey>("1m");
  const [nowTickMs, setNowTickMs] = useState(() => Date.now());
  const isMountedRef = useRef(false);
  const inFlightRef = useRef(false);
  const requestIdRef = useRef(0);

  async function load() {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    inFlightRef.current = true;
    try {
      const [payload, nextSettings] = await Promise.all([fetchBenchmark(), fetchSettings()]);
      if (!isMountedRef.current || requestId !== requestIdRef.current) {
        return;
      }
      setBenchmark(payload);
      setSettingsPayload(nextSettings);
      setError(null);
      setActionMessage("");
      setSelectedScenarioId((current) => current || payload.selectedBattery?.scenarios?.[0]?.id || "");
      setBatteryName(payload.selectedBattery?.name ?? "");
      setScenariosDraft(payload.selectedBattery?.scenarios ?? []);
      setSelectedCompareRunIds((current) =>
        current.filter((runId) => payload.savedRuns.some((run) => run.runId === runId)),
      );
    } catch (reason: unknown) {
      if (!isMountedRef.current || requestId !== requestIdRef.current) {
        return;
      }
      setError(reason instanceof Error ? reason.message : "Nepoznata greska");
    } finally {
      if (requestId === requestIdRef.current) {
        inFlightRef.current = false;
      }
      if (isMountedRef.current) {
        setNowTickMs(Date.now());
      }
    }
  }

  useEffect(() => {
    isMountedRef.current = true;

    function tick() {
      setNowTickMs(Date.now());
      if (!inFlightRef.current) {
        void load();
      }
    }

    void tick();
    const timer = window.setInterval(() => {
      void tick();
    }, REALTIME_REFRESH_MS);

    return () => {
      isMountedRef.current = false;
      window.clearInterval(timer);
    };
  }, []);
  const currentWorkflowPreset = useMemo(
    () => resolveSelectedWorkflowPreset(settingsPayload),
    [settingsPayload],
  );

  useEffect(() => {
    if (selectedCompareRunIds.length < 2) {
      setComparePayload(null);
      setCompareError(null);
      return;
    }

    let cancelled = false;
    void fetchBenchmarkCompare(selectedCompareRunIds)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setComparePayload(payload);
        setCompareError(null);
      })
      .catch((reason: unknown) => {
        if (cancelled) {
          return;
        }
        setComparePayload(null);
        setCompareError(reason instanceof Error ? reason.message : "Benchmark compare nije uspeo.");
      });

    return () => {
      cancelled = true;
    };
  }, [selectedCompareRunIds]);

  const selectedBattery = benchmark?.selectedBattery ?? {
    id: "default",
    name: "Default battery",
    source: "default",
    scenarios: [],
  };
  const activeRun = benchmark?.activeRun;
  const benchmarkEnvironment = benchmark?.environment;

  const normalizedSignalHistory = useMemo<HistoryPoint[]>(
    () =>
      [...(benchmark?.history ?? []), ...(benchmark?.liveHistory ?? [])]
        .map((item) => {
          const timestampMs = parseTimestamp(item.measuredAt);
          if (timestampMs === null) {
            return null;
          }
          return {
            ...item,
            timestampMs,
          };
        })
        .filter((item): item is HistoryPoint => item !== null)
        .sort((left, right) => left.timestampMs - right.timestampMs)
        .filter((item, index, items) => {
          const previous = items[index - 1];
          if (!previous) {
            return true;
          }
          return !(
            previous.timestampMs === item.timestampMs &&
            previous.label === item.label &&
            previous.totalTokensPerSecond === item.totalTokensPerSecond &&
            previous.completionTokensPerSecond === item.completionTokensPerSecond &&
            previous.promptTokensPerSecond === item.promptTokensPerSecond
          );
        }),
    [benchmark],
  );

  const chartModel = useMemo(() => {
    const selectedRange = findRangeByKey(selectedRangeKey);
    const rangeEndMs = nowTickMs;
    const rangeStartMs = rangeEndMs - selectedRange.durationMs;
    const visibleSamples = normalizedSignalHistory.filter(
      (item) => item.timestampMs >= rangeStartMs && item.timestampMs <= rangeEndMs,
    );
    const previousSample =
      [...normalizedSignalHistory].reverse().find((item) => item.timestampMs < rangeStartMs) ?? null;
    const lastSample =
      (() => {
        const parsedLiveCurrentTimestamp = parseTimestamp(benchmark?.liveCurrent?.measuredAt);
        if (benchmark?.liveCurrent && parsedLiveCurrentTimestamp !== null) {
          return {
            ...benchmark.liveCurrent,
            timestampMs: parsedLiveCurrentTimestamp,
          } as HistoryPoint;
        }
        return normalizedSignalHistory[normalizedSignalHistory.length - 1] ?? null;
      })();
    const fallbackValues = [previousSample, lastSample]
      .flatMap((item) =>
        item
          ? [
              parseMetricValue(item.promptTokensPerSecond),
              parseMetricValue(item.completionTokensPerSecond),
              parseMetricValue(item.totalTokensPerSecond),
            ]
          : [],
      )
      .filter((value): value is number => value !== null);
    const maxValue = Math.max(
      ...visibleSamples.map((item) =>
        Math.max(
          parseMetricValue(item.promptTokensPerSecond) ?? 0,
          parseMetricValue(item.completionTokensPerSecond) ?? 0,
          parseMetricValue(item.totalTokensPerSecond) ?? 0,
        ),
      ),
      ...fallbackValues,
      1,
    );
    const yAxisLabels = [maxValue, maxValue * 0.66, maxValue * 0.33, 0].map(formatYAxisLabel);
    const promptPoints = buildMetricPoints(
      visibleSamples,
      "promptTokensPerSecond",
      rangeStartMs,
      rangeEndMs,
      maxValue,
    );
    const outputPoints = buildMetricPoints(
      visibleSamples,
      "completionTokensPerSecond",
      rangeStartMs,
      rangeEndMs,
      maxValue,
    );
    const totalPoints = buildMetricPoints(
      visibleSamples,
      "totalTokensPerSecond",
      rangeStartMs,
      rangeEndMs,
      maxValue,
    );
    const inactiveForMs = lastSample ? Math.max(0, nowTickMs - lastSample.timestampMs) : null;
    const lastSampleOutsideRange = Boolean(lastSample && lastSample.timestampMs < rangeStartMs);

    return {
      promptPoints,
      promptSegments: buildSolidSegments(promptPoints),
      outputPoints,
      outputSegments: buildSolidSegments(outputPoints),
      totalPoints,
      totalSegments: buildSolidSegments(totalPoints),
      totalGapSegments: buildInactivitySegments(
        totalPoints,
        rangeStartMs,
        rangeEndMs,
        maxValue,
        previousSample ? parseMetricValue(previousSample.totalTokensPerSecond) : null,
      ),
      rangeStartMs,
      rangeEndMs,
      statusText: buildChartStatus(lastSample, nowTickMs),
      tickMarks: buildTimeTicks(rangeStartMs, rangeEndMs, selectedRangeKey),
      visibleSamples,
      lastSampleOutsideRange,
      inactiveForMs,
      yAxisLabels,
    };
  }, [benchmark?.liveCurrent, normalizedSignalHistory, nowTickMs, selectedRangeKey]);

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!benchmark) {
    return <section className="status-card wide-card">Ucitavam benchmark...</section>;
  }

  const scenarioOptions = selectedBattery.scenarios.map((scenario) => ({
    value: scenario.id,
    label: scenario.name,
  }));
  const batteryOptions = benchmark.batteries.map((battery) => ({
    value: battery.id,
    label: battery.name,
  }));

  async function handleRunSelected() {
    const result = await runSelectedBenchmark(selectedScenarioId);
    setActionMessage(result.summary);
    await load();
  }

  async function handleRunBattery() {
    const result = await runBatteryBenchmark(selectedBattery.id);
    setActionMessage(result.summary);
    await load();
  }

  async function handleSaveBattery() {
    const result = await saveBenchmarkBattery(batteryName, scenariosDraft);
    setActionMessage(result.summary);
    await load();
  }

  async function handleLoadBattery(batteryId: string) {
    const result = await loadBenchmarkBattery(batteryId);
    setActionMessage(result.summary);
    await load();
  }

  async function handleRestoreDefaults() {
    const result = await restoreDefaultBenchmarkTests();
    setActionMessage(result.summary);
    await load();
  }

  async function handleClearHistory() {
    const result = await clearBenchmarkHistory();
    setActionMessage(result.summary);
    await load();
  }

  function toggleCompareRun(runId: string) {
    setSelectedCompareRunIds((current) =>
      current.includes(runId) ? current.filter((item) => item !== runId) : [...current, runId],
    );
  }

  async function handleExport(format: "json" | "csv") {
    const exportRunIds =
      selectedCompareRunIds.length >= 1
        ? selectedCompareRunIds
        : (benchmark?.savedRuns ?? []).map((run) => run.runId);
    const blob = await exportBenchmarkRuns(format, exportRunIds);
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const suffix = format === "csv" ? "csv" : "json";
    anchor.href = url;
    anchor.download = `lacc-benchmark-${formatDateTimeLabel(new Date().toISOString()).replace(/[\\/: ]/g, "-")}.${suffix}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
    setActionMessage(
      format === "csv"
        ? "CSV benchmark export je preuzet."
        : "JSON benchmark export je preuzet.",
    );
  }

  function updateScenario(index: number, patch: Partial<BenchmarkScenario>) {
    setScenariosDraft((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );
  }

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Benchmark controls</span>
        {currentWorkflowPreset ? (
          <p className="helper-text">
            Workflow preset: {currentWorkflowPreset.label} | {currentWorkflowPreset.benchmarkDefaults.runLabel}
          </p>
        ) : null}
        <div className="inline-actions" style={{ flexWrap: "wrap", gap: "12px" }}>
          <CustomSelect
            value={selectedScenarioId}
            options={scenarioOptions}
            onChange={setSelectedScenarioId}
            ariaLabel="Izaberi benchmark scenario"
          />
          <button type="button" onClick={handleRunSelected}>
            Run selected test
          </button>
          <button type="button" onClick={handleRunBattery}>
            Run full battery
          </button>
          <button type="button" onClick={handleSaveBattery}>
            Save battery
          </button>
          <span className="helper-text">Load battery</span>
          <CustomSelect
            value={selectedBattery.id}
            options={batteryOptions}
            onChange={(batteryId) => void handleLoadBattery(batteryId)}
            ariaLabel="Ucitaj benchmark bateriju"
          />
          <button type="button" onClick={handleRestoreDefaults}>
            Restore default tests
          </button>
          <button type="button" className="secondary-button" onClick={handleClearHistory}>
            Clear benchmark values
          </button>
        </div>
        <p className="helper-text">
          {actionMessage || "Benchmark testovi mogu da se pokrenu pojedinacno ili kao cela baterija."}
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Battery editor</span>
        <div className="battery-editor-shell">
          <div className="battery-editor-topline">
            <input
              value={batteryName}
              onChange={(event) => setBatteryName(event.target.value)}
              placeholder="Ime baterije"
            />
            <div className="helper-text">Aktivna baterija: {selectedBattery.name}</div>
          </div>
          <div className="battery-scenario-list">
            {scenariosDraft.map((scenario) => {
              const isSelected = scenario.id === selectedScenarioId;
              return (
                <button
                  type="button"
                  key={scenario.id}
                  className={`battery-scenario-row${isSelected ? " battery-scenario-row-active" : ""}`}
                  onClick={() => setSelectedScenarioId(scenario.id)}
                >
                  <span className="battery-scenario-name">{scenario.name}</span>
                  <span className="battery-scenario-preview">{scenario.prompt}</span>
                </button>
              );
            })}
          </div>
          {(() => {
            const activeScenarioIndex = scenariosDraft.findIndex((item) => item.id === selectedScenarioId);
            const activeScenario =
              activeScenarioIndex >= 0 ? scenariosDraft[activeScenarioIndex] : scenariosDraft[0];
            if (!activeScenario) {
              return null;
            }
            const scenarioIndex = activeScenarioIndex >= 0 ? activeScenarioIndex : 0;
            return (
              <div className="battery-editor-detail">
                <div className="battery-editor-detail-header">
                  <strong>{activeScenario.name}</strong>
                  <span className="helper-text">
                    Uredujes jedan scenario, lista gore ostaje kompaktna.
                  </span>
                </div>
                <div className="battery-editor-detail-grid">
                  <input
                    value={activeScenario.name}
                    onChange={(event) => updateScenario(scenarioIndex, { name: event.target.value })}
                    placeholder="Naziv scenarija"
                  />
                  <textarea
                    value={activeScenario.prompt}
                    onChange={(event) => updateScenario(scenarioIndex, { prompt: event.target.value })}
                    placeholder="Prompt scenarija"
                    rows={4}
                  />
                </div>
              </div>
            );
          })()}
        </div>
      </section>

      <TelemetryPanel benchmark={benchmark} variant="benchmark" />

      <section className="status-card wide-card">
        <span className="status-label">Benchmark context</span>
        <div className="benchmark-context-grid">
          <div className="benchmark-context-main">
            <strong className="status-value">
              Model: {benchmarkEnvironment?.modelLabel || "Nema aktivnog modela"}
            </strong>
            <p className="helper-text">
              Runtime: {benchmarkEnvironment?.runtimeLabel || "--"} | Profil: {benchmarkEnvironment?.profile || "--"} |
              Thinking: {benchmarkEnvironment?.thinkingMode || "--"}
            </p>
          </div>
          <div className="browser-chip-row">
            <span className="browser-badge">Context {formatCompactTokens(benchmarkEnvironment?.context)}</span>
            <span className="browser-badge">Output {formatCompactTokens(benchmarkEnvironment?.outputTokens)}</span>
            <span className="browser-badge">
              Live state {benchmark?.liveState?.status || "idle"}
            </span>
          </div>
        </div>
        <p className="helper-text">{benchmark?.liveState?.reason}</p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Benchmark run</span>
        <div className="benchmark-run-summary">
          <div className="benchmark-run-main">
            <strong className="status-value">
              {activeRun?.mode === "battery"
                ? `${activeRun.currentIndex}/${activeRun.totalScenarios} | ${
                    activeRun.currentScenarioName || "ceka"
                  }`
                : activeRun?.scenarioName || "nema aktivnog testa"}
            </strong>
            <span className={`scenario-status-badge scenario-status-${activeRun?.status || "idle"}`}>
              {activeRun?.status || "idle"}
            </span>
          </div>
          <div className="benchmark-run-meta">
            <span>{activeRun?.percent ?? 0}%</span>
            <span>{activeRun?.message || "Benchmark nije pokrenut."}</span>
          </div>
        </div>
        <div className="benchmark-run-status-list">
          {(activeRun?.scenarioStatuses ?? []).map((item) => (
            <article className="benchmark-run-status-row" key={item.scenarioId}>
              <strong>{item.scenarioName}</strong>
              <span className={`scenario-status-badge scenario-status-${item.status}`}>
                {item.status}
              </span>
              <div className="muted-line">{item.summary}</div>
            </article>
          ))}
        </div>
        <div style={{ display: "none" }}>queued running done failed</div>
      </section>

      <section className="status-card wide-card">
        <div className="benchmark-card-header">
          <div>
            <span className="status-label">Benchmark grafikon</span>
            <strong className="status-value benchmark-chart-status">{chartModel.statusText}</strong>
          </div>
          <div className="benchmark-range-segment" role="tablist" aria-label="Benchmark range">
            {RANGE_OPTIONS.map((option) => (
              <button
                type="button"
                key={option.key}
                className={`benchmark-range-button${
                  option.key === selectedRangeKey ? " benchmark-range-button-active" : ""
                }`}
                onClick={() => setSelectedRangeKey(option.key)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <div className="benchmark-chart-layout">
          <div className="benchmark-chart-panel">
            <svg
              viewBox={`0 0 ${CHART_WIDTH + 60} ${CHART_HEIGHT + 50}`}
              width="100%"
              height="280"
              role="img"
              aria-label="Benchmark grafikon"
            >
              <line
                x1={CHART_OFFSET_X}
                y1={CHART_OFFSET_Y}
                x2={CHART_OFFSET_X}
                y2={CHART_HEIGHT + CHART_OFFSET_Y}
                stroke="#8a8177"
                strokeWidth="1.5"
              />
              <line
                x1={CHART_OFFSET_X}
                y1={CHART_HEIGHT + CHART_OFFSET_Y}
                x2={CHART_WIDTH + 40}
                y2={CHART_HEIGHT + CHART_OFFSET_Y}
                stroke="#8a8177"
                strokeWidth="1.5"
              />
              {chartModel.yAxisLabels.map((label, index) => {
                const y = CHART_OFFSET_Y + (CHART_HEIGHT / (chartModel.yAxisLabels.length - 1)) * index;
                return (
                  <g key={`y-axis-${index}-${label}`}>
                    <line
                      x1="44"
                      y1={y}
                      x2={CHART_WIDTH + 40}
                      y2={y}
                      stroke="#4f463f"
                      strokeOpacity="0.15"
                    />
                    <text x="0" y={y + 4} fontSize="11" fill="#d8d0c5">
                      {label}
                    </text>
                  </g>
                );
              })}
              {chartModel.tickMarks.map((tick) => (
                <g key={tick.key}>
                  <line
                    x1={tick.x}
                    y1={CHART_OFFSET_Y}
                    x2={tick.x}
                    y2={CHART_HEIGHT + CHART_OFFSET_Y}
                    stroke="#4f463f"
                    strokeOpacity="0.08"
                  />
                  <text
                    x={tick.x}
                    y={CHART_HEIGHT + 28}
                    fontSize="10"
                    textAnchor="middle"
                    fill="#d8d0c5"
                  >
                    {tick.label}
                  </text>
                </g>
              ))}
              {chartModel.totalGapSegments.map((segment) => (
                <line
                  key={segment.key}
                  x1={segment.x1}
                  y1={segment.y1}
                  x2={segment.x2}
                  y2={segment.y2}
                  stroke="#9a948a"
                  strokeWidth="2"
                  strokeDasharray="6 6"
                  strokeLinecap="round"
                  opacity="0.75"
                />
              ))}
              {chartModel.totalSegments.map((points, index) => (
                <polyline
                  key={`total-${index}`}
                  fill="none"
                  stroke="#f2b84b"
                  strokeWidth="4"
                  strokeOpacity="0.65"
                  strokeDasharray="10 6"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  points={points}
                />
              ))}
              {chartModel.outputPoints.map((point) => (
                <circle
                  key={point.key}
                  cx={point.x}
                  cy={point.y}
                  r="2.5"
                  fill="#dc3f3a"
                  stroke="#f5f2ea"
                  strokeWidth="0.8"
                />
              ))}
              {chartModel.outputSegments.map((points, index) => (
                <polyline
                  key={`output-${index}`}
                  fill="none"
                  stroke="#dc3f3a"
                  strokeWidth="2.7"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  points={points}
                />
              ))}
              {chartModel.promptSegments.map((points, index) => (
                <polyline
                  key={`prompt-${index}`}
                  fill="none"
                  stroke="#2c7be5"
                  strokeWidth="2.5"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  points={points}
                />
              ))}
              {chartModel.promptPoints.map((point) => (
                <circle
                  key={point.key}
                  cx={point.x}
                  cy={point.y}
                  r="2.5"
                  fill="#2c7be5"
                  stroke="#f5f2ea"
                  strokeWidth="0.8"
                />
              ))}
              {chartModel.totalPoints.map((point) => (
                <circle
                  key={point.key}
                  cx={point.x}
                  cy={point.y}
                  r="2.2"
                  fill="#f2b84b"
                  stroke="#1d140d"
                  strokeWidth="0.9"
                />
              ))}
            </svg>
            {!chartModel.visibleSamples.length ? (
              <p className="helper-text benchmark-chart-empty">
                {chartModel.lastSampleOutsideRange
                  ? `Nema uzoraka u izabranom opsegu. Poslednji stvarni uzorak je star ${formatDurationLabel(
                      chartModel.inactiveForMs ?? 0,
                    )}; probaj 15m ili 1h za siri pregled.`
                  : "Nema uzoraka u izabranom opsegu. Graf i dalje prati vreme u realnom intervalu od 5s."}
              </p>
            ) : null}
          </div>
          <div className="benchmark-legend">
            <span className="status-label">Legenda</span>
            <div className="helper-text">
              <span
                style={{
                  display: "inline-block",
                  width: "14px",
                  height: "14px",
                  background: "#2c7be5",
                  marginRight: "8px",
                  borderRadius: "999px",
                }}
              />
              Input tok/s
            </div>
            <div className="helper-text">
              <span
                style={{
                  display: "inline-block",
                  width: "14px",
                  height: "14px",
                  background: "#dc3f3a",
                  marginRight: "8px",
                  borderRadius: "999px",
                }}
              />
              Output tok/s
            </div>
            <div className="helper-text">
              <span
                style={{
                  display: "inline-block",
                  width: "14px",
                  height: "14px",
                  background: "#f2b84b",
                  marginRight: "8px",
                  borderRadius: "999px",
                }}
              />
              Ukupno tok/s
            </div>
            <div className="helper-text">
              <span
                style={{
                  display: "inline-block",
                  width: "14px",
                  height: "2px",
                  background: "#9a948a",
                  marginRight: "8px",
                  verticalAlign: "middle",
                }}
              />
              Neaktivan period
            </div>
          </div>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Request activity</span>
        <p className="helper-text">
          Zahtevi: {benchmark.requestCount} | Stabilnost: {benchmark.activity.stability.label} (
          {benchmark.activity.stability.score})
        </p>
        <p className="helper-text">{benchmark.activity.stability.reason}</p>
        <div className="inline-actions">
          <button type="button" onClick={onOpenLogs}>
            Otvori puni live log
          </button>
        </div>
        <p className="helper-text">Zadnjih 30 linija</p>
        <pre
          className="helper-text"
          style={{
            whiteSpace: "pre-wrap",
            maxHeight: "260px",
            overflowY: "auto",
            background: "rgba(0,0,0,0.12)",
            padding: "12px",
            borderRadius: "12px",
          }}
        >
          {(benchmark.liveLog.lines.length
            ? benchmark.liveLog.lines
            : ["Jos nema dostupnog live log preview-ja."]).join("\n")}
        </pre>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Benchmark istorija</span>
        <div className="inline-actions benchmark-export-row">
          <button type="button" onClick={() => void handleExport("json")}>
            Export JSON
          </button>
          <button type="button" onClick={() => void handleExport("csv")}>
            Export CSV
          </button>
          <span className="helper-text">
            Compare selected runs: {selectedCompareRunIds.length}
          </span>
        </div>
        <div className="benchmark-compare-panel">
          {compareError ? <p className="helper-text">{compareError}</p> : null}
          {comparePayload ? (
            <>
              <div className="benchmark-compare-grid">
                <article className="status-card">
                  <span className="status-label">Best total tok/s</span>
                  <strong className="status-value">
                    {formatThroughput(comparePayload.comparison.totalTokensPerSecond.bestValue)}
                  </strong>
                  <p className="helper-text">
                    Run: {comparePayload.comparison.totalTokensPerSecond.bestRunId || "--"}
                  </p>
                </article>
                <article className="status-card">
                  <span className="status-label">Best output tok/s</span>
                  <strong className="status-value">
                    {formatThroughput(comparePayload.comparison.completionTokensPerSecond.bestValue)}
                  </strong>
                  <p className="helper-text">
                    Run: {comparePayload.comparison.completionTokensPerSecond.bestRunId || "--"}
                  </p>
                </article>
                <article className="status-card">
                  <span className="status-label">Fastest avg ms</span>
                  <strong className="status-value">
                    {comparePayload.comparison.totalMs.bestValue !== null
                      ? `${comparePayload.comparison.totalMs.bestValue.toFixed(0)} ms`
                      : "--"}
                  </strong>
                  <p className="helper-text">Run: {comparePayload.comparison.totalMs.bestRunId || "--"}</p>
                </article>
              </div>
              <p className="helper-text">{comparePayload.summary}</p>
            </>
          ) : (
            <p className="helper-text">
              Izaberi najmanje dva saved run-a da bi compare prikaz bio aktivan.
            </p>
          )}
        </div>
        <div className="model-list">
          {benchmark.savedRuns.length ? (
            benchmark.savedRuns.map((run) => (
              <article className="model-item benchmark-saved-run-card" key={run.runId}>
                <div className="section-header">
                  <div>
                    <strong>{run.mode === "battery" ? run.batteryName : run.scenarioName}</strong>
                    <div className="muted-line">
                      {run.status} | {run.runtimeLabel} | {run.modelLabel}
                    </div>
                  </div>
                  <label className="benchmark-compare-toggle">
                    <input
                      type="checkbox"
                      checked={selectedCompareRunIds.includes(run.runId)}
                      onChange={() => toggleCompareRun(run.runId)}
                    />
                    Compare
                  </label>
                </div>
                <div className="browser-chip-row">
                  <span className="browser-badge">Context {formatCompactTokens(run.context)}</span>
                  <span className="browser-badge">Output {formatCompactTokens(run.outputTokens)}</span>
                  <span className="browser-badge">Profile {run.profile}</span>
                  <span className="browser-badge">Thinking {run.thinkingMode}</span>
                </div>
                <div className="muted-line">
                  Start {formatDateTimeLabel(run.startedAt)}{" "}
                  {run.finishedAt ? `-> ${formatDateTimeLabel(run.finishedAt)}` : ""}
                </div>
                {run.currentMetric ? (
                  <div className="summary-metrics">
                    <span>Total {formatThroughput(run.currentMetric.totalTokensPerSecond)}</span>
                    <span>Output {formatThroughput(run.currentMetric.completionTokensPerSecond)}</span>
                    <span>
                      Avg ms{" "}
                      {run.currentMetric.totalMs !== undefined ? `${run.currentMetric.totalMs.toFixed(0)} ms` : "--"}
                    </span>
                  </div>
                ) : null}
              </article>
            ))
          ) : (
            <article className="model-item">
              <div className="muted-line">Jos nema sacuvane benchmark istorije.</div>
            </article>
          )}
        </div>
      </section>
    </>
  );
}
