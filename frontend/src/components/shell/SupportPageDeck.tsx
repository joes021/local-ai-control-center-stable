import type { ReactNode } from "react";

import { RuntimePilotIcon } from "../RuntimePilotIcon";

type SupportPageDeckStep = {
  title: string;
  detail: string;
};

type SupportPageDeckProps = {
  eyebrow: string;
  title: string;
  summary: string;
  steps: readonly SupportPageDeckStep[];
  actions?: ReactNode;
  resultHint?: ReactNode;
};

export function SupportPageDeck({
  eyebrow,
  title,
  summary,
  steps,
  actions,
  resultHint,
}: SupportPageDeckProps) {
  return (
    <section className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module runtimepilot-support-page-deck">
      <div className="runtimepilot-support-page-deck-head">
        <div className="runtimepilot-section-heading">
          <span className="runtimepilot-section-glyph">
            <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name="control" />
          </span>
          <div>
            <span className="status-label">{eyebrow}</span>
            <strong className="status-value">{title}</strong>
          </div>
        </div>
        {actions ? (
          <div className="inline-actions compact-actions runtimepilot-support-page-deck-actions">{actions}</div>
        ) : null}
      </div>
      <p className="helper-text runtimepilot-support-page-deck-summary">{summary}</p>
      <div
        className={`runtimepilot-support-page-deck-layout${resultHint ? " runtimepilot-support-page-deck-layout-with-side" : ""}`}
      >
        <div className="runtimepilot-support-page-deck-main">
          <div className="runtimepilot-support-page-deck-grid">
            {steps.map((step, index) => (
              <article className="runtimepilot-support-page-deck-step" key={`${index + 1}-${step.title}`}>
                <span className="runtimepilot-support-page-deck-step-index">{index + 1}</span>
                <div className="runtimepilot-support-page-deck-step-copy">
                  <strong>{step.title}</strong>
                  <p className="helper-text">{step.detail}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
        {resultHint ? <aside className="runtimepilot-support-page-deck-side">{resultHint}</aside> : null}
      </div>
    </section>
  );
}
