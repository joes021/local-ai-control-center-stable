import { useEffect, useMemo, useRef, useState } from "react";

import { Layout } from "./components/Layout";
import { fetchSettings, fetchStatus } from "./lib/api";
import type { CompatibilityLaunchTarget } from "./lib/compatibility";
import { applyTheme, readStoredTheme, THEME_CHANGED_EVENT } from "./lib/theme";
import type { StatusPayload } from "./lib/types";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { BrowserPage } from "./pages/BrowserPage";
import { CompatibilityPage } from "./pages/CompatibilityPage";
import { FleetPage } from "./pages/FleetPage";
import { HomePage } from "./pages/HomePage";
import { JobsPage } from "./pages/JobsPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { LogsPage } from "./pages/LogsPage";
import { ModelsPage } from "./pages/ModelsPage";
import { ObservabilityPage } from "./pages/ObservabilityPage";
import { OpenCodePage } from "./pages/OpenCodePage";
import { RepairPage } from "./pages/RepairPage";
import { SearchPage } from "./pages/SearchPage";
import { ServerPage } from "./pages/ServerPage";
import { SettingsPage } from "./pages/SettingsPage";
import { UpdatesPage } from "./pages/UpdatesPage";
import { WorkflowsPage } from "./pages/WorkflowsPage";

const PAGE_LABELS = {
  home: "Početna",
  server: "Server",
  fleet: "Flota",
  jobs: "Poslovi",
  workflows: "Radni tokovi",
  opencode: "OpenCode",
  models: "Modeli",
  browser: "Browser",
  knowledge: "Znanje",
  search: "Pretraga",
  compatibility: "Kompatibilnost",
  observability: "Telemetrija",
  benchmark: "Benchmark",
  settings: "Podešavanja",
  logs: "Logovi",
  repair: "Popravka",
  updates: "Ažuriranja",
} as const;

type PageKey = keyof typeof PAGE_LABELS;

const PRIMARY_PAGES: PageKey[] = ["home", "server", "models", "opencode", "search", "settings"];

const MORE_PAGE_SECTIONS: Array<{ label: string; pages: PageKey[] }> = [
  {
    label: "Analiza i alati",
    pages: ["browser", "knowledge", "compatibility", "benchmark", "observability"],
  },
  {
    label: "Tokovi i automatizacija",
    pages: ["workflows", "jobs", "fleet"],
  },
  {
    label: "Održavanje",
    pages: ["logs", "repair", "updates"],
  },
];

const MORE_PAGES = MORE_PAGE_SECTIONS.flatMap((section) => section.pages);

export default function App() {
  const [page, setPage] = useState<PageKey>("home");
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [themeId, setThemeId] = useState<string>(readStoredTheme);
  const [compatibilityLaunchTarget, setCompatibilityLaunchTarget] =
    useState<CompatibilityLaunchTarget | null>(null);
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    applyTheme(readStoredTheme());

    fetchStatus()
      .then((payload) => {
        if (active) {
          setStatus(payload);
        }
      })
      .catch(() => {
        if (active) {
          setStatus(null);
        }
      });

    fetchSettings()
      .then((payload) => {
        if (active) {
          setThemeId(payload.themeId);
          applyTheme(payload.themeId);
        }
      })
      .catch(() => {
        if (active) {
          applyTheme(readStoredTheme());
        }
      });

    const handleThemeChanged = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      setThemeId(detail || readStoredTheme());
    };
    window.addEventListener(THEME_CHANGED_EVENT, handleThemeChanged as EventListener);

    return () => {
      active = false;
      window.removeEventListener(THEME_CHANGED_EVENT, handleThemeChanged as EventListener);
    };
  }, []);

  useEffect(() => {
    setIsMoreOpen(false);
  }, [page]);

  useEffect(() => {
    if (!isMoreOpen) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!moreMenuRef.current?.contains(event.target as Node)) {
        setIsMoreOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMoreOpen(false);
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [isMoreOpen]);

  const isMoreActive = MORE_PAGES.includes(page);

  const activeMoreLabel = useMemo(() => {
    if (!isMoreActive) {
      return null;
    }
    return PAGE_LABELS[page];
  }, [isMoreActive, page]);

  const nav = (
    <>
      <div className="top-nav-primary">
        {PRIMARY_PAGES.map((key) => (
          <button
            className={`nav-button ${page === key ? "nav-button-active" : ""}`}
            key={key}
            onClick={() => setPage(key)}
            type="button"
          >
            {PAGE_LABELS[key]}
          </button>
        ))}
      </div>
      <div className="nav-more-shell" ref={moreMenuRef}>
        <button
          aria-expanded={isMoreOpen ? "true" : "false"}
          aria-haspopup="menu"
          className={`nav-button nav-more-button ${isMoreOpen || isMoreActive ? "nav-button-active" : ""}`}
          onClick={() => setIsMoreOpen((current) => !current)}
          type="button"
        >
          <span>Više</span>
          <span aria-hidden="true" className={`nav-more-chevron ${isMoreOpen ? "nav-more-chevron-open" : ""}`}>
            ▾
          </span>
        </button>
        {isMoreOpen ? (
          <div className="nav-menu-panel" role="menu">
            {activeMoreLabel ? <p className="nav-menu-current">Aktivno: {activeMoreLabel}</p> : null}
            {MORE_PAGE_SECTIONS.map((section) => (
              <section className="nav-menu-section" key={section.label}>
                <p className="nav-menu-section-label">{section.label}</p>
                <div className="nav-menu-grid">
                  {section.pages.map((key) => (
                    <button
                      className={`nav-menu-item ${page === key ? "nav-menu-item-active" : ""}`}
                      key={key}
                      onClick={() => {
                        setPage(key);
                        setIsMoreOpen(false);
                      }}
                      role="menuitem"
                      type="button"
                    >
                      {PAGE_LABELS[key]}
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : null}
      </div>
    </>
  );

  return (
    <Layout
      eyebrow={status?.hostShellLabel ?? "Lokalni AI desktop shell"}
      nav={nav}
      subtitle={`Veb interfejs i lokalni backend za ${status?.hostPlatformLabel ?? "desktop"} okruženje.`}
      themeId={themeId}
      title={`Local AI Control Center${status?.version ? ` ${status.version}` : ""}`}
    >
      {page === "home" ? <HomePage /> : null}
      {page === "server" ? <ServerPage /> : null}
      {page === "fleet" ? <FleetPage /> : null}
      {page === "jobs" ? <JobsPage /> : null}
      {page === "workflows" ? (
        <WorkflowsPage
          onOpenBenchmark={() => setPage("benchmark")}
          onOpenKnowledge={() => setPage("knowledge")}
          onOpenSearch={() => setPage("search")}
        />
      ) : null}
      {page === "opencode" ? <OpenCodePage /> : null}
      {page === "models" ? (
        <ModelsPage
          onOpenCompatibilityTab={(target) => {
            setCompatibilityLaunchTarget(target);
            setPage("compatibility");
          }}
        />
      ) : null}
      {page === "browser" ? (
        <BrowserPage
          onOpenCompatibilityTab={(target) => {
            setCompatibilityLaunchTarget(target);
            setPage("compatibility");
          }}
        />
      ) : null}
      {page === "knowledge" ? <KnowledgePage onOpenSearch={() => setPage("search")} /> : null}
      {page === "search" ? <SearchPage onOpenSettings={() => setPage("settings")} /> : null}
      {page === "compatibility" ? (
        <CompatibilityPage
          launchTarget={compatibilityLaunchTarget}
          onOpenBrowser={() => setPage("browser")}
          onOpenModels={() => setPage("models")}
        />
      ) : null}
      {page === "observability" ? <ObservabilityPage /> : null}
      {page === "benchmark" ? <BenchmarkPage onOpenLogs={() => setPage("logs")} /> : null}
      {page === "settings" ? <SettingsPage /> : null}
      {page === "logs" ? <LogsPage /> : null}
      {page === "repair" ? <RepairPage /> : null}
      {page === "updates" ? <UpdatesPage /> : null}
    </Layout>
  );
}
