import type { PropsWithChildren, ReactNode } from "react";

import { LiveResourceStrip } from "./LiveResourceStrip";
import { RuntimePilotIcon } from "./RuntimePilotIcon";

type LayoutProps = PropsWithChildren<{
  title: string;
  subtitle: ReactNode;
  deckTitle?: ReactNode;
  deckSummary?: ReactNode;
  eyebrow?: ReactNode;
  nav?: ReactNode;
  activeModelStrip?: ReactNode;
  brand?: ReactNode;
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
  activeModelStrip,
  brand,
  children,
  themeId = "dark-chocolate",
  onOpenSettingsSection,
}: LayoutProps) {
  return (
    <div className="app-shell" data-theme={themeId}>
      <header className="hero runtimepilot-hero-panel">
        <div className="runtimepilot-hero-brandline">
          {brand ? (
            <>
              <div className="hero-brand">{brand}</div>
              <div className="runtimepilot-hero-copy">
                <p className="eyebrow">{eyebrow ?? "Lokalni AI shell"}</p>
                <h1 className="visually-hidden">{title}</h1>
                <div className="subtitle">{subtitle}</div>
              </div>
            </>
          ) : (
            <div className="runtimepilot-hero-copy runtimepilot-hero-copy-full">
              <p className="eyebrow">{eyebrow ?? "Lokalni AI shell"}</p>
              <h1>{title}</h1>
              <div className="subtitle">{subtitle}</div>
            </div>
          )}
        </div>
      </header>
      {nav ? (
        <div className="runtimepilot-nav-shell runtimepilot-nav-shell-subtle">
          <div className="runtimepilot-nav-shell-copy">
            <span className="status-label">Glavni tokovi</span>
            <strong className="runtimepilot-nav-shell-title">
              Biraj direktan rad ili klikni na vodič kada želiš jasan redosled koraka.
            </strong>
          </div>
          <nav className="top-nav runtimepilot-nav-surface">
            {nav}
          </nav>
        </div>
      ) : null}
      {activeModelStrip ? <div className="runtimepilot-status-rack">{activeModelStrip}</div> : null}
      <LiveResourceStrip onOpenSettingsSection={onOpenSettingsSection} />
      <section className="runtimepilot-page-shell runtimepilot-page-shell-flat">
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
