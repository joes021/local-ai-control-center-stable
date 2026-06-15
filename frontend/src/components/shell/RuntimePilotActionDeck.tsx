import type { ReactNode } from "react";

import { RuntimePilotIcon, type RuntimePilotIconName } from "../RuntimePilotIcon";

export type RuntimePilotActionDeckItem = {
  actions?: ReactNode;
  code: string;
  detail?: string;
  disabled?: boolean;
  icon?: RuntimePilotIconName;
  id: string;
  onClick?: () => void;
  subtitle: string;
  title: string;
  tone?: "default" | "primary";
};

export function RuntimePilotActionDeck({
  eyebrow,
  footer,
  helper,
  items,
  title,
}: {
  eyebrow: string;
  footer?: ReactNode;
  helper: string;
  items: readonly RuntimePilotActionDeckItem[];
  title: string;
}) {
  return (
    <section className="status-card wide-card runtimepilot-action-deck runtimepilot-faceplate-module">
      <header className="runtimepilot-action-deck-header">
        <div>
          <span className="status-label">{eyebrow}</span>
          <strong className="status-value">{title}</strong>
        </div>
        <p className="helper-text">{helper}</p>
      </header>

      <div className="runtimepilot-action-deck-grid">
        {items.map((item) => {
          const iconName = item.icon ?? "control";
          const toneClass =
            item.tone === "primary"
              ? " runtimepilot-action-deck-item-primary"
              : "";

          if (item.actions) {
            return (
              <article
                className={`runtimepilot-action-deck-item runtimepilot-action-deck-item-panel${toneClass}`}
                key={item.id}
              >
                <div className="runtimepilot-action-deck-item-core">
                  <span className="runtimepilot-action-deck-item-code">{item.code}</span>
                  <span className="runtimepilot-action-deck-item-copy">
                    <span className="runtimepilot-action-deck-item-title">{item.title}</span>
                    <span className="runtimepilot-action-deck-item-subtitle">{item.subtitle}</span>
                    {item.detail ? (
                      <span className="runtimepilot-action-deck-item-detail">{item.detail}</span>
                    ) : null}
                  </span>
                  <span className="runtimepilot-action-deck-item-indicator" aria-hidden="true">
                    <RuntimePilotIcon
                      className="runtimepilot-action-deck-item-icon"
                      name={iconName}
                    />
                  </span>
                </div>
                <div className="runtimepilot-action-deck-item-actions">{item.actions}</div>
              </article>
            );
          }

          return (
            <button
              type="button"
              className={`runtimepilot-action-deck-item${toneClass}`}
              key={item.id}
              disabled={item.disabled || !item.onClick}
              onClick={() => item.onClick?.()}
            >
              <span className="runtimepilot-action-deck-item-code">{item.code}</span>
              <span className="runtimepilot-action-deck-item-copy">
                <span className="runtimepilot-action-deck-item-title">{item.title}</span>
                <span className="runtimepilot-action-deck-item-subtitle">{item.subtitle}</span>
                {item.detail ? (
                  <span className="runtimepilot-action-deck-item-detail">{item.detail}</span>
                ) : null}
              </span>
              <span className="runtimepilot-action-deck-item-indicator" aria-hidden="true">
                <RuntimePilotIcon className="runtimepilot-action-deck-item-icon" name={iconName} />
              </span>
            </button>
          );
        })}
      </div>

      {footer ? <div className="runtimepilot-action-deck-footer">{footer}</div> : null}
    </section>
  );
}
