type GuidedFlowStep = {
  id: string;
  title: string;
  detail: string;
  actionLabel: string;
  status: string;
  tone?: "active" | "ready";
  onAction: () => void;
};

type GuidedFlowPanelProps = {
  title: string;
  summary: string;
  steps: readonly GuidedFlowStep[];
};

export function GuidedFlowPanel({ title, summary, steps }: GuidedFlowPanelProps) {
  return (
    <section className="status-card wide-card runtimepilot-guided-flow">
      <div className="section-header">
        <div>
          <span className="status-label">Glavni tokovi</span>
          <strong className="status-value">{title}</strong>
        </div>
      </div>
      <p className="helper-text">{summary}</p>
      <div className="runtimepilot-guided-flow-grid">
        {steps.map((step, index) => (
          <article className="runtimepilot-guided-step" key={step.id}>
            <div className="runtimepilot-guided-step-header">
              <span className="runtimepilot-guided-step-index">{index + 1}</span>
              <div className="runtimepilot-guided-step-copy">
                <strong>{step.title}</strong>
                <span
                  className={`runtimepilot-guided-step-status ${
                    step.tone === "active"
                      ? "runtimepilot-guided-step-status-active"
                      : "runtimepilot-guided-step-status-ready"
                  }`}
                >
                  {step.status}
                </span>
              </div>
            </div>
            <p className="helper-text">{step.detail}</p>
            <div className="runtimepilot-guided-step-footer">
              <button type="button" className="action-button" onClick={step.onAction}>
                {step.actionLabel}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
