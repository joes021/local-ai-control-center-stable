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
  return "Portal još čeka dovoljno signala da pouzdano razdvoji GPU, hibridni ili CPU-only režim.";
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

  return (
    <section className="status-card wide-card runtime-resource-panel">
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
