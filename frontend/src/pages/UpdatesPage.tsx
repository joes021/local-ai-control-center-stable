import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
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
      ? "Pročitaj poruku iznad. Ako pominje pristup fajlu ili zaključan installer, zatvori stari installer i probaj ponovo."
      : progress.status === "completed"
        ? "Installer je pokrenut. Prati installer prozor da bi update bio završen."
        : progress.status === "launching-installer"
          ? "Sačekaj da se installer prozor pojavi. Ne moraš ručno da ga tražiš."
          : progress.status === "downloading"
            ? "Sačekaj da download stigne do 100%. Installer će se zatim pokrenuti automatski."
            : "Ako pokreneš instalaciju ažuriranja, ovde ćeš videti ceo tok preuzimanja i pokretanja installera.";

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
        <strong>Sledeći korak:</strong> {nextStep}
      </div>
      <div className="helper-text">
        <strong>Pokretanje installera:</strong> Posle preuzimanja installer se pokreće automatski.
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
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  async function loadUpdates() {
    try {
      const [updateResult, progressPayload] = await Promise.all([
        checkUpdates(),
        fetchUpdateProgress(),
      ]);
      setResult(updateResult);
      setProgress(progressPayload);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Provera ažuriranja nije uspela.");
    } finally {
      setHasLoaded(true);
    }
  }

  useEffect(() => {
    void loadUpdates();
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function pollProgress() {
      try {
        const payload = await fetchUpdateProgress();
        if (!cancelled) {
          setProgress(payload);
        }
      } catch (reason: unknown) {
        if (!cancelled) {
          setProgress(null);
          setError(reason instanceof Error ? reason.message : "Update progress nije mogao da se učita.");
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

  if (!hasLoaded) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam ažuriranja..."
        onRetry={() => {
          setError(null);
          setHasLoaded(false);
          void loadUpdates();
        }}
      />
    );
  }

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Updates tok"
        summary="Najprirodnije je da prvo proveriš novu verziju, zatim pokreneš instalaciju i onda ovde pratiš ceo download i installer tok."
        steps={[
          {
            title: "Proveri ažuriranja",
            detail: "Prvi korak je proverna akcija da vidiš da li nova verzija postoji i šta portal zna o njoj.",
          },
          {
            title: "Pokreni instalaciju",
            detail: "Kada prihvatiš update, backend preuzima installer i pokreće ga bez dodatnog ručnog traženja fajla.",
          },
          {
            title: "Prati progress karticu",
            detail: "Status, procenat, brzina i sledeći korak ovde treba da budu dovoljni da ne nagađaš šta se događa.",
          },
        ]}
        actions={
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              setError(null);
              setHasLoaded(false);
              void loadUpdates();
            }}
          >
            Osveži status
          </button>
        }
      />
      <section className="status-card wide-card">
        <span className="status-label">Ažuriranja</span>
        <p className="helper-text">
          Instalacija ažuriranja sada ide kao pozadinski tok: vidi se napredak preuzimanja, brzina,
          ETA i jasno je kada kreće pokretanje installera.
        </p>
        <div className="inline-actions">
          <button
            type="button"
            onClick={() => {
              setError(null);
              void checkUpdates()
                .then((payload) => {
                  setResult(payload);
                })
                .catch((reason: unknown) => {
                  setError(reason instanceof Error ? reason.message : "Provera ažuriranja nije uspela.");
                });
            }}
          >
            Proveri ažuriranja
          </button>
          <button
            type="button"
            onClick={() => {
              setError(null);
              void (async () => {
                try {
                  const actionResult = await installUpdate();
                  setResult(actionResult);
                  const payload = await fetchUpdateProgress();
                  setProgress(payload);
                } catch (reason: unknown) {
                  setError(
                    reason instanceof Error ? reason.message : "Instalacija ažuriranja nije uspela.",
                  );
                }
              })();
            }}
          >
            Instaliraj ažuriranje
          </button>
        </div>
      </section>
      <UpdateProgressCard progress={progress} />
      <ActionResultPanel result={result} />
    </>
  );
}
