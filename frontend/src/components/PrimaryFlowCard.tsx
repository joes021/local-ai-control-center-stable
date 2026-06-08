import type { ReactNode } from "react";

import type { RuntimePilotIconName } from "./RuntimePilotIcon";
import { RuntimePilotIcon } from "./RuntimePilotIcon";

type PrimaryFlowCardProps = {
  className?: string;
  eyebrow: string;
  title: string;
  stateTitle: string;
  stateSummary: string;
  icon: RuntimePilotIconName;
  primaryLabel: string;
  primaryActionLabel: string;
  primaryActionIcon?: RuntimePilotIconName;
  onPrimaryAction: () => void;
  secondaryLabel: string;
  secondaryActionLabel: string;
  secondaryActionIcon?: RuntimePilotIconName;
  onSecondaryAction: () => void;
  resultLabel: string;
  resultSummary: string;
  stateMeta?: ReactNode;
  liveResult?: ReactNode;
  primaryDisabled?: boolean;
  primaryTitle?: string;
  secondaryDisabled?: boolean;
  secondaryTitle?: string;
};

export function PrimaryFlowCard({
  className,
  eyebrow,
  title,
  stateTitle,
  stateSummary,
  icon,
  primaryLabel,
  primaryActionLabel,
  primaryActionIcon = "play",
  onPrimaryAction,
  secondaryLabel,
  secondaryActionLabel,
  secondaryActionIcon = "play",
  onSecondaryAction,
  resultLabel,
  resultSummary,
  stateMeta,
  liveResult,
  primaryDisabled = false,
  primaryTitle,
  secondaryDisabled = false,
  secondaryTitle,
}: PrimaryFlowCardProps) {
  return (
    <section
      className={`status-card primary-flow-card runtimepilot-section-shell runtimepilot-faceplate-module${
        className ? ` ${className}` : ""
      }`}
    >
      <div className="primary-flow-card-header">
        <span className="runtimepilot-section-glyph">
          <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name={icon} />
        </span>
        <div>
          <span className="status-label">{eyebrow}</span>
          <strong className="status-value">{title}</strong>
        </div>
      </div>

      <article className="primary-flow-card-block">
        <span className="status-label">Stanje sada</span>
        <strong className="primary-flow-card-state">{stateTitle}</strong>
        <p className="helper-text">{stateSummary}</p>
        {stateMeta ? <div className="summary-metrics">{stateMeta}</div> : null}
      </article>

      <div className="primary-flow-card-action-grid">
        <article className="primary-flow-card-block">
          <span className="status-label">{primaryLabel}</span>
          <button
            type="button"
            className="action-button deck-control-button deck-control-button-primary"
            onClick={onPrimaryAction}
            disabled={primaryDisabled}
            title={primaryTitle}
          >
            <span className="deck-control-symbol" aria-hidden="true">
              <RuntimePilotIcon name={primaryActionIcon} />
            </span>
            <span className="deck-control-copy">{primaryActionLabel}</span>
          </button>
        </article>

        <article className="primary-flow-card-block">
          <span className="status-label">{secondaryLabel}</span>
          <button
            type="button"
            className="action-button-soft deck-control-button deck-control-button-secondary"
            onClick={onSecondaryAction}
            disabled={secondaryDisabled}
            title={secondaryTitle}
          >
            <span className="deck-control-symbol" aria-hidden="true">
              <RuntimePilotIcon name={secondaryActionIcon} />
            </span>
            <span className="deck-control-copy">{secondaryActionLabel}</span>
          </button>
        </article>
      </div>

      <article className="primary-flow-card-block primary-flow-card-result">
        <span className="status-label">{resultLabel}</span>
        <p className="helper-text">{resultSummary}</p>
        {liveResult ? <div className="primary-flow-card-live-result">{liveResult}</div> : null}
      </article>
    </section>
  );
}
