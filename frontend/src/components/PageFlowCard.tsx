import type { ReactNode } from "react";

import { RuntimePilotIcon } from "./RuntimePilotIcon";

type PageFlowStep = {
  title: string;
  detail: string;
};

type PageFlowCardProps = {
  title: string;
  summary: string;
  steps: PageFlowStep[];
  actions?: ReactNode;
};

export function PageFlowCard({ title, summary, steps, actions }: PageFlowCardProps) {
  return (
    <section className="status-card wide-card page-flow-card runtimepilot-section-shell">
      <div className="section-header page-flow-header">
        <div className="runtimepilot-section-heading">
          <span className="runtimepilot-section-glyph">
            <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name="control" />
          </span>
          <div>
            <span className="status-label">Prirodan tok rada</span>
            <strong className="status-value">{title}</strong>
          </div>
        </div>
        {actions ? <div className="inline-actions compact-actions page-flow-actions">{actions}</div> : null}
      </div>
      <p className="helper-text">{summary}</p>
      <div className="page-flow-grid">
        {steps.map((step, index) => (
          <article className="page-flow-step" key={`${index + 1}-${step.title}`}>
            <span className="page-flow-step-index">{index + 1}</span>
            <div className="page-flow-step-copy">
              <strong>{step.title}</strong>
              <p className="helper-text">{step.detail}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
