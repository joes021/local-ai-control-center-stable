import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { checkUpdates, fetchUpdateProgress, installUpdate } from "../lib/api";
import type { ActionResult, UpdateProgressPayload } from "../lib/types";

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

function UpdateProgressCard({ progress }: { progress: UpdateProgressPayload | null }) {
  if (!progress) {
    return null;
  }

  const nextStep =
    progress.status === "error"
      ? "Procitaj poruku iznad. Ako pominje pristup fajlu ili zakljucan installer, zatvori stari installer i probaj ponovo."
      : progress.status === "completed"
        ? "Installer je pokrenut. Prati installer prozor da bi update bio zavrsen."
        : progress.status === "launching-installer"
          ? "Sacekaj da se installer prozor pojavi. Ne moras rucno da ga trazis."
          : progress.status === "downloading"
            ? "Sacekaj da download stigne do 100%. Installer ce se zatim pokrenuti automatski."
            : "Ako pokrenes Install update, ovde ces videti ceo tok preuzimanja i pokretanja installera.";

  return (
    <section className="status-card wide-card">
      <div className="section-header">
        <span className="status-label">Update status</span>
        <strong className="status-value">{progress.status}</strong>
      </div>
      <div className="helper-text">
        <strong>Trenutna verzija:</strong> {progress.currentVersion || "nepoznato"}
      </div>
      <div className="helper-text">
        <strong>Nova verzija:</strong> {progress.latestVersion || "nepoznato"}
      </div>
      <div className="helper-text">
        <strong>Procenat:</strong>{" "}
        {progress.percent === null ? "nepoznato" : `${progress.percent.toFixed(1)}%`}
      </div>
      <div className="helper-text">
        <strong>Preuzeto:</strong> {formatGiB(progress.downloadedGiB)} / {formatGiB(progress.totalGiB)}
      </div>
      <div className="helper-text">
        <strong>Brzina:</strong> {formatSpeed(progress.speedMBps)}
      </div>
      <div className="helper-text">
        <strong>ETA:</strong> {formatEta(progress.etaSeconds)}
      </div>
      <div className="helper-text">
        <strong>Faza:</strong> {progress.phase}
      </div>
      <div className="helper-text">
        <strong>Poruka:</strong> {progress.message}
      </div>
      <div className="helper-text">
        <strong>Sledeci korak:</strong> {nextStep}
      </div>
      <div className="helper-text">
        <strong>Pokretanje installera:</strong> Posle preuzimanja installer se pokrece automatski.
      </div>
      {progress.releaseUrl ? (
        <div className="helper-text">
          <strong>Release URL:</strong> {progress.releaseUrl}
        </div>
      ) : null}
      {progress.targetPath ? (
        <div className="helper-text">
          <strong>Installer putanja:</strong> {progress.targetPath}
        </div>
      ) : null}
    </section>
  );
}

export function UpdatesPage() {
  const [result, setResult] = useState<ActionResult | null>(null);
  const [progress, setProgress] = useState<UpdateProgressPayload | null>(null);

  useEffect(() => {
    checkUpdates().then(setResult).catch(() => {});
    fetchUpdateProgress().then(setProgress).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function pollProgress() {
      try {
        const payload = await fetchUpdateProgress();
        if (!cancelled) {
          setProgress(payload);
        }
      } catch {
        if (!cancelled) {
          setProgress(null);
        }
      }
    }

    void pollProgress();
    const timer = window.setInterval(() => {
      void pollProgress();
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Updates</span>
        <p className="helper-text">
          Install update sada ide kao background tok: vidi se download progress, brzina, ETA i
          jasno je kada krece pokretanje installera.
        </p>
        <div className="inline-actions">
          <button type="button" onClick={() => checkUpdates().then(setResult)}>
            Check updates
          </button>
          <button
            type="button"
            onClick={async () => {
              const actionResult = await installUpdate();
              setResult(actionResult);
              const payload = await fetchUpdateProgress();
              setProgress(payload);
            }}
          >
            Install update
          </button>
        </div>
      </section>
      <UpdateProgressCard progress={progress} />
      <ActionResultPanel result={result} />
    </>
  );
}
