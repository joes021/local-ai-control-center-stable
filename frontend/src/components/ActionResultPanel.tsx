type ActionResult = {
  status: string;
  action: string;
  summary: string;
  details: {
    returncode: number;
    stdout: string;
    stderr: string;
  };
};

function humanizeAction(action: string) {
  return action.replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
}

function describeStatus(status: string) {
  switch (status) {
    case "ok":
      return { label: "Uspešno", tone: "ok" };
    case "pending":
      return { label: "U toku", tone: "pending" };
    case "warning":
      return { label: "Pažnja", tone: "warning" };
    case "cancelled":
      return { label: "Prekinuto", tone: "muted" };
    case "error":
    default:
      return { label: "Greška", tone: "error" };
  }
}

export function ActionResultPanel({ result }: { result: ActionResult | null }) {
  if (!result) {
    return null;
  }

  const statusMeta = describeStatus(result.status);

  return (
    <section className="status-card wide-card runtimepilot-section-shell runtimepilot-action-shell">
      <div className="runtimepilot-action-head">
        <div className="runtimepilot-action-copy">
          <span className="status-label">Poslednja akcija</span>
          <strong className="status-value">{result.summary}</strong>
        </div>
        <span className={`runtimepilot-action-badge runtimepilot-action-badge-${statusMeta.tone}`}>
          {statusMeta.label}
        </span>
      </div>
      <div className="summary-metrics">
        <span>Akcija: {humanizeAction(result.action) || "nepoznato"}</span>
        <span>Sažetak: Rezultat je spreman u detaljima ispod.</span>
      </div>
      <details className="details-block">
        <summary>Detalji</summary>
        <pre>{result.details.stdout || result.details.stderr || "Nema detalja."}</pre>
      </details>
    </section>
  );
}
