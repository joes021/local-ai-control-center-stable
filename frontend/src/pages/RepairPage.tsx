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
        <span className="status-label">Bezbedan repair tok</span>
        <strong className="status-value">Ako nesto nije u redu, ovde pokrecete jednu jasnu i bezbednu popravku.</strong>
        <p className="status-text">
          Ovaj tok je namenjen netehnickim korisnicima: izaberite sta zelite da popravite, sacekajte rezultat, pa pratite
          sledeci korak koji vam aplikacija prikaze.
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
            Popravka podesavanja
          </button>
        </div>
      </section>
      {result ? (
        <section className="status-card wide-card">
          <span className="status-label">{result.title ?? "Repair rezultat"}</span>
          <strong className="status-value">{result.userMessage ?? result.summary}</strong>
          <p className="status-text">
            <strong>Sledeci korak:</strong> {result.nextStep ?? "Otvorite Detalji ako zelite vise informacija."}
          </p>
        </section>
      ) : null}
      <ActionResultPanel result={result} />
    </>
  );
}
