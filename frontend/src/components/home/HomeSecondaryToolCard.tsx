import type { RuntimePilotIconName } from "../RuntimePilotIcon";
import { RuntimePilotIcon } from "../RuntimePilotIcon";

type HomeSecondaryToolCardProps = {
  eyebrow: string;
  title: string;
  summary: string;
  actionLabel: string;
  icon?: RuntimePilotIconName;
  onClick: () => void;
};

export function HomeSecondaryToolCard({
  eyebrow,
  title,
  summary,
  actionLabel,
  icon = "control",
  onClick,
}: HomeSecondaryToolCardProps) {
  return (
    <article className="status-card runtimepilot-advanced-tool-card runtimepilot-faceplate-module">
      <span className="status-label">{eyebrow}</span>
      <strong className="status-value">{title}</strong>
      <p className="helper-text">{summary}</p>
      <button type="button" className="action-button-soft deck-control-button deck-control-button-secondary" onClick={onClick}>
        <span className="deck-control-symbol" aria-hidden="true">
          <RuntimePilotIcon name={icon} />
        </span>
        <span className="deck-control-copy">{actionLabel}</span>
      </button>
    </article>
  );
}
