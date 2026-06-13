import { useEffect, useState } from "react";

import { TelemetryPanel } from "../components/TelemetryPanel";
import { HomeStatusDeck } from "../components/shell/HomeStatusDeck";
import {
  fetchBenchmark,
  fetchOpenCodeStatus,
  fetchServerStatus,
  fetchStatus,
} from "../lib/api";
import type {
  BenchmarkPayload,
  OpenCodeStatusPayload,
  ServerStatusPayload,
  StatusPayload,
} from "../lib/types";

const GENERAL_REFRESH_MS = 5000;
const BENCHMARK_REALTIME_REFRESH_MS = 1000;

function renderOpenCodeState(opencode: OpenCodeStatusPayload | null) {
  if (!opencode?.available) {
    return "Nedostupan";
  }
  if (opencode.sessionState === "launching") {
    return "Pokretanje u toku";
  }
  if (opencode.sessionState === "connected") {
    return "Aktivan";
  }
  if (opencode.sessionState === "app-only") {
    return "Otvoren bez backend veze";
  }
  if (opencode.sessionState === "runtime-ready") {
    return "Spreman";
  }
  return "Dostupan";
}

function formatContextCompact(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  if (value >= 1000) {
    return `${Math.round(value / 1024)}K`;
  }
  return String(Math.round(value));
}

function summarizeModelName(modelName: string) {
  if (!modelName || modelName === "Nema aktivnog modela") {
    return modelName;
  }

  const compactMatch = modelName.match(/([A-Za-z][A-Za-z0-9.+-]*)[^0-9]*(\d+(?:\.\d+)?B)/i);
  if (compactMatch) {
    return `${compactMatch[1].replace(/[-_.]+/g, " ")} ${compactMatch[2]}`.trim();
  }

  const stripped = modelName.replace(/\.gguf$/i, "");
  return stripped.length > 28 ? `${stripped.slice(0, 28)}...` : stripped;
}

export function HomePage({
  onOpenModels,
  onOpenOpenCode,
  onOpenServer,
  onOpenSettingsContext,
}: {
  onOpenModels?: () => void;
  onOpenOpenCode?: () => void;
  onOpenServer?: () => void;
  onOpenSettingsContext?: () => void;
}) {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [serverStatus, setServerStatus] = useState<ServerStatusPayload | null>(null);
  const [opencode, setOpencode] = useState<OpenCodeStatusPayload | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadStatus() {
    try {
      const [statusPayload, serverPayload, opencodePayload] = await Promise.all([
        fetchStatus(),
        fetchServerStatus(),
        fetchOpenCodeStatus(),
      ]);
      setStatus(statusPayload);
      setServerStatus(serverPayload);
      setOpencode(opencodePayload);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    }
  }

  async function loadBenchmarkOnly() {
    try {
      const benchmarkPayload = await fetchBenchmark();
      setBenchmark(benchmarkPayload);
    } catch {
      setBenchmark(null);
    }
  }

  useEffect(() => {
    let active = true;
    void loadStatus();
    void loadBenchmarkOnly();

    const timer = window.setInterval(() => {
      if (active) {
        void loadStatus();
      }
    }, GENERAL_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let active = true;

    const timer = window.setInterval(() => {
      if (active) {
        void loadBenchmarkOnly();
      }
    }, BENCHMARK_REALTIME_REFRESH_MS);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const runtimeStateTitle =
    status?.activeRuntimeLabel || serverStatus?.activeRuntimeLabel || "Runtime nije izabran";
  const runtimeHealthShort = serverStatus?.health || status?.health || "--";
  const runtimeHealthReason =
    serverStatus?.healthReason ||
    status?.runtimeLiveReason ||
    "Brzi signal prvo potvrđuje da li je runtime zaista zdrav.";
  const runtimeStateSummary =
    status?.runtimeSummary ||
    serverStatus?.lastReason ||
    "Otvorena runtime strana pokazuje health, pristup i dijagnostiku bez dodatnog traženja.";

  const modelStateTitle =
    status?.activeModel && status.activeModel.trim() && status.activeModel.trim() !== "--"
      ? status.activeModel.trim()
      : "Nema aktivnog modela";
  const modelStateSummary =
    modelStateTitle === "Nema aktivnog modela"
      ? "Otvori modele i zaključaј lokalni GGUF pre nego što kreneš u rad."
      : `Profil ${status?.profile || "--"} i runtime ${status?.activeRuntimeLabel || "--"} su već aktivni.`;
  const compactModelName = summarizeModelName(modelStateTitle);

  const contextValue = formatContextCompact(
    serverStatus?.runtimeDiagnostics?.effectiveProcessContext ??
      serverStatus?.runtimeDiagnostics?.configuredContext,
  );
  const contextLabel = serverStatus?.runtimeDiagnostics?.contextAlignmentLabel || "Podešen";
  const contextSummary =
    serverStatus?.runtimeDiagnostics?.contextAlignmentSummary ||
    "Otvaranjem context podešavanja odmah proveravaš šta runtime stvarno koristi.";

  const openCodeStateTitle = renderOpenCodeState(opencode);
  const openCodeStateSummary =
    opencode?.sessionSummary ||
    "Kad su runtime i model zdravi, ovde prelaziš na task, sesiju i rezultat.";
  const openCodeBackend = opencode?.runtimeConnected ? "Backend vezan" : "Čeka backend";

  const homeStatusItems = [
    {
      label: "Health" as const,
      value: runtimeHealthShort,
      detail: runtimeHealthReason,
      onClick: () => onOpenServer?.(),
    },
    {
      label: "Runtime" as const,
      value: runtimeStateTitle,
      detail: runtimeStateSummary,
      onClick: () => onOpenServer?.(),
    },
    {
      label: "Model" as const,
      value: compactModelName,
      detail: `Brzi signal modela: ${modelStateSummary}`,
      onClick: () => onOpenModels?.(),
    },
    {
      label: "Context" as const,
      value: contextValue,
      detail: `${contextLabel} · ${contextSummary}`,
      onClick: () => onOpenSettingsContext?.(),
    },
    {
      label: "OpenCode" as const,
      value: openCodeStateTitle,
      detail: `${openCodeBackend} · ${openCodeStateSummary}`,
      onClick: () => onOpenOpenCode?.(),
    },
  ];

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <HomeStatusDeck items={homeStatusItems} />
      <TelemetryPanel benchmark={benchmark} variant="home" />
    </>
  );
}
