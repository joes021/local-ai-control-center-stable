import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { fetchLogs } from "../lib/api";
import type { ActionResult } from "../lib/types";

export function LogsPage() {
  const [result, setResult] = useState<ActionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLogs().then(setResult).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    });
  }, []);

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  return <ActionResultPanel result={result} />;
}
