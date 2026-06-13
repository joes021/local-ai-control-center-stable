import { estimateHybridRuntimeUsage } from "../lib/runtimeDiagnostics";
import type { ObservabilityPayload } from "../lib/types";

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(1)}%`;
}

function formatGiB(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(2)} GiB`;
}

function formatMiB(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} MiB`;
}

function formatContext(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return String(Math.round(value));
}

function buildModeNote(modeId: string | undefined) {
  if (modeId === "gpu-vram") {
    return "Model je dominantno u GPU VRAM-u. RAM i dalje može da se koristi za mapiranje fajla i pomoćne bafere.";
  }
  if (modeId === "hybrid-vram-ram") {
    return "Model koristi i VRAM i sistemski RAM. To obično znači da je deo slojeva na GPU-u, a deo rada i dalje ide kroz RAM.";
  }
  if (modeId === "cpu-ram") {
    return "Model trenutno nema potvrđen GPU offload i oslanja se na CPU + RAM.";
  }
  return "RuntimePilot još čeka dovoljno signala da pouzdano razdvoji GPU, hibridni ili CPU-only režim.";
}

type RuntimeResourcePanelProps = {
  observability: ObservabilityPayload | null;
};

export function RuntimeResourcePanel({ observability }: RuntimeResourcePanelProps) {
  if (!observability) {
    return null;
  }

  const selectedGpu =
    observability.system.gpuDevices.find((item) => item.selected) ?? observability.system.gpuDevices[0] ?? null;
  const diagnostics = observability.runtime.runtimeDiagnostics;
  const hybridEstimate = estimateHybridRuntimeUsage(
    diagnostics,
    observability.runtime.selectedGpuTotalGiB ?? selectedGpu?.totalGiB ?? null,
  );

  return (
    <section className="status-card wide-card runtime-resource-panel runtimepilot-section-shell runtimepilot-faceplate-module benchmark-resource-shell">
      <span className="status-label">Resursi i offload</span>
      <strong className="status-value">CPU uživo, RAM uživo, VRAM uživo i stvarni režim izvršavanja</strong>
      <p className="helper-text">
        Ovaj blok razdvaja dve stvari koje Task Manager često pomeša: koliko je sistema zauzeto ukupno i kako je
        stvarni runtime rasporedio model između GPU VRAM-a i sistemskog RAM-a.
      </p>
      <div className="runtime-resource-grid">
        <article className="runtime-resource-card">
          <span className="status-label">CPU uživo</span>
          <strong>{formatPercent(observability.system.cpuPercent)}</strong>
          <span className="helper-text">Ukupno opterećenje mašine u ovom trenutku.</span>
        </article>
        <article className="runtime-resource-card">
          <span className="status-label">RAM uživo</span>
          <strong>
            {formatGiB(observability.system.ramUsedGiB)} / {formatGiB(observability.system.ramTotalGiB)}
          </strong>
          <span className="helper-text">Sistemski RAM cele mašine, ne samo model procesa.</span>
        </article>
        <article className="runtime-resource-card">
          <span className="status-label">VRAM uživo</span>
          <strong>
            {formatGiB(observability.system.vramUsedGiB)} / {formatGiB(observability.system.vramTotalGiB)}
          </strong>
          <span className="helper-text">Dedicated GPU memorija za izabrani GPU.</span>
        </article>
        <article className="runtime-resource-card">
          <span className="status-label">Model proces RAM</span>
          <strong>{formatMiB(observability.runtime.runtimeProcessRamMiB)}</strong>
          <span className="helper-text">Radni set aktivnog runtime procesa ako ga je sistem uspešno očitao.</span>
        </article>
        <article className="runtime-resource-card">
          <span className="status-label">Režim izvršavanja</span>
          <strong>{observability.runtime.executionModeLabel}</strong>
          <span className="helper-text">{buildModeNote(observability.runtime.executionModeId)}</span>
        </article>
        <article className="runtime-resource-card">
          <span className="status-label">GPU offload</span>
          <strong>{observability.runtime.offloadLabel}</strong>
          <span className="helper-text">{observability.runtime.offloadSummary || observability.runtime.runtimeLiveReason}</span>
        </article>
        <article className="runtime-resource-card">
          <span className="status-label">Procena RAM preliva</span>
          <strong>{formatMiB(hybridEstimate?.estimatedRamSpillMiB)}</strong>
          <span className="helper-text">
            Ovo je procena na osnovu odnosa GPU slojeva i već učitanog model buffer-a. Najviše znači kada je režim
            stvarno potvrđen kao hibridan.
          </span>
        </article>
        <article className="runtime-resource-card">
          <span className="status-label">Još VRAM-a za puni GPU fit</span>
          <strong>{formatMiB(hybridEstimate?.estimatedAdditionalVramToFitMiB)}</strong>
          <span className="helper-text">
            Približan dodatni VRAM koji bi bio potreban da isti model i isti context stanu potpuno na GPU, bez
            oslanjanja na RAM.
          </span>
        </article>
        <article className="runtime-resource-card">
          <span className="status-label">Context poravnanje</span>
          <strong>{diagnostics?.contextAlignmentLabel || "Čeka proveru"}</strong>
          <span className="helper-text">
            Config context: {formatContext(diagnostics?.configuredContext)} | Živi process context:{" "}
            {formatContext(diagnostics?.effectiveProcessContext)}
          </span>
          <span className="helper-text">
            {diagnostics?.contextAlignmentSummary ||
              "Ovde vidiš da li je zapisani ctx-size stvarno isti kao onaj sa kojim živi runtime proces trenutno radi."}
          </span>
          <span className="helper-text">
            Kada ovde piše `Potreban restart runtime-a`, to znači da su config context i živi process context
            različiti i da restart tek tada poravnava stvarno stanje.
          </span>
        </article>
      </div>
      <div className="summary-metrics runtime-resource-summary">
        <span>Izabrani GPU: {selectedGpu?.name || observability.runtime.selectedGpuName || "nije poznat"}</span>
        <span>Najjači GPU se bira automatski kada runtime podržava eksplicitan GPU izbor.</span>
        <span>Model: {observability.runtime.activeModel || "--"}</span>
        <span>Runtime: {observability.runtime.activeRuntime || "--"}</span>
      </div>
      {diagnostics ? (
        <div className="runtime-resource-explainer">
          <div>
            <span className="status-label">Šta je launch tražio</span>
            <p className="helper-text">{diagnostics.requestedSummary}</p>
          </div>
          <div>
            <span className="status-label">Šta log potvrđuje</span>
            <p className="helper-text">{diagnostics.confirmedSummary}</p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
