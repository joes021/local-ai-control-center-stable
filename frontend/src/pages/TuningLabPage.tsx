import { useEffect, useMemo, useRef, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import {
  applyTuningLabWinner,
  bootstrapOpenCode,
  exportTuningLabRun,
  fetchTuningLabRunStatus,
  fetchTuningLabSummary,
  importTuningSnippet,
  queueTuningLabBatch,
  queueTuningLabExperiment,
} from "../lib/api";
import type {
  ActionResult,
  TuningLabBatchPreset,
  TuningLabBatchTask,
  TuningLabDiffFile,
  TuningLabRun,
  TuningLabSettingsPatch,
  TuningLabSlot,
  TuningLabSummaryPayload,
} from "../lib/types";

const REFRESH_MS = 4000;

type SuccessCheckDraft = {
  label: string;
  command: string;
  kind: string;
};

type TuningDraft = {
  name: string;
  goal: string;
  taskPrompt: string;
  workingDirectory: string;
  successChecks: SuccessCheckDraft[];
  slots: TuningLabSlot[];
};

type HistoryFilters = {
  query: string;
  goal: string;
  runtime: string;
  status: string;
};

function formatDateTime(value: string | undefined) {
  if (!value) {
    return "--";
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString("sr-RS");
}

function formatTok(value: number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return `${value.toFixed(1)} tok/s`;
}

function formatMs(value: number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  const seconds = value / 1000;
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
}

function formatCount(value: number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return new Intl.NumberFormat("sr-RS").format(value);
}

function buildDraftFromSummary(payload: TuningLabSummaryPayload): TuningDraft {
  return {
    name: `Tuning Lab ${payload.context.activeModel || "run"}`,
    goal: "code",
    taskPrompt: "",
    workingDirectory: payload.context.workingDirectory || "",
    successChecks: [],
    slots: payload.slots.map((slot) => ({
      ...slot,
      settingsPatch: { ...slot.settingsPatch },
    })),
  };
}

function buildDraftForBatchTask(
  current: TuningDraft,
  preset: TuningLabBatchPreset,
  task: TuningLabBatchTask,
): TuningDraft {
  return {
    ...current,
    name: `${preset.label} · ${task.label}`,
    goal: task.goal,
    taskPrompt: task.taskPrompt,
    successChecks: task.successChecks.map((check) => ({
      label: check.label,
      command: check.command,
      kind: check.kind,
    })),
  };
}

function buildBatchRunName(preset: TuningLabBatchPreset, task: TuningLabBatchTask) {
  return `${preset.label} · ${task.label}`;
}

function buildBatchLoadLabel(difficulty: string) {
  if (difficulty === "easy") {
    return "Učitaj easy";
  }
  if (difficulty === "medium") {
    return "Učitaj medium";
  }
  if (difficulty === "hard") {
    return "Učitaj hard";
  }
  return `Učitaj ${difficulty}`;
}

function buildBatchDifficultyLabel(difficulty: string) {
  if (difficulty === "easy") {
    return "easy";
  }
  if (difficulty === "medium") {
    return "medium";
  }
  if (difficulty === "hard") {
    return "hard";
  }
  return difficulty;
}

function countBatchSuccessChecks(preset: TuningLabBatchPreset) {
  return preset.tasks.reduce((total, task) => total + task.successChecks.length, 0);
}

function buildBatchSuccessChecksLabel(task: TuningLabBatchTask) {
  return `${task.successChecks.length} success check-a`;
}

function buildPlayableActionLabel(playableUrl: string) {
  return playableUrl ? "Otvori rezultat" : "Čeka rezultat";
}

function buildTaskRunState(
  runName: string,
  activeRun: TuningLabRun | null,
  queue: TuningLabRun[],
  history: TuningLabRun[],
) {
  if (activeRun?.name === runName) {
    return {
      badge: "U toku",
      summary: activeRun.currentStepSummary || activeRun.summary || "Task trenutno radi.",
      detail: buildActiveRunSummary(activeRun),
    };
  }
  const queuedRun = queue.find((item) => item.name === runName);
  if (queuedRun) {
    return {
      badge: "U redu čekanja",
      summary: "Task je dodat u queue i čeka svoj red.",
      detail: formatDateTime(queuedRun.queuedAt),
    };
  }
  const lastRun = history.find((item) => item.name === runName);
  if (lastRun) {
    return {
      badge: lastRun.status === "completed" ? "Poslednji run" : "Poslednji pokušaj",
      summary: lastRun.winnerSummary || lastRun.summary || "Postoji raniji rezultat za ovaj task.",
      detail: formatDateTime(lastRun.finishedAt || lastRun.startedAt),
    };
  }
  return {
    badge: "Spremno",
    summary: "Task je spreman za pokretanje čim klikneš `Pokreni task`.",
    detail: "",
  };
}

function formatPlayableFilesLabel(value: number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "Playable fajlovi nisu evidentirani";
  }
  const normalized = Math.trunc(value);
  if (normalized % 10 === 1 && normalized % 100 !== 11) {
    return `${normalized} sačuvan playable fajl`;
  }
  if (
    normalized % 10 >= 2 &&
    normalized % 10 <= 4 &&
    (normalized % 100 < 12 || normalized % 100 > 14)
  ) {
    return `${normalized} sačuvana playable fajla`;
  }
  return `${normalized} sačuvanih playable fajlova`;
}

function isBatchTaskLoaded(
  draft: TuningDraft,
  task: TuningLabBatchTask,
) {
  return draft.taskPrompt.trim() === task.taskPrompt.trim() && draft.goal === task.goal;
}

function findPlayableSlot(run: TuningLabRun) {
  const winner =
    run.suggestedWinnerSlotId
      ? run.slots.find((slot) => slot.id === run.suggestedWinnerSlotId)
      : null;
  if (winner?.playableEntryPath) {
    return winner;
  }
  return run.slots.find((slot) => slot.status === "completed" && !!slot.playableEntryPath) || null;
}

function buildPlayableUrl(runId: string, slot: TuningLabSlot) {
  if (!slot.playableEntryPath) {
    return "";
  }
  const encodedPath = slot.playableEntryPath
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  if (!encodedPath) {
    return "";
  }
  return `/api/tuning-lab/play/${encodeURIComponent(runId)}/${encodeURIComponent(slot.id)}/${encodedPath}`;
}

function patchSlotSettings(
  slots: TuningLabSlot[],
  slotId: string,
  patch: Partial<TuningLabSettingsPatch>,
) {
  return slots.map((slot) =>
    slot.id === slotId
      ? {
          ...slot,
          settingsPatch: {
            ...slot.settingsPatch,
            ...patch,
          },
        }
      : slot,
  );
}

function buildInferenceSummary(slot: TuningLabSlot) {
  const settings = slot.settingsPatch;
  return [
    `temp ${settings.temperature}`,
    `top-k ${settings.topK}`,
    `top-p ${settings.topP}`,
    `ctx ${Math.round(settings.context / 1024)}k`,
    `out ${Math.round(settings.outputTokens / 1024)}k`,
  ].join(" | ");
}

function renderWinnerLabel(run: TuningLabRun) {
  if (!run.suggestedWinnerSlotId) {
    return "Nema pobednika";
  }
  const slot = run.slots.find((candidate) => candidate.id === run.suggestedWinnerSlotId);
  return slot?.label || run.suggestedWinnerSlotId;
}

function buildActiveRunSummary(run: TuningLabRun) {
  const slotLabel = run.currentSlotLabel || "--";
  const phaseLabel = run.currentPhaseLabel || "Čeka signal";
  return `${slotLabel} | ${phaseLabel}`;
}

function hasMissingTokenTelemetry(slot: TuningLabSlot) {
  return slot.status === "completed" && (slot.totalTokens ?? 0) <= 0;
}

function parseDiffFilesFromText(diffText: string | undefined): TuningLabDiffFile[] {
  if (!diffText?.trim()) {
    return [];
  }
  const normalized = diffText.trim();
  const matches = normalized.matchAll(/(^|\n)--- a\/([^\n]+)\n\+\+\+ b\/[^\n]+\n/g);
  const sections: Array<{ path: string; start: number }> = [];
  for (const match of matches) {
    const index = typeof match.index === "number" ? match.index + (match[1]?.length ?? 0) : 0;
    sections.push({ path: match[2], start: index });
  }
  if (!sections.length) {
    return [{ path: "diff", summary: "Konsolidovani diff", diffText: normalized }];
  }
  return sections.map((section, index) => {
    const next = sections[index + 1];
    const end = next ? next.start : normalized.length;
    return {
      path: section.path,
      summary: section.path,
      diffText: normalized.slice(section.start, end).trim(),
      isBinary: false,
      isTruncated: false,
    };
  });
}

function getSlotDiffFiles(slot: TuningLabSlot): TuningLabDiffFile[] {
  if (Array.isArray(slot.diffFiles) && slot.diffFiles.length) {
    return slot.diffFiles;
  }
  return parseDiffFilesFromText(slot.diffText);
}

function buildSettingsDiff(referenceSlot: TuningLabSlot | undefined, slot: TuningLabSlot) {
  if (!referenceSlot) {
    return [];
  }
  const pairs: Array<{ key: keyof TuningLabSettingsPatch; label: string }> = [
    { key: "profile", label: "Profil" },
    { key: "thinkingMode", label: "Thinking" },
    { key: "context", label: "Context" },
    { key: "outputTokens", label: "Output" },
    { key: "temperature", label: "Temperature" },
    { key: "topK", label: "Top-k" },
    { key: "topP", label: "Top-p" },
    { key: "minP", label: "Min-p" },
    { key: "repeatPenalty", label: "Repeat" },
    { key: "repeatLastN", label: "Last N" },
    { key: "presencePenalty", label: "Presence" },
    { key: "frequencyPenalty", label: "Frequency" },
    { key: "seed", label: "Seed" },
  ];
  return pairs
    .map(({ key, label }) => ({
      key,
      label,
      before: referenceSlot.settingsPatch[key],
      after: slot.settingsPatch[key],
    }))
    .filter((item) => item.before !== item.after);
}

function buildWinnerReason(run: TuningLabRun) {
  const winner = run.slots.find((slot) => slot.id === run.suggestedWinnerSlotId);
  if (!winner) {
    return "Nijedan slot nije završio zadatak i success check uspešno.";
  }
  const completedCount = run.slots.filter((slot) => slot.taskCompleted && slot.successChecksPassed).length;
  return [
    `${winner.label} je predložen kao pobednik jer je uspešno završio task i prošao success check.`,
    completedCount > 1
      ? `Od uspešnih slotova, imao je najzdraviji odnos trajanja ${formatMs(winner.totalDurationMs)} i throughput-a ${formatTok(winner.averageOutputTokensPerSecond)}.`
      : "Bio je jedini slot koji je ostao tehnički upotrebljiv do kraja eksperimenta.",
  ].join(" ");
}

async function copyText(
  text: string,
  onResult: (result: ActionResult) => void,
  summary: string,
) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    onResult({
      status: "ok",
      action: "copy-to-clipboard",
      summary,
      details: { returncode: 0, stdout: text, stderr: "" },
    });
  } catch (error) {
    onResult({
      status: "error",
      action: "copy-to-clipboard",
      summary: "Kopiranje u clipboard nije uspelo.",
      details: {
        returncode: 1,
        stdout: "",
        stderr: error instanceof Error ? error.message : "clipboard error",
      },
    });
  }
}

function buildSlotParamCopy(slot: TuningLabSlot) {
  return JSON.stringify(
    {
      label: slot.label,
      source: slot.source,
      settingsPatch: slot.settingsPatch,
    },
    null,
    2,
  );
}

function buildSlotExportName(runId: string, slot: TuningLabSlot) {
  return `${runId}-${slot.id}.json`;
}

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" });
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  window.URL.revokeObjectURL(objectUrl);
}

export function TuningLabPage() {
  const [summary, setSummary] = useState<TuningLabSummaryPayload | null>(null);
  const [runStatus, setRunStatus] = useState<TuningLabRun | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [draft, setDraft] = useState<TuningDraft | null>(null);
  const [customSnippet, setCustomSnippet] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [isQueueing, setIsQueueing] = useState(false);
  const [historyFilters, setHistoryFilters] = useState<HistoryFilters>({
    query: "",
    goal: "all",
    runtime: "all",
    status: "all",
  });
  const [selectedDiffs, setSelectedDiffs] = useState<Record<string, string>>({});
  const editorRef = useRef<HTMLElement | null>(null);
  const progressRef = useRef<HTMLElement | null>(null);

  async function load(targetPage = historyPage) {
    try {
      const [summaryPayload, runPayload] = await Promise.all([
        fetchTuningLabSummary(targetPage),
        fetchTuningLabRunStatus(),
      ]);
      setSummary(summaryPayload);
      setRunStatus(Object.keys(runPayload).length ? (runPayload as TuningLabRun) : null);
      setError(null);
      setHistoryPage(targetPage);
      setDraft((current) => current ?? buildDraftFromSummary(summaryPayload));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Tuning Lab nije mogao da se učita.");
    }
  }

  useEffect(() => {
    let cancelled = false;
    void load(1);
    const timer = window.setInterval(() => {
      if (!cancelled) {
        void load(historyPage);
      }
    }, REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [historyPage]);

  const goalOptions = summary?.goalOptions ?? [];
  const successTemplates = summary?.successCheckTemplates ?? [];
  const batchPresets = summary?.batchPresets ?? [];
  const activeRun = runStatus ?? summary?.activeRun ?? null;
  const runBlockers = summary?.context.runBlockers ?? [];
  const canQueueRuns = summary?.context.canQueue ?? false;
  const hasRuntimeBinary = summary?.context.runtimeBinaryReady ?? false;
  const hasActiveModel = summary?.context.activeModelReady ?? false;
  const hasOpenCode = summary?.context.opencodeReady ?? false;
  const canQueueCurrentDraft =
    canQueueRuns && !!draft?.taskPrompt.trim() && !!draft?.workingDirectory.trim() && !isQueueing;

  const recommendedSourceLabel = useMemo(() => {
    return summary?.context.recommendedOrigin || "interna pravila";
  }, [summary?.context.recommendedOrigin]);

  const historyRuntimeOptions = useMemo(() => {
    const values = new Set<string>();
    for (const item of summary?.history ?? []) {
      if (item.activeRuntime) {
        values.add(item.activeRuntime);
      }
    }
    return Array.from(values);
  }, [summary?.history]);

  const filteredHistory = useMemo(() => {
    const query = historyFilters.query.trim().toLowerCase();
    return (summary?.history ?? []).filter((run) => {
      if (historyFilters.goal !== "all" && run.goal !== historyFilters.goal) {
        return false;
      }
      if (historyFilters.runtime !== "all" && (run.activeRuntime || "--") !== historyFilters.runtime) {
        return false;
      }
      if (historyFilters.status !== "all" && run.status !== historyFilters.status) {
        return false;
      }
      if (!query) {
        return true;
      }
      const haystack = [
        run.name,
        run.goalLabel,
        run.goal,
        run.modelLabel,
        run.modelId,
        run.activeRuntime,
        run.summary,
        run.winnerSummary,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [historyFilters, summary?.history]);

  async function runMutation(callback: () => Promise<ActionResult | { status: string; summary: string }>) {
    try {
      const payload = await callback();
      setResult({
        status: payload.status,
        action: "tuning-lab-action",
        summary: payload.summary,
        details: {
          returncode: payload.status === "ok" || payload.status === "accepted" ? 0 : 1,
          stdout: payload.summary,
          stderr: payload.status === "ok" || payload.status === "accepted" ? "" : payload.summary,
        },
      });
      await load(historyPage);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Tuning Lab akcija nije uspela.");
    }
  }

  function scrollSectionIntoView(target: HTMLElement | null) {
    if (!target) {
      return;
    }
    window.requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  async function queueDraftExperiment(nextDraft: TuningDraft) {
    setIsQueueing(true);
    try {
      await runMutation(async () =>
        queueTuningLabExperiment({
          name: nextDraft.name,
          goal: nextDraft.goal,
          taskPrompt: nextDraft.taskPrompt,
          workingDirectory: nextDraft.workingDirectory,
          successChecks: nextDraft.successChecks,
          slots: nextDraft.slots.map((slot) => ({
            id: slot.id,
            label: slot.label,
            source: slot.source,
            settingsPatch: slot.settingsPatch,
          })),
        }),
      );
    } finally {
      setIsQueueing(false);
    }
  }

  async function queueBatchPreset(presetId: string, currentDraft: TuningDraft) {
    setIsQueueing(true);
    try {
      await runMutation(async () =>
        queueTuningLabBatch({
          presetId,
          workingDirectory: currentDraft.workingDirectory,
          slots: currentDraft.slots.map((slot) => ({
            id: slot.id,
            label: slot.label,
            source: slot.source,
            settingsPatch: slot.settingsPatch,
          })),
        }),
      );
    } finally {
      setIsQueueing(false);
    }
  }

  function openPlayableResult(playableUrl: string, label: string) {
    if (!playableUrl) {
      setResult({
        status: "error",
        action: "open-playable-output",
        summary: "Playable rezultat još nije dostupan.",
        details: {
          returncode: 1,
          stdout: "",
          stderr: "Playable rezultat još nije dostupan.",
        },
      });
      return;
    }
    const opened = window.open(playableUrl, "_blank", "noopener,noreferrer");
    if (!opened) {
      setResult({
        status: "error",
        action: "open-playable-output",
        summary: "Browser nije dozvolio otvaranje playable rezultata.",
        details: {
          returncode: 1,
          stdout: "",
          stderr: "Browser nije dozvolio otvaranje playable rezultata.",
        },
      });
      return;
    }
    opened.opener = null;
    setResult({
      status: "ok",
      action: "open-playable-output",
      summary: `Otvoren je rezultat za ${label}.`,
      details: {
        returncode: 0,
        stdout: playableUrl,
        stderr: "",
      },
    });
  }

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!summary || !draft) {
    return <section className="status-card wide-card">Učitavam Tuning Lab...</section>;
  }

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Tuning Lab</span>
        <strong className="status-value">Poređenje, objašnjenje i primena tuning setova</strong>
        <p className="helper-text">
          Ovaj lab pokreće stvarni OpenCode task nad izolovanim radnim prostorom i poredi tri seta
          podešavanja: `Baseline`, `Recommended` i `Custom`.
        </p>
        <div className="summary-metrics">
          <span>Aktivni model: {summary.context.activeModel || "--"}</span>
          <span>Runtime: {summary.context.activeRuntime || "--"}</span>
          <span>Radni direktorijum: {summary.context.workingDirectory || "--"}</span>
          <span>Recommended izvor: {recommendedSourceLabel}</span>
        </div>
        {summary.context.workingDirectoryWasAdjusted ? (
          <p className="helper-text">
            Tuning Lab ne koristi install root kao radni direktorijum. Umesto toga je predložen
            sigurniji scratch workspace: {summary.context.workingDirectory}
          </p>
        ) : null}
{runBlockers.length ? (
          <div className="error-panel">
            <strong>Tuning Lab trenutno nije spreman za pokretanje.</strong>
            {runBlockers.map((message) => (
              <div key={message}>{message}</div>
            ))}
            {!hasOpenCode ? (
              <div className="inline-actions">
                <button
                  type="button"
                  onClick={() =>
                    void runMutation(async () => {
                      const payload = await bootstrapOpenCode();
                      return { status: payload.status, summary: payload.summary };
                    })
                  }
                >
                  Instaliraj ili popravi OpenCode
                </button>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="helper-text">
            Napredak run-a prati u panelu `Queue i aktivni run` niže na strani.
          </p>
        )}
      </section>

      <ActionResultPanel result={result} />

      <section className="status-card wide-card">
        <span className="status-label">Gotovi batch testovi</span>
        <strong className="status-value">Prvi uporedivi game batch za Tuning Lab</strong>
        <p className="helper-text">
          Ovi batch testovi su normalizovani za benchmark, tako da isti set podešavanja možeš da
          porediš kroz `easy`, `medium` i `hard` zadatak bez ručnog kopiranja promptova.
        </p>
        <p className="helper-text">`Game Batch 01` je prvi gotov batch za browser igre.</p>
        <div className="tuning-lab-batch-grid">
          {batchPresets.map((preset) => {
            const loadedTask = preset.tasks.find((task) => isBatchTaskLoaded(draft, task)) || null;
            return (
              <article className="status-card tuning-lab-slot-card" key={preset.id}>
                <div className="tuning-lab-batch-overview">
                  <div className="tuning-lab-batch-overview-copy">
                    <span className="status-label">{preset.label}</span>
                    <strong className="status-value">{preset.summary}</strong>
                    <div className="summary-metrics">
                      <span>{preset.tasks.length} zadatka</span>
                      <span>{countBatchSuccessChecks(preset)} success check-a</span>
                      <span>Jedan klik = {preset.tasks.length} run-a</span>
                    </div>
                  </div>
                  <div className="tuning-lab-batch-run-hint">
                    <span className="status-label">Šta ovaj batch meri</span>
                    <ul className="tuning-lab-batch-focus-list">
                      {(preset.focusAreas || []).map((item) => (
                        <li key={`${preset.id}-${item}`}>{item}</li>
                      ))}
                    </ul>
                    <p className="helper-text">
                      Pokretanje koristi trenutne slot postavke iz editora i isti radni direktorijum
                      za sva tri uporediva run-a.
                    </p>
                    <p className="helper-text">
                      Osnovni tok sada ostaje u istoj kartici: `Učitaj` → `Pokreni task` → `Otvori rezultat`.
                    </p>
                    {loadedTask ? (
                      <div className="warning-badge">
                        Trenutno u editoru: {loadedTask.label}. Napredna podešavanja i dalje postoje niže,
                        u sekciji `Eksperiment`, ali za osnovni tok više ne moraš da skroluješ do njih.
                      </div>
                    ) : (
                      <p className="helper-text">
                        Učitaj jedan task ako želiš brzi vođeni tok, ili odmah pokreni ceo batch.
                      </p>
                    )}
                  </div>
                </div>
                <div className="tuning-lab-batch-task-list">
                  {preset.tasks.map((task) => {
                    const taskLoaded = isBatchTaskLoaded(draft, task);
                    const loadLabel = buildBatchLoadLabel(task.difficulty);
                    const runName = buildBatchRunName(preset, task);
                    const taskRunState = buildTaskRunState(
                      runName,
                      activeRun,
                      summary.queue || [],
                      summary.history || [],
                    );
                    const latestPlayableRun =
                      (summary.history || []).find((run) => {
                        if (run.name !== runName) {
                          return false;
                        }
                        return !!findPlayableSlot(run);
                      }) || null;
                    const latestPlayableSlot = latestPlayableRun ? findPlayableSlot(latestPlayableRun) : null;
                    const playableUrl =
                      latestPlayableRun && latestPlayableSlot
                        ? buildPlayableUrl(latestPlayableRun.runId, latestPlayableSlot)
                        : "";
                    return (
                      <div
                        className={`tuning-lab-batch-task-row ${taskLoaded ? "tuning-lab-batch-task-row-active" : ""}`}
                        key={task.id}
                      >
                        <div className="tuning-lab-batch-task-copy">
                          <strong>{task.label}</strong>
                          <div className="tuning-lab-batch-task-badges">
                            <span
                              className={`compat-badge tuning-lab-batch-difficulty tuning-lab-batch-difficulty-${task.difficulty}`}
                            >
                              {buildBatchDifficultyLabel(task.difficulty)}
                            </span>
                            {task.scopeLabel ? <span className="browser-chip">{task.scopeLabel}</span> : null}
                            <span className="browser-chip">
                              {buildBatchSuccessChecksLabel(task)}
                            </span>
                            {task.focusLabel ? <span className="browser-chip">{task.focusLabel}</span> : null}
                            {task.expectedArtifact ? (
                              <span className="browser-chip">{task.expectedArtifact}</span>
                            ) : null}
                            {taskLoaded ? <span className="warning-badge">Trenutno u editoru</span> : null}
                          </div>
                          <p className="helper-text">{task.summary}</p>
                          {latestPlayableRun && latestPlayableSlot ? (
                            <div className="tuning-lab-batch-task-state">
                              <span className="compat-badge">Spremno za otvaranje</span>
                              <div className="tuning-lab-batch-playable-meta">
                                <span>
                                  Poslednji playable: {latestPlayableSlot.label} ·{" "}
                                  {formatDateTime(latestPlayableRun.finishedAt || latestPlayableRun.startedAt)}
                                </span>
                                <span>{formatPlayableFilesLabel(latestPlayableSlot.playableFilesPreserved)}</span>
                              </div>
                            </div>
                          ) : (
                            <div className="tuning-lab-batch-task-state">
                              <span className="helper-text">Playable rezultat još nije dostupan</span>
                              <div className="tuning-lab-batch-playable-meta">
                                <span>Pokreni task da bi se ovde pojavio rezultat za otvaranje.</span>
                              </div>
                            </div>
                          )}
                          {taskLoaded ? (
                            <div className="tuning-lab-batch-quick-run">
                              <div className="section-header">
                                <div>
                                  <strong>Brzi tok za ovaj task</strong>
                                  <div className="helper-text">
                                    Sve osnovne akcije za ovaj task ostaju u istoj kartici. Donji
                                    editor služi samo za naprednija podešavanja.
                                  </div>
                                </div>
                                <span className="warning-badge">Trenutno u editoru</span>
                              </div>
                              <div className="tuning-lab-batch-quick-steps">
                                <div className="tuning-lab-batch-quick-step">
                                  <span className="compat-badge">Korak 1</span>
                                  <div>
                                    <strong>Task je učitan</strong>
                                    <p className="helper-text">
                                      Prompt, cilj i success check lanac su već prebačeni u aktivni
                                      draft.
                                    </p>
                                  </div>
                                </div>
                                <div className="tuning-lab-batch-quick-step">
                                  <span className="compat-badge">Korak 2</span>
                                  <div>
                                    <strong>Koristi trenutni radni direktorijum</strong>
                                    <p className="helper-text">
                                      {draft.workingDirectory.trim()
                                        ? draft.workingDirectory
                                        : "Radni direktorijum još nije unet. Postavi ga u sekciji Eksperiment ili učitaj bezbedni scratch folder."}
                                    </p>
                                  </div>
                                </div>
                                <div className="tuning-lab-batch-quick-step">
                                  <span className="compat-badge">Korak 3</span>
                                  <div>
                                    <strong>Pokreni i prati status</strong>
                                    <p className="helper-text">
                                      {taskRunState.summary}
                                      {taskRunState.detail ? ` (${taskRunState.detail})` : ""}
                                    </p>
                                  </div>
                                </div>
                                <div className="tuning-lab-batch-quick-step">
                                  <span className="compat-badge">Korak 4</span>
                                  <div>
                                    <strong>Otvori rezultat kada run uspe</strong>
                                    <p className="helper-text">
                                      HTML igra će se otvoriti tek kada ovaj task sačuva playable
                                      izlaz.
                                    </p>
                                  </div>
                                </div>
                              </div>
                              <div className="inline-actions">
                                <button
                                  type="button"
                                  className="secondary-button"
                                  onClick={() => scrollSectionIntoView(editorRef.current)}
                                >
                                  Otvori napredna podešavanja
                                </button>
                              </div>
                            </div>
                          ) : null}
                          <div className="tuning-lab-batch-task-actions tuning-lab-batch-action-rail">
                            <article className="tuning-lab-batch-action-card">
                              <span className="compat-badge">1. Učitaj task</span>
                              <p className="helper-text">
                                Ubaci ovaj prompt i success check lanac u aktivni draft.
                              </p>
                              <button
                                type="button"
                                className={taskLoaded ? "secondary-button" : undefined}
                                onClick={() => {
                                  setDraft(buildDraftForBatchTask(draft, preset, task));
                                  setResult({
                                    status: "ok",
                                    action: "load-tuning-batch-task",
                                    summary: `${preset.label} · ${task.label} je učitan i spreman za brzi tok u istoj kartici. Ako želiš dublje izmene, napredna podešavanja su niže u sekciji Eksperiment.`,
                                    details: {
                                      returncode: 0,
                                      stdout: task.taskPrompt,
                                      stderr: "",
                                    },
                                  });
                                }}
                              >
                                {taskLoaded ? "Ponovo učitaj task" : loadLabel}
                              </button>
                            </article>
                            <article className="tuning-lab-batch-action-card">
                              <span className="compat-badge">2. Pokreni task</span>
                              <p className="helper-text">
                                {taskRunState.summary}
                                {taskRunState.detail ? ` (${taskRunState.detail})` : ""}
                              </p>
                              <button
                                type="button"
                                disabled={!canQueueRuns || !draft.workingDirectory.trim() || isQueueing}
                                onClick={() =>
                                  void (async () => {
                                    const nextDraft = buildDraftForBatchTask(draft, preset, task);
                                    setDraft(nextDraft);
                                    await queueDraftExperiment(nextDraft);
                                  })()
                                }
                              >
                                Pokreni task
                              </button>
                            </article>
                            <article className="tuning-lab-batch-action-card">
                              <span className="compat-badge">3. Otvori rezultat</span>
                              <p className="helper-text">
                                Otvara HTML igru tek kada ovaj task sačuva playable izlaz.
                              </p>
                              <button
                                type="button"
                                className="secondary-button"
                                disabled={!playableUrl}
                                onClick={() =>
                                  openPlayableResult(
                                    playableUrl,
                                    `${preset.label} · ${task.label}`,
                                  )
                                }
                              >
                                {buildPlayableActionLabel(playableUrl)}
                              </button>
                            </article>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    disabled={!canQueueRuns || !draft.workingDirectory.trim() || isQueueing}
                    onClick={() => void queueBatchPreset(preset.id, draft)}
                  >
                    Pokreni ceo batch
                  </button>
                </div>
                <p className="helper-text">
                  Koristi trenutne slot postavke iz `Baseline`, `Recommended` i `Custom` kolona.
                </p>
                {!draft.workingDirectory.trim() ? (
                  <div className="warning-badge">
                    Unesi radni direktorijum u editoru da bi batch mogao da se doda u queue.
                  </div>
                ) : !canQueueRuns ? (
                  <div className="warning-badge">
                    Tuning Lab trenutno nije spreman za pokretanje. Reši blocker-e iznad pa onda
                    pokreni batch.
                  </div>
                ) : !hasOpenCode ? (
                  <div className="warning-badge">
                    OpenCode nedostaje za Tuning Lab. Instaliraj ili popravi OpenCode pa onda
                    pokreni batch.
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>

      <section className="status-card wide-card" ref={editorRef}>
        <span className="status-label">Eksperiment</span>
        <strong className="status-value">Priprema run-a</strong>
        {summary.context.workingDirectoryWasAdjusted ? (
          <p className="helper-text">
            Konfigurisani radni direktorijum je bio preširok za Tuning Lab, pa je ovde već
            predložen sigurniji scratch workspace. Ako želiš pravi projekat, slobodno unesi njegov
            folder ručno.
          </p>
        ) : null}
        <div className="tuning-lab-layout">
          <label className="settings-compact-field">
            <span>Naziv eksperimenta</span>
            <input
              type="text"
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
            />
          </label>
          <label className="settings-compact-field">
            <span>Cilj</span>
            <select
              value={draft.goal}
              onChange={(event) => setDraft({ ...draft, goal: event.target.value })}
            >
              {goalOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="settings-compact-field settings-medium-field">
            <span>Radni direktorijum</span>
            <input
              type="text"
              value={draft.workingDirectory}
              onChange={(event) => setDraft({ ...draft, workingDirectory: event.target.value })}
            />
          </label>
        </div>
        <label className="settings-compact-field settings-field-wide">
          <span>OpenCode task</span>
          <textarea
            value={draft.taskPrompt}
            onChange={(event) => setDraft({ ...draft, taskPrompt: event.target.value })}
            placeholder="Opiši konkretan zadatak koji OpenCode treba da uradi nad projektom."
          />
        </label>
        <div className="tuning-lab-check-grid">
          <article className="status-card">
            <span className="status-label">Success check lanac</span>
            <p className="helper-text">
              Ako ga ostaviš praznim, Tuning Lab će probati auto-detect. Možeš i ručno da dodaš do 3
              koraka.
            </p>
            <div className="inline-actions">
              {successTemplates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    if (template.id === "auto-detect") {
                      setDraft({ ...draft, successChecks: [] });
                      return;
                    }
                    if (!template.command || draft.successChecks.length >= 3) {
                      return;
                    }
                    setDraft({
                      ...draft,
                      successChecks: [
                        ...draft.successChecks,
                        {
                          label: template.label,
                          command: template.command,
                          kind: template.id,
                        },
                      ],
                    });
                  }}
                >
                  {template.label}
                </button>
              ))}
            </div>
            <div className="tuning-lab-check-list">
              {draft.successChecks.length ? (
                draft.successChecks.map((check, index) => (
                  <div className="tuning-lab-check-row" key={`${check.label}-${index}`}>
                    <input
                      type="text"
                      value={check.label}
                      onChange={(event) => {
                        const next = [...draft.successChecks];
                        next[index] = { ...next[index], label: event.target.value };
                        setDraft({ ...draft, successChecks: next });
                      }}
                      placeholder="Label"
                    />
                    <input
                      type="text"
                      value={check.command}
                      onChange={(event) => {
                        const next = [...draft.successChecks];
                        next[index] = { ...next[index], command: event.target.value };
                        setDraft({ ...draft, successChecks: next });
                      }}
                      placeholder="Komanda za proveru"
                    />
                    <button
                      type="button"
                      className="danger-button"
                      onClick={() =>
                        setDraft({
                          ...draft,
                          successChecks: draft.successChecks.filter(
                            (_, currentIndex) => currentIndex !== index,
                          ),
                        })
                      }
                    >
                      Ukloni
                    </button>
                  </div>
                ))
              ) : (
                <p className="helper-text">
                  Auto-detect će odlučiti da li treba `pytest`, `npm test` ili `cargo test`.
                </p>
              )}
            </div>
          </article>
          <article className="status-card">
            <span className="status-label">Custom import</span>
            <p className="helper-text">
              Nalepi forumsku komandu, config snippet ili parametre tipa `temperature=0.6 top_p=0.95`.
            </p>
            <textarea
              value={customSnippet}
              onChange={(event) => setCustomSnippet(event.target.value)}
              placeholder="Uvezi forum / Reddit snippet"
            />
            <div className="inline-actions">
              <button
                type="button"
                className="secondary-button"
                disabled={!customSnippet.trim()}
                onClick={() =>
                  void runMutation(async () => {
                    const payload = await importTuningSnippet(customSnippet);
                    if (payload.status === "ok") {
                      setDraft({
                        ...draft,
                        slots: patchSlotSettings(
                          draft.slots,
                          "custom",
                          payload.settingsPatch as Partial<TuningLabSettingsPatch>,
                        ),
                      });
                    }
                    return {
                      status: payload.status,
                      summary: payload.summary,
                    };
                  })
                }
              >
                Uvezi forum / Reddit snippet
              </button>
            </div>
          </article>
        </div>
        <div className="inline-actions">
          <button
            type="button"
            disabled={!canQueueCurrentDraft}
            onClick={() => void queueDraftExperiment(draft)}
          >
            Dodaj u queue
          </button>
        </div>
        {!hasRuntimeBinary ? (
          <div className="warning-badge">
            Runtime binar nije spreman. Prvo osposobi aktivni runtime pre Tuning Lab pokretanja.
          </div>
        ) : null}
        {!hasActiveModel ? (
          <div className="warning-badge">
            Aktivan model još nije spreman. Aktiviraj lokalni model pa tek onda pokreni Tuning Lab.
          </div>
        ) : null}
        {!hasOpenCode ? (
          <div className="warning-badge">
            OpenCode nedostaje za Tuning Lab. Otvori karticu OpenCode ili klikni iznad na
            `Instaliraj ili popravi OpenCode`.
          </div>
        ) : null}
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Tri slota</span>
        <div className="tuning-lab-slot-grid">
          {draft.slots.map((slot) => (
            <article className="status-card tuning-lab-slot-card" key={slot.id}>
              <span className="status-label">{slot.label}</span>
              <strong className="status-value">{slot.source}</strong>
              <p className="helper-text">{buildInferenceSummary(slot)}</p>
              <div className="tuning-lab-compact-grid">
                <label className="settings-compact-field">
                  <span>Profil</span>
                  <select
                    value={slot.settingsPatch.profile}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        slots: patchSlotSettings(draft.slots, slot.id, {
                          profile: event.target.value,
                        }),
                      })
                    }
                  >
                    <option value="balanced">balanced</option>
                    <option value="speed">speed</option>
                    <option value="video">video</option>
                  </select>
                </label>
                <label className="settings-compact-field">
                  <span>Thinking</span>
                  <select
                    value={slot.settingsPatch.thinkingMode}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        slots: patchSlotSettings(draft.slots, slot.id, {
                          thinkingMode: event.target.value,
                        }),
                      })
                    }
                  >
                    <option value="no-thinking">no-thinking</option>
                    <option value="low">low</option>
                    <option value="mid">mid</option>
                    <option value="high">high</option>
                    <option value="extra-high">extra-high</option>
                  </select>
                </label>
                <label className="settings-compact-field">
                  <span>Context</span>
                  <input
                    type="number"
                    value={slot.settingsPatch.context}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        slots: patchSlotSettings(draft.slots, slot.id, {
                          context: Number(event.target.value || 0),
                        }),
                      })
                    }
                  />
                </label>
                <label className="settings-compact-field">
                  <span>Output</span>
                  <input
                    type="number"
                    value={slot.settingsPatch.outputTokens}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        slots: patchSlotSettings(draft.slots, slot.id, {
                          outputTokens: Number(event.target.value || 0),
                        }),
                      })
                    }
                  />
                </label>
                {(
                  [
                    ["Temperature", "temperature"],
                    ["Top-k", "topK"],
                    ["Top-p", "topP"],
                    ["Min-p", "minP"],
                    ["Repeat", "repeatPenalty"],
                    ["Last N", "repeatLastN"],
                    ["Presence", "presencePenalty"],
                    ["Frequency", "frequencyPenalty"],
                    ["Seed", "seed"],
                  ] as const
                ).map(([label, key]) => (
                  <label className="settings-compact-field" key={`${slot.id}-${key}`}>
                    <span>{label}</span>
                    <input
                      type="number"
                      step={key === "repeatLastN" || key === "seed" || key === "topK" ? 1 : 0.05}
                      value={slot.settingsPatch[key]}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          slots: patchSlotSettings(draft.slots, slot.id, {
                            [key]: Number(event.target.value || 0),
                          } as Partial<TuningLabSettingsPatch>),
                        })
                      }
                    />
                  </label>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="status-card wide-card" ref={progressRef}>
        <span className="status-label">Queue i aktivni run</span>
        <div className="tuning-lab-progress-grid">
          <article className="status-card">
            <strong className="status-value">Aktivni run</strong>
            {activeRun ? (
              <>
                <div className="tuning-lab-progress-metrics">
                  <span>Naziv: {activeRun.name}</span>
                  <span>Status: {activeRun.status}</span>
                  <span>Slot: {activeRun.currentIndex ?? 0} / {activeRun.slots.length}</span>
                  <span>Trenutni slot: {activeRun.currentSlotLabel || "--"}</span>
                  <span>Aktivni korak: {activeRun.currentPhaseLabel || "--"}</span>
                  <span>Trajanje do sada: {formatMs(activeRun.elapsedMs)}</span>
                  <span>Početak: {formatDateTime(activeRun.startedAt)}</span>
                  <span>Poslednje osveženje: {formatDateTime(activeRun.lastUpdatedAt)}</span>
                </div>
                <p className="helper-text">{buildActiveRunSummary(activeRun)}</p>
                <p className="helper-text">{activeRun.currentStepSummary || activeRun.summary || "--"}</p>
                <div className="tuning-lab-log-panel">
                  <span className="status-label">Poslednji log signal</span>
                  <pre>{activeRun.currentLogExcerpt || "Još nema log signala za aktivni korak."}</pre>
                </div>
              </>
            ) : (
              <p className="helper-text">Trenutno nema aktivnog Tuning Lab run-a.</p>
            )}
          </article>
          <article className="status-card">
            <strong className="status-value">Queue</strong>
            {summary.queue.length ? (
              <ul className="tuning-lab-queue-list">
                {summary.queue.map((item) => (
                  <li key={item.runId}>
                    <strong>{item.name}</strong>
                    <span>
                      {item.goal} | {formatDateTime(item.queuedAt)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="helper-text">Red čekanja je trenutno prazan.</p>
            )}
          </article>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Istorija</span>
        <strong className="status-value">Filtriraj istoriju</strong>
        <div className="tuning-lab-filter-grid">
          <label className="settings-compact-field">
            <span>Pretraga</span>
            <input
              type="text"
              value={historyFilters.query}
              placeholder="Naziv, model, runtime..."
              onChange={(event) =>
                setHistoryFilters((current) => ({ ...current, query: event.target.value }))
              }
            />
          </label>
          <label className="settings-compact-field">
            <span>Cilj</span>
            <select
              value={historyFilters.goal}
              onChange={(event) =>
                setHistoryFilters((current) => ({ ...current, goal: event.target.value }))
              }
            >
              <option value="all">Svi ciljevi</option>
              {goalOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="settings-compact-field">
            <span>Runtime</span>
            <select
              value={historyFilters.runtime}
              onChange={(event) =>
                setHistoryFilters((current) => ({ ...current, runtime: event.target.value }))
              }
            >
              <option value="all">Svi runtime-i</option>
              {historyRuntimeOptions.map((runtime) => (
                <option key={runtime} value={runtime}>
                  {runtime}
                </option>
              ))}
            </select>
          </label>
          <label className="settings-compact-field">
            <span>Status</span>
            <select
              value={historyFilters.status}
              onChange={(event) =>
                setHistoryFilters((current) => ({ ...current, status: event.target.value }))
              }
            >
              <option value="all">Svi statusi</option>
              <option value="completed">Uspešni</option>
              <option value="failed">Neuspešni</option>
              <option value="running">Running</option>
              <option value="queued">Queued</option>
            </select>
          </label>
        </div>
        {filteredHistory.length ? (
          <>
            <div className="tuning-lab-history-list">
              {filteredHistory.map((run) => {
                const baselineSlot = run.slots.find((slot) => slot.id === "baseline");
                const winnerSlot = run.slots.find((slot) => slot.id === run.suggestedWinnerSlotId);
                return (
                  <article className="status-card tuning-lab-history-card" key={run.runId}>
                    <div className="section-header">
                      <div>
                        <strong>{run.name}</strong>
                        <div className="muted-line">
                          {run.goalLabel || run.goal} | {run.modelLabel || run.modelId || "--"} |{" "}
                          {run.activeRuntime || "--"}
                        </div>
                      </div>
                      <span className="warning-badge">{renderWinnerLabel(run)}</span>
                    </div>
                    <p className="helper-text">
                      Start: {formatDateTime(run.startedAt)} | Kraj: {formatDateTime(run.finishedAt)} |
                      Status: {run.status}
                    </p>
                    <p className="helper-text">{run.winnerSummary || run.summary || "--"}</p>
                    <div className="inline-actions">
                      <button
                        type="button"
                        onClick={() =>
                          void runMutation(() =>
                            applyTuningLabWinner(run.runId, run.suggestedWinnerSlotId || undefined),
                          )
                        }
                      >
                        Primeni pobednički set
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() =>
                          void runMutation(async () => {
                            const payload = await exportTuningLabRun(run.runId);
                            downloadJson(`${run.runId}.json`, payload.experiment);
                            return { status: payload.status, summary: payload.summary };
                          })
                        }
                      >
                        Export / share
                      </button>
                    </div>

                    {winnerSlot ? (
                      <div className="tuning-lab-winner-panel">
                        <div className="section-header">
                          <strong>Zašto je ovaj slot pobedio</strong>
                          <span className="compat-badge">{winnerSlot.label}</span>
                        </div>
                        <p className="helper-text">{buildWinnerReason(run)}</p>
                        <div className="summary-metrics">
                          <span>Trajanje: {formatMs(winnerSlot.totalDurationMs)}</span>
                          <span>Output: {formatTok(winnerSlot.averageOutputTokensPerSecond)}</span>
                          <span>Ukupno: {formatTok(winnerSlot.averageTotalTokensPerSecond)}</span>
                          <span>Diff: {winnerSlot.diffSummary || "--"}</span>
                        </div>
                        <div className="tuning-lab-delta-list">
                          {buildSettingsDiff(baselineSlot, winnerSlot).length ? (
                            buildSettingsDiff(baselineSlot, winnerSlot).map((item) => (
                              <span className="browser-chip" key={`${run.runId}-${winnerSlot.id}-${item.key}`}>
                                {item.label}: {String(item.before)} → {String(item.after)}
                              </span>
                            ))
                          ) : (
                            <span className="browser-chip">Nema razlike u odnosu na Baseline.</span>
                          )}
                        </div>
                      </div>
                    ) : null}

                    <div className="details-block">
                      <table className="tuning-lab-results-table">
                        <thead>
                          <tr>
                            <th>Slot</th>
                            <th>Status</th>
                            <th>Trajanje</th>
                            <th>Output</th>
                            <th>Ukupno</th>
                            <th>Diff</th>
                          </tr>
                        </thead>
                        <tbody>
                          {run.slots.map((slot) => (
                            <tr key={`${run.runId}-${slot.id}`}>
                              <td>{slot.label}</td>
                              <td>{slot.status || "--"}</td>
                              <td>{formatMs(slot.totalDurationMs)}</td>
                              <td>
                                {formatTok(slot.averageOutputTokensPerSecond)}
                                {hasMissingTokenTelemetry(slot) ? (
                                  <div className="helper-text">Token telemetry nije prijavljen</div>
                                ) : null}
                              </td>
                              <td>{formatTok(slot.averageTotalTokensPerSecond)}</td>
                              <td>{slot.diffSummary || "--"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {run.slots.map((slot) => {
                      const diffFiles = getSlotDiffFiles(slot);
                      const diffKey = `${run.runId}:${slot.id}`;
                      const selectedPath = selectedDiffs[diffKey] || diffFiles[0]?.path || "";
                      const selectedFile =
                        diffFiles.find((item) => item.path === selectedPath) || diffFiles[0] || null;
                      return (
                        <details className="tuning-lab-history-detail" key={`${run.runId}-detail-${slot.id}`}>
                          <summary>
                            {slot.label} detalji | {slot.summary || slot.status || "--"}
                          </summary>
                          {slot.playableEntryPath ? (
                            <div className="tuning-lab-batch-task-state">
                              <span className="compat-badge">Sačuvan playable izlaz</span>
                              <div className="tuning-lab-batch-playable-meta">
                                <span>Ulazna stranica: {slot.playableEntryPath}</span>
                                <span>{formatPlayableFilesLabel(slot.playableFilesPreserved)}</span>
                              </div>
                            </div>
                          ) : null}
                          <div className="tuning-lab-copy-row">
                            <button
                              type="button"
                              className="secondary-button"
                              disabled={!slot.playableEntryPath}
                              onClick={() =>
                                openPlayableResult(
                                  buildPlayableUrl(run.runId, slot),
                                  `${run.name} · ${slot.label}`,
                                )
                              }
                            >
                              Otvori rezultat
                            </button>
                            <button
                              type="button"
                              className="secondary-button"
                              onClick={() =>
                                void copyText(
                                  buildSlotParamCopy(slot),
                                  setResult,
                                  `${slot.label} parametri su kopirani u clipboard.`,
                                )
                              }
                            >
                              Kopiraj parametre
                            </button>
                            <button
                              type="button"
                              className="secondary-button"
                              disabled={!slot.runtimeCommand}
                              onClick={() =>
                                void copyText(
                                  slot.runtimeCommand || "",
                                  setResult,
                                  `${slot.label} runtime komanda je kopirana.`,
                                )
                              }
                            >
                              Kopiraj runtime komandu
                            </button>
                            <button
                              type="button"
                              className="secondary-button"
                              disabled={!slot.opencodeCommand}
                              onClick={() =>
                                void copyText(
                                  slot.opencodeCommand || "",
                                  setResult,
                                  `${slot.label} OpenCode komanda je kopirana.`,
                                )
                              }
                            >
                              Kopiraj OpenCode komandu
                            </button>
                            <button
                              type="button"
                              className="secondary-button"
                              onClick={() =>
                                downloadJson(buildSlotExportName(run.runId, slot), {
                                  runId: run.runId,
                                  slot,
                                })
                              }
                            >
                              Export samo ovaj slot
                            </button>
                          </div>
                          <div className="summary-metrics">
                            <span>Fajlovi: {(slot.changedFiles || []).length || 0}</span>
                            <span>Input tokeni: {formatCount(slot.inputTokens)}</span>
                            <span>Output tokeni: {formatCount(slot.outputTokens)}</span>
                            <span>Ukupno tokeni: {formatCount(slot.totalTokens)}</span>
                          </div>
                          {hasMissingTokenTelemetry(slot) ? (
                            <p className="helper-text">
                              Task je uspešan, ali token telemetry nije prijavljen za ovaj run.
                            </p>
                          ) : null}
                          <div className="tuning-lab-diff-browser">
                            <div className="tuning-lab-diff-sidebar">
                              <span className="status-label">Izmenjeni fajlovi</span>
                              {diffFiles.length ? (
                                diffFiles.map((file) => (
                                  <button
                                    key={`${diffKey}-${file.path}`}
                                    type="button"
                                    className={`secondary-button ${selectedPath === file.path ? "selected-row" : ""}`}
                                    onClick={() =>
                                      setSelectedDiffs((current) => ({
                                        ...current,
                                        [diffKey]: file.path,
                                      }))
                                    }
                                  >
                                    Otvori diff · {file.path}
                                  </button>
                                ))
                              ) : (
                                <p className="helper-text">Nema diff fajlova za prikaz.</p>
                              )}
                            </div>
                            <div className="tuning-lab-diff-content">
                              <p className="helper-text">Komanda: {slot.opencodeCommand || "--"}</p>
                              <p className="helper-text">Runtime: {slot.runtimeCommand || "--"}</p>
                              <div className="details-block">
                                <pre>
                                  {selectedFile?.diffText ||
                                    slot.diffText ||
                                    slot.assistantText ||
                                    "Nema dodatnih detalja."}
                                </pre>
                              </div>
                            </div>
                          </div>
                        </details>
                      );
                    })}
                  </article>
                );
              })}
            </div>
            <div className="inline-actions">
              <button
                type="button"
                className="secondary-button"
                disabled={summary.historyPage <= 1}
                onClick={() => void load(Math.max(1, summary.historyPage - 1))}
              >
                Prethodna strana
              </button>
              <button
                type="button"
                className="secondary-button"
                disabled={summary.historyPage >= summary.historyTotalPages}
                onClick={() => void load(summary.historyPage + 1)}
              >
                Sledeća strana
              </button>
            </div>
          </>
        ) : (
          <p className="helper-text">
            Još nema Tuning Lab istorije. Dodaj prvi run u queue da bi počelo poređenje `Baseline /
            Recommended / Custom`.
          </p>
        )}
      </section>

    </>
  );
}
