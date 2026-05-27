import type { PropsWithChildren, ReactNode } from "react";

type LayoutProps = PropsWithChildren<{
  title: string;
  subtitle: ReactNode;
  eyebrow?: ReactNode;
  nav?: ReactNode;
  themeId?: string;
}>;

export function Layout({ title, subtitle, eyebrow, nav, children, themeId = "dark-chocolate" }: LayoutProps) {
  return (
    <div className="app-shell" data-theme={themeId}>
      <header className="hero">
        <p className="eyebrow">{eyebrow ?? "Lokalni AI shell"}</p>
        <h1>{title}</h1>
        <div className="subtitle">{subtitle}</div>
      </header>
      {nav ? <nav className="top-nav">{nav}</nav> : null}
      <main className="content-grid">{children}</main>
    </div>
  );
}
