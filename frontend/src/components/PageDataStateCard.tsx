type PageDataStateCardProps = {
  loadingText: string;
  error?: string | null;
  onRetry?: () => void;
};

export function PageDataStateCard({ loadingText, error, onRetry }: PageDataStateCardProps) {
  return (
    <section className="status-card wide-card page-data-state-card runtimepilot-data-state-shell">
      <span className="status-label">{error ? "Problem pri učitavanju" : "Učitavanje"}</span>
      <strong className="status-value">{error || loadingText}</strong>
      <p className="helper-text">
        {error
          ? "RuntimePilot je ostao u kontrolisanom stanju. Pokušaj ponovo ili sačekaj da lokalni servis vrati odgovor."
          : "Sačekaj trenutak dok lokalni servis vrati potrebne podatke za ovu stranu."}
      </p>
      {error && onRetry ? (
        <div className="inline-actions compact-actions">
          <button type="button" onClick={onRetry}>
            Pokušaj ponovo
          </button>
        </div>
      ) : null}
    </section>
  );
}
