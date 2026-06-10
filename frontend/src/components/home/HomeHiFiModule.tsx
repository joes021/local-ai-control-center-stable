import type { ReactNode } from "react";

import { HomeHiFiSignalRail } from "./HomeHiFiSignalRail";
import type { HomeHiFiSignalItem } from "./HomeHiFiSignalRail";

type HomeHiFiModuleProps = {
  eyebrow: string;
  title: string;
  railItems: readonly HomeHiFiSignalItem[];
  summaryTitle: string;
  summaryText: string;
  readouts: readonly { label: string; value: string; detail: string }[];
  actions: readonly ReactNode[];
  footer: readonly { label: string; value: string; detail: string }[];
};

export function HomeHiFiModule({
  eyebrow,
  title,
  railItems,
  summaryTitle,
  summaryText,
  readouts,
  actions,
  footer,
}: HomeHiFiModuleProps) {
  return (
    <section className="status-card wide-card runtimepilot-home-hifi-module runtimepilot-faceplate-module">
      <header className="runtimepilot-home-hifi-module-header">
        <div>
          <span className="status-label">{eyebrow}</span>
          <strong className="status-value">{title}</strong>
        </div>
      </header>
      <div className="runtimepilot-home-hifi-module-grid">
        <HomeHiFiSignalRail items={railItems} />
        <div className="runtimepilot-home-hifi-module-display">
          <article className="runtimepilot-home-hifi-module-summary">
            <span className="status-label">Glavni display</span>
            <strong className="status-value">{summaryTitle}</strong>
            <p className="helper-text">{summaryText}</p>
          </article>
          <div className="runtimepilot-home-hifi-module-readouts">
            {readouts.map((item) => (
              <article key={`${item.label}-${item.value}`} className="runtimepilot-home-hifi-module-readout">
                <span className="status-label">{item.label}</span>
                <strong>{item.value}</strong>
                <p className="helper-text">{item.detail}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="runtimepilot-home-hifi-module-actions">{actions}</div>
      </div>
      <div className="runtimepilot-home-hifi-module-footer">
        {footer.map((item) => (
          <article key={`${item.label}-${item.value}`} className="runtimepilot-home-hifi-module-footer-item">
            <span className="status-label">{item.label}</span>
            <strong>{item.value}</strong>
            <p className="helper-text">{item.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
