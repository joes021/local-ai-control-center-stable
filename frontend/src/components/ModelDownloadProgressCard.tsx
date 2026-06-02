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

  return (
    <section className="status-card wide-card">
      <div className="section-header">
        <span className="status-label">Status preuzimanja</span>
        <strong className="status-value">{progress.status}</strong>
      </div>
      <div className="download-progress-track" aria-hidden="true">
        <div
          className={`download-progress-fill${usesIndeterminateProgress ? " download-progress-fill-indeterminate" : ""}`}
          style={{ width: `${Math.max(0, Math.min(percent ?? 42, 100))}%` }}
        />
      </div>
      <div className="helper-text">
        <strong>Model:</strong> {progress.modelId || progress.fileName || "nema aktivnog modela"}
      </div>
      <div className="helper-text">
        <strong>Procenat:</strong> {percentLabel}
      </div>
      <div className="helper-text">
        <strong>Preuzeto:</strong> {downloadedLabel}
      </div>
      <div className="helper-text">
        <strong>Brzina:</strong> {formatSpeed(progress.speedMBps)}
      </div>
      <div className="helper-text">
        <strong>ETA:</strong> {formatEta(progress.etaSeconds)}
      </div>
      <div className="helper-text">
        <strong>Poruka:</strong> {progress.message}
      </div>
      {progress.source ? (
        <div className="helper-text">
          <strong>Izvor:</strong> {progress.source}
        </div>
      ) : null}
      {usesIndeterminateProgress ? (
        <div className="helper-text">
          <strong>Napredak:</strong> Izvor trenutno ne prijavljuje ukupnu veličinu, pa kartica prati
          živi tok preuzetih podataka dok ne stigne završni snapshot.
        </div>
      ) : null}
      <div className="helper-text">
        <strong>Napomena:</strong> {nextStepNote}
      </div>
    </section>
  );
}

function valueOrNull(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
