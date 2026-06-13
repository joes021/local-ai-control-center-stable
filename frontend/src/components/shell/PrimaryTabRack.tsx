import type { ReactNode } from "react";

type PrimaryTabRackProps = {
  eyebrow: string;
  title: string;
  signal: ReactNode;
  commands: ReactNode;
  deep: ReactNode;
};

export function PrimaryTabRack({
  eyebrow,
  title,
  signal,
  commands,
  deep,
}: PrimaryTabRackProps) {
  return (
    <section className="status-card wide-card runtimepilot-primary-tab-rack runtimepilot-faceplate-module">
      <div className="runtimepilot-primary-tab-rack-signal">
        <div className="runtimepilot-primary-tab-rack-heading">
          <span className="status-label">{eyebrow}</span>
          <strong className="runtimepilot-primary-tab-rack-title">{title}</strong>
        </div>
        <div className="runtimepilot-primary-tab-rack-panel">
          <span className="status-label">Signal</span>
          {signal}
        </div>
      </div>
      <div className="runtimepilot-primary-tab-rack-commands">
        <span className="status-label">Komande</span>
        {commands}
      </div>
      <div className="runtimepilot-primary-tab-rack-deep">
        <span className="status-label">Duboko</span>
        {deep}
      </div>
    </section>
  );
}
