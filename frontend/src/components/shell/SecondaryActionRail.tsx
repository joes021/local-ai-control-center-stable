import type { ReactNode } from "react";

import { RuntimePilotIcon, type RuntimePilotIconName } from "../RuntimePilotIcon";

type SecondaryActionRailItem = {
  code: string;
  title: string;
  subtitle: string;
  icon?: RuntimePilotIconName;
  detail?: string;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "default" | "primary";
  actions?: ReactNode;
};

type SecondaryActionRailProps = {
  eyebrow: string;
  title: string;
  summary: string;
  items: readonly SecondaryActionRailItem[];
  footer?: ReactNode;
};

export type { SecondaryActionRailItem };

export function SecondaryActionRail({
  eyebrow,
  title,
  summary,
  items,
  footer,
}: SecondaryActionRailProps) {
  return (
    <aside className="status-card runtimepilot-secondary-action-rail-shell runtimepilot-faceplate-module">
      <div className="runtimepilot-secondary-action-rail-head">
        <span className="status-label">{eyebrow}</span>
        <strong className="runtimepilot-secondary-action-rail-title">{title}</strong>
        <p className="helper-text runtimepilot-secondary-action-rail-summary">{summary}</p>
      </div>

      <div className="runtimepilot-secondary-action-rail">
        {items.map((item, index) => {
          const iconName = item.icon ?? "control";
          const toneClass =
            item.tone === "primary"
              ? " runtimepilot-secondary-action-rail-item-primary"
              : "";

          if (item.actions) {
            return (
              <article
                className={`runtimepilot-secondary-action-rail-item runtimepilot-secondary-action-rail-item-panel${toneClass}`}
                key={item.code}
              >
                <div className="runtimepilot-secondary-action-rail-item-core">
                  <span className="runtimepilot-secondary-action-rail-item-code">{item.code}</span>
                  <span className="runtimepilot-secondary-action-rail-item-copy">
                    <span className="runtimepilot-secondary-action-rail-item-title">{item.title}</span>
                    <span className="runtimepilot-secondary-action-rail-item-subtitle">{item.subtitle}</span>
                    {item.detail ? (
                      <span className="runtimepilot-secondary-action-rail-item-detail">{item.detail}</span>
                    ) : null}
                  </span>
                  <span className="runtimepilot-secondary-action-rail-item-indicator" aria-hidden="true">
                    <RuntimePilotIcon className="runtimepilot-secondary-action-rail-item-icon" name={iconName} />
                  </span>
                </div>
                <div className="runtimepilot-secondary-action-rail-inline-actions">{item.actions}</div>
              </article>
            );
          }

          return (
            <button
              type="button"
              className={`runtimepilot-secondary-action-rail-item${toneClass}`}
              key={item.code}
              disabled={item.disabled || !item.onClick}
              onClick={() => item.onClick?.()}
            >
              <span className="runtimepilot-secondary-action-rail-item-code">{item.code}</span>
              <span className="runtimepilot-secondary-action-rail-item-copy">
                <span className="runtimepilot-secondary-action-rail-item-title">{item.title}</span>
                <span className="runtimepilot-secondary-action-rail-item-subtitle">{item.subtitle}</span>
                {item.detail ? (
                  <span className="runtimepilot-secondary-action-rail-item-detail">{item.detail}</span>
                ) : null}
              </span>
              <span className="runtimepilot-secondary-action-rail-item-indicator" aria-hidden="true">
                <RuntimePilotIcon className="runtimepilot-secondary-action-rail-item-icon" name={iconName} />
              </span>
            </button>
          );
        })}
      </div>

      {footer ? <div className="runtimepilot-secondary-action-rail-footer">{footer}</div> : null}
    </aside>
  );
}
