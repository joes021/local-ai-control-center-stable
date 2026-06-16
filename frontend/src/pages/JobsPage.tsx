import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import {
  RuntimePilotActionDeck,
  type RuntimePilotActionDeckItem,
} from "../components/shell/RuntimePilotActionDeck";
import {
  RuntimePilotStatusDeck,
  type RuntimePilotStatusDeckItem,
} from "../components/shell/RuntimePilotStatusDeck";
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

  const selectedPreset = workflowPresets.find((preset) => preset.id === workflowPresetId) ?? null;

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
      setError(reason instanceof Error ? reason.message : "Akcija poslova nije uspela.");
    }
  }

  function scrollToForm() {
    document.getElementById("jobs-create-form")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function scrollToList() {
    document.getElementById("jobs-list")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function scrollToResult() {
    document.getElementById("jobs-action-result")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function saveCurrentJob() {
    if (!name.trim()) {
      return;
    }
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
    });
  }

  if (!summary || !settingsPayload) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam poslove..."
        onRetry={() => {
          setError(null);
          void load();
        }}
      />
    );
  }

  const nextRunLabel = summary.jobs[0]?.nextRunAt
    ? formatDateTime(summary.jobs[0].nextRunAt)
    : "nema rasporeda";

  const jobsStatusItems: RuntimePilotStatusDeckItem[] = [
    {
      id: "jobs-count",
      label: "Aktivni poslovi",
      value: String(summary.jobCount ?? 0),
      detail: "Ukupan broj sačuvanih pozadinskih poslova koje vodi ugrađeni zakazivač.",
      action: "Ritam sistema",
      icon: "jobs",
      accent: "rgba(242, 184, 75, 0.34)",
    },
    {
      id: "jobs-kind",
      label: "Vrsta posla",
      value: selectedKind?.label || "nije izabrano",
      detail: selectedKind?.summary || "Izaberi vrstu posla da vidiš čemu služi i kako utiče na ritam sistema.",
      action: "Izabrani tok",
      icon: "workflows",
      accent: "rgba(109, 172, 255, 0.34)",
      onClick: scrollToForm,
    },
    {
      id: "jobs-preset",
      label: "Preset",
      value: selectedPreset?.label || "opciono",
      detail:
        selectedPreset?.summary ||
        "Preset radnog toka je dodatni sloj koji posao čini bližim stvarnom režimu rada mašine.",
      action: "Skok na formu",
      icon: "settings",
      accent: "rgba(88, 222, 193, 0.34)",
      onClick: scrollToForm,
    },
    {
      id: "jobs-schedule",
      label: "Ritam",
      value: `Svakih ${intervalMinutes} min`,
      detail: `Sledeće očekivano izvršavanje: ${nextRunLabel}`,
      action: "Skok na listu",
      icon: "telemetry",
      accent: "rgba(205, 162, 255, 0.34)",
      onClick: scrollToList,
    },
  ];

  const jobsActionItems: RuntimePilotActionDeckItem[] = [
    {
      id: "jobs-form-jump",
      code: "NEW",
      title: "Skok na formu",
      subtitle: "UNOS + PODEŠAVANJE",
      icon: "jobs",
      detail: "Vodi pravo na unos novog posla: naziv, vrsta, interval i preset radnog toka.",
      onClick: scrollToForm,
    },
    {
      id: "jobs-save",
      code: "SAVE",
      title: "Sačuvaj posao",
      subtitle: "DODAJ U RASPORED",
      icon: "workflows",
      tone: "primary",
      detail: "Koristi trenutne vrednosti iz forme i odmah ih upisuje u listu pozadinskih poslova.",
      disabled: !name.trim(),
      onClick: saveCurrentJob,
    },
    {
      id: "jobs-list-jump",
      code: "LIST",
      title: "Skok na listu",
      subtitle: "RASPORED + STATUS",
      icon: "browser",
      detail: "Posle čuvanja ovde prvo proveri da li se posao pojavio i kada mu je sledeće izvršavanje.",
      onClick: scrollToList,
    },
    {
      id: "jobs-refresh",
      code: "SYNC",
      title: "Osveži poslove",
      subtitle: "STANJE + GENERATED AT",
      icon: "reload",
      detail: "Ručno osvežava listu, status i generated-at signal scheduler pregleda.",
      onClick: () => {
        setError(null);
        void load();
      },
    },
    {
      id: "jobs-result-jump",
      code: "LOG",
      title: "Skok na rezultat",
      subtitle: "POSLEDNJA AKCIJA",
      icon: "logs",
      detail: "Ovde čitaš rezultat čuvanja, ručnog pokretanja ili uklanjanja posla.",
      onClick: scrollToResult,
    },
  ];

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <PageFlowCard
        title="Tok poslova"
        summary="Ovde prvo izabereš vrstu posla, zatim interval i preset, a tek onda pratiš listu sačuvanih i ručno ih pokrećeš po potrebi."
        steps={[
          {
            title: "Izaberi vrstu posla",
            detail: "Provera zdravlja, benchmark i ažuriranje imaju različit ritam, pa prvo zaključaš šta automatizuješ.",
          },
          {
            title: "Podesi interval i preset",
            detail: "Preset radnog toka je opcioni sloj koji posao čini bližim stvarnom radu mašine.",
          },
          {
            title: "Sačuvaj i proveri listu",
            detail: "Lista poslova je glavno mesto za ručno pokretanje, proveru ritma i brisanje.",
          },
        ]}
      />

      <RuntimePilotStatusDeck
        eyebrow="Scheduler signal"
        title="Raspored, unos i lista poslova"
        helper="Četiri karte odmah pokazuju broj poslova, izabranu vrstu, preset i ritam pre nego što otvoriš formu ili listu."
        items={jobsStatusItems}
      />

      <RuntimePilotActionDeck
        eyebrow="Akcije"
        title="Forma, čuvanje i provera rezultata"
        helper="Gornji klikovi vode pravo na unos, čuvanje, listu, osvežavanje i poslednji rezultat bez lutanja po dnu strane."
        items={jobsActionItems}
      />

      <section className="status-card wide-card runtimepilot-faceplate-module">
        <div className="runtimepilot-inline-heading">
          <span className="status-label">Pozadinski ritam</span>
          <strong className="status-value">Pozadinski poslovi</strong>
        </div>
        <p className="helper-text">
          Ovo su pozadinski poslovi koje ugrađeni scheduler vrti dok je backend aktivan. Ovde centralno upravljaš proverom zdravlja, benchmark ciklusima, proverom ažuriranja i drugim dužim ritmovima rada.
        </p>
        <div className="summary-metrics">
          <span>Aktivnih poslova: {summary.jobCount}</span>
          <span>Osveženo: {formatDateTime(summary.generatedAt)}</span>
          <span>Selektovana vrsta: {selectedKind?.label || "--"}</span>
        </div>
      </section>

      <section id="jobs-create-form" className="status-card wide-card runtimepilot-faceplate-module runtimepilot-service-anchor">
        <div className="runtimepilot-inline-heading">
          <span className="status-label">Sačuvaj posao</span>
          <strong className="status-value">Unesi posao, ritam i opcioni preset radnog toka.</strong>
        </div>
        <div className="settings-page-grid">
          <label className="settings-compact-field">
            <span>Naziv</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Provera zdravlja na sat, benchmark noću..."
            />
          </label>
          <label className="settings-compact-field">
            <span>Vrsta</span>
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              {(summary.availableKinds ?? []).map((item) => (
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
          {selectedKind?.summary || "Izaberi vrstu posla da vidiš čemu služi."}
        </p>
        <div className="inline-actions">
          <button type="button" className="action-button" disabled={!name.trim()} onClick={saveCurrentJob}>
            Sačuvaj posao
          </button>
        </div>
      </section>

      <section id="jobs-list" className="status-card wide-card runtimepilot-faceplate-module runtimepilot-service-anchor">
        <div className="runtimepilot-inline-heading">
          <span className="status-label">Lista poslova</span>
          <strong className="status-value">Sačuvani poslovi, ručno pokretanje i uklanjanje.</strong>
        </div>
        {summary.jobs.length ? (
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
                <p className="helper-text">{job.lastSummary || "Posao još nije pokretan."}</p>
                <div className="inline-actions">
                  <button
                    type="button"
                    className="action-button"
                    onClick={() => void runMutation(() => runJobNow(job.id))}
                  >
                    Pokreni sada
                  </button>
                  <button
                    type="button"
                    className="danger-button"
                    onClick={() => void runMutation(() => deleteJob(job.id))}
                  >
                    Ukloni
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">
            Još nema sačuvanih poslova. Dodaj proveru zdravlja, proveru ažuriranja ili benchmark bateriju da RuntimePilot dobije pravi operativni ritam.
          </p>
        )}
      </section>

      <div id="jobs-action-result" className="wide-card runtimepilot-service-anchor">
        <ActionResultPanel result={result} />
      </div>
    </>
  );
}
