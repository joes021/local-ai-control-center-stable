import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
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

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Log tok"
        summary="Ovde prvo osveži logove, zatim pročitaj kratki rezime, a tek onda ulazi u detalje kada nešto stvarno izgleda čudno."
        steps={[
          {
            title: "Osveži logove",
            detail: "Prvi korak je da povučeš svež installer-managed log snapshot, a ne da gledaš zastareli izlaz.",
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
        actions={
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              setError(null);
              setHasLoaded(false);
              void loadLogs();
            }}
          >
            Osveži logove
          </button>
        }
      />
      <ActionResultPanel result={result} />
    </>
  );
}
