import type { CSSProperties } from "react";

import { RuntimePilotIcon, type RuntimePilotIconName } from "../RuntimePilotIcon";

export type RuntimePilotStatusDeckItem = {
  accent?: string;
  action: string;
  detail: string;
  icon: RuntimePilotIconName;
  id: string;
  label: string;
  onClick?: () => void;
  value: string;
};

export function RuntimePilotStatusDeck({
  eyebrow,
  helper,
  items,
  title,
}: {
  eyebrow: string;
  helper: string;
  items: readonly RuntimePilotStatusDeckItem[];
  title: string;
}) {
  return (
    <section className="status-card wide-card runtimepilot-status-deck runtimepilot-faceplate-module">
      <header className="runtimepilot-status-deck-header">
        <div>
          <span className="status-label">{eyebrow}</span>
          <strong className="status-value">{title}</strong>
        </div>
        <p className="helper-text">{helper}</p>
      </header>

      <div className="runtimepilot-status-deck-grid">
        {items.map((item) => {
          const accentStyle = item.accent
            ? ({ "--runtimepilot-status-accent": item.accent } as CSSProperties)
            : undefined;

          const content = (
            <>
              <span className="runtimepilot-status-deck-card-icon" aria-hidden="true">
                <RuntimePilotIcon name={item.icon} />
              </span>
              <span className="status-label">{item.label}</span>
              <strong className="runtimepilot-status-deck-card-value" title={item.value}>
                {item.value}
              </strong>
              <p className="helper-text">{item.detail}</p>
              {item.onClick ? (
                <span className="runtimepilot-status-deck-card-action">{item.action}</span>
              ) : null}
            </>
          );

          if (!item.onClick) {
            return (
              <article
                className="runtimepilot-status-deck-card"
                key={item.id}
                style={accentStyle}
              >
                {content}
              </article>
            );
          }

          return (
            <button
              key={item.id}
              type="button"
              className="runtimepilot-status-deck-card"
              onClick={item.onClick}
              style={accentStyle}
            >
              {content}
            </button>
          );
        })}
      </div>
    </section>
  );
}
