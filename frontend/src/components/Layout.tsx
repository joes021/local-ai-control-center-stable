import type { PropsWithChildren, ReactNode } from "react";

import { useEffect, useState } from "react";
import { RuntimePilotIcon } from "./RuntimePilotIcon";

type LayoutProps = PropsWithChildren<{
  title: string;
  subtitle: ReactNode;
  deckTitle?: ReactNode;
  deckSummary?: ReactNode;
  eyebrow?: ReactNode;
  nav?: ReactNode;
  systemStatusLayer?: ReactNode;
  brand?: ReactNode;
  brandVersion?: ReactNode;
  suppressPageShellHeader?: boolean;
  themeId?: string;
}>;

const SCROLL_TOP_VISIBILITY_OFFSET = 360;

export function Layout({
  title,
  subtitle,
  deckTitle,
  deckSummary,
  eyebrow,
  nav,
  systemStatusLayer,
  brand,
  brandVersion,
  suppressPageShellHeader = false,
  children,
  themeId = "dark-chocolate",
}: LayoutProps) {
  const [showScrollTop, setShowScrollTop] = useState(false);

  useEffect(() => {
    const syncScrollTopVisibility = () => {
      setShowScrollTop(window.scrollY > SCROLL_TOP_VISIBILITY_OFFSET);
    };

    syncScrollTopVisibility();
    window.addEventListener("scroll", syncScrollTopVisibility, { passive: true });

    return () => {
      window.removeEventListener("scroll", syncScrollTopVisibility);
    };
  }, []);

  const handleScrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="app-shell" data-theme={themeId}>
      <header className="hero runtimepilot-hero-panel">
        <div className={`runtimepilot-hero-layout${nav ? " runtimepilot-hero-layout-with-nav" : ""}`}>
          <div className="runtimepilot-hero-brandline">
            <div className="runtimepilot-shell-brand-panel">
              <div className="runtimepilot-shell-brand-header">
                {brand ? <div className="hero-brand runtimepilot-hero-brandmark">{brand}</div> : null}
                {brandVersion ? <span className="runtimepilot-shell-brand-version">{brandVersion}</span> : null}
              </div>
              <div className="runtimepilot-hero-main">
                <div className={`runtimepilot-hero-copy${brand ? "" : " runtimepilot-hero-copy-full"}`}>
                  <p className="eyebrow runtimepilot-shell-brand-eyebrow">{eyebrow ?? "Lokalni AI shell"}</p>
                  {brand ? <h1 className="visually-hidden">{title}</h1> : <h1>{title}</h1>}
                  <div className="subtitle visually-hidden">{subtitle}</div>
                </div>
              </div>
            </div>
            {nav ? (
              <div className="runtimepilot-nav-shell runtimepilot-nav-shell-subtle runtimepilot-hero-nav-shell">
                <span className="visually-hidden runtimepilot-nav-shell-title">
                  Glavni tokovi RuntimePilot shell-a
                </span>
                <nav aria-label="Glavni tokovi" className="top-nav runtimepilot-nav-surface">
                  {nav}
                </nav>
              </div>
            ) : null}
          </div>
        </div>
      </header>
      {systemStatusLayer}
      <section className="runtimepilot-page-shell runtimepilot-page-shell-flat">
        {suppressPageShellHeader ? null : (
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
        )}
        <main className="content-grid runtimepilot-content-grid">{children}</main>
      </section>
      <button
        aria-hidden={showScrollTop ? "false" : "true"}
        aria-label="Vrati na vrh stranice"
        className={`runtimepilot-scroll-top-button ${showScrollTop ? "runtimepilot-scroll-top-button-visible" : ""}`}
        onClick={handleScrollToTop}
        tabIndex={showScrollTop ? 0 : -1}
        type="button"
      >
        <span aria-hidden="true" className="runtimepilot-scroll-top-button-symbol">
          ↑
        </span>
        <span className="runtimepilot-scroll-top-button-label">Na vrh</span>
      </button>
    </div>
  );
}
