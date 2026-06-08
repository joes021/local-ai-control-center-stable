import { useEffect, useMemo, useRef, useState } from "react";

import { BrandLockup } from "./components/BrandLockup";
import { GuidedFlowPanel } from "./components/GuidedFlowPanel";
import { Layout } from "./components/Layout";
import type { RuntimePilotIconName } from "./components/RuntimePilotIcon";
import { RuntimePilotIcon } from "./components/RuntimePilotIcon";
import {
  fetchProjectMemory,
  fetchSettings,
  fetchStatus,
  primeModelsCache,
  primeServerStatusCache,
  primeSettingsCache,
} from "./lib/api";
import type { CompatibilityLaunchTarget } from "./lib/compatibility";
import { applyTheme, readStoredTheme, THEME_CHANGED_EVENT } from "./lib/theme";
import type { ProjectMemoryPayload, StatusPayload } from "./lib/types";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { BrowserPage } from "./pages/BrowserPage";
import { CompatibilityPage } from "./pages/CompatibilityPage";
import { FleetPage } from "./pages/FleetPage";
import { HomePage } from "./pages/HomePage";
import { HelpPage } from "./pages/HelpPage";
import { JobsPage } from "./pages/JobsPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { LogsPage } from "./pages/LogsPage";
import { ModelsPage } from "./pages/ModelsPage";
import { ObservabilityPage } from "./pages/ObservabilityPage";
import { OpenCodePage } from "./pages/OpenCodePage";
import { ProjectMemoryPage } from "./pages/ProjectMemoryPage";
import { RepairPage } from "./pages/RepairPage";
import { SearchPage } from "./pages/SearchPage";
import { ServerPage } from "./pages/ServerPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TuningLabPage } from "./pages/TuningLabPage";
import { UpdatesPage } from "./pages/UpdatesPage";
import { WorkflowsPage } from "./pages/WorkflowsPage";

const PAGE_META = {
  home: { label: "Početna", cue: "Pregled", icon: "home" },
  server: { label: "Runtime", cue: "Engine", icon: "server" },
  guidedFlow: { label: "Vodi me redom", cue: "Koraci", icon: "control" },
  fleet: { label: "Flota", cue: "Mašine", icon: "fleet" },
  jobs: { label: "Poslovi", cue: "Red", icon: "jobs" },
  workflows: { label: "Radni tokovi", cue: "Automatika", icon: "workflows" },
  opencode: { label: "OpenCode", cue: "Agent", icon: "opencode" },
  models: { label: "Modeli", cue: "Biblioteka", icon: "models" },
  browser: { label: "Browser", cue: "Katalog", icon: "browser" },
  knowledge: { label: "Znanje", cue: "Dokovi", icon: "knowledge" },
  search: { label: "Pretraga", cue: "Web + lokalno", icon: "search" },
  compatibility: { label: "Kompatibilnost", cue: "Fit", icon: "compatibility" },
  observability: { label: "Telemetrija", cue: "Signal", icon: "observability" },
  benchmark: { label: "Benchmark", cue: "Brzina", icon: "benchmark" },
  tuningLab: { label: "Tuning Lab", cue: "Parametri", icon: "tuning" },
  settings: { label: "Podešavanja", cue: "Kontrola", icon: "settings" },
  logs: { label: "Logovi", cue: "Tragovi", icon: "logs" },
  repair: { label: "Popravka", cue: "Oporavak", icon: "repair" },
  updates: { label: "Ažuriranja", cue: "Release", icon: "updates" },
  projectMemory: { label: "Project Memory", cue: "Fokus", icon: "memory" },
  help: { label: "Pomoć", cue: "Vodiči", icon: "help" },
} as const satisfies Record<string, { label: string; cue: string; icon: RuntimePilotIconName }>;

type PageKey = keyof typeof PAGE_META;

const PAGE_LABELS = Object.fromEntries(
  Object.entries(PAGE_META).map(([key, value]) => [key, value.label]),
) as Record<PageKey, string>;

const PRIMARY_PAGES: PageKey[] = ["home", "server", "models", "opencode"];
const GUIDED_FLOW_PAGE: PageKey = "guidedFlow";

const MORE_PAGE_SECTIONS: Array<{ label: string; pages: PageKey[] }> = [
  {
    label: "Analiza i alati",
    pages: ["browser", "knowledge", "compatibility", "benchmark", "observability", "tuningLab"],
  },
  {
    label: "Tokovi i automatizacija",
    pages: ["workflows", "jobs", "fleet"],
  },
  {
    label: "Održavanje",
    pages: ["logs", "repair", "updates"],
  },
  {
    label: "Fokus projekta",
    pages: ["projectMemory"],
  },
  {
    label: "Pomoć",
    pages: ["help"],
  },
];

const MORE_PAGES = MORE_PAGE_SECTIONS.flatMap((section) => section.pages);

const runtimePilotDeckTitle = "RuntimePilot Control Deck";
const runtimePilotDeckSummary =
  "Jedan komandni most za runtime, modele, OpenCode, telemetriju i tuning bez lutanja po zasebnim alatima.";
const STATUS_REFRESH_MS = 5000;
const PROJECT_MEMORY_REFRESH_MS = 8000;

export default function App() {
  const [page, setPage] = useState<PageKey>("home");
  const [settingsFocusSection, setSettingsFocusSection] = useState<string | null>(null);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [projectMemory, setProjectMemory] = useState<ProjectMemoryPayload | null>(null);
  const [projectMemoryLoading, setProjectMemoryLoading] = useState(true);
  const [projectMemoryError, setProjectMemoryError] = useState<string | null>(null);
  const [themeId, setThemeId] = useState<string>(readStoredTheme);
  const [compatibilityLaunchTarget, setCompatibilityLaunchTarget] =
    useState<CompatibilityLaunchTarget | null>(null);
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    applyTheme(readStoredTheme());
    const modelsWarmTimer = window.setTimeout(() => {
      void primeModelsCache().catch(() => null);
    }, 250);

    void primeServerStatusCache().catch(() => null);
    void primeSettingsCache().catch(() => null);

    const loadStatus = async () => {
      try {
        const payload = await fetchStatus();
        if (active) {
          setStatus(payload);
        }
      } catch {
        if (active) {
          setStatus(null);
        }
      }
    };

    void loadStatus();
    const statusTimer = window.setInterval(() => {
      void loadStatus();
    }, STATUS_REFRESH_MS);

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
      window.clearTimeout(modelsWarmTimer);
      window.clearInterval(statusTimer);
      window.removeEventListener(THEME_CHANGED_EVENT, handleThemeChanged as EventListener);
    };
  }, []);

  useEffect(() => {
    let active = true;

    const loadProjectMemory = async () => {
      try {
        const payload = await fetchProjectMemory();
        if (active) {
          setProjectMemory(payload);
          setProjectMemoryError(null);
          setProjectMemoryLoading(false);
        }
      } catch (error) {
        if (active) {
          setProjectMemoryError(
            error instanceof Error ? error.message : "Project Memory trenutno nije dostupan.",
          );
          setProjectMemoryLoading(false);
        }
      }
    };

    void loadProjectMemory();
    const memoryTimer = window.setInterval(() => {
      void loadProjectMemory();
    }, PROJECT_MEMORY_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(memoryTimer);
    };
  }, []);

  useEffect(() => {
    const versionSuffix = status?.version ? ` ${status.version}` : "";
    document.title = `RuntimePilot${versionSuffix}`;
  }, [status?.version]);

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

  const refreshProjectMemory = async () => {
    setProjectMemoryLoading(true);
    try {
      const payload = await fetchProjectMemory();
      setProjectMemory(payload);
      setProjectMemoryError(null);
    } catch (error) {
      setProjectMemoryError(
        error instanceof Error ? error.message : "Project Memory trenutno nije dostupan.",
      );
    } finally {
      setProjectMemoryLoading(false);
    }
  };

  const isMoreActive = MORE_PAGES.includes(page);

  const guidedFlowSteps = [
    {
      id: "runtime",
      title: "Runtime",
      detail:
        "Prvo proveri koji engine želiš da koristiš, da li je pokrenut i da li je spreman za sledeći rad.",
      status: page === "server" ? "Trenutno otvoreno" : "Korak 1",
      tone: page === "server" ? "active" : "ready",
      actionLabel: "Otvori Runtime",
      onAction: () => setPage("server"),
    },
    {
      id: "local-model",
      title: "Lokalni model",
      detail:
        "Zatim izaberi ili zameni lokalni model, proveri da li staje i sačuvaj izbor koji želiš da koristiš.",
      status: page === "models" ? "Trenutno otvoreno" : "Korak 2",
      tone: page === "models" ? "active" : "ready",
      actionLabel: "Otvori Modele",
      onAction: () => setPage("models"),
    },
    {
      id: "opencode",
      title: "OpenCode",
      detail:
        "Na kraju otvori OpenCode sesiju i kreni na konkretan rad, task ili rezultat koristeći već pripremljen runtime i model.",
      status: page === "opencode" ? "Trenutno otvoreno" : "Korak 3",
      tone: page === "opencode" ? "active" : "ready",
      actionLabel: "Otvori OpenCode",
      onAction: () => setPage("opencode"),
    },
  ] as const;

  const activeMoreLabel = useMemo(() => {
    if (!isMoreActive) {
      return null;
    }
    return PAGE_LABELS[page];
  }, [isMoreActive, page]);

  const activeModelName =
    status?.activeModel && status.activeModel.trim() && status.activeModel.trim() !== "--"
      ? status.activeModel.trim()
      : "Nema aktivnog modela";
  const runtimeLabel = status?.activeRuntimeLabel || status?.requestedRuntimeLabel || "Runtime nije poznat";
  const runtimeStateLabel =
    status?.runtimeLiveStatus === "started"
      ? "Runtime aktivan"
      : status?.runtimeLiveStatus === "stopped"
        ? "Runtime nije pokrenut"
        : "Čeka runtime";
  const runtimeStateSummary =
    status?.runtimeLiveReason || status?.runtimeSummary || "Model je izabran, ali runtime još nije prijavio jasno stanje.";

  const activeModelStrip = (
    <section
      className="runtimepilot-status-rail runtimepilot-utility-module runtimepilot-active-model-strip"
      aria-label="Aktivni model"
    >
      <div className="runtimepilot-active-model-layout">
        <div className="runtimepilot-active-model-primary">
          <div className="runtimepilot-utility-label">
            <span className="runtimepilot-active-model-glyph" aria-hidden="true">
              <RuntimePilotIcon className="runtimepilot-active-model-icon" name="models" />
            </span>
            <span className="status-label">Aktivni model</span>
          </div>
          <strong className="runtimepilot-utility-title runtimepilot-active-model-value" title={activeModelName}>
            {activeModelName}
          </strong>
        </div>
        <div className="runtimepilot-active-model-status runtimepilot-active-model-meta">
          <span className="runtimepilot-active-model-chip" title={runtimeLabel}>
            Runtime · {runtimeLabel}
          </span>
          <span className="runtimepilot-active-model-chip" title={runtimeStateSummary}>
            Status · {runtimeStateLabel}
          </span>
        </div>
        <button
          type="button"
          className="runtimepilot-status-rail-action runtimepilot-active-model-open"
          onClick={() => setPage("models")}
        >
          Otvori modele
        </button>
      </div>
      <p className="runtimepilot-utility-inline runtimepilot-active-model-summary" title={runtimeStateSummary}>
        {runtimeStateSummary}
      </p>
    </section>
  );

  const nav = (
    <>
      <div className="runtimepilot-primary-flows">
        <div className="top-nav-primary">
          {PRIMARY_PAGES.map((key) => (
            <button
              className={`nav-button ${page === key ? "nav-button-active" : ""}`}
              key={key}
              onClick={() => setPage(key)}
              type="button"
            >
              <span className="runtimepilot-nav-button-glyph">
                <RuntimePilotIcon className="runtimepilot-nav-icon" name={PAGE_META[key].icon} />
              </span>
              <span className="runtimepilot-nav-button-copy">
                <span className="runtimepilot-nav-button-label">{PAGE_META[key].label}</span>
                <span className="runtimepilot-nav-button-cue">{PAGE_META[key].cue}</span>
              </span>
            </button>
          ))}
        </div>
        <button
          className={`nav-button nav-button-guided ${page === GUIDED_FLOW_PAGE ? "nav-button-active" : ""}`}
          onClick={() => setPage(GUIDED_FLOW_PAGE)}
          type="button"
        >
          <span className="runtimepilot-nav-button-glyph">
            <RuntimePilotIcon className="runtimepilot-nav-icon" name={PAGE_META.guidedFlow.icon} />
          </span>
          <span className="runtimepilot-nav-button-copy">
            <span className="runtimepilot-nav-button-label">{PAGE_META.guidedFlow.label}</span>
            <span className="runtimepilot-nav-button-cue">{PAGE_META.guidedFlow.cue}</span>
          </span>
        </button>
      </div>
      <div className="nav-more-shell" ref={moreMenuRef}>
        <button
          aria-expanded={isMoreOpen ? "true" : "false"}
          aria-haspopup="menu"
          className={`nav-button nav-more-button ${isMoreOpen || isMoreActive ? "nav-button-active" : ""}`}
          onClick={() => setIsMoreOpen((current) => !current)}
          type="button"
        >
          <span className="runtimepilot-nav-button-glyph">
            <RuntimePilotIcon className="runtimepilot-nav-icon" name="control" />
          </span>
          <span className="runtimepilot-nav-button-copy">
            <span className="runtimepilot-nav-button-label">Više</span>
            <span className="runtimepilot-nav-button-cue">{activeMoreLabel ?? "Analiza + alati"}</span>
          </span>
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
                      <span className="runtimepilot-nav-menu-glyph">
                        <RuntimePilotIcon className="runtimepilot-nav-menu-icon" name={PAGE_META[key].icon} />
                      </span>
                      <span className="runtimepilot-nav-menu-copy">
                        <span className="runtimepilot-nav-menu-label">{PAGE_META[key].label}</span>
                        <span className="runtimepilot-nav-menu-cue">{PAGE_META[key].cue}</span>
                      </span>
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
      brand={<BrandLockup />}
      deckSummary={runtimePilotDeckSummary}
      deckTitle={runtimePilotDeckTitle}
      eyebrow={
        <>
          <span>LOCAL AI RUNTIME CONTROL CENTER</span>
          {status?.version ? <span className="runtimepilot-hero-version">v{status.version}</span> : null}
        </>
      }
      nav={nav}
      activeModelStrip={activeModelStrip}
      subtitle={
        <>
          <strong>Control. Monitor. Optimize.</strong>
          <br />
          Everything running locally. Under your command.
        </>
      }
      themeId={themeId}
      title={`RuntimePilot${status?.version ? ` ${status.version}` : ""}`}
      onOpenSettingsSection={(sectionId) => {
        setSettingsFocusSection(sectionId);
        setPage("settings");
      }}
    >
      {page === "home" ? (
        <HomePage
          onOpenBenchmark={() => setPage("benchmark")}
          onOpenCompatibility={() => setPage("compatibility")}
          onOpenModels={() => setPage("models")}
          onOpenOpenCode={() => setPage("opencode")}
          onOpenProjectMemory={() => setPage("projectMemory")}
          onOpenServer={() => setPage("server")}
          onOpenTuningLab={() => setPage("tuningLab")}
          onStartGuidedFlow={() => setPage("guidedFlow")}
        />
      ) : null}
      {page === "guidedFlow" ? (
        <GuidedFlowPanel
          title="Vodi me redom"
          summary="Ako ne želiš da razmišljaš gde prvo treba da klikneš, prati ovaj tok: runtime, zatim lokalni model, pa tek onda OpenCode rad."
          steps={guidedFlowSteps}
        />
      ) : null}
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
      {page === "benchmark" ? (
        <BenchmarkPage
          onOpenLogs={() => setPage("logs")}
          onOpenTuningLab={() => setPage("tuningLab")}
        />
      ) : null}
      {page === "tuningLab" ? <TuningLabPage /> : null}
      {page === "projectMemory" ? (
        <ProjectMemoryPage
          memory={projectMemory}
          loading={projectMemoryLoading}
          error={projectMemoryError}
          onMemoryChange={setProjectMemory}
          onRefresh={refreshProjectMemory}
          onOpenTuningLab={() => setPage("tuningLab")}
        />
      ) : null}
      {page === "settings" ? (
        <SettingsPage
          focusSectionId={settingsFocusSection}
          onFocusHandled={() => setSettingsFocusSection(null)}
        />
      ) : null}
      {page === "logs" ? <LogsPage /> : null}
      {page === "repair" ? <RepairPage /> : null}
      {page === "updates" ? <UpdatesPage /> : null}
      {page === "help" ? (
        <HelpPage
          onOpenBenchmark={() => setPage("benchmark")}
          onOpenModels={() => setPage("models")}
          onOpenOpenCode={() => setPage("opencode")}
          onOpenSearch={() => setPage("search")}
          onOpenServer={() => setPage("server")}
          onOpenSettings={() => setPage("settings")}
          onOpenTuningLab={() => setPage("tuningLab")}
        />
      ) : null}
    </Layout>
  );
}
