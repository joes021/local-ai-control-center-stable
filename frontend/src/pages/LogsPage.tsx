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
import { fetchLogs } from "../lib/api";
import type { ActionResult } from "../lib/types";

export function LogsPage() {
  const [result, setResult] = useState<ActionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);

  async function loadLogs() {
    try {
      const payload = await fetchLogs();
      setResult(payload);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    } finally {
      setHasLoaded(true);
    }
  }

  function refreshLogs() {
    setError(null);
    setHasLoaded(false);
    void loadLogs();
  }

  function scrollToResult() {
    document.getElementById("logs-action-result")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  useEffect(() => {
    void loadLogs();
  }, []);

  if (!hasLoaded) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam logove..."
        onRetry={() => {
          setError(null);
          setHasLoaded(false);
          void loadLogs();
        }}
      />
    );
  }

  const stdoutReady = Boolean(result?.details.stdout.trim());
  const stderrReady = Boolean(result?.details.stderr.trim());
  const resultState = error
    ? "Greška pri čitanju"
    : result?.status === "ok"
      ? "Snapshot spreman"
      : result
        ? "Potrebna provera"
        : "Čeka snapshot";

  const logsStatusItems: RuntimePilotStatusDeckItem[] = [
    {
      id: "logs-snapshot",
      label: "Snapshot",
      value: resultState,
      detail:
        result?.summary ||
        "Ovde odmah vidiš da li je installer-managed paket logova stigao i da li ima smisla otvarati detalje.",
      action: "Svež paket logova",
      icon: "logs",
      accent: "rgba(242, 184, 75, 0.34)",
    },
    {
      id: "logs-stdout",
      label: "Stdout",
      value: stdoutReady ? "Ima izlaz" : "Nema značajnog izlaza",
      detail: stdoutReady
        ? "Glavni izlaz je popunjen i spreman za čitanje."
        : "Ako je stdout prazan, verovatno je dovoljan sažetak ili stderr signal.",
      action: "Glavni izlaz",
      icon: "control",
      accent: "rgba(88, 222, 193, 0.34)",
    },
    {
      id: "logs-stderr",
      label: "Stderr",
      value: stderrReady ? "Ima signal" : "Čist kanal",
      detail: stderrReady
        ? "Postoji stderr izlaz koji vredi prvi pregledati kada nešto izgleda sumnjivo."
        : "Nema stderr signala, pa problem verovatno nije očigledan runtime pad.",
      action: "Greške i upozorenja",
      icon: "repair",
      accent: "rgba(255, 129, 177, 0.34)",
    },
    {
      id: "logs-result",
      label: "Detalji",
      value: "Rezultat i payload",
      detail: "Skok vodi pravo na ActionResultPanel da ne moraš ručno da tražiš poslednji snapshot.",
      action: "Skok na rezultat",
      icon: "search",
      accent: "rgba(109, 172, 255, 0.34)",
      onClick: scrollToResult,
    },
  ];

  const logsActionItems: RuntimePilotActionDeckItem[] = [
    {
      id: "logs-refresh",
      code: "LOG",
      title: "Osveži snapshot",
      subtitle: "UČITAJ SVEŽE LOGOVE",
      icon: "reload",
      tone: "primary",
      detail: "Povlači novi installer-managed snapshot da ne čitaš zastarele poruke.",
      onClick: refreshLogs,
    },
    {
      id: "logs-result-jump",
      code: "SUM",
      title: "Skok na rezultat",
      subtitle: "SAŽETAK + DETALJI",
      icon: "logs",
      detail: "Posle osvežavanja prvo pročitaj kratak rezultat, pa tek onda dublje stdout i stderr sekcije.",
      onClick: scrollToResult,
    },
  ];

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <PageFlowCard
        title="Log tok"
        summary="Ovde prvo osveži snapshot, zatim pročitaj kratak rezime, a tek onda ulazi u detalje kada nešto stvarno izgleda čudno."
        steps={[
          {
            title: "Osveži snapshot",
            detail: "Prvi korak je da povučeš svež installer-managed log paket, a ne da gledaš zastareli izlaz.",
          },
          {
            title: "Pogledaj rezime i stderr",
            detail: "Najčešće je dovoljan vrh sažetka i stderr deo da vidiš da li je problem u runtime-u, mreži ili konfiguraciji.",
          },
          {
            title: "Tek onda idi u dubinu",
            detail: "Detaljan stdout i ostali logovi služe za dublju dijagnostiku kada kratki rezime nije dovoljan.",
          },
        ]}
      />

      <RuntimePilotStatusDeck
        eyebrow="Status log signala"
        title="Šta je stiglo i gde prvo gledaš"
        helper="Četiri karte odmah kažu da li je snapshot svež, da li postoje stdout ili stderr signali i gde je poslednji rezultat."
        items={logsStatusItems}
      />

      <RuntimePilotActionDeck
        eyebrow="Akcije"
        title="Osveži i otvori detalje"
        helper='Ovde nema mrtvih kartica: prvo možeš da klikneš na "Osveži logove", pa da skočiš pravo na rezultat poslednjeg učitavanja.'
        items={logsActionItems}
      />

      <section className="status-card wide-card runtimepilot-faceplate-module">
        <div className="runtimepilot-inline-heading">
          <span className="status-label">Brzo čitanje</span>
          <strong className="status-value">
            Prvo proveri sažetak, pa stderr, pa tek onda puni stdout.
          </strong>
        </div>
        <p className="helper-text">
          Ova strana je namenjena brzom pronalaženju problema. Ako sažetak već jasno kaže šta nije u redu, nema potrebe da ručno čitaš ceo log paket.
        </p>
        <div className="summary-metrics">
          <span>Status: {result?.status || "--"}</span>
          <span>Stdout: {stdoutReady ? "popunjen" : "prazan"}</span>
          <span>Stderr: {stderrReady ? "ima signal" : "čist"}</span>
        </div>
      </section>

      <div id="logs-action-result" className="wide-card runtimepilot-service-anchor">
        <ActionResultPanel result={result} />
      </div>
    </>
  );
}
