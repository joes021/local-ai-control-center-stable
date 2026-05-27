import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { deleteJob, fetchJobsSummary, fetchSettings, runJobNow, saveJob } from "../lib/api";
import type { ActionResult, JobsSummaryPayload, SettingsPayload } from "../lib/types";

const REFRESH_MS = 15000;

function formatDateTime(value: string) {
  if (!value) {
    return "--";
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString("sr-RS");
}

export function JobsPage() {
  const [summary, setSummary] = useState<JobsSummaryPayload | null>(null);
  const [settingsPayload, setSettingsPayload] = useState<SettingsPayload | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("health-check");
  const [intervalMinutes, setIntervalMinutes] = useState(60);
  const [workflowPresetId, setWorkflowPresetId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);

  const workflowPresets = settingsPayload?.availableWorkflowPresets ?? [];

  async function load() {
    try {
      const [jobsPayload, settings] = await Promise.all([fetchJobsSummary(), fetchSettings()]);
      setSummary(jobsPayload);
      setSettingsPayload(settings);
      setError(null);
      if (!workflowPresetId && settings.availableWorkflowPresets.length) {
        setWorkflowPresetId(settings.availableWorkflowPresets[0].id);
      }
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Jobs nisu mogli da se ucitaju.");
    }
  }

  useEffect(() => {
    let cancelled = false;
    void load();
    const timer = window.setInterval(() => {
      if (!cancelled) {
        void load();
      }
    }, REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const selectedKind = useMemo(
    () => summary?.availableKinds.find((item) => item.id === kind) ?? null,
    [summary?.availableKinds, kind],
  );

  async function runMutation(callback: () => Promise<{ status: string; summary: string }>) {
    try {
      const payload = await callback();
      setResult({
        status: payload.status,
        action: "jobs-action",
        summary: payload.summary,
        details: {
          returncode: payload.status === "ok" ? 0 : 1,
          stdout: payload.summary,
          stderr: payload.status === "ok" ? "" : payload.summary,
        },
      });
      await load();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Jobs akcija nije uspela.");
    }
  }

  return (
    <>
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="status-card wide-card">
        <span className="status-label">Jobs</span>
        <strong className="status-value">Scheduled jobs</strong>
        <p className="helper-text">
          Installer-managed scheduler za benchmark, health, update i fleet ritam. Job-ovi rade u
          pozadini dok je Control Center backend aktivan.
        </p>
        <div className="summary-metrics">
          <span>Aktivnih job-ova: {summary?.jobCount ?? 0}</span>
          <span>Osvezeno: {summary ? formatDateTime(summary.generatedAt) : "--"}</span>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Save job</span>
        <div className="settings-page-grid">
          <label className="settings-compact-field">
            <span>Name</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Hourly health, Nightly benchmark..."
            />
          </label>
          <label className="settings-compact-field">
            <span>Kind</span>
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {(summary?.availableKinds ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="settings-compact-field">
            <span>Interval (min)</span>
            <input
              type="number"
              min={5}
              max={1440}
              step={5}
              value={intervalMinutes}
              onChange={(event) => setIntervalMinutes(Number(event.target.value || 60))}
            />
          </label>
          <label className="settings-compact-field">
            <span>Workflow preset</span>
            <select value={workflowPresetId} onChange={(event) => setWorkflowPresetId(event.target.value)}>
              <option value="">(optional)</option>
              {workflowPresets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="helper-text">
          {selectedKind?.summary || "Izaberi job tip da vidiš čemu služi."}
        </p>
        <div className="inline-actions">
          <button
            type="button"
            disabled={!name.trim()}
            onClick={() =>
              void runMutation(async () => {
                const payload = await saveJob({
                  name,
                  kind,
                  intervalMinutes,
                  enabled: true,
                  workflowPresetId,
                });
                if (payload.status === "ok") {
                  setName("");
                }
                return payload;
              })
            }
          >
            Save job
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Job list</span>
        {summary?.jobs.length ? (
          <div className="model-list">
            {summary.jobs.map((job) => (
              <article className="model-item" key={job.id}>
                <div className="model-item-header">
                  <div>
                    <strong>{job.name}</strong>
                    <div className="muted-line">
                      {job.kind} | svakih {job.intervalMinutes} min
                    </div>
                  </div>
                  <span className="warning-badge">{job.lastStatus || "idle"}</span>
                </div>
                <p className="helper-text">
                  Last run: {formatDateTime(job.lastRunAt)} | Next run: {formatDateTime(job.nextRunAt)}
                </p>
                <p className="helper-text">{job.lastSummary || "Job jos nije pokretan."}</p>
                <div className="inline-actions">
                  <button type="button" onClick={() => void runMutation(() => runJobNow(job.id))}>
                    Run now
                  </button>
                  <button type="button" onClick={() => void runMutation(() => deleteJob(job.id))}>
                    Remove
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">
            Jos nema sacuvanih job-ova. Dodaj health check, update check ili benchmark battery da
            Control Center dobije pravi operativni ritam.
          </p>
        )}
      </section>

      <ActionResultPanel result={result} />
    </>
  );
}
