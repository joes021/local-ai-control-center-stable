import { useEffect, useMemo, useRef, useState } from "react";

import { CustomSelect } from "../components/CustomSelect";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import { RuntimeResourcePanel } from "../components/RuntimeResourcePanel";
import { TelemetryPanel } from "../components/TelemetryPanel";
import {
  RuntimePilotActionDeck,
  type RuntimePilotActionDeckItem,
} from "../components/shell/RuntimePilotActionDeck";
import {
  RuntimePilotStatusDeck,
  type RuntimePilotStatusDeckItem,
} from "../components/shell/RuntimePilotStatusDeck";
import {
  clearBenchmarkHistory,
  exportBenchmarkRuns,
  fetchBenchmark,
  fetchObservability,
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
  ObservabilityPayload,
  SettingsPayload,
} from "../lib/types";

const REALTIME_REFRESH_MS = 1000;
const CHART_GAP_MS = REALTIME_REFRESH_MS + 1500;
const CHART_WIDTH = 640;
const CHART_HEIGHT = 180;
const CHART_OFFSET_X = 48;
const CHART_OFFSET_Y = 10;
const SAVED_RUNS_PER_PAGE = 10;

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

const METRIC_OPTIONS = [
  {
    key: "promptTokensPerSecond",
    label: "Input tokeni",
    shortLabel: "Input tok/s",
    color: "#2c7be5",
    pointStroke: "#f5f2ea",
  },
  {
    key: "completionTokensPerSecond",
    label: "Output tokeni",
    shortLabel: "Output tok/s",
    color: "#dc3f3a",
    pointStroke: "#f5f2ea",
  },
  {
    key: "totalTokensPerSecond",
    label: "Ukupno tokeni",
    shortLabel: "Ukupno tok/s",
    color: "#f2b84b",
    pointStroke: "#1d140d",
  },
] as const;

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

type BenchmarkSourceSummaryItem = {
  key: string;
  label: string;
  count: number;
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

function formatBenchmarkState(status: string | undefined | null) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "running") {
    return "U toku";
  }
  if (normalized === "queued") {
    return "U redu";
  }
  if (normalized === "completed" || normalized === "done") {
    return "Završeno";
  }
  if (normalized === "failed" || normalized === "error") {
    return "Greška";
  }
  if (normalized === "idle") {
    return "Miruje";
  }
  return normalized ? normalized : "Spremno";
}

function formatBenchmarkRunStatusBadge(status: string | undefined | null) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "queued") {
    return "Čeka";
  }
  if (normalized === "running") {
    return "Radi";
  }
  if (normalized === "done" || normalized === "completed") {
    return "Gotovo";
  }
  if (normalized === "failed" || normalized === "error") {
    return "Greška";
  }
  return formatBenchmarkState(status);
}

function splitBenchmarkRunStatusTitle(scenarioName: string | undefined | null) {
  const normalizedName = String(scenarioName || "").trim();
  if (!normalizedName) {
    return { title: "Scenario", passLabel: "" };
  }
  const separator = "· prolaz";
  const separatorIndex = normalizedName.toLowerCase().indexOf(separator);
  if (separatorIndex === -1) {
    return { title: normalizedName, passLabel: "" };
  }
  const title = normalizedName.slice(0, separatorIndex).trim();
  const passDetail = normalizedName.slice(separatorIndex + separator.length).trim();
  return {
    title: title || normalizedName,
    passLabel: passDetail ? `Prolaz ${passDetail}` : "",
  };
}

function compactBenchmarkRunStatusSummary(summary: string | undefined | null, status: string | undefined | null) {
  const normalizedSummary = String(summary || "").trim();
  const normalizedStatus = String(status || "").trim().toLowerCase();
  if (!normalizedSummary) {
    return "";
  }
  if (normalizedSummary === "Benchmark scenario je završen." || normalizedStatus === "done") {
    return "Završen signal.";
  }
  if (normalizedSummary === "Scenario se izvršava." || normalizedStatus === "running") {
    return "Run je u toku.";
  }
  if (normalizedSummary === "čeka pokretanje." || normalizedSummary === "Čeka pokretanje." || normalizedStatus === "queued") {
    return "Čeka start.";
  }
  return normalizedSummary;
}

function shouldShowBenchmarkRunStatusSummary(status: string | undefined | null, summary: string) {
  const normalizedStatus = String(status || "").trim().toLowerCase();
  if (normalizedStatus === "done" && summary === "Završen signal.") {
    return false;
  }
  if (normalizedStatus === "running" && summary === "Run je u toku.") {
    return false;
  }
  if (normalizedStatus === "queued" && summary === "Čeka start.") {
    return false;
  }
  return Boolean(summary);
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

function buildChartStatus(
  lastSample: HistoryPoint | null,
  nowTickMs: number,
  metricKey: MetricKey,
  metricLabel: string,
) {
  if (!lastSample) {
    return `čekam prve benchmark uzorke | poslednji ${metricLabel.toLowerCase()}: --`;
  }

  const inactiveForMs = Math.max(0, nowTickMs - lastSample.timestampMs);
  const lastThroughput = formatThroughput(lastSample[metricKey]);

  if (inactiveForMs <= CHART_GAP_MS) {
    return `live | ${metricLabel}: ${lastThroughput} | pre ${formatDurationLabel(inactiveForMs)}`;
  }

  return `nema novih zahteva u poslednjih ${formatDurationLabel(inactiveForMs)} | poslednji ${metricLabel.toLowerCase()}: ${lastThroughput}`;
}

function findRangeByKey(rangeKey: RangeKey) {
  return RANGE_OPTIONS.find((option) => option.key === rangeKey) ?? RANGE_OPTIONS[0];
}

function normalizeBenchmarkSource(source: string | undefined) {
  if (source === "runtime") {
    return "runtime";
  }
  if (source === "tuning-lab") {
    return "tuning-lab";
  }
  return "other";
}

function buildBenchmarkSourceLabel(source: string) {
  if (source === "runtime") {
    return "Aktivni runtime";
  }
  if (source === "tuning-lab") {
    return "Tuning Lab";
  }
  return "Drugi llama.cpp tok";
}

function buildBenchmarkSourceSummary(samples: HistoryPoint[], liveCurrent: BenchmarkHistoryItem | null) {
  const counts = new Map<string, number>();
  samples.forEach((sample) => {
    const normalizedSource = normalizeBenchmarkSource(sample.source);
    counts.set(normalizedSource, (counts.get(normalizedSource) ?? 0) + 1);
  });

  if (liveCurrent) {
    const normalizedSource = normalizeBenchmarkSource(liveCurrent.source);
    if (!counts.has(normalizedSource)) {
      counts.set(normalizedSource, 1);
    }
  }

  return (["runtime", "tuning-lab", "other"] as const)
    .filter((source) => counts.has(source))
    .map((source) => ({
      key: source,
      label: buildBenchmarkSourceLabel(source),
      count: counts.get(source) ?? 0,
    })) satisfies BenchmarkSourceSummaryItem[];
}

export function BenchmarkPage({
  onOpenLogs,
  onOpenTuningLab,
}: {
  onOpenLogs: () => void;
  onOpenTuningLab?: () => void;
}) {
  const [benchmark, setBenchmark] = useState<BenchmarkPayload | null>(null);
  const [observability, setObservability] = useState<ObservabilityPayload | null>(null);
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
  const [selectedMetricKey, setSelectedMetricKey] = useState<MetricKey>("totalTokensPerSecond");
  const [nowTickMs, setNowTickMs] = useState(() => Date.now());
  const [savedRunsPage, setSavedRunsPage] = useState(1);
  const isMountedRef = useRef(false);
  const inFlightRef = useRef(false);
  const requestIdRef = useRef(0);
  const setupSectionRef = useRef<HTMLElement | null>(null);
  const runSectionRef = useRef<HTMLElement | null>(null);
  const chartSectionRef = useRef<HTMLElement | null>(null);
  const historySectionRef = useRef<HTMLElement | null>(null);

  async function load() {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    inFlightRef.current = true;
    try {
      const [payload, nextSettings, nextObservability] = await Promise.all([
        fetchBenchmark(),
        fetchSettings(),
        fetchObservability(),
      ]);
      if (!isMountedRef.current || requestId !== requestIdRef.current) {
        return;
      }
      setBenchmark(payload);
      setSettingsPayload(nextSettings);
      setObservability(nextObservability);
      setError(null);
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
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
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
  const selectedMetricOption = useMemo(
    () => METRIC_OPTIONS.find((option) => option.key === selectedMetricKey) ?? METRIC_OPTIONS[2],
    [selectedMetricKey],
  );
  const selectedRangeOption = useMemo(() => findRangeByKey(selectedRangeKey), [selectedRangeKey]);

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
  const savedRuns = benchmark?.savedRuns ?? [];
  const selectedScenario =
    selectedBattery.scenarios.find((scenario) => scenario.id === selectedScenarioId) ??
    selectedBattery.scenarios[0] ??
    null;
  const benchmarkStateTitle = formatBenchmarkState(
    activeRun?.status && activeRun.status !== "idle" ? activeRun.status : benchmark?.liveState?.status,
  );
  const benchmarkStateDetail =
    actionMessage ||
    activeRun?.message ||
    benchmark?.liveState?.reason ||
    "Pokreni scenario ili celu bateriju, pa prati signal uživo i istoriju ispod.";
  const benchmarkLiveThroughput =
    benchmark?.telemetry?.liveNowTokensPerSecond ??
    benchmark?.telemetry?.lastSignalTokensPerSecond ??
    benchmark?.averages?.totalTokensPerSecond;
  const benchmarkThroughputLabel = formatThroughput(benchmarkLiveThroughput);
  const benchmarkRunHeadline =
    activeRun?.mode === "battery" && activeRun?.totalScenarios
      ? `${Math.max(activeRun.currentIndex || 0, 1)}/${activeRun.totalScenarios} · ${
          activeRun.currentScenarioName || selectedBattery.name
        }`
      : activeRun?.scenarioName || selectedScenario?.name || "Nema izabranog testa";
  const benchmarkPresetSummary = currentWorkflowPreset
    ? `${currentWorkflowPreset.label} · ${currentWorkflowPreset.benchmarkDefaults.runLabel}`
    : "Ručno pokretanje benchmarka";

  const savedRunsTotalPages = useMemo(
    () => Math.max(1, Math.ceil(savedRuns.length / SAVED_RUNS_PER_PAGE)),
    [savedRuns.length],
  );

  useEffect(() => {
    setSavedRunsPage((current) => Math.min(current, savedRunsTotalPages));
  }, [savedRunsTotalPages]);

  const savedRunsPageStart = (savedRunsPage - 1) * SAVED_RUNS_PER_PAGE;
  const paginatedSavedRuns = savedRuns.slice(savedRunsPageStart, savedRunsPageStart + SAVED_RUNS_PER_PAGE);
  const savedRunsPageEnd = Math.min(savedRunsPageStart + SAVED_RUNS_PER_PAGE, savedRuns.length);

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
      .map((item) => (item ? parseMetricValue(item[selectedMetricKey]) : null))
      .filter((value): value is number => value !== null);
    const maxValue = Math.max(
      ...visibleSamples.map((item) => parseMetricValue(item[selectedMetricKey]) ?? 0),
      ...fallbackValues,
      1,
    );
    const yAxisLabels = [maxValue, maxValue * 0.66, maxValue * 0.33, 0].map(formatYAxisLabel);
    const selectedPoints = buildMetricPoints(
      visibleSamples,
      selectedMetricKey,
      rangeStartMs,
      rangeEndMs,
      maxValue,
    );
    const inactiveForMs = lastSample ? Math.max(0, nowTickMs - lastSample.timestampMs) : null;
    const lastSampleOutsideRange = Boolean(lastSample && lastSample.timestampMs < rangeStartMs);

    return {
      selectedPoints,
      selectedSegments: buildSolidSegments(selectedPoints),
      selectedGapSegments: buildInactivitySegments(
        selectedPoints,
        rangeStartMs,
        rangeEndMs,
        maxValue,
        previousSample ? parseMetricValue(previousSample[selectedMetricKey]) : null,
      ),
      rangeStartMs,
      rangeEndMs,
      statusText: buildChartStatus(lastSample, nowTickMs, selectedMetricKey, selectedMetricOption.shortLabel),
      tickMarks: buildTimeTicks(rangeStartMs, rangeEndMs, selectedRangeKey),
      visibleSamples,
      lastSampleOutsideRange,
      inactiveForMs,
      yAxisLabels,
    };
  }, [
    benchmark?.liveCurrent,
    normalizedSignalHistory,
    nowTickMs,
    selectedMetricKey,
    selectedMetricOption.shortLabel,
    selectedRangeKey,
  ]);

  const chartSourceSummary = useMemo(
    () => buildBenchmarkSourceSummary(chartModel.visibleSamples, benchmark?.liveCurrent ?? null),
    [benchmark?.liveCurrent, chartModel.visibleSamples],
  );

  if (!benchmark) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam benchmark..."
        onRetry={() => {
          setError(null);
          void load();
        }}
      />
    );
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

  async function handleRunBattery(repeatCount = 1) {
    const result = await runBatteryBenchmark(selectedBattery.id, repeatCount);
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
    setSavedRunsPage(1);
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

  const benchmarkStatusItems: RuntimePilotStatusDeckItem[] = [
    {
      id: "run-state",
      label: "Run stanje",
      value: benchmarkStateTitle,
      detail: benchmarkStateDetail,
      action: "Idi na run signal",
      icon: "benchmark",
      accent: "rgba(88, 222, 193, 0.38)",
      onClick: () => runSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "scenario",
      label: "Scenario",
      value: benchmarkRunHeadline,
      detail: selectedScenario?.description || "Izabrani scenario ili trenutni battery tok koji benchmark sada prati.",
      action: "Vrati se na izbor testa",
      icon: "control",
      accent: "rgba(109, 172, 255, 0.34)",
      onClick: () => setupSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "throughput",
      label: "Throughput",
      value: benchmarkThroughputLabel,
      detail: "Živi benchmark signal koji kasnije potvrđuje grafikon i telemetrija.",
      action: "Idi na grafikon",
      icon: "telemetry",
      accent: "rgba(242, 184, 75, 0.38)",
      onClick: () => chartSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "battery",
      label: "Baterija",
      value: selectedBattery.name,
      detail: `${selectedBattery.scenarios.length} scenarija | izvor ${selectedBattery.source}`,
      action: "Pogledaj setup",
      icon: "benchmark",
      accent: "rgba(156, 126, 255, 0.34)",
      onClick: () => setupSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "profile",
      label: "Profil",
      value: currentWorkflowPreset?.label ?? settingsPayload?.profile ?? "--",
      detail: benchmarkPresetSummary,
      action: "Otvori istoriju",
      icon: "settings",
      accent: "rgba(255, 129, 177, 0.34)",
      onClick: () => historySectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
  ];

  const benchmarkActionItems: RuntimePilotActionDeckItem[] = [
    {
      id: "run-selected",
      code: "RUN",
      title: "Pokreni scenario",
      subtitle: selectedScenario?.name || "SCENARIO + SIGNAL",
      icon: "play",
      detail: benchmarkStateDetail,
      tone: "primary",
      disabled: !selectedScenarioId,
      onClick: () => void handleRunSelected(),
    },
    {
      id: "run-battery",
      code: "BAT",
      title: "Pokreni bateriju",
      subtitle: `${selectedBattery.scenarios.length} scenarija`,
      icon: "benchmark",
      detail: selectedBattery.name,
      disabled: !selectedBattery.scenarios.length,
      onClick: () => void handleRunBattery(1),
    },
    {
      id: "open-lab",
      code: "LAB",
      title: "Otvori Tuning Lab",
      subtitle: "SLOTOVI + WINNER",
      icon: "tuning",
      disabled: !onOpenTuningLab,
      onClick: () => onOpenTuningLab?.(),
    },
    {
      id: "open-logs",
      code: "LOG",
      title: "Otvori Logove",
      subtitle: "LIVE TRAG + PORUKE",
      icon: "logs",
      onClick: onOpenLogs,
    },
    {
      id: "export",
      code: "EXP",
      title: "Izvoz istorije",
      subtitle: "JSON + CSV",
      icon: "benchmark",
      detail:
        selectedCompareRunIds.length >= 1
          ? `Izabrano za compare: ${selectedCompareRunIds.length}`
          : `Sačuvani run-ovi: ${savedRuns.length}`,
      actions: (
        <>
          <button
            type="button"
            className="benchmark-export-button benchmark-export-button-primary"
            onClick={() => void handleExport("json")}
          >
            <span className="benchmark-export-code">JSN</span>
            <span className="benchmark-export-copy">
              <span className="benchmark-export-title">Izvezi JSON</span>
              <span className="benchmark-export-subtitle">RAW RUN ISTORIJA</span>
            </span>
          </button>
          <button
            type="button"
            className="benchmark-export-button"
            onClick={() => void handleExport("csv")}
          >
            <span className="benchmark-export-code">CSV</span>
            <span className="benchmark-export-copy">
              <span className="benchmark-export-title">Izvezi CSV</span>
              <span className="benchmark-export-subtitle">TABELARNI PRESEK</span>
            </span>
          </button>
        </>
      ),
    },
  ];

  return (
    <div className="benchmark-page runtimepilot-rack-page">
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <div className="runtimepilot-secondary-hub runtimepilot-secondary-hub-fullwidth">
        <div className="runtimepilot-secondary-hub-main">
          <PageFlowCard
            title="Benchmark tok"
            summary="Prvo namesti scenario ili bateriju, zatim pokreni benchmark iz vršnog action deck-a, pa dole prati throughput, grafikon i istoriju bez bočnog rail-a."
            steps={[
              {
                title: "Izaberi scenario ili bateriju",
                detail: "Prvo namesti ulaz koji želiš da meriš, bez lutanja po dodatnim komandnim blokovima.",
              },
              {
                title: "Pokreni run sa desnog rail-a",
                detail: "Scenario i baterija se pokreću direktno sa action rail-a, pa ekran levo ostaje fokusiran na rezultat.",
              },
              {
                title: "Gledaj telemetriju i istoriju",
                detail: "Kad vidiš signal, uporedi ga sa saved run-ovima ili pređi u Tuning Lab za dublji winner workflow.",
              },
            ]}
          />
          <RuntimePilotStatusDeck
            eyebrow="Status dashboard"
            title="Brzi signal benchmarka"
            helper="Pet kartica odmah pokazuje run stanje, scenario, throughput, bateriju i aktivni profil ili preset."
            items={benchmarkStatusItems}
          />
          <RuntimePilotActionDeck
            eyebrow="Akcije"
            title="Pokretanje i izvoz"
            helper="Na vrhu ostaju samo stvarni klikovi: start scenarija, start baterije, prelaz u Tuning Lab, logovi i izvoz istorije."
            items={benchmarkActionItems}
          />

          <div className="benchmark-hifi-stack">
            <div className="benchmark-mixer-deck">
              <section
                ref={setupSectionRef}
                className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module benchmark-faceplate-panel"
              >
        <div className="benchmark-faceplate-headline">
          <div className="runtimepilot-inline-heading">
            <span className="status-label">Izbor scenarija i baterije</span>
            <strong className="status-value">Ulaz pre pokretanja</strong>
          </div>
          {currentWorkflowPreset ? (
            <span className="runtimepilot-home-guidance-pill">
              Preset radnog toka: {currentWorkflowPreset.label}
            </span>
          ) : null}
        </div>
        <div className="benchmark-setup-grid">
          <div className="benchmark-setup-row">
            <div className="benchmark-select-shell">
              <span className="status-label">Scenario</span>
              <CustomSelect
                value={selectedScenarioId}
                options={scenarioOptions}
                onChange={setSelectedScenarioId}
                ariaLabel="Izaberi benchmark scenario"
              />
            </div>
            <div className="benchmark-select-shell">
              <span className="status-label">Učitaj bateriju</span>
              <CustomSelect
                value={selectedBattery.id}
                options={batteryOptions}
                onChange={(batteryId) => void handleLoadBattery(batteryId)}
                ariaLabel="Učitaj benchmark bateriju"
              />
            </div>
            <article className="benchmark-setup-readout runtimepilot-readout-card">
              <span className="status-label">Glavni rezultat</span>
              <strong>{benchmarkRunHeadline}</strong>
              <p className="helper-text">{benchmarkStateDetail}</p>
            </article>
            <article className="benchmark-setup-readout runtimepilot-readout-card">
              <span className="status-label">Signal sada</span>
              <strong>{benchmarkThroughputLabel}</strong>
              <p className="helper-text">
                {benchmarkStateTitle} ·{" "}
                {benchmark?.telemetry?.lastSignalStateLabel || "Čeka sledeći throughput signal."}
              </p>
            </article>
          </div>
          <div className="benchmark-setup-row benchmark-setup-row-compact">
            <article className="benchmark-setup-readout runtimepilot-readout-card">
              <span className="status-label">Baterija</span>
              <strong>{selectedBattery.name}</strong>
              <p className="helper-text">
                {selectedBattery.scenarios.length} scenarija · {benchmarkPresetSummary}
              </p>
            </article>
            <button
              type="button"
              className="secondary-button"
              title="Pokreni bateriju x2"
              onClick={() => void handleRunBattery(2)}
            >
              BX2
            </button>
            <button
              type="button"
              className="secondary-button"
              title="Pokreni bateriju x5"
              onClick={() => void handleRunBattery(5)}
            >
              BX5
            </button>
            <button
              type="button"
              className="secondary-button"
              title="Pokreni bateriju x10"
              onClick={() => void handleRunBattery(10)}
            >
              BX10
            </button>
          </div>
          <div className="inline-actions benchmark-setup-utility-actions">
            <button type="button" className="action-button-soft" onClick={handleSaveBattery}>
              Sačuvaj bateriju
            </button>
            <button type="button" className="action-button-soft" onClick={handleRestoreDefaults}>
              Vrati podrazumevane testove
            </button>
            <button type="button" className="secondary-button" onClick={handleClearHistory}>
              Obriši benchmark vrednosti
            </button>
          </div>
        </div>
        <p className="helper-text benchmark-command-note">
          {actionMessage || "Rail desno pokreće scenario ili celu bateriju, a ovde ostaju izbor, repeat i uređivanje."}
        </p>
      </section>

      <section className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module benchmark-faceplate-panel">
        <div className="benchmark-faceplate-headline">
          <div className="runtimepilot-inline-heading">
            <span className="status-label">Editor baterije</span>
            <strong className="status-value">Scenario i prompt</strong>
          </div>
          <span className="runtimepilot-home-guidance-pill">Jedan izbor, jedna izmena</span>
        </div>
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
                    Uređuješ jedan scenario, lista gore ostaje kompaktna.
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
      </div>

      <div className="benchmark-transport-deck">
      <section className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module benchmark-faceplate-panel benchmark-support-shell benchmark-context-shell">
        <div className="runtime-faceplate-head runtimepilot-inline-heading">
          <span className="status-label">Kontekst benchmarka</span>
          <strong className="status-value">
            {benchmarkEnvironment?.modelLabel || "Nema aktivnog modela"}
          </strong>
        </div>
        <div className="runtime-faceplate-copy benchmark-context-main">
          <p className="helper-text">
            Model: {benchmarkEnvironment?.modelLabel || "--"} | Runtime: {benchmarkEnvironment?.runtimeLabel || "--"} |
            Profil: {benchmarkEnvironment?.profile || "--"} | Razmišljanje:{" "}
            {benchmarkEnvironment?.thinkingMode || "--"}
          </p>
          <p className="helper-text">{benchmark?.liveState?.reason}</p>
        </div>
        <div className="runtime-faceplate-rail">
          <span className="status-label">Brzi signal</span>
          <div className="browser-chip-row">
            <span className="browser-badge">Kontekst {formatCompactTokens(benchmarkEnvironment?.context)}</span>
            <span className="browser-badge">Izlaz {formatCompactTokens(benchmarkEnvironment?.outputTokens)}</span>
            <span className="browser-badge">
              Stanje uživo {benchmark?.liveState?.status || "idle"}
            </span>
          </div>
        </div>
      </section>

      <section
        ref={runSectionRef}
        className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module benchmark-faceplate-panel benchmark-run-shell"
      >
        <div className="benchmark-support-shell">
          <div className="runtime-faceplate-head runtimepilot-inline-heading">
            <span className="status-label">Pokretanje benchmarka</span>
            <strong className="status-value">
              {activeRun?.mode === "battery"
                ? `${activeRun.currentIndex}/${activeRun.totalScenarios} · ${
                    activeRun.currentScenarioName || "čeka"
                  }`
                : activeRun?.scenarioName || "nema aktivnog testa"}
            </strong>
          </div>
          <div className="runtime-faceplate-copy">
            <div className="benchmark-run-summary">
              <div className="benchmark-run-main">
                <strong className="status-value">{activeRun?.message || "Benchmark nije pokrenut."}</strong>
                <span className={`scenario-status-badge scenario-status-${activeRun?.status || "idle"}`}>
                  {activeRun?.status || "idle"}
                </span>
              </div>
              <div className="benchmark-run-meta">
                <span>Napredak {activeRun?.percent ?? 0}%</span>
                <span>Scenarija {activeRun?.totalScenarios ?? 0}</span>
              </div>
            </div>
          </div>
          <div className="runtime-faceplate-rail">
            <span className="status-label">Run signal</span>
            <p className="helper-text">
              {activeRun?.mode === "battery"
                ? "Baterija vrti scenarije redom i ovde odmah vidiš gde je stala."
                : "Jedan scenario daje najbrži signal pre šire baterije."}
            </p>
          </div>
        </div>
        <div className="benchmark-run-status-list">
          {(activeRun?.scenarioStatuses ?? []).map((item) => {
            const titleParts = splitBenchmarkRunStatusTitle(item.scenarioName);
            const compactSummary = compactBenchmarkRunStatusSummary(item.summary, item.status);
            const shouldShowSummary = shouldShowBenchmarkRunStatusSummary(item.status, compactSummary);

            return (
              <article
                className={`benchmark-run-status-row${shouldShowSummary ? "" : " benchmark-run-status-row-terse"}`}
                key={item.scenarioId}
              >
                <div className="benchmark-run-status-header">
                  <div className="benchmark-run-status-title-block">
                    <strong>{titleParts.title}</strong>
                    {titleParts.passLabel ? (
                      <span className="benchmark-run-status-pass">{titleParts.passLabel}</span>
                    ) : null}
                  </div>
                  <span className={`scenario-status-badge scenario-status-${item.status}`}>
                    {formatBenchmarkRunStatusBadge(item.status)}
                  </span>
                </div>
                {shouldShowSummary ? (
                  <div className="benchmark-run-status-copy">
                    <div className="muted-line">{compactSummary}</div>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
        <div style={{ display: "none" }}>queued running done failed</div>
      </section>

      <section className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module benchmark-faceplate-panel benchmark-activity-shell">
        <div className="benchmark-support-shell">
          <div className="runtime-faceplate-head runtimepilot-inline-heading">
            <span className="status-label">Aktivnost zahteva</span>
            <strong className="status-value">
              {benchmark.activity.stability.label} ({benchmark.activity.stability.score})
            </strong>
          </div>
          <div className="runtime-faceplate-copy">
            <p className="helper-text">Zahtevi: {benchmark.requestCount}</p>
            <p className="helper-text">{benchmark.activity.stability.reason}</p>
          </div>
          <div className="runtime-faceplate-rail">
            <span className="status-label">Trag uživo</span>
            <p className="helper-text">Otvaranje punih logova je premešteno na desni action rail.</p>
          </div>
        </div>
        <p className="helper-text">Zadnjih 30 linija</p>
        <pre className="helper-text benchmark-log-preview">
          {(benchmark.liveLog.lines.length
            ? benchmark.liveLog.lines
            : ["Još nema dostupnog live log preview-ja."]).join("\n")}
        </pre>
      </section>
      </div>

      <div className="benchmark-monitor-deck">
      <p className="helper-text benchmark-monitor-note">
        CPU uživo, RAM uživo i VRAM uživo ostaju odmah vidljivi dok telemetrija, offload i istorija
        rade kao jedan hi-fi nadzorni dek. Režim izvršavanja brzo razlikuje GPU VRAM dominantno,
        Hibrid VRAM + RAM i CPU + RAM tok.
      </p>
      <TelemetryPanel benchmark={benchmark} variant="benchmark" />
      <RuntimeResourcePanel observability={observability} />

      <section
        ref={chartSectionRef}
        className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module benchmark-faceplate-panel benchmark-chart-shell"
      >
        <div className="benchmark-card-header">
          <div className="benchmark-chart-head">
            <div className="runtimepilot-inline-heading">
              <span className="status-label">Grafikon benchmarka</span>
              <strong className="status-value benchmark-chart-status">{chartModel.statusText}</strong>
            </div>
            <div className="benchmark-chart-readouts">
              <article className="benchmark-chart-readout runtimepilot-readout-card">
                <span className="status-label">Metrika</span>
                <strong>{selectedMetricOption.shortLabel}</strong>
                <p className="helper-text">Aktivna linija na display-u.</p>
              </article>
              <article className="benchmark-chart-readout runtimepilot-readout-card">
                <span className="status-label">Opseg</span>
                <strong>{selectedRangeOption.label}</strong>
                <p className="helper-text">Vremenski prozor prikaza.</p>
              </article>
              <article className="benchmark-chart-readout runtimepilot-readout-card">
                <span className="status-label">Uzorci</span>
                <strong>{chartModel.visibleSamples.length}</strong>
                <p className="helper-text">Tačke trenutno vidljive na grafu.</p>
              </article>
            </div>
          </div>
        </div>
        <div className="benchmark-chart-layout">
          <div className="benchmark-chart-panel">
            <div className="benchmark-chart-panel-topline">
              <div className="benchmark-chart-panel-metric-controls">
                <span className="status-label">Prikaz na grafikonu</span>
                <div className="benchmark-range-segment" role="tablist" aria-label="Prikaz na grafikonu">
                  {METRIC_OPTIONS.map((option) => (
                    <button
                      type="button"
                      key={option.key}
                      className={`benchmark-range-button${
                        option.key === selectedMetricKey ? " benchmark-range-button-active" : ""
                      }`}
                      onClick={() => setSelectedMetricKey(option.key)}
                    >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
              <div className="benchmark-chart-panel-range-controls">
                <span className="status-label">Vremenski opseg</span>
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
            </div>
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
              {chartModel.selectedGapSegments.map((segment) => (
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
              {chartModel.selectedSegments.map((points, index) => (
                <polyline
                  key={`selected-${index}`}
                  fill="none"
                  stroke={selectedMetricOption.color}
                  strokeWidth="3.2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  points={points}
                />
              ))}
              {chartModel.selectedPoints.map((point) => (
                <circle
                  key={point.key}
                  cx={point.x}
                  cy={point.y}
                  r="2.2"
                  fill={selectedMetricOption.color}
                  stroke={selectedMetricOption.pointStroke}
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
            <div className="benchmark-legend benchmark-legend-horizontal">
              <div className="benchmark-legend-strip">
                <article className="benchmark-legend-item benchmark-legend-item-title">
                  <span className="status-label">Aktivna metrika</span>
                  <strong>{selectedMetricOption.shortLabel}</strong>
                  <p className="helper-text">Skala i linija prate samo ovu metriku.</p>
                </article>
                <div className="benchmark-legend-readout">
                  <span
                    style={{
                      display: "inline-block",
                      width: "14px",
                      height: "14px",
                      background: selectedMetricOption.color,
                      marginRight: "8px",
                      borderRadius: "999px",
                    }}
                  />
                  {selectedMetricOption.shortLabel}
                </div>
                <div className="benchmark-legend-readout benchmark-legend-readout-muted">
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
                <article className="benchmark-legend-item">
                  <span className="status-label">Napomena</span>
                  <strong>Skala Y ose je fokusirana</strong>
                  <p className="helper-text">
                    Druge serije više ne razvlače prikaz dok porediš aktivni signal.
                  </p>
                </article>
              </div>
              <div className="benchmark-source-summary">
                <span className="status-label">Izvori llama.cpp signala</span>
                <p className="helper-text">
                  Graf sada prati sav llama.cpp-kompatibilni /slots throughput, pa se ovde vide i
                  tuning run-ovi i drugi lokalni tokovi, ne samo ručno pokrenut benchmark.
                </p>
                <div className="benchmark-source-chip-row">
                  {chartSourceSummary.length ? (
                    chartSourceSummary.map((item) => (
                      <span className="browser-chip" key={item.key}>
                        {item.label} · {item.count}
                      </span>
                    ))
                  ) : (
                    <>
                      <span className="browser-chip">Aktivni runtime</span>
                      <span className="browser-chip">Tuning Lab</span>
                      <span className="browser-chip">Drugi llama.cpp tok</span>
                    </>
                  )}
                </div>
                <p className="helper-text benchmark-chart-metric-note">
                  U izabranom opsegu prikazujemo samo izvore koji su stvarno poslali signal. Ako sada
                  nema uzoraka, oznake gore ostaju kao orijentir šta će graf uhvatiti čim tokeni krenu.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        ref={historySectionRef}
        className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module benchmark-faceplate-panel benchmark-history-shell"
      >
        <div className="benchmark-history-head">
          <div className="benchmark-history-headline runtimepilot-inline-heading">
            <span className="status-label">Benchmark istorija</span>
            <strong className="status-value">Sačuvani run-ovi i compare izlaz</strong>
          </div>
          <div className="browser-chip-row">
            <span className="browser-badge">Run-ovi {savedRuns.length}</span>
            <span className="browser-badge">Compare izbor {selectedCompareRunIds.length}</span>
          </div>
        </div>
        <article className="benchmark-history-compare-readout runtimepilot-readout-card">
          <span className="status-label">Compare signal</span>
          <strong>Uporedi izabrana pokretanja: {selectedCompareRunIds.length}</strong>
          <p className="helper-text">
            Kad čekiraš dva ili više run-a, dole se pali compare blok. Izvoz JSON/CSV je premešten na desni rail.
          </p>
        </article>
        {savedRuns.length ? (
          <div className="browser-pagination">
            <span>
              Prikazani rezultati {savedRunsPageStart + 1}-{savedRunsPageEnd} od {savedRuns.length} | Strana{" "}
              {savedRunsPage} / {savedRunsTotalPages}
            </span>
            <div className="inline-actions compact-actions">
              <button
                type="button"
                className="secondary-button"
                disabled={savedRunsPage <= 1}
                onClick={() => setSavedRunsPage((page) => Math.max(1, page - 1))}
              >
                Prethodna strana
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={savedRunsPage >= savedRunsTotalPages}
                onClick={() => setSavedRunsPage((page) => Math.min(savedRunsTotalPages, page + 1))}
              >
                Sledeća strana
              </button>
            </div>
          </div>
        ) : null}
        <div className="benchmark-compare-panel">
          {compareError ? <p className="helper-text">{compareError}</p> : null}
          {comparePayload ? (
            <>
              <div className="benchmark-compare-grid">
                <article className="status-card benchmark-compare-summary-card">
                  <span className="status-label">Best total tok/s</span>
                  <strong className="status-value">
                    {formatThroughput(comparePayload.comparison.totalTokensPerSecond.bestValue)}
                  </strong>
                  <p className="helper-text">
                    Run: {comparePayload.comparison.totalTokensPerSecond.bestRunId || "--"}
                  </p>
                </article>
                <article className="status-card benchmark-compare-summary-card">
                  <span className="status-label">Best output tok/s</span>
                  <strong className="status-value">
                    {formatThroughput(comparePayload.comparison.completionTokensPerSecond.bestValue)}
                  </strong>
                  <p className="helper-text">
                    Run: {comparePayload.comparison.completionTokensPerSecond.bestRunId || "--"}
                  </p>
                </article>
                <article className="status-card benchmark-compare-summary-card">
                  <span className="status-label">Fastest avg ms</span>
                  <strong className="status-value">
                    {comparePayload.comparison.totalMs.bestValue !== null
                      ? `${comparePayload.comparison.totalMs.bestValue.toFixed(0)} ms`
                      : "--"}
                  </strong>
                  <p className="helper-text">Run: {comparePayload.comparison.totalMs.bestRunId || "--"}</p>
                </article>
              </div>
              <article className="benchmark-history-empty runtimepilot-readout-card">
                <span className="status-label">Compare rezime</span>
                <strong>{comparePayload.summary}</strong>
                <p className="helper-text">
                  Ovde je namerno samo kratak zaključak, da ne tražiš bitan signal po karticama ispod.
                </p>
              </article>
            </>
          ) : (
            <article className="benchmark-history-empty runtimepilot-readout-card">
              <span className="status-label">Compare čeka izbor</span>
              <strong>Izaberi najmanje dva saved run-a da bi compare prikaz bio aktivan.</strong>
              <p className="helper-text">
                Čim čekiraš dva run-a, ovde ćeš dobiti pobednika bez ručnog poređenja po metrikama.
              </p>
            </article>
          )}
        </div>
        <div className="model-list">
          {savedRuns.length ? (
            paginatedSavedRuns.map((run) => (
              <article className="model-item benchmark-saved-run-card" key={run.runId}>
                <div className="benchmark-saved-run-topline">
                  <div className="benchmark-saved-run-head">
                    <span className="status-label">
                      {run.mode === "battery" ? "Battery run" : "Single scenario"}
                    </span>
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
                <div className="benchmark-saved-run-strip">
                  <article className="benchmark-saved-run-readout runtimepilot-readout-card">
                    <span className="status-label">Kontekst</span>
                    <strong>{formatCompactTokens(run.context)}</strong>
                    <p className="helper-text">Aktivni context za taj run.</p>
                  </article>
                  <article className="benchmark-saved-run-readout runtimepilot-readout-card">
                    <span className="status-label">Izlaz</span>
                    <strong>{formatCompactTokens(run.outputTokens)}</strong>
                    <p className="helper-text">Maksimalni output token limit.</p>
                  </article>
                  <article className="benchmark-saved-run-readout runtimepilot-readout-card">
                    <span className="status-label">Profil</span>
                    <strong>{run.profile}</strong>
                    <p className="helper-text">Profil koji je bio aktivan.</p>
                  </article>
                  <article className="benchmark-saved-run-readout runtimepilot-readout-card">
                    <span className="status-label">Razmišljanje</span>
                    <strong>{run.thinkingMode}</strong>
                    <p className="helper-text">Inference način za ovaj run.</p>
                  </article>
                </div>
                <div className="benchmark-saved-run-meta-line">
                  Start {formatDateTimeLabel(run.startedAt)}{" "}
                  {run.finishedAt ? `-> ${formatDateTimeLabel(run.finishedAt)}` : ""}
                </div>
                <div className="benchmark-saved-run-metrics">
                  <article className="benchmark-saved-run-metric runtimepilot-readout-card">
                    <span className="status-label">Total tok/s</span>
                    <strong>
                      {run.currentMetric ? formatThroughput(run.currentMetric.totalTokensPerSecond) : "--"}
                    </strong>
                  </article>
                  <article className="benchmark-saved-run-metric runtimepilot-readout-card">
                    <span className="status-label">Output tok/s</span>
                    <strong>
                      {run.currentMetric
                        ? formatThroughput(run.currentMetric.completionTokensPerSecond)
                        : "--"}
                    </strong>
                  </article>
                  <article className="benchmark-saved-run-metric runtimepilot-readout-card">
                    <span className="status-label">Avg ms</span>
                    <strong>
                      {run.currentMetric?.totalMs !== undefined
                        ? `${run.currentMetric.totalMs.toFixed(0)} ms`
                        : "--"}
                    </strong>
                  </article>
                </div>
              </article>
            ))
          ) : (
            <article className="model-item">
              <div className="muted-line">Još nema sačuvane benchmark istorije.</div>
            </article>
          )}
        </div>
      </section>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
