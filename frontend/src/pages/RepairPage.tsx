import { useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageFlowCard } from "../components/PageFlowCard";
import { runRepair } from "../lib/api";
import type { ActionResult } from "../lib/types";

type RepairResult = ActionResult & {
  repairKind?: string;
  title?: string;
  userMessage?: string;
  nextStep?: string;
  safeForNonTechnicalUsers?: boolean;
};

export function RepairPage() {
  const [result, setResult] = useState<RepairResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKind, setBusyKind] = useState<string>("");

  function triggerRepair(kind: string) {
    setBusyKind(kind);
    setError(null);
    void runRepair(kind)
      .then((payload) => setResult(payload as RepairResult))
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Popravka nije uspela.");
      })
      .finally(() => {
        setBusyKind("");
      });
  }

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Repair tok"
        summary="Ovde prvo izabereš vrstu popravke, zatim sačekaš jasan rezultat, pa pratiš sledeći korak koji RuntimePilot predloži."
        steps={[
          {
            title: "Izaberi jednu vrstu problema",
            detail: "Ne pokreći više popravki odjednom; najčistije je da prvo zaključaš da li je problem u instalaciji, modelu, runtime-u ili podešavanjima.",
          },
          {
            title: "Sačekaj završetak i poruku",
            detail: "Repair je zamišljen za netehnički tok: jedna akcija, jedan rezultat, jedan naredni korak.",
          },
          {
            title: "Tek onda proveri detalje",
            detail: "Ako kratko objašnjenje nije dovoljno, ActionResultPanel ostaje tu za dublji uvid u izlaz popravke.",
          },
        ]}
      />
      <section className="status-card wide-card runtimepilot-faceplate-module">
        <span className="status-label">Bezbedan tok popravke</span>
        <strong className="status-value">
          Ako nešto nije u redu, ovde pokrećete jednu jasnu i bezbednu popravku.
        </strong>
        <p className="status-text">
          Ovaj tok je namenjen netehničkim korisnicima: izaberite šta želite da popravite,
          sačekajte rezultat, pa pratite sledeći korak koji vam aplikacija prikaže.
        </p>
        <div className="inline-actions">
          <button
            type="button"
            className="action-button"
            disabled={Boolean(busyKind)}
            onClick={() => triggerRepair("install")}
          >
            {busyKind === "install" ? "Pokrećem..." : "Popravka instalacije"}
          </button>
          <button
            type="button"
            className="action-button"
            disabled={Boolean(busyKind)}
            onClick={() => triggerRepair("model")}
          >
            {busyKind === "model" ? "Pokrećem..." : "Popravka modela"}
          </button>
          <button
            type="button"
            className="action-button"
            disabled={Boolean(busyKind)}
            onClick={() => triggerRepair("runtime")}
          >
            {busyKind === "runtime" ? "Pokrećem..." : "Popravka runtime-a"}
          </button>
          <button
            type="button"
            className="action-button"
            disabled={Boolean(busyKind)}
            onClick={() => triggerRepair("config")}
          >
            {busyKind === "config" ? "Pokrećem..." : "Popravka podešavanja"}
          </button>
        </div>
      </section>
      {result ? (
        <section className="status-card wide-card runtimepilot-faceplate-module">
          <span className="status-label">{result.title ?? "Rezultat popravke"}</span>
          <strong className="status-value">{result.userMessage ?? result.summary}</strong>
          <p className="status-text">
            <strong>Sledeći korak:</strong>{" "}
            {result.nextStep ?? "Otvorite Detalji ako želite više informacija."}
          </p>
        </section>
      ) : null}
      <ActionResultPanel result={result} />
    </>
  );
}
