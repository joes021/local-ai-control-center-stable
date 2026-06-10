import type { RuntimePilotIconName } from "../RuntimePilotIcon";
import { RuntimePilotIcon } from "../RuntimePilotIcon";

type HomeHiFiCommandButtonProps = {
  code: string;
  title: string;
  subtitle: string;
  tone?: "default" | "primary" | "danger";
  icon?: RuntimePilotIconName;
  disabled?: boolean;
  titleAttr?: string;
  onClick: () => void;
};

export function HomeHiFiCommandButton({
  code,
  title,
  subtitle,
  tone = "default",
  icon = "control",
  disabled = false,
  titleAttr,
  onClick,
}: HomeHiFiCommandButtonProps) {
  return (
    <button
      type="button"
      className={`runtimepilot-home-hifi-command runtimepilot-home-hifi-command-${tone}`}
      disabled={disabled}
      title={titleAttr}
      onClick={onClick}
    >
      <span className="runtimepilot-home-hifi-command-code">{code}</span>
      <span className="runtimepilot-home-hifi-command-copy">
        <span className="runtimepilot-home-hifi-command-title">{title}</span>
        <span className="runtimepilot-home-hifi-command-subtitle">{subtitle}</span>
      </span>
      <span className="runtimepilot-home-hifi-command-indicator" aria-hidden="true">
        <RuntimePilotIcon className="runtimepilot-home-hifi-command-icon" name={icon} />
      </span>
    </button>
  );
}
