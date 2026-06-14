import type { ReactNode } from "react";

type PrimaryTabRackProps = {
  eyebrow: string;
  title: string;
  signal: ReactNode;
  commands: ReactNode;
  deep: ReactNode;
  signalLabel?: string;
  commandsLabel?: string;
  deepLabel?: string;
};

export function PrimaryTabRack({
  eyebrow,
  title,
  signal,
  commands,
  deep,
  signalLabel = "Signal",
  commandsLabel = "Komande",
  deepLabel = "Duboko",
}: PrimaryTabRackProps) {
  return (
    <section className="status-card wide-card runtimepilot-primary-tab-rack runtimepilot-faceplate-module">
      <div className="runtimepilot-primary-tab-rack-signal">
        <div className="runtimepilot-primary-tab-rack-heading">
          <span className="status-label">{eyebrow}</span>
          <strong className="runtimepilot-primary-tab-rack-title">{title}</strong>
        </div>
        <div className="runtimepilot-primary-tab-rack-panel">
          <span className="status-label">{signalLabel}</span>
          {signal}
        </div>
      </div>
      <div className="runtimepilot-primary-tab-rack-commands">
        <span className="status-label">{commandsLabel}</span>
        {commands}
      </div>
      <div className="runtimepilot-primary-tab-rack-deep">
        <span className="status-label">{deepLabel}</span>
        {deep}
      </div>
    </section>
  );
}
