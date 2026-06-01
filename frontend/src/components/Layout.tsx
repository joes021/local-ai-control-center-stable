import type { PropsWithChildren, ReactNode } from "react";

import { LiveResourceStrip } from "./LiveResourceStrip";

type LayoutProps = PropsWithChildren<{
  title: string;
  subtitle: ReactNode;
  eyebrow?: ReactNode;
  nav?: ReactNode;
  brand?: ReactNode;
  shellMarkers?: Array<{ label: string; value: string }>;
  themeId?: string;
  onOpenSettingsSection?: (sectionId: string) => void;
}>;

export function Layout({
  title,
  subtitle,
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
      <main className="content-grid">{children}</main>
    </div>
  );
}
