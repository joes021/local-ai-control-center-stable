import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PrimaryTabRack } from "../components/shell/PrimaryTabRack";
import {
  fetchServerStatus,
  peekServerStatusCache,
  restartServer,
  startServer,
  stopServer,
} from "../lib/api";
import type { ActionResult, RuntimeDiagnostics, ServerStatusPayload } from "../lib/types";

function formatRuntimeCommandMeta(
  context: number | null,
  specType: string,
): string {
  const parts = [context ? `ctx-size ${context}` : "ctx-size --"];
  if (specType) {
    parts.push(`spec-type ${specType}`);
  }
  return parts.join(" | ");
}

function formatShellLabel(label: string, shell: "powershell" | "cmd"): string {
  return shell === "powershell" ? `${label} / PowerShell` : `${label} / cmd.exe`;
}

function formatMiB(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return `${value.toFixed(value >= 100 ? 0 : 2)} MiB`;
}

function formatContext(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return String(Math.round(value));
}

function renderRuntimeStatusLink(
  label: string,
  url: string | null | undefined,
  fallback: string,
) {
  if (!url) {
    return (
      <p className="helper-text runtimepilot-status-link runtimepilot-status-link-disabled">
        <span className="runtimepilot-status-link-label">{label}:</span>
        <span className="runtimepilot-status-link-value">{fallback}</span>
      </p>
    );
  }

  return (
    <a
      className="helper-text runtimepilot-status-link"
      href={url}
      target="_blank"
      rel="noreferrer"
      title={`Otvori ${label.toLowerCase()}`}
    >
      <span className="runtimepilot-status-link-label">{label}:</span>
      <span className="runtimepilot-status-link-value">{url}</span>
    </a>
  );
}

function buildRuntimeDiagnosticsHighlights(diagnostics: RuntimeDiagnostics | undefined) {
  if (!diagnostics) {
    return [];
  }
  return [
    diagnostics.requestedGpuLayers > 0
      ? `Traženo: ${diagnostics.requestedGpuLayers} GPU slojeva`
      : "Traženo: bez eksplicitnog GPU offload-a",
    diagnostics.requestedFlashAttention
      ? `Flash-attn: ${diagnostics.requestedFlashAttention}`
      : "Flash-attn: --",
    diagnostics.backend ? `Backend: ${diagnostics.backend}` : "Backend: --",
    diagnostics.confirmedGpuLayers && diagnostics.confirmedTotalLayers
      ? `Potvrđeno: ${diagnostics.confirmedGpuLayers}/${diagnostics.confirmedTotalLayers}`
      : "Potvrđeno: čeka log dokaz",
  ];
}

function looksStarted(status: ServerStatusPayload | null) {
  if (!status) {
    return false;
  }
  return Boolean(status.pid) || ["started", "running", "healthy"].includes(status.status);
}

type ServerPageProps = {
  onOpenContextSettings?: () => void;
};

export function ServerPage({ onOpenContextSettings }: ServerPageProps) {
  const [serverStatus, setServerStatus] = useState<ServerStatusPayload | null>(() =>
    peekServerStatusCache(),
  );
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);

  async function loadStatus() {
    try {
      const payload = await fetchServerStatus();
      setServerStatus(payload);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    }
  }

  async function runAction(action: () => Promise<ActionResult>) {
    try {
      const actionResult = await action();
      setResult(actionResult);
      await loadStatus();
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Nepoznata greška";
      setError(message);
    }
  }

  function openServerWebNow() {
    const url = serverStatus?.localWebUrl || serverStatus?.webUrl || "http://127.0.0.1:8091/";
    window.open(url, "_blank", "noopener,noreferrer");
    setResult({
      status: "ok",
      action: "open-server-web",
      summary: `Otvoren llama.cpp web: ${url}`,
      details: { returncode: 0, stdout: url, stderr: "" },
    });
  }

  async function copyCommand(text: string, label: string) {
    if (!text.trim()) {
      setError(`Nema komande za kopiranje: ${label}.`);
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setResult({
        status: "ok",
        action: "copy-command-preview",
        summary: `${label} je kopirana u clipboard.`,
        details: { returncode: 0, stdout: text, stderr: "" },
      });
    } catch (reason: unknown) {
      setError(
        reason instanceof Error
          ? reason.message
          : `Komanda nije mogla da se kopira: ${label}.`,
      );
    }
  }

  useEffect(() => {
    let active = true;
    fetchServerStatus()
      .then((payload) => {
        if (active) {
          setServerStatus(payload);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Nepoznata greška");
        }
      });

    const timer = window.setInterval(() => {
      void loadStatus();
    }, 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const runtimeStarted = looksStarted(serverStatus);
  const primaryActionLabel = runtimeStarted ? "Restartuj runtime" : "Pokreni runtime";
  const runtimeStateTitle =
    serverStatus?.requestedRuntimeLabel || serverStatus?.activeRuntimeLabel || "Runtime još nije izabran";
  const runtimeStateSummary =
    serverStatus?.lastReason ||
    "Ovde prvo potvrđuješ da engine radi kako treba, pa tek onda ideš na model i OpenCode rad.";
  const actionSummary = result
    ? result.summary
    : "Posle ovog klika odmah vidiš da li je runtime pokrenut, restartovan ili blokiran.";

  const openRuntimeDiagnostics = () => {
    const details = document.getElementById("runtime-advanced-rack");
    if (details instanceof HTMLDetailsElement) {
      details.open = true;
      details.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <PrimaryTabRack
        eyebrow="Runtime"
        title="Runtime cockpit"
        signal={
          <div className="runtimepilot-primary-tab-rack-body">
            <strong className="runtimepilot-primary-tab-rack-state">{runtimeStateTitle}</strong>
            <p className="helper-text runtimepilot-primary-tab-rack-copy">{runtimeStateSummary}</p>
            <div className="summary-metrics">
              <span>Status: {serverStatus?.status || "--"}</span>
              <span>Health: {serverStatus?.health || "--"}</span>
              <span>
                Context: {serverStatus?.runtimeDiagnostics?.contextAlignmentLabel || "Čeka proveru"}
              </span>
              <span>
                Režim: {serverStatus?.runtimeDiagnostics?.executionModeLabel || "Nije potvrđen"}
              </span>
            </div>
            <p className="helper-text runtimepilot-primary-tab-rack-copy">
              Runtime signal: {serverStatus?.runtimeLiveStatus || "--"} ·{" "}
              {serverStatus?.runtimeLiveReason || "Nema dodatnog runtime signala."}
            </p>
          </div>
        }
        commands={
          <div className="runtimepilot-primary-tab-rack-command-grid">
            <button
              type="button"
              className="action-button deck-control-button deck-control-button-primary"
              disabled={runtimeStarted || serverStatus?.canStart === false}
              title={runtimeStarted ? "Runtime je već pokrenut." : serverStatus?.startBlockedReason || undefined}
              onClick={() => void runAction(startServer)}
            >
              <span className="deck-control-symbol" aria-hidden="true">
                ▶
              </span>
              <span className="deck-control-copy">Pokreni runtime</span>
            </button>
            <button
              type="button"
              className="action-button-soft deck-control-button deck-control-button-secondary"
              disabled={!runtimeStarted}
              onClick={() => void runAction(restartServer)}
            >
              <span className="deck-control-symbol" aria-hidden="true">
                ↻
              </span>
              <span className="deck-control-copy">Restartuj runtime</span>
            </button>
            <button
              type="button"
              className="action-button-soft deck-control-button deck-control-button-secondary"
              disabled={serverStatus?.canStop === false}
              title={serverStatus?.stopBlockedReason || undefined}
              onClick={() => void runAction(stopServer)}
            >
              <span className="deck-control-symbol" aria-hidden="true">
                ■
              </span>
              <span className="deck-control-copy">Zaustavi runtime</span>
            </button>
            <button
              type="button"
              className="action-button-soft deck-control-button deck-control-button-secondary"
              disabled={serverStatus?.canOpenWeb === false}
              title={serverStatus?.openWebBlockedReason || undefined}
              onClick={openServerWebNow}
            >
              <span className="deck-control-symbol" aria-hidden="true">
                ↗
              </span>
              <span className="deck-control-copy">Otvori runtime veb</span>
            </button>
          </div>
        }
        deep={
          <div className="runtimepilot-primary-tab-rack-detail-stack">
            {renderRuntimeStatusLink("Health URL", serverStatus?.healthUrl, "--")}
            {renderRuntimeStatusLink(
              "Lokalni web",
              serverStatus?.localWebUrl || serverStatus?.webUrl,
              "nije dostupan",
            )}
            <p className="helper-text runtimepilot-primary-tab-rack-copy">
              {serverStatus?.runtimeDiagnostics?.contextAlignmentSummary ||
                "Ovde odmah vidiš da li runtime zaista radi sa istim context-om koji je upisan u config."}
            </p>
            <div className="runtimepilot-primary-tab-rack-command-grid runtimepilot-primary-tab-rack-command-grid-compact">
              <button
                type="button"
                className="action-button-soft deck-control-button deck-control-button-secondary"
                onClick={() => onOpenContextSettings?.()}
                disabled={!onOpenContextSettings}
              >
                <span className="deck-control-symbol" aria-hidden="true">
                  CTX
                </span>
                <span className="deck-control-copy">Otvori context</span>
              </button>
              <button
                type="button"
                className="action-button-soft deck-control-button deck-control-button-secondary"
                onClick={openRuntimeDiagnostics}
              >
                <span className="deck-control-symbol" aria-hidden="true">
                  ADV
                </span>
                <span className="deck-control-copy">Dijagnostika</span>
              </button>
            </div>
            <p className="helper-text runtimepilot-primary-tab-rack-copy">
              Rezultat posle klika: {actionSummary}
            </p>
          </div>
        }
      />

      <ActionResultPanel result={result} />

      <details
        id="runtime-advanced-rack"
        className="status-card wide-card runtimepilot-section-shell runtimepilot-advanced-disclosure"
      >
        <summary>
          <span className="runtimepilot-advanced-summary-copy">
            <span className="status-label">Runtime rack</span>
            <span className="runtimepilot-advanced-summary-title">Napredna dijagnostika i ručne komande</span>
          </span>
          <span className="runtimepilot-advanced-summary-indicator" aria-hidden="true">
            ADV
          </span>
        </summary>
        <div className="runtimepilot-advanced-intro-shell">
          <div className="runtimepilot-advanced-intro-copy">
            <span className="status-label">Šta je u rack-u</span>
            <h3 className="runtimepilot-advanced-intro-title">Kada osnovni signal nije dovoljan</h3>
            <p className="helper-text runtimepilot-advanced-summary">
              Ovde ostaju GPU offload detalji, planirana i potvrđena potrošnja, context mismatch
              dijagnostika i ručni ekvivalenti komandi. Glavni klikovi su gore, a ovaj rack
              otvaraš kada proveravaš fit, porediš CLI ili tražiš root cause.
            </p>
          </div>
          <div className="runtimepilot-advanced-overview-grid">
            <article className="runtimepilot-advanced-overview-card runtimepilot-faceplate-module">
              <span className="status-label">Offload signal</span>
              <strong>{serverStatus?.runtimeDiagnostics?.summary || "Čeka runtime dokaz"}</strong>
              <p className="helper-text">
                Launch plan, potvrđeni GPU slojevi i memorijski fit skupljeni na jednom mestu.
              </p>
            </article>
            <article className="runtimepilot-advanced-overview-card runtimepilot-faceplate-module">
              <span className="status-label">Context signal</span>
              <strong>{serverStatus?.runtimeDiagnostics?.contextAlignmentLabel || "Čeka proveru"}</strong>
              <p className="helper-text">
                Odmah vidiš da li se config i živi proces zaista poklapaju.
              </p>
            </article>
            <article className="runtimepilot-advanced-overview-card runtimepilot-faceplate-module">
              <span className="status-label">CLI preview</span>
              <strong>{serverStatus?.commandPreview?.activeRuntimeLabel || "Runtime command preview"}</strong>
              <p className="helper-text">
                PowerShell i cmd.exe varijante ostaju spremne za ručno poređenje i launch.
              </p>
            </article>
          </div>
        </div>

        <section className="status-card wide-card runtimepilot-faceplate-module runtimepilot-advanced-module">
          <div className="runtimepilot-advanced-module-shell">
            <div className="runtime-faceplate-head">
              <span className="status-label">GPU offload dijagnostika</span>
              <strong className="status-value">
                {serverStatus?.runtimeDiagnostics?.summary || "Dijagnostika se učitava..."}
              </strong>
            </div>
            <div className="runtime-faceplate-copy">
              <p className="helper-text">
                Ovaj blok razdvaja ono što launch komanda planira od onoga što je runtime log stvarno
                potvrdio. Na Windows mašinama to je pošteniji dokaz od samog Task Manager prikaza.
              </p>
            </div>
            <div className="runtime-faceplate-rail runtime-faceplate-rail-stack">
              <span className="status-label">Signal pregled</span>
              <div className="summary-metrics">
                {buildRuntimeDiagnosticsHighlights(serverStatus?.runtimeDiagnostics).map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            </div>
          </div>
          <div className="runtimepilot-advanced-module-divider" aria-hidden="true" />
          <div className="server-diagnostics-grid runtimepilot-advanced-rack">
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-advanced-card">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">PLAN</span>
                <span className="status-label">Launch</span>
              </div>
              <span className="status-label">Planirano kroz launch komandu</span>
              <strong className="status-value">
                {serverStatus?.runtimeDiagnostics?.requestedSummary || "--"}
              </strong>
              <p className="helper-text">
                Ako ovde vidiš `--n-gpu-layers` i `--flash-attn`, RuntimePilot je stvarno pokušao GPU
                offload za izabrani runtime.
              </p>
            </article>
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-advanced-card">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">CONF</span>
                <span className="status-label">Log</span>
              </div>
              <span className="status-label">Potvrđeno kroz runtime log</span>
              <strong className="status-value">
                {serverStatus?.runtimeDiagnostics?.confirmedSummary || "--"}
              </strong>
              <div className="runtimepilot-advanced-metric-grid">
                <span>
                  <strong>Device</strong>
                  <em>{formatMiB(serverStatus?.runtimeDiagnostics?.projectedDeviceMemoryMiB)}</em>
                </span>
                <span>
                  <strong>Host</strong>
                  <em>{formatMiB(serverStatus?.runtimeDiagnostics?.projectedHostMemoryMiB)}</em>
                </span>
                <span>
                  <strong>Model</strong>
                  <em>{formatMiB(serverStatus?.runtimeDiagnostics?.modelBufferMiB)}</em>
                </span>
                <span>
                  <strong>KV</strong>
                  <em>{formatMiB(serverStatus?.runtimeDiagnostics?.kvBufferMiB)}</em>
                </span>
                <span>
                  <strong>Compute</strong>
                  <em>{formatMiB(serverStatus?.runtimeDiagnostics?.computeBufferMiB)}</em>
                </span>
              </div>
            </article>
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-advanced-card">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">CTX</span>
                <span className="status-label">Sync</span>
              </div>
              <span className="status-label">Context poravnanje</span>
              <button
                type="button"
                className="runtimepilot-advanced-inline-link"
                onClick={() => onOpenContextSettings?.()}
                disabled={!onOpenContextSettings}
                aria-label="Otvori context podešavanje"
              >
                <strong className="status-value">
                  {serverStatus?.runtimeDiagnostics?.contextAlignmentLabel || "Čeka proveru"}
                </strong>
                <span className="helper-text runtimepilot-advanced-inline-link-copy">
                  Config context: {formatContext(serverStatus?.runtimeDiagnostics?.configuredContext)} | Živi
                  process context: {formatContext(serverStatus?.runtimeDiagnostics?.effectiveProcessContext)}
                </span>
                <span className="helper-text runtimepilot-advanced-inline-link-copy">
                  {serverStatus?.runtimeDiagnostics?.contextAlignmentSummary ||
                    "Ovde vidiš da li je ctx-size koji je upisan u config zaista isti kao onaj sa kojim živi runtime proces trenutno radi."}
                </span>
                <span className="runtimepilot-advanced-inline-link-note">Otvori context podešavanje</span>
              </button>
            </article>
            <article className="command-preview-card runtimepilot-faceplate-module runtimepilot-advanced-card">
              <div className="runtimepilot-advanced-card-topline">
                <span className="runtimepilot-advanced-card-code">LIVE</span>
                <span className="status-label">Status</span>
              </div>
              <span className="status-label">Poslednja poruka</span>
              <strong className="status-value">{serverStatus?.lastReason || "Nema lifecycle poruke."}</strong>
              {renderRuntimeStatusLink("Health URL", serverStatus?.healthUrl, "--")}
              {renderRuntimeStatusLink(
                "Lokalni web",
                serverStatus?.localWebUrl || serverStatus?.webUrl,
                "nije dostupan",
              )}
              {renderRuntimeStatusLink(
                "Tailscale veb",
                serverStatus?.tailscaleWebUrl,
                "nije izložen kroz Tailscale",
              )}
            </article>
          </div>
          {serverStatus?.runtimeDiagnostics?.notes?.length ? (
            <div className="server-diagnostics-notes">
              {serverStatus.runtimeDiagnostics.notes.map((note) => (
                <p className="helper-text" key={note}>
                  {note}
                </p>
              ))}
            </div>
          ) : null}
        </section>

        <section className="status-card wide-card runtimepilot-faceplate-module runtimepilot-command-module">
          <div className="runtimepilot-advanced-module-shell">
            <div className="runtime-faceplate-head">
              <span className="status-label">Ekvivalentne CLI komande</span>
              <strong className="status-value">
                {serverStatus?.commandPreview?.activeRuntimeLabel || "Runtime command preview"}
              </strong>
            </div>
            <div className="runtime-faceplate-copy">
              <p className="helper-text">
                Ovde vidiš ručni ekvivalent onoga što RuntimePilot radi kada pokreće runtime server. Lokalni model
                se prosleđuje kroz `--model` argument, a najbitnije vrednosti za poređenje su `ctx-size` i
                sampling parametri.
              </p>
              <p className="helper-text">
                `PowerShell` koristi prefiks `&`, dok `cmd.exe` koristi istu komandu bez tog prefiksa.
              </p>
            </div>
            <div className="runtime-faceplate-rail runtime-faceplate-rail-stack">
              <span className="status-label">Ručno izvršavanje</span>
              <p className="helper-text runtime-faceplate-note">
                Ako ručno lepiš komandu u Command Prompt, kopiraj samo `cmd.exe` blok ispod. `PowerShell`
                varijanta sa `&` nije namenjena za običan `cmd`.
              </p>
            </div>
          </div>
          <div className="runtimepilot-advanced-module-divider" aria-hidden="true" />
          <div className="command-preview-stack runtimepilot-command-rack">
            {serverStatus?.commandPreview?.variants.map((variant) => (
              <article
                className="command-preview-card runtimepilot-faceplate-module runtimepilot-command-card"
                key={variant.runtime}
              >
                <div className="runtimepilot-command-card-topline">
                  <div className="runtimepilot-command-card-head">
                    <span className="runtimepilot-advanced-card-code">
                      {variant.runtimeLabel.slice(0, 3).toUpperCase()}
                    </span>
                    <div>
                      <span className="status-label">{variant.runtimeLabel}</span>
                      <strong className="status-value">
                        {variant.available ? "Spreman za launch" : "Preview sa upozorenjem"}
                      </strong>
                    </div>
                  </div>
                  <div className="runtimepilot-command-card-actions">
                    <button
                      type="button"
                      className="action-button-soft deck-control-button deck-control-button-secondary"
                      disabled={!variant.command}
                      onClick={() =>
                        void copyCommand(
                          variant.command,
                          formatShellLabel(variant.runtimeLabel, "powershell"),
                        )
                      }
                    >
                      <span className="deck-control-symbol" aria-hidden="true">PS</span>
                      <span className="deck-control-copy">Kopiraj PowerShell</span>
                    </button>
                    <button
                      type="button"
                      className="action-button-soft deck-control-button deck-control-button-secondary"
                      disabled={!variant.cmdCommand}
                      onClick={() =>
                        void copyCommand(
                          variant.cmdCommand || "",
                          formatShellLabel(variant.runtimeLabel, "cmd"),
                        )
                      }
                    >
                      <span className="deck-control-symbol" aria-hidden="true">CMD</span>
                      <span className="deck-control-copy">Kopiraj cmd.exe</span>
                    </button>
                  </div>
                </div>
                <p className="helper-text">{variant.summary}</p>
                <div className="runtimepilot-command-chip-row">
                  <span className="runtimepilot-command-chip">Binar: {variant.binaryPath || "--"}</span>
                  <span className="runtimepilot-command-chip">Model: {variant.modelPath || "--"}</span>
                  <span className="runtimepilot-command-chip">
                    {formatRuntimeCommandMeta(variant.context, variant.specType)}
                  </span>
                  {variant.samplingSummary ? (
                    <span className="runtimepilot-command-chip">Sampling: {variant.samplingSummary}</span>
                  ) : null}
                </div>
                <div className="runtimepilot-command-surface-grid">
                  <div className="details-block runtimepilot-command-surface">
                    <span className="status-label">PowerShell</span>
                    <pre>{variant.command || "Komanda nije dostupna dok binar ili model ne budu spremni."}</pre>
                  </div>
                  <div className="details-block runtimepilot-command-surface">
                    <span className="status-label">cmd.exe</span>
                    <pre>{variant.cmdCommand || "cmd.exe varijanta nije dostupna dok binar ili model ne budu spremni."}</pre>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      </details>
    </>
  );
}
