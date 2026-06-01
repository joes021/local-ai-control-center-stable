import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageFlowCard } from "../components/PageFlowCard";
import { StatusCard } from "../components/StatusCard";
import { fetchServerStatus, restartServer, startServer, stopServer } from "../lib/api";
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

export function ServerPage() {
  const [serverStatus, setServerStatus] = useState<ServerStatusPayload | null>(null);
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

  return (
    <>
      {error ? <div className="error-panel">{error}</div> : null}
      <PageFlowCard
        title="Server tok"
        summary="Na ovoj strani je prirodan redosled: prvo proveri da li je runtime pravi, zatim ga startuj ili zaustavi, pa tek onda koristi ručnu CLI komandu ili web pregled."
        steps={[
          {
            title: "Proveri da li je runtime izabran",
            detail: "Pogledaj status, health i izabrani runtime pre bilo kakvog start/stop poteza.",
          },
          {
            title: "Start ili stop runtime server",
            detail: "Primarni tok je da ovde kontrolišeš runtime server, bez odlaska na druge tabove.",
          },
          {
            title: "Ručna CLI komanda",
            detail: "Ako porediš podešavanja sa forumima ili Reddit-om, ovde odmah kopiraš PowerShell ili cmd.exe ekvivalent.",
          },
        ]}
      />
      <ActionResultPanel result={result} />
      <section className="status-card wide-card">
        <span className="status-label">Runtime server</span>
        <strong className="status-value">{serverStatus?.lastReason || "Učitavam server status..."}</strong>
        <p className="helper-text">
          Ovo je mesto za kontrolu rada servera. Home prikazuje samo kratak summary.
        </p>
        <p className="helper-text">
          Izabrani runtime: {serverStatus?.requestedRuntimeLabel || "--"} |{" "}
          {serverStatus?.runtimeSelectionSummary || "Nema dodatnih detalja o izboru runtime-a."}
        </p>
        <div className="inline-actions">
          <button
            type="button"
            disabled={serverStatus?.canStart === false}
            title={serverStatus?.startBlockedReason || undefined}
            onClick={() => void runAction(startServer)}
          >
            Start runtime server
          </button>
          <button
            type="button"
            disabled={serverStatus?.canStop === false}
            title={serverStatus?.stopBlockedReason || undefined}
            onClick={() => void runAction(stopServer)}
          >
            Stop runtime server
          </button>
          <button
            type="button"
            disabled={serverStatus?.canOpenWeb === false}
            title={serverStatus?.openWebBlockedReason || undefined}
            onClick={openServerWebNow}
          >
            Otvori runtime veb
          </button>
        </div>
      </section>

      <StatusCard label="Status servera" value={serverStatus?.status ?? "--"} />
      <StatusCard label="Health servera" value={serverStatus?.health ?? "--"} />
      <StatusCard
        label="PID servera"
        value={serverStatus?.pid ? String(serverStatus.pid) : "nije potvrđen"}
      />
      <StatusCard label="Port servera" value={serverStatus ? String(serverStatus.port) : "--"} />

      <section className="status-card wide-card">
        <span className="status-label">Poslednja poruka</span>
        <strong className="status-value">{serverStatus?.lastReason || "Nema lifecycle poruke."}</strong>
        <p className="helper-text">Health URL: {serverStatus?.healthUrl || "--"}</p>
        <p className="helper-text">Lokalni web: {serverStatus?.localWebUrl || "nije dostupan"}</p>
        <p className="helper-text">
          Tailscale veb: {serverStatus?.tailscaleWebUrl || "nije izložen kroz Tailscale"}
        </p>
        <p className="helper-text">
          Runtime live signal: {serverStatus?.runtimeLiveStatus || "--"} |{" "}
          {serverStatus?.runtimeLiveReason || "Nema dodatnih detalja."}
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">GPU offload dijagnostika</span>
        <strong className="status-value">
          {serverStatus?.runtimeDiagnostics?.summary || "Dijagnostika se učitava..."}
        </strong>
        <p className="helper-text">
          Ovaj blok razdvaja ono što launch komanda planira od onoga što je runtime log stvarno
          potvrdio. Na Windows mašinama to je pošteniji dokaz od samog Task Manager prikaza.
        </p>
        <div className="summary-metrics">
          {buildRuntimeDiagnosticsHighlights(serverStatus?.runtimeDiagnostics).map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
        <div className="server-diagnostics-grid">
          <article className="command-preview-card">
            <span className="status-label">Planirano kroz launch komandu</span>
            <strong className="status-value">
              {serverStatus?.runtimeDiagnostics?.requestedSummary || "--"}
            </strong>
            <p className="helper-text">
              Ako ovde vidiš `--n-gpu-layers` i `--flash-attn`, RuntimePilot je stvarno pokušao GPU
              offload za izabrani runtime.
            </p>
          </article>
          <article className="command-preview-card">
            <span className="status-label">Potvrđeno kroz runtime log</span>
            <strong className="status-value">
              {serverStatus?.runtimeDiagnostics?.confirmedSummary || "--"}
            </strong>
            <div className="summary-metrics">
              <span>
                Device mem: {formatMiB(serverStatus?.runtimeDiagnostics?.projectedDeviceMemoryMiB)}
              </span>
              <span>
                Host mem: {formatMiB(serverStatus?.runtimeDiagnostics?.projectedHostMemoryMiB)}
              </span>
              <span>
                Model buffer: {formatMiB(serverStatus?.runtimeDiagnostics?.modelBufferMiB)}
              </span>
              <span>KV buffer: {formatMiB(serverStatus?.runtimeDiagnostics?.kvBufferMiB)}</span>
              <span>
                Compute buffer: {formatMiB(serverStatus?.runtimeDiagnostics?.computeBufferMiB)}
              </span>
            </div>
          </article>
          <article className="command-preview-card">
            <span className="status-label">Context poravnanje</span>
            <strong className="status-value">
              {serverStatus?.runtimeDiagnostics?.contextAlignmentLabel || "Čeka proveru"}
            </strong>
            <p className="helper-text">
              Config context: {formatContext(serverStatus?.runtimeDiagnostics?.configuredContext)} | Živi process
              context: {formatContext(serverStatus?.runtimeDiagnostics?.effectiveProcessContext)}
            </p>
            <p className="helper-text">
              {serverStatus?.runtimeDiagnostics?.contextAlignmentSummary ||
                "Ovde vidiš da li je ctx-size koji je upisan u config zaista isti kao onaj sa kojim živi runtime proces trenutno radi."}
            </p>
            {serverStatus?.runtimeDiagnostics?.contextMismatch ? (
              <div className="inline-actions">
                <button type="button" className="secondary-button" onClick={() => void runAction(restartServer)}>
                  Restartuj runtime da poravnaš context
                </button>
              </div>
            ) : null}
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

      <section className="status-card wide-card">
        <span className="status-label">Ekvivalentne CLI komande</span>
        <strong className="status-value">
          {serverStatus?.commandPreview?.activeRuntimeLabel || "Runtime command preview"}
        </strong>
        <p className="helper-text">
          Ovde vidiš ručni ekvivalent onoga što RuntimePilot radi kada pokreće runtime server. Lokalni model
          se prosleđuje kroz `--model` argument, a najbitnije vrednosti za poređenje su `ctx-size` i
          sampling parametri.
        </p>
        <p className="helper-text">
          `PowerShell` koristi prefiks `&`, dok `cmd.exe` koristi istu komandu bez tog prefiksa.
        </p>
        <p className="helper-text">
          Ako ručno lepiš komandu u Command Prompt, kopiraj samo `cmd.exe` blok ispod. `PowerShell`
          varijanta sa `&` nije namenjena za običan `cmd`.
        </p>
        <div className="command-preview-stack">
          {serverStatus?.commandPreview?.variants.map((variant) => (
            <article className="command-preview-card" key={variant.runtime}>
              <div className="section-header">
                <div>
                  <span className="status-label">{variant.runtimeLabel}</span>
                  <strong className="status-value">
                    {variant.available ? "Spreman za launch" : "Preview sa upozorenjem"}
                  </strong>
                </div>
                <div className="inline-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={!variant.command}
                    onClick={() =>
                      void copyCommand(
                        variant.command,
                        formatShellLabel(variant.runtimeLabel, "powershell"),
                      )
                    }
                  >
                    Kopiraj PowerShell
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={!variant.cmdCommand}
                    onClick={() =>
                      void copyCommand(
                        variant.cmdCommand || "",
                        formatShellLabel(variant.runtimeLabel, "cmd"),
                      )
                    }
                  >
                    Kopiraj cmd.exe
                  </button>
                </div>
              </div>
              <p className="helper-text">{variant.summary}</p>
              <p className="helper-text">Runtime binar: {variant.binaryPath || "--"}</p>
              <p className="helper-text">Model putanja: {variant.modelPath || "--"}</p>
              <p className="helper-text">
                {formatRuntimeCommandMeta(variant.context, variant.specType)}
              </p>
              {variant.samplingSummary ? (
                <p className="helper-text">Sampling: {variant.samplingSummary}</p>
              ) : null}
              <div className="details-block">
                <span className="status-label">PowerShell</span>
                <pre>{variant.command || "Komanda nije dostupna dok binar ili model ne budu spremni."}</pre>
              </div>
              <div className="details-block">
                <span className="status-label">cmd.exe</span>
                <pre>{variant.cmdCommand || "cmd.exe varijanta nije dostupna dok binar ili model ne budu spremni."}</pre>
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
