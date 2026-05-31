import type { PropsWithChildren, ReactNode } from "react";

import { LiveResourceStrip } from "./LiveResourceStrip";

type LayoutProps = PropsWithChildren<{
  title: string;
  subtitle: ReactNode;
  eyebrow?: ReactNode;
  nav?: ReactNode;
  themeId?: string;
  onOpenSettingsSection?: (sectionId: string) => void;
}>;

export function Layout({
  title,
  subtitle,
  eyebrow,
  nav,
  children,
  themeId = "dark-chocolate",
  onOpenSettingsSection,
}: LayoutProps) {
  return (
    <div className="app-shell" data-theme={themeId}>
      <header className="hero">
        <p className="eyebrow">{eyebrow ?? "Lokalni AI shell"}</p>
        <h1>{title}</h1>
        <div className="subtitle">{subtitle}</div>
      </header>
      {nav ? <nav className="top-nav">{nav}</nav> : null}
      <LiveResourceStrip onOpenSettingsSection={onOpenSettingsSection} />
      <main className="content-grid">{children}</main>
    </div>
  );
}
