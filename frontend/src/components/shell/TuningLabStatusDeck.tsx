import type { RuntimePilotIconName } from "../RuntimePilotIcon";
import { RuntimePilotIcon } from "../RuntimePilotIcon";

export type TuningLabStatusDeckItem = {
  action: string;
  detail: string;
  icon: RuntimePilotIconName;
  id: string;
  label: string;
  onClick: () => void;
  tone: "readiness" | "opencode" | "runtime" | "model" | "workspace";
  value: string;
};

export function TuningLabStatusDeck({
  eyebrow,
  helper,
  items,
  title,
}: {
  eyebrow: string;
  helper: string;
  items: TuningLabStatusDeckItem[];
  title: string;
}) {
  return (
    <section className="status-card wide-card tuning-lab-status-deck runtimepilot-faceplate-module tuning-rack-module">
      <header className="tuning-lab-status-deck-header">
        <div>
          <span className="status-label">{eyebrow}</span>
          <strong className="status-value">{title}</strong>
        </div>
        <p className="helper-text">{helper}</p>
      </header>

      <div className="tuning-lab-status-grid">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`tuning-lab-status-card tuning-lab-status-card-${item.tone}`}
            onClick={item.onClick}
          >
            <span className="tuning-lab-status-card-icon" aria-hidden="true">
              <RuntimePilotIcon name={item.icon} />
            </span>
            <span className="status-label">{item.label}</span>
            <strong className="tuning-lab-status-card-value" title={item.value}>
              {item.value}
            </strong>
            <p className="helper-text">{item.detail}</p>
            <span className="tuning-lab-status-card-action">{item.action}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
