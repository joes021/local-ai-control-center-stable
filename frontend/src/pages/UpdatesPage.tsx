import { useEffect, useState } from "react";

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
import { checkUpdates, fetchStatus, fetchUpdateProgress, installUpdate } from "../lib/api";
import type { ActionResult, StatusPayload, UpdateProgressPayload } from "../lib/types";

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

function describeUpdateNextStep(progress: UpdateProgressPayload | null) {
  if (!progress) {
    return "Ako pokreneš instalaciju ažuriranja, ovde ćeš videti ceo tok preuzimanja i pokretanja installera.";
  }
  if (progress.status === "error") {
    return "Pročitaj poruku iznad. Ako pominje pristup fajlu ili zaključan installer, zatvori stari installer i probaj ponovo.";
  }
  if (progress.status === "completed") {
    return "Installer je pokrenut. Prati installer prozor da bi update bio završen.";
  }
  if (progress.status === "launching-installer") {
    return "Sačekaj da se installer prozor pojavi. Ne moraš ručno da ga tražiš.";
  }
  if (progress.status === "downloading") {
    return "Sačekaj da download stigne do 100%. Installer će se zatim pokrenuti automatski.";
  }
  return "Ovde pratiš ceo update tok bez ručnog traženja installer fajla.";
}

function UpdateProgressCard({ progress }: { progress: UpdateProgressPayload | null }) {
  if (!progress) {
    return null;
  }

  return (
    <section className="status-card wide-card runtimepilot-faceplate-module">
      <div className="runtimepilot-inline-heading">
        <span className="status-label">Update status</span>
        <strong className="status-value">{progress.status}</strong>
      </div>
      <p className="helper-text">
        Installer tok sada radi kao jedna jasna cev: provera verzije, download, ETA i automatsko pokretanje installera.
      </p>
      <div className="runtimepilot-service-summary-grid">
        <article className="runtimepilot-service-summary-card">
          <span className="status-label">Instalirano → release</span>
          <strong className="status-value">
            {progress.currentVersion || "nepoznato"} → {progress.latestVersion || "nepoznato"}
          </strong>
          <p className="helper-text">
            Instalirana verzija koju updater poredi sa ciljnom GitHub release verzijom.
          </p>
        </article>
        <article className="runtimepilot-service-summary-card">
          <span className="status-label">Download</span>
          <strong className="status-value">
            {progress.percent === null ? "nepoznato" : `${progress.percent.toFixed(1)}%`}
          </strong>
          <p className="helper-text">
            {formatGiB(progress.downloadedGiB)} / {formatGiB(progress.totalGiB)} · {formatSpeed(progress.speedMBps)}
          </p>
        </article>
        <article className="runtimepilot-service-summary-card">
          <span className="status-label">Faza</span>
          <strong className="status-value">{progress.phase}</strong>
          <p className="helper-text">ETA: {formatEta(progress.etaSeconds)}</p>
        </article>
      </div>
      <div className="summary-metrics">
        <span>Poruka: {progress.message}</span>
        <span>Sledeći korak: {describeUpdateNextStep(progress)}</span>
      </div>
      {progress.releaseUrl ? (
        <p className="helper-text">
          <strong>Release URL:</strong> {progress.releaseUrl}
        </p>
      ) : null}
      {progress.targetPath ? (
        <p className="helper-text">
          <strong>Installer putanja:</strong> {progress.targetPath}
        </p>
      ) : null}
    </section>
  );
}

export function UpdatesPage() {
  const [result, setResult] = useState<ActionResult | null>(null);
  const [progress, setProgress] = useState<UpdateProgressPayload | null>(null);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  async function loadUpdates() {
    try {
      const [updateResult, progressPayload, statusPayload] = await Promise.all([
        checkUpdates(),
        fetchUpdateProgress(),
        fetchStatus().catch(() => null),
      ]);
      setResult(updateResult);
      setProgress(progressPayload);
      setStatus(statusPayload);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Provera ažuriranja nije uspela.");
    } finally {
      setHasLoaded(true);
    }
  }

  function refreshStatus() {
    setError(null);
    setHasLoaded(false);
    void loadUpdates();
  }

  function scrollToProgress() {
    document.getElementById("updates-progress-panel")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function scrollToResult() {
    document.getElementById("updates-action-result")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
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

  const updatesStatusItems: RuntimePilotStatusDeckItem[] = [
    {
      id: "updates-current",
      label: "Portal build",
      value: status?.version || "nepoznato",
      detail: "Verzija pokrenutog RuntimePilot portala.",
      action: "Portal build",
      icon: "updates",
      accent: "rgba(242, 184, 75, 0.34)",
    },
    {
      id: "updates-installed",
      label: "Instalirana verzija",
      value: status?.installedVersion || progress?.currentVersion || "nepoznato",
      detail:
        "Verzija upisana u lokalnu instalaciju koju updater poredi sa GitHub release-om.",
      action: "Installer kanal",
      icon: "settings",
      accent: "rgba(205, 162, 255, 0.34)",
    },
    {
      id: "updates-latest",
      label: "Nova verzija",
      value: progress?.latestVersion || "nepoznato",
      detail:
        result?.summary ||
        "Prvo proveri da li nova verzija postoji, pa tek onda pokreći download i installer tok.",
      action: "Ciljna verzija",
      icon: "browser",
      accent: "rgba(109, 172, 255, 0.34)",
    },
    {
      id: "updates-progress",
      label: "Download",
      value:
        progress?.percent === null || progress?.percent === undefined
          ? "bez toka"
          : `${progress.percent.toFixed(1)}%`,
      detail:
        progress?.status === "downloading"
          ? `${formatGiB(progress.downloadedGiB)} / ${formatGiB(progress.totalGiB)} · ${formatSpeed(progress.speedMBps)}`
          : describeUpdateNextStep(progress),
      action: "Tok preuzimanja",
      icon: "reload",
      accent: "rgba(88, 222, 193, 0.34)",
      onClick: scrollToProgress,
    },
    {
      id: "updates-installer",
      label: "Installer",
      value: progress?.phase || "čeka pokretanje",
      detail: progress?.message || "Kada se download završi, installer kreće automatski i to se ovde prijavljuje.",
      action: "Skok na rezultat",
      icon: "settings",
      accent: "rgba(166, 205, 255, 0.34)",
      onClick: scrollToResult,
    },
  ];

  const updatesActionItems: RuntimePilotActionDeckItem[] = [
    {
      id: "updates-refresh",
      code: "SYNC",
      title: "Osveži status",
      subtitle: "PROVERI CEO UPDATE TOK",
      icon: "reload",
      detail: "Ponovo učitava proveru verzije i trenutno stanje download/install toka.",
      onClick: refreshStatus,
    },
    {
      id: "updates-check",
      code: "CHK",
      title: "Proveri ažuriranja",
      subtitle: "NOVA VERZIJA + RELEASE",
      icon: "search",
      detail: "Ručno pokreće proveru nove verzije i osvežava rezultat bez startovanja installera.",
      onClick: () => {
        setError(null);
        void checkUpdates()
          .then((payload) => {
            setResult(payload);
          })
          .catch((reason: unknown) => {
            setError(reason instanceof Error ? reason.message : "Provera ažuriranja nije uspela.");
          });
      },
    },
    {
      id: "updates-install",
      code: "UPD",
      title: "Instaliraj ažuriranje",
      subtitle: "DOWNLOAD + INSTALLER",
      icon: "updates",
      tone: "primary",
      detail: "Preuzima installer, prati progress i zatim ga automatski pokreće.",
      onClick: () => {
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
      },
    },
    {
      id: "updates-progress-jump",
      code: "ETA",
      title: "Skok na progress",
      subtitle: "PROCENAT + BRZINA",
      icon: "telemetry",
      detail: "Vodi pravo na karticu sa procentom, brzinom, ETA i trenutnom fazom update toka.",
      onClick: scrollToProgress,
    },
    {
      id: "updates-result-jump",
      code: "LOG",
      title: "Skok na rezultat",
      subtitle: "POSLEDNJA AKCIJA",
      icon: "logs",
      detail: "Ovde proveravaš zaključak poslednjeg klika i eventualnu grešku ili sledeći korak.",
      onClick: scrollToResult,
    },
  ];

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <PageFlowCard
        title="Updates tok"
        summary="Najprirodnije je da prvo proveriš novu verziju, zatim pokreneš instalaciju i onda ovde pratiš ceo download i installer tok."
        steps={[
          {
            title: "Proveri ažuriranja",
            detail: "Prvi korak je proverna akcija da vidiš da li nova verzija postoji i šta RuntimePilot zna o njoj.",
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
      />

      <RuntimePilotStatusDeck
        eyebrow="Update signal"
        title="Verzija, tok i installer"
        helper="Pet kartica odmah razdvajaju portal build, instaliranu verziju, novu verziju, download tok i fazu installera."
        items={updatesStatusItems}
      />

      <RuntimePilotActionDeck
        eyebrow="Akcije"
        title="Provera, instalacija i skokovi"
        helper="Sve glavne komande su gore: osvežavanje, provera, start installera i brzi skok na progress ili rezultat."
        items={updatesActionItems}
      />

      <section className="status-card wide-card runtimepilot-faceplate-module">
        <span className="status-label">Kako čitaš ovaj ekran</span>
        <strong className="status-value">
          Prvo proveri verziju, pa startuj update, pa prati download i installer bez ručnog traženja fajla.
        </strong>
        <p className="helper-text">
          Update sada ide kao pozadinski tok sa jasnim procentom, brzinom i ETA signalom. Kada installer krene, to se ovde vidi kao sledeća faza.
        </p>
      </section>

      <div id="updates-progress-panel" className="wide-card runtimepilot-service-anchor">
        <UpdateProgressCard progress={progress} />
      </div>

      <div id="updates-action-result" className="wide-card runtimepilot-service-anchor">
        <ActionResultPanel result={result} />
      </div>
    </>
  );
}
