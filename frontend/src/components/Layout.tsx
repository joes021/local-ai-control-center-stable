import type { PropsWithChildren, ReactNode } from "react";

import { LiveResourceStrip } from "./LiveResourceStrip";

type LayoutProps = PropsWithChildren<{
  title: string;
  subtitle: ReactNode;
  eyebrow?: ReactNode;
  nav?: ReactNode;
  brand?: ReactNode;
  themeId?: string;
  onOpenSettingsSection?: (sectionId: string) => void;
}>;

export function Layout({
  title,
  subtitle,
  eyebrow,
  nav,
  brand,
  children,
  themeId = "dark-chocolate",
  onOpenSettingsSection,
}: LayoutProps) {
  return (
    <div className="app-shell" data-theme={themeId}>
      <header className="hero">
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
      </header>
      {nav ? <nav className="top-nav">{nav}</nav> : null}
      <LiveResourceStrip onOpenSettingsSection={onOpenSettingsSection} />
      <main className="content-grid">{children}</main>
    </div>
  );
}
