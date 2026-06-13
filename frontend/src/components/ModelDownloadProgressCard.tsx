import type { DownloadProgressPayload } from "../lib/types";

function formatGiB(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "nepoznato";
  }
  return `${value.toFixed(2)} GiB`;
}

function formatSpeed(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "nepoznato";
  }
  return `${value.toFixed(1)} MB/s`;
}

function formatEta(seconds: number | null) {
  if (seconds === null || seconds < 0) {
    return "nepoznato";
  }
  if (seconds === 0) {
    return "0s";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  const parts: string[] = [];
  if (hours) {
    parts.push(`${hours}h`);
  }
  if (minutes) {
    parts.push(`${minutes}m`);
  }
  if (secs && hours === 0) {
    parts.push(`${secs}s`);
  }
  return parts.join(" ") || "0s";
}

export function ModelDownloadProgressCard({ progress }: { progress: DownloadProgressPayload | null }) {
  if (!progress) {
    return null;
  }

  const percent = valueOrNull(progress.percent);
  const usesIndeterminateProgress =
    percent === null && (progress.status === "starting" || progress.status === "downloading");
  const percentLabel = usesIndeterminateProgress
    ? "Ukupna veličina još nije prijavljena"
    : progress.percent === null
      ? "nepoznato"
      : `${progress.percent.toFixed(1)}%`;
  const downloadedLabel =
    progress.totalGiB === null
      ? `${formatGiB(progress.downloadedGiB)} / Ukupna veličina još nije prijavljena`
      : `${formatGiB(progress.downloadedGiB)} / ${formatGiB(progress.totalGiB)}`;
  const nextStepNote =
    progress.status === "error"
      ? "Posle greške možeš odmah ponovo kliknuti Preuzmi. Resume nije podržan; pravi se nov pokušaj od početka."
      : progress.status === "completed" || progress.status === "already-installed"
        ? "Ako želiš novi pokušaj, klik na Preuzmi pokreće novi provereni tok za izabrani model."
        : "Dodaj HF i Dodaj Unsloth samo dodaju model u spisak. Pravo skidanje kreće tek na Preuzmi.";
  const statusTone = downloadStatusTone(progress.status);

  return (
    <section className="status-card wide-card model-download-monitor-card runtimepilot-faceplate-module">
      <div className="model-download-monitor-top">
        <div className="model-download-monitor-copy">
          <span className="status-label">Status preuzimanja</span>
          <strong className="status-value">{progress.status}</strong>
          <p className="helper-text">{progress.message}</p>
        </div>
        <span className={`browser-badge model-download-status-pill model-download-status-${statusTone}`}>
          {progress.status}
        </span>
      </div>
      <div className="download-progress-track" aria-hidden="true">
        <div
          className={`download-progress-fill${usesIndeterminateProgress ? " download-progress-fill-indeterminate" : ""}`}
          style={{ width: `${Math.max(0, Math.min(percent ?? 42, 100))}%` }}
        />
      </div>
      <div className="model-download-monitor-grid">
        <article className="browser-readout-card">
          <span className="status-label">Model</span>
          <strong className="status-value">{progress.modelId || progress.fileName || "nema aktivnog modela"}</strong>
        </article>
        <article className="browser-readout-card">
          <span className="status-label">Procenat</span>
          <strong className="status-value">{percentLabel}</strong>
        </article>
        <article className="browser-readout-card">
          <span className="status-label">Preuzeto</span>
          <strong className="status-value">{downloadedLabel}</strong>
        </article>
        <article className="browser-readout-card">
          <span className="status-label">Brzina</span>
          <strong className="status-value">{formatSpeed(progress.speedMBps)}</strong>
        </article>
        <article className="browser-readout-card">
          <span className="status-label">ETA</span>
          <strong className="status-value">{formatEta(progress.etaSeconds)}</strong>
        </article>
        {progress.source ? (
          <article className="browser-readout-card">
            <span className="status-label">Izvor</span>
            <strong className="status-value">{progress.source}</strong>
          </article>
        ) : null}
      </div>
      {usesIndeterminateProgress ? (
        <div className="helper-text model-download-monitor-note">
          <strong>Napredak:</strong> Izvor trenutno ne prijavljuje ukupnu veličinu, pa kartica prati
          živi tok preuzetih podataka dok ne stigne završni snapshot.
        </div>
      ) : null}
      <div className="helper-text model-download-monitor-note">
        <strong>Napomena:</strong> {nextStepNote}
      </div>
    </section>
  );
}

function valueOrNull(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function downloadStatusTone(status: string) {
  const normalized = status.trim().toLowerCase();
  if (normalized === "completed" || normalized === "already-installed") {
    return "good";
  }
  if (normalized === "error" || normalized === "failed") {
    return "bad";
  }
  if (normalized === "downloading" || normalized === "starting") {
    return "active";
  }
  return "idle";
}
