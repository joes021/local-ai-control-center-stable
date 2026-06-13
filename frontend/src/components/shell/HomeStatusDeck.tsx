import type { RuntimePilotIconName } from "../RuntimePilotIcon";
import { RuntimePilotIcon } from "../RuntimePilotIcon";

type HomeStatusDeckLabel = "Health" | "Runtime" | "Model" | "Context" | "OpenCode";

export type HomeStatusDeckItem = {
  label: HomeStatusDeckLabel;
  value: string;
  detail: string;
  onClick: () => void;
};

const HOME_STATUS_DECK_ORDER: HomeStatusDeckLabel[] = [
  "Health",
  "Runtime",
  "Model",
  "Context",
  "OpenCode",
];

const HOME_STATUS_DECK_META: Record<
  HomeStatusDeckLabel,
  { action: string; icon: RuntimePilotIconName }
> = {
  Health: { action: "Otvori health", icon: "privacy" },
  Runtime: { action: "Otvori runtime", icon: "server" },
  Model: { action: "Otvori modele", icon: "models" },
  Context: { action: "Otvori context", icon: "settings" },
  OpenCode: { action: "Otvori OpenCode", icon: "opencode" },
};

export function HomeStatusDeck({ items }: { items: HomeStatusDeckItem[] }) {
  const itemsByLabel = new Map(items.map((item) => [item.label, item] as const));

  return (
    <section className="status-card wide-card runtimepilot-home-status-deck runtimepilot-faceplate-module">
      <header className="runtimepilot-home-status-deck-header">
        <div>
          <span className="status-label">Status dashboard</span>
          <strong className="status-value">Brzi signal</strong>
        </div>
        <p className="helper-text">
          Pet zaključanih kartica vodi pravo ka runtime-u, modelu, context-u i OpenCode radu bez duplirane navigacije.
        </p>
      </header>

      <div className="runtimepilot-home-status-grid">
        {HOME_STATUS_DECK_ORDER.map((label) => {
          const item = itemsByLabel.get(label);
          if (!item) {
            return null;
          }

          const meta = HOME_STATUS_DECK_META[label];

          return (
            <button
              key={label}
              type="button"
              className={`runtimepilot-home-status-card runtimepilot-home-status-card-${label.toLowerCase()}`}
              onClick={item.onClick}
            >
              <span className="runtimepilot-home-status-card-icon" aria-hidden="true">
                <RuntimePilotIcon name={meta.icon} />
              </span>
              <span className="status-label">{label}</span>
              <strong className="runtimepilot-home-status-card-value" title={item.value}>
                {item.value}
              </strong>
              <p className="helper-text">{item.detail}</p>
              <span className="runtimepilot-home-status-card-action">{meta.action}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
