import type { PropsWithChildren, ReactNode } from "react";

import { LiveResourceStrip } from "./LiveResourceStrip";
import type { RuntimePilotIconName } from "./RuntimePilotIcon";
import { RuntimePilotIcon } from "./RuntimePilotIcon";

type LayoutProps = PropsWithChildren<{
  title: string;
  subtitle: ReactNode;
  deckTitle?: ReactNode;
  deckSummary?: ReactNode;
  eyebrow?: ReactNode;
  nav?: ReactNode;
  brand?: ReactNode;
  shellMarkers?: Array<{ label: string; value: string; icon?: RuntimePilotIconName }>;
  themeId?: string;
  onOpenSettingsSection?: (sectionId: string) => void;
}>;

export function Layout({
  title,
  subtitle,
  deckTitle,
  deckSummary,
  eyebrow,
  nav,
  brand,
  shellMarkers = [],
  children,
  themeId = "dark-chocolate",
  onOpenSettingsSection,
}: LayoutProps) {
  return (
    <div className="app-shell" data-theme={themeId}>
      <header className="hero runtimepilot-hero-panel">
        <div className="runtimepilot-hero-main">
          <p className="eyebrow">{eyebrow ?? "Lokalni AI shell"}</p>
          {brand ? (
            <>
              <div className="hero-brand">{brand}</div>
              <h1 className="visually-hidden">{title}</h1>
            </>
          ) : (
            <h1>{title}</h1>
          )}
          <div className="subtitle">{subtitle}</div>
        </div>
        {shellMarkers.length ? (
          <div className="runtimepilot-shell-markers" aria-label="RuntimePilot fokus oblasti">
            {shellMarkers.map((item) => (
              <article className="runtimepilot-shell-marker" key={item.label}>
                <span className="runtimepilot-shell-marker-icon">
                  <RuntimePilotIcon className="runtimepilot-shell-marker-svg" name={item.icon || "control"} />
                </span>
                <span className="runtimepilot-shell-marker-label">{item.label}</span>
                <strong className="runtimepilot-shell-marker-value">{item.value}</strong>
              </article>
            ))}
          </div>
        ) : null}
      </header>
      {nav ? (
        <nav className="top-nav runtimepilot-nav-surface">
          {nav}
        </nav>
      ) : null}
      <LiveResourceStrip onOpenSettingsSection={onOpenSettingsSection} />
      <section className="runtimepilot-page-shell">
        <div className="runtimepilot-page-shell-header">
          <div className="runtimepilot-page-shell-copy">
            <div className="runtimepilot-page-shell-signal" aria-hidden="true">
              <span className="runtimepilot-page-shell-signal-core">
                <RuntimePilotIcon className="runtimepilot-page-shell-signal-icon" name="control" />
              </span>
              <span className="runtimepilot-page-shell-signal-line" />
              <span className="runtimepilot-page-shell-signal-dot runtimepilot-page-shell-signal-dot-primary" />
              <span className="runtimepilot-page-shell-signal-dot" />
            </div>
            <div>
              <span className="status-label">{deckTitle ?? "RuntimePilot Control Deck"}</span>
              <strong className="runtimepilot-page-shell-title">
                Jedinstven pregled lokalnog AI sistema
              </strong>
            </div>
          </div>
          <p className="helper-text runtimepilot-page-shell-summary">
            {deckSummary ??
              "Svaka strana sada ostaje u istom komandnom okviru, sa jasnijim ritmom između navigacije, resursa i radnog sadržaja."}
          </p>
        </div>
        <main className="content-grid runtimepilot-content-grid">{children}</main>
      </section>
    </div>
  );
}
