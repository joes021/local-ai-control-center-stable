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
    case "completed":
    case "done":
      return { label: "Uspešno", tone: "ok" };
    case "accepted":
      return { label: "Primljeno", tone: "pending" };
    case "pending":
    case "running":
    case "started":
    case "queued":
      return { label: "U toku", tone: "pending" };
    case "warning":
      return { label: "Pažnja", tone: "warning" };
    case "cancelled":
      return { label: "Prekinuto", tone: "muted" };
    case "idle":
      return { label: "Čeka", tone: "muted" };
    case "error":
    default:
      return { label: "Greška", tone: "error" };
  }
}

function describeResultSummary(status: string) {
  switch (status) {
    case "accepted":
      return "Akcija je primljena i pokrenuta.";
    case "pending":
    case "running":
    case "started":
    case "queued":
      return "Akcija je u toku. Prati detalje ispod za novi signal.";
    case "ok":
    case "completed":
    case "done":
      return "Rezultat je spreman u detaljima ispod.";
    case "cancelled":
      return "Akcija je prekinuta pre završetka.";
    case "idle":
      return "Akcija još čeka sledeći signal.";
    case "warning":
      return "Akcija je završena uz napomenu u detaljima ispod.";
    case "error":
    default:
      return "Greška je opisana u detaljima ispod.";
  }
}

export function ActionResultPanel({ result }: { result: ActionResult | null }) {
  if (!result) {
    return null;
  }

  const statusMeta = describeStatus(result.status);
  const statusSummary = describeResultSummary(result.status);

  return (
    <section
      className="status-card wide-card runtimepilot-section-shell runtimepilot-action-shell runtimepilot-faceplate-module"
      role="status"
      aria-live="polite"
    >
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
        <span>Sažetak: {statusSummary}</span>
      </div>
      <details className="details-block">
        <summary>Detalji</summary>
        <pre>{result.details.stdout || result.details.stderr || "Nema detalja."}</pre>
      </details>
    </section>
  );
}
