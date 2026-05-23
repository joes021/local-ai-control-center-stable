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

export function ActionResultPanel({ result }: { result: ActionResult | null }) {
  if (!result) {
    return null;
  }

  return (
    <section className="status-card wide-card">
      <span className="status-label">
        Rezultat: {result.action} / {result.status}
      </span>
      <strong className="status-value">{result.summary}</strong>
      <details className="details-block">
        <summary>Detalji</summary>
        <pre>{result.details.stdout || result.details.stderr || "Nema detalja."}</pre>
      </details>
    </section>
  );
}
