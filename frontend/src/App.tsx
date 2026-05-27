import { useEffect, useState } from "react";

import { Layout } from "./components/Layout";
import { fetchSettings, fetchStatus } from "./lib/api";
import { applyTheme, readStoredTheme, THEME_CHANGED_EVENT } from "./lib/theme";
import type { CompatibilityLaunchTarget } from "./lib/compatibility";
import type { StatusPayload } from "./lib/types";
import { BrowserPage } from "./pages/BrowserPage";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { FleetPage } from "./pages/FleetPage";
import { HomePage } from "./pages/HomePage";
import { JobsPage } from "./pages/JobsPage";
import { LogsPage } from "./pages/LogsPage";
import { ModelsPage } from "./pages/ModelsPage";
import { ObservabilityPage } from "./pages/ObservabilityPage";
import { OpenCodePage } from "./pages/OpenCodePage";
import { CompatibilityPage } from "./pages/CompatibilityPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { RepairPage } from "./pages/RepairPage";
import { SearchPage } from "./pages/SearchPage";
import { ServerPage } from "./pages/ServerPage";
import { SettingsPage } from "./pages/SettingsPage";
import { UpdatesPage } from "./pages/UpdatesPage";
import { WorkflowsPage } from "./pages/WorkflowsPage";

const PAGES = {
  home: "Home",
  server: "Server",
  fleet: "Fleet",
  jobs: "Jobs",
  workflows: "Workflows",
  opencode: "OpenCode",
  models: "Models",
  browser: "Browser",
  knowledge: "Knowledge",
  search: "Search",
  compatibility: "Compatibility",
  observability: "Observability",
  benchmark: "Benchmark",
  settings: "Settings",
  logs: "Logs",
  repair: "Repair",
  updates: "Updates",
} as const;

type PageKey = keyof typeof PAGES;

export default function App() {
  const [page, setPage] = useState<PageKey>("home");
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [themeId, setThemeId] = useState<string>(readStoredTheme);
  const [compatibilityLaunchTarget, setCompatibilityLaunchTarget] =
    useState<CompatibilityLaunchTarget | null>(null);

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

  const nav = (
    <>
      {Object.entries(PAGES).map(([key, label]) => (
        <button
          className={`nav-button ${page === key ? "nav-button-active" : ""}`}
          key={key}
          onClick={() => setPage(key as PageKey)}
          type="button"
        >
          {label}
        </button>
      ))}
    </>
  );

  return (
    <Layout
      title={`Local AI Control Center${status?.version ? ` ${status.version}` : ""}`}
      eyebrow={status?.hostShellLabel ?? "Local AI Desktop GUI Shell"}
      subtitle={`Web UI + lokalni backend pravac za ${status?.hostPlatformLabel ?? "desktop"}.`}
      nav={nav}
      themeId={themeId}
    >
      {page === "home" ? <HomePage /> : null}
      {page === "server" ? <ServerPage /> : null}
      {page === "fleet" ? <FleetPage /> : null}
      {page === "jobs" ? <JobsPage /> : null}
      {page === "workflows" ? (
        <WorkflowsPage
          onOpenSearch={() => setPage("search")}
          onOpenKnowledge={() => setPage("knowledge")}
          onOpenBenchmark={() => setPage("benchmark")}
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
          onOpenModels={() => setPage("models")}
          onOpenBrowser={() => setPage("browser")}
          launchTarget={compatibilityLaunchTarget}
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
