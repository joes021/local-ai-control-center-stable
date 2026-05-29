import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import {
  applyTuningLabWinner,
  exportTuningLabRun,
  fetchTuningLabRunStatus,
  fetchTuningLabSummary,
  importTuningSnippet,
  queueTuningLabExperiment,
} from "../lib/api";
import type {
  ActionResult,
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

export function TuningLabPage() {
  const [summary, setSummary] = useState<TuningLabSummaryPayload | null>(null);
  const [runStatus, setRunStatus] = useState<TuningLabRun | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [draft, setDraft] = useState<TuningDraft | null>(null);
  const [customSnippet, setCustomSnippet] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [isQueueing, setIsQueueing] = useState(false);

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
  const activeRun = runStatus ?? summary?.activeRun ?? null;

  const recommendedSourceLabel = useMemo(() => {
    return summary?.context.recommendedOrigin || "interna pravila";
  }, [summary?.context.recommendedOrigin]);

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
        <strong className="status-value">Poređenje i primena tuning setova</strong>
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
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Eksperiment</span>
        <strong className="status-value">Priprema run-a</strong>
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
              Ako ga ostaviš praznim, Tuning Lab će probati auto-detect. Možeš i ručno da dodaš do
              3 koraka.
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
                          successChecks: draft.successChecks.filter((_, currentIndex) => currentIndex !== index),
                        })
                      }
                    >
                      Ukloni
                    </button>
                  </div>
                ))
              ) : (
                <p className="helper-text">Auto-detect će odlučiti da li treba `pytest`, `npm test` ili `cargo test`.</p>
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
            disabled={!draft.taskPrompt.trim() || !draft.workingDirectory.trim() || isQueueing}
            onClick={() =>
              void (async () => {
                setIsQueueing(true);
                await runMutation(async () => {
                  const payload = await queueTuningLabExperiment({
                    name: draft.name,
                    goal: draft.goal,
                    taskPrompt: draft.taskPrompt,
                    workingDirectory: draft.workingDirectory,
                    successChecks: draft.successChecks,
                    slots: draft.slots.map((slot) => ({
                      id: slot.id,
                      label: slot.label,
                      source: slot.source,
                      settingsPatch: slot.settingsPatch,
                    })),
                  });
                  return payload;
                });
                setIsQueueing(false);
              })()
            }
          >
            Dodaj u queue
          </button>
        </div>
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
                        slots: patchSlotSettings(draft.slots, slot.id, { profile: event.target.value }),
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
                        slots: patchSlotSettings(draft.slots, slot.id, { thinkingMode: event.target.value }),
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
                        slots: patchSlotSettings(draft.slots, slot.id, { context: Number(event.target.value || 0) }),
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

      <section className="status-card wide-card">
        <span className="status-label">Queue i aktivni run</span>
        <div className="tuning-lab-layout">
          <article className="status-card">
            <strong className="status-value">Aktivni run</strong>
            {activeRun ? (
              <>
                <p className="helper-text">
                  {activeRun.name} | {activeRun.status} | slot {activeRun.currentIndex ?? 0} /{" "}
                  {activeRun.slots.length}
                </p>
                <p className="helper-text">
                  Trenutni slot: {activeRun.currentSlotLabel || "--"} | Početak:{" "}
                  {formatDateTime(activeRun.startedAt)}
                </p>
                <p className="helper-text">{activeRun.winnerSummary || activeRun.summary || "--"}</p>
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
        {summary.history.length ? (
          <>
            <div className="tuning-lab-history-list">
              {summary.history.map((run) => (
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
                    Start: {formatDateTime(run.startedAt)} | Kraj: {formatDateTime(run.finishedAt)} | Status:{" "}
                    {run.status}
                  </p>
                  <p className="helper-text">{run.winnerSummary || run.summary || "--"}</p>
                  <div className="inline-actions">
                    <button
                      type="button"
                      onClick={() =>
                        void runMutation(() => applyTuningLabWinner(run.runId, run.suggestedWinnerSlotId || undefined))
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
                          const blob = new Blob([JSON.stringify(payload.experiment, null, 2)], {
                            type: "application/json",
                          });
                          const objectUrl = window.URL.createObjectURL(blob);
                          const anchor = document.createElement("a");
                          anchor.href = objectUrl;
                          anchor.download = `${run.runId}.json`;
                          anchor.click();
                          window.URL.revokeObjectURL(objectUrl);
                          return { status: payload.status, summary: payload.summary };
                        })
                      }
                    >
                      Export / share
                    </button>
                  </div>
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
                            <td>{formatTok(slot.averageOutputTokensPerSecond)}</td>
                            <td>{formatTok(slot.averageTotalTokensPerSecond)}</td>
                            <td>{slot.diffSummary || "--"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {run.slots.map((slot) => (
                    <details className="tuning-lab-history-detail" key={`${run.runId}-detail-${slot.id}`}>
                      <summary>
                        {slot.label} detalji | {slot.summary || slot.status || "--"}
                      </summary>
                      <p className="helper-text">Fajlovi: {(slot.changedFiles || []).join(", ") || "bez izmena"}</p>
                      <p className="helper-text">Komanda: {slot.opencodeCommand || "--"}</p>
                      <p className="helper-text">Runtime: {slot.runtimeCommand || "--"}</p>
                      <div className="details-block">
                        <pre>{slot.diffText || slot.assistantText || "Nema dodatnih detalja."}</pre>
                      </div>
                    </details>
                  ))}
                </article>
              ))}
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

      <ActionResultPanel result={result} />
    </>
  );
}
