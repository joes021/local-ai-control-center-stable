import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
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
      setError(reason instanceof Error ? reason.message : "Poslovi nisu mogli da se učitaju.");
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

  if (!summary || !settingsPayload) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="U\u010ditavam poslove..."
        onRetry={() => {
          setError(null);
          void load();
        }}
      />
    );
  }

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Jobs tok"
        summary="Ovde prvo izabere\u0161 vrstu posla, zatim interval i preset, a tek onda prati\u0161 listu sa\u010duvanih i ru\u010dno ih pokre\u0107e\u0161 po potrebi."
        steps={[
          {
            title: "Izaberi vrstu posla",
            detail: "Health, benchmark i update poslovi imaju razli\u010dit ritam, pa prvo zaklju\u010daj \u0161ta automatizuje\u0161.",
          },
          {
            title: "Podesi interval i preset",
            detail: "Preset radnog toka je opcioni sloj koji posao \u010dini bli\u017eim stvarnom radu ma\u0161ine.",
          },
          {
            title: "Sa\u010duvaj i proveri listu",
            detail: "Lista poslova je glavno mesto za ru\u010dno pokretanje, proveru ritma i brisanje.",
          },
        ]}
      />

      <section className="status-card wide-card">
        <span className="status-label">Poslovi</span>
        <strong className="status-value">Zakazani poslovi</strong>
        <p className="helper-text">
          Installer-managed scheduler za benchmark, health, update i fleet ritam. Job-ovi rade u
          pozadini dok je Control Center backend aktivan.
        </p>
        <div className="summary-metrics">
          <span>Aktivnih job-ova: {summary?.jobCount ?? 0}</span>
          <span>Osveženo: {summary ? formatDateTime(summary.generatedAt) : "--"}</span>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Sačuvaj posao</span>
        <div className="settings-page-grid">
          <label className="settings-compact-field">
            <span>Naziv</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Health na sat, benchmark noću..."
            />
          </label>
          <label className="settings-compact-field">
            <span>Vrsta</span>
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
            <span>Preset radnog toka</span>
            <select value={workflowPresetId} onChange={(event) => setWorkflowPresetId(event.target.value)}>
              <option value="">(opciono)</option>
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
            Sačuvaj posao
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Lista poslova</span>
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
                  Poslednje pokretanje: {formatDateTime(job.lastRunAt)} | Sledeće: {formatDateTime(job.nextRunAt)}
                </p>
                <p className="helper-text">{job.lastSummary || "Job još nije pokretan."}</p>
                <div className="inline-actions">
                  <button type="button" onClick={() => void runMutation(() => runJobNow(job.id))}>
                    Pokreni sada
                  </button>
                  <button type="button" onClick={() => void runMutation(() => deleteJob(job.id))}>
                    Ukloni
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">
            Još nema sačuvanih job-ova. Dodaj health check, update check ili benchmark battery da
            Control Center dobije pravi operativni ritam.
          </p>
        )}
      </section>

      <ActionResultPanel result={result} />
    </>
  );
}
