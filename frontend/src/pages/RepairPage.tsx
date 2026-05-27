import { useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
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

  function triggerRepair(kind: string) {
    runRepair(kind).then((payload) => setResult(payload as RepairResult));
  }

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Bezbedan tok popravke</span>
        <strong className="status-value">
          Ako nešto nije u redu, ovde pokrećete jednu jasnu i bezbednu popravku.
        </strong>
        <p className="status-text">
          Ovaj tok je namenjen netehničkim korisnicima: izaberite šta želite da popravite,
          sačekajte rezultat, pa pratite sledeći korak koji vam aplikacija prikaže.
        </p>
        <div className="inline-actions">
          <button type="button" onClick={() => triggerRepair("install")}>
            Popravka instalacije
          </button>
          <button type="button" onClick={() => triggerRepair("model")}>
            Popravka modela
          </button>
          <button type="button" onClick={() => triggerRepair("runtime")}>
            Popravka runtime-a
          </button>
          <button type="button" onClick={() => triggerRepair("config")}>
            Popravka podešavanja
          </button>
        </div>
      </section>
      {result ? (
        <section className="status-card wide-card">
          <span className="status-label">{result.title ?? "Rezultat popravke"}</span>
          <strong className="status-value">{result.userMessage ?? result.summary}</strong>
          <p className="status-text">
            <strong>Sledeći korak:</strong> {result.nextStep ?? "Otvorite Detalji ako želite više informacija."}
          </p>
        </section>
      ) : null}
      <ActionResultPanel result={result} />
    </>
  );
}
