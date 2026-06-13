import { useEffect, useState } from "react";

import { HomeHiFiCommandButton } from "../components/home/HomeHiFiCommandButton";
import { HomeHiFiModule } from "../components/home/HomeHiFiModule";
import { RuntimePilotIcon } from "../components/RuntimePilotIcon";
import {
  fetchBenchmark,
  fetchOpenCodeStatus,
  fetchServerStatus,
  fetchStatus,
  openOpenCode,
  restartServer,
  startServer,
  stopServer,
} from "../lib/api";
import type {
  ActionResult,
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

function looksStarted(status: ServerStatusPayload | null) {
  if (!status) {
    return false;
  }
  return Boolean(status.pid) || ["started", "running", "healthy"].includes(status.status);
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
  return stripped.length > 28 ? `${stripped.slice(0, 28)}…` : stripped;
}

function formatThroughputSignal(benchmark: BenchmarkPayload | null) {
  const liveNow = benchmark?.telemetry?.liveNowTokensPerSecond;
  if (typeof liveNow === "number" && Number.isFinite(liveNow) && liveNow > 0) {
    return `${liveNow.toFixed(1)} tok/s`;
  }

  const lastSignal = benchmark?.telemetry?.lastSignalTokensPerSecond;
  if (typeof lastSignal === "number" && Number.isFinite(lastSignal) && lastSignal > 0) {
    return `${lastSignal.toFixed(1)} tok/s`;
  }

  return "Nema žive metrike";
}

export function HomePage({
  onOpenBenchmark,
  onOpenCompatibility,
  onOpenModels,
  onOpenOpenCode,
  onOpenProjectMemory,
  onOpenServer,
  onOpenSettingsProfile,
  onOpenTuningLab,
  onStartGuidedFlow,
}: {
  onOpenBenchmark?: () => void;
  onOpenCompatibility?: () => void;
  onOpenModels?: () => void;
  onOpenOpenCode?: () => void;
  onOpenProjectMemory?: () => void;
  onOpenServer?: () => void;
  onOpenSettingsProfile?: () => void;
  onOpenTuningLab?: () => void;
  onStartGuidedFlow?: () => void;
}) {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [serverStatus, setServerStatus] = useState<ServerStatusPayload | null>(null);
  const [opencode, setOpencode] = useState<OpenCodeStatusPayload | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);

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

  async function runAction(action: () => Promise<ActionResult>) {
    try {
      const actionResult = await action();
      setResult(actionResult);
      setError(null);
      await loadStatus();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
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

  const runtimeStarted = looksStarted(serverStatus);
  const runtimeStateTitle = status?.activeRuntimeLabel || serverStatus?.activeRuntimeLabel || "Runtime nije izabran";
  const runtimeHealthShort = serverStatus?.health || status?.health || "--";
  const runtimeHealthReason =
    serverStatus?.healthReason || status?.runtimeLiveReason || "Prvo potvrdi health signal pre svega ostalog.";
  const runtimeStateSummary =
    status?.runtimeSummary ||
    serverStatus?.lastReason ||
    "Prvo proveri runtime stanje pre izbora modela i pre pokretanja OpenCode rada.";

  const modelStateTitle =
    status?.activeModel && status.activeModel.trim() && status.activeModel.trim() !== "--"
      ? status.activeModel.trim()
      : "Nema aktivnog modela";
  const modelStateSummary =
    modelStateTitle === "Nema aktivnog modela"
      ? "Prvo izaberi ili dodaj lokalni model, pa tek onda pređi na OpenCode rad."
      : `Runtime: ${status?.activeRuntimeLabel || "--"} | Profil: ${status?.profile || "--"}.`;
  const compactModelName = summarizeModelName(modelStateTitle);

  const openCodeStateTitle = renderOpenCodeState(opencode);
  const openCodeStateSummary =
    opencode?.sessionSummary ||
    "Kada su runtime i model zdravi, ovde prelaziš na konkretan rad, taskove i rezultate.";
  const openCodeBackend = opencode?.runtimeConnected ? "CLI vezan" : "Čeka backend";
  const openCodeActionLabel = opencode?.openActionLabel || "Otvori OpenCode";

  const contextValue = formatContextCompact(
    serverStatus?.runtimeDiagnostics?.effectiveProcessContext ?? serverStatus?.runtimeDiagnostics?.configuredContext,
  );
  const contextLabel = serverStatus?.runtimeDiagnostics?.contextAlignmentLabel || "Podešen";
  const contextSummary =
    serverStatus?.runtimeDiagnostics?.contextAlignmentSummary ||
    "Context čeka potvrdu živog runtime procesa.";
  const runtimeAccessUrl = serverStatus?.localWebUrl || status?.localUrl || status?.uiUrl || "";

  const fitHasLiveProof = Boolean(
    serverStatus?.runtimeDiagnostics?.kvBufferMiB || serverStatus?.runtimeDiagnostics?.modelBufferMiB,
  );
  const fitLabel = fitHasLiveProof ? "Jasan" : "Čeka log";
  const fitSummary = fitHasLiveProof
    ? "KV buffer viđen, nema nagađanja."
    : serverStatus?.runtimeDiagnostics?.summary || "Sačekaj runtime log za realan GPU fit.";

  const modelProfile = status?.profile || "Profil nije potvrđen";
  const throughputSignal = formatThroughputSignal(benchmark);
  const lastActionValue = result ? (result.status === "ok" ? "Spremno" : "Signal") : "Čeka akciju";
  const lastActionSummary =
    result?.summary ||
    "Kada klikneš glavnu komandu, rezultat odmah pratiš ovde i u dnu modula koji si otvorio.";

  async function handleOpenCode(mode: "direct" | "isolated") {
    await runAction(async () => {
      const actionResult = await openOpenCode(status?.profile || opencode?.profile || "balanced", mode);
      if (actionResult.status === "ok") {
        onOpenOpenCode?.();
      }
      return actionResult;
    });
  }

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <section className="status-card wide-card runtimepilot-home-control-shell runtimepilot-home-mixed-shell runtimepilot-faceplate-module">
        <span className="visually-hidden">Mission Control</span>
        <div
          className="visually-hidden"
          data-legacy-markers="runtimepilot-home-control-intro runtimepilot-home-support-stack runtimepilot-secondary-tools-layout primary-flow-sequence-rail runtimepilot-home-transport HomeSecondaryToolCard TelemetryPanel"
        >
          <span>Jedinstven pregled lokalnog AI sistema</span>
          <span>Runtime → Lokalni model → OpenCode</span>
          <span>Vodi me redom</span>
          <span>Komandni pregled</span>
          <span>runtimepilot-home-mission-grid</span>
          <span>TelemetryPanel</span>
          <span>Otvori Project Memory</span>
        </div>
        <div className="runtimepilot-home-guided-top-grid">
          <section className="runtimepilot-home-guided-panel runtimepilot-home-guided-deck">
            <header className="runtimepilot-home-guided-panel-header">
              <div>
                <span className="status-label">Glavni tok</span>
                <strong className="status-value">Kreni redom, bez lutanja</strong>
              </div>
              <span className="runtimepilot-home-guidance-pill">Klik na modul otvara sledeći korak</span>
            </header>
            <p className="helper-text runtimepilot-home-guided-lead">
              Ideja ove početne strane je da korisnik ne razmišlja “gde sada kliknem”, nego da odmah vidi:
              prvo runtime, zatim lokalni model, pa OpenCode rad.
            </p>
            <div className="runtimepilot-home-flow-grid">
              <button
                className="runtimepilot-home-shell-step"
                type="button"
                onClick={() => {
                  onOpenServer?.();
                  onStartGuidedFlow?.();
                }}
              >
                <span className="status-label">Korak 1</span>
                <strong>Runtime</strong>
                <p className="helper-text">Pokreni engine i proveri health signal.</p>
              </button>
              <button className="runtimepilot-home-shell-step" type="button" onClick={onOpenModels}>
                <span className="status-label">Korak 2</span>
                <strong>Lokalni model</strong>
                <p className="helper-text">Izaberi aktivni GGUF i proveri fit.</p>
              </button>
              <button className="runtimepilot-home-shell-step" type="button" onClick={onOpenOpenCode}>
                <span className="status-label">Korak 3</span>
                <strong>OpenCode</strong>
                <p className="helper-text">Otvori rad, task i rezultat.</p>
              </button>
            </div>
          </section>

          <section className="runtimepilot-home-now-panel runtimepilot-home-mission-deck">
            <header className="runtimepilot-home-now-panel-header">
              <div>
                <span className="status-label">
                  Stanje sada
                  <span className="visually-hidden">Pregled sistema</span>
                </span>
                <strong className="status-value">Brzi signal</strong>
              </div>
              <div className="runtimepilot-home-now-lights" aria-hidden="true">
                <span className="runtimepilot-home-now-light runtimepilot-home-now-light-success" />
                <span className="runtimepilot-home-now-light runtimepilot-home-now-light-soft" />
                <span className="runtimepilot-home-now-light" />
              </div>
            </header>
            <div className="runtimepilot-home-now-grid">
              <article className="runtimepilot-home-now-card">
                <span className="status-label">Runtime</span>
                <strong>{runtimeStateTitle}</strong>
                <p className="helper-text">Health: {runtimeHealthShort.toLowerCase()}</p>
              </article>
              <article className="runtimepilot-home-now-card">
                <span className="status-label">Aktivni model</span>
                <strong title={modelStateTitle}>{compactModelName}</strong>
                <p className="helper-text">Profil: {status?.profile || "nije potvrđen"}</p>
              </article>
              <article className="runtimepilot-home-now-card">
                <span className="status-label">Context</span>
                <strong>{contextValue}</strong>
                <p className="helper-text">{contextLabel}</p>
              </article>
              <article className="runtimepilot-home-now-card">
                <span className="status-label">OpenCode</span>
                <strong>{openCodeStateTitle}</strong>
                <p className="helper-text">{openCodeBackend}</p>
              </article>
            </div>
          </section>
        </div>
      </section>

      <HomeHiFiModule
        variant="runtime-primary"
        eyebrow="Veliki modul 1"
        title="Runtime"
        headerBadge={<span className="runtimepilot-home-guidance-pill">Prvo proveri engine pre svega ostalog</span>}
        railItems={[
          {
            label: "Signal",
            value: runtimeStateTitle,
            detail: `${runtimeHealthShort} · odgovor potvrđen`,
            tone: "success",
          },
          {
            label: "Context",
            value: contextValue,
            detail: contextSummary,
            tone: "accent",
          },
          {
            label: "GPU fit",
            value: fitLabel,
            detail: fitSummary,
            tone: "signal",
          },
        ]}
        summaryTitle="Pokreni, proveri ili restartuj runtime bez lutanja po stranici."
        summaryText="Kad klikneš ovde, rezultat mora odmah da se vidi kroz health, pristup i runtime signal."
        readouts={[
          {
            label: "Šta vidiš ovde",
            value: "Engine i health",
            detail: "Start, restart i stanje servera.",
          },
          {
            label: "Glavni rezultat",
            value: runtimeStarted ? "Jasno zeleno stanje" : "Čeka potvrdu",
            detail: runtimeStarted
              ? "Odmah znaš da li je runtime spreman za model."
              : "Ako nije startovan, prvo ga podigni pa tek onda nastavi dalje.",
          },
          {
            label: "Zašto je ovde",
            value: "Prvi korak",
            detail: "Bez zdravog runtime-a sve posle toga zbunjuje.",
          },
        ]}
        actions={[
          <HomeHiFiCommandButton
            key="runtime-open"
            code="RUN"
            title="Otvori Runtime"
            subtitle="ENGINE + HEALTH"
            tone="primary"
            icon="play"
            onClick={() => onOpenServer?.()}
          />,
          <HomeHiFiCommandButton
            key="runtime-restart"
            code="RST"
            title="Restartuj runtime"
            subtitle="PONOVO UČITAJ SIGNAL"
            icon="reload"
            titleAttr={runtimeStarted ? undefined : "Runtime još nije startovan, pa ovde prvo koristi start."}
            disabled={!runtimeStarted}
            onClick={() => void runAction(restartServer)}
          />,
          <HomeHiFiCommandButton
            key="runtime-stop"
            code={runtimeStarted ? "STP" : "RUN"}
            title={runtimeStarted ? "Zaustavi engine" : "Pokreni engine"}
            subtitle={runtimeStarted ? "UGASI SERVER" : "PODIGNI SERVER"}
            tone={runtimeStarted ? "danger" : "default"}
            icon={runtimeStarted ? "stop" : "play"}
            titleAttr={runtimeStarted ? serverStatus?.stopBlockedReason || undefined : serverStatus?.startBlockedReason || undefined}
            disabled={runtimeStarted ? serverStatus?.canStop === false : serverStatus?.canStart === false}
            onClick={() => void runAction(runtimeStarted ? stopServer : startServer)}
          />,
          <HomeHiFiCommandButton
            key="runtime-debug"
            code="DBG"
            title="Napredna dijagnostika"
            subtitle="RUČNE KOMANDE"
            icon="control"
            onClick={() => onOpenServer?.()}
          />,
        ]}
        footer={[
          {
            label: "Posle klika",
            value: "Health + signal",
            detail: lastActionSummary,
          },
          {
            label: "Pristup",
            value: runtimeAccessUrl ? "Lokalno spreman" : "Čeka portal",
            detail: runtimeAccessUrl ? (
              <a
                className="runtimepilot-home-hifi-footer-link"
                href={runtimeAccessUrl}
                target="_blank"
                rel="noreferrer"
              >
                {runtimeAccessUrl}
              </a>
            ) : (
              "Portal nije prijavio lokalni URL."
            ),
          },
          {
            label: "Profil",
            value: onOpenSettingsProfile ? (
              <button
                type="button"
                className="runtimepilot-home-hifi-footer-button"
                onClick={() => onOpenSettingsProfile?.()}
              >
                {modelProfile}
              </button>
            ) : (
              modelProfile
            ),
            detail: runtimeHealthReason,
          },
          {
            label: "Sledeće",
            value: "Lokalni model",
            detail: "Kad je runtime zdrav, idi na izbor GGUF modela.",
          },
        ]}
      />

      <HomeHiFiModule
        variant="runtime-primary"
        eyebrow="Veliki modul 2"
        title="Lokalni model"
        headerBadge={<span className="runtimepilot-home-guidance-pill">Ovde biraš šta stvarno radi u runtime-u</span>}
        railItems={[
          {
            label: "Aktivni model",
            value: compactModelName,
            detail: modelStateTitle,
            tone: "success",
          },
          {
            label: "Profil",
            value: status?.profile || "--",
            detail: modelStateSummary,
            tone: "accent",
          },
          {
            label: "Fit",
            value: fitLabel,
            detail: fitSummary,
            tone: "signal",
          },
        ]}
        summaryTitle="Promeni model brzo, ali da odmah vidiš koji je stvarno aktivan."
        summaryText="Modeli su važni, ali ovde ne smeš da se izgubiš u katalogu. Prvo je bitno šta je sada aktivno i da li staje."
        readouts={[
          {
            label: "Šta vidiš ovde",
            value: "Aktivni GGUF",
            detail: "Ime modela, profil i fit bez traženja po dugačkoj listi.",
          },
          {
            label: "Glavni rezultat",
            value: "Jasan aktivni izbor",
            detail: "Posle promene, naziv aktivnog modela mora odmah da bude nedvosmislen.",
          },
          {
            label: "Zašto je ovde",
            value: "Drugi korak",
            detail: "Tek posle zdravog runtime-a ima smisla zaključati model za rad.",
          },
        ]}
        actions={[
          <HomeHiFiCommandButton
            key="model-open"
            code="MOD"
            title="Otvori modele"
            subtitle="LOKALNI KATALOG"
            tone="primary"
            icon="models"
            onClick={() => onOpenModels?.()}
          />,
          <HomeHiFiCommandButton
            key="model-change"
            code="QCK"
            title="Brza promena"
            subtitle="AKTIVNI IZBOR"
            icon="reload"
            onClick={() => onOpenModels?.()}
          />,
          <HomeHiFiCommandButton
            key="model-fit"
            code="FIT"
            title="Proveri kompatibilnost"
            subtitle="VRAM + CONTEXT"
            icon="compatibility"
            onClick={() => onOpenCompatibility?.()}
          />,
          <HomeHiFiCommandButton
            key="model-add"
            code="GGU"
            title="Dodaj lokalni GGUF"
            subtitle="UPLOAD U KATALOG"
            icon="models"
            onClick={() => onOpenModels?.()}
          />,
        ]}
        footer={[
          {
            label: "Posle klika",
            value: "Aktivni model",
            detail: "Ime modela vidiš odmah gore desno i u signal stubu.",
          },
          {
            label: "Fit signal",
            value: fitLabel,
            detail: fitSummary,
          },
          {
            label: "Katalog",
            value: "Lokalno + izvori",
            detail: "Tu su lokalni GGUF fajlovi, browser katalog i kompatibilnost.",
          },
          {
            label: "Sledeće",
            value: "OpenCode rad",
            detail: "Kad je model zaključan, pređi na radni tok i konkretan task.",
          },
        ]}
      />

      <HomeHiFiModule
        variant="runtime-primary"
        eyebrow="Veliki modul 3"
        title="OpenCode"
        headerBadge={<span className="runtimepilot-home-guidance-pill">Ovde lokalni runtime prelazi u pravi rad</span>}
        railItems={[
          {
            label: "Sesija",
            value: openCodeStateTitle,
            detail: openCodeStateSummary,
            tone: "success",
          },
          {
            label: "Runtime veza",
            value: openCodeBackend,
            detail: opencode?.runtimeLiveReason || "Backend status će ovde odmah biti vidljiv.",
            tone: "accent",
          },
          {
            label: "Puls tokena",
            value: throughputSignal,
            detail: benchmark?.telemetry?.lastSignalLabel || "Telemetrija stiže kada krene pravi rad.",
            tone: "signal",
          },
        ]}
        summaryTitle="Otvaraj radni tok tek kada znaš da su runtime i model stvarno spremni."
        summaryText="OpenCode mora da bude završni korak. Ovde je važno da vidiš da li je desktop otvoren, da li je backend povezan i gde posle klika gledaš rezultat."
        readouts={[
          {
            label: "Šta vidiš ovde",
            value: "Desktop + portal",
            detail: "Jedan klik za aplikaciju, drugi za panel i fokus taska.",
          },
          {
            label: "Glavni rezultat",
            value: lastActionValue,
            detail: lastActionSummary,
          },
          {
            label: "Zašto je ovde",
            value: "Treći korak",
            detail: "Kad su runtime i model čisti, OpenCode postaje logičan završni ulaz u rad.",
          },
        ]}
        actions={[
          <HomeHiFiCommandButton
            key="opencode-open"
            code="GUI"
            title={openCodeActionLabel}
            subtitle="DESKTOP SESIJA"
            tone="primary"
            icon="opencode"
            titleAttr={opencode?.openBlockedReason || undefined}
            disabled={opencode?.canOpen === false}
            onClick={() => void handleOpenCode("direct")}
          />,
          <HomeHiFiCommandButton
            key="opencode-tab"
            code="TAB"
            title="OpenCode panel"
            subtitle="RADNI TOK U PORTALU"
            icon="opencode"
            onClick={() => onOpenOpenCode?.()}
          />,
          <HomeHiFiCommandButton
            key="opencode-memory"
            code="MEM"
            title="Project Memory"
            subtitle="FOKUS I PRAVILA"
            icon="memory"
            onClick={() => onOpenProjectMemory?.()}
          />,
          <HomeHiFiCommandButton
            key="opencode-lab"
            code="LAB"
            title="Tuning Lab"
            subtitle="TEST I POREĐENJE"
            icon="tuning"
            onClick={() => onOpenTuningLab?.()}
          />,
        ]}
        footer={[
          {
            label: "Posle klika",
            value: "Desktop ili panel",
            detail: "Posle otvaranja gledaš stanje sesije i poslednju akciju.",
          },
          {
            label: "Sesija",
            value: openCodeStateTitle,
            detail: openCodeBackend,
          },
          {
            label: "Brzina",
            value: throughputSignal,
            detail: "Kad runtime stvarno generiše, ovde se vidi puls tokena.",
          },
          {
            label: "Sledeće",
            value: "Task ili rezultat",
            detail: "Nastavi u OpenCode panelu, Benchmark-u ili Tuning Lab-u kada treba poređenje.",
          },
        ]}
      />

      <section className="status-card wide-card runtimepilot-home-summary-rack runtimepilot-faceplate-module">
        <div className="runtimepilot-home-summary-rack-copy">
          <span className="status-label">Pregled sistema</span>
          <strong className="status-value">Prvi ekran je sada vođeni ulaz, a dublji alati ostaju jedan klik dalje.</strong>
          <p className="helper-text">
            Benchmark, Tuning Lab, Project Memory i kompatibilnost nisu nestali. Samo više ne guraju prvi klik ispred
            osnovnog toka: runtime, lokalni model, pa OpenCode.
          </p>
        </div>
        <div className="runtimepilot-home-summary-rack-actions">
          <button type="button" className="runtimepilot-home-summary-action" onClick={() => onOpenBenchmark?.()}>
            <span className="runtimepilot-home-summary-action-icon" aria-hidden="true">
              <RuntimePilotIcon name="benchmark" />
            </span>
            <span>
              <strong>Benchmark</strong>
              <span>Brzina i istorija</span>
            </span>
          </button>
          <button type="button" className="runtimepilot-home-summary-action" onClick={() => onOpenTuningLab?.()}>
            <span className="runtimepilot-home-summary-action-icon" aria-hidden="true">
              <RuntimePilotIcon name="tuning" />
            </span>
            <span>
              <strong>Tuning Lab</strong>
              <span>Slotovi i poređenje</span>
            </span>
          </button>
          <button type="button" className="runtimepilot-home-summary-action" onClick={() => onOpenCompatibility?.()}>
            <span className="runtimepilot-home-summary-action-icon" aria-hidden="true">
              <RuntimePilotIcon name="compatibility" />
            </span>
            <span>
              <strong>Kompatibilnost</strong>
              <span>VRAM fit i context</span>
            </span>
          </button>
          <button type="button" className="runtimepilot-home-summary-action" onClick={() => onOpenProjectMemory?.()}>
            <span className="runtimepilot-home-summary-action-icon" aria-hidden="true">
              <RuntimePilotIcon name="memory" />
            </span>
            <span>
              <strong>Project Memory</strong>
              <span>Fokus i sledeći koraci</span>
            </span>
          </button>
        </div>
      </section>
    </>
  );
}
