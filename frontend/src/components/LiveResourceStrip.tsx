import { useEffect, useMemo, useState } from "react";

import { fetchObservability } from "../lib/api";
import type { ObservabilityPayload } from "../lib/types";

const REFRESH_MS = 5000;

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

function buildModeTone(modeId: string | undefined) {
  if (modeId === "gpu-vram") {
    return "resource-chip-tone-good";
  }
  if (modeId === "hybrid-vram-ram") {
    return "resource-chip-tone-warm";
  }
  if (modeId === "cpu-ram") {
    return "resource-chip-tone-muted";
  }
  return "resource-chip-tone-neutral";
}

export function LiveResourceStrip() {
  const [observability, setObservability] = useState<ObservabilityPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const payload = await fetchObservability();
        if (cancelled) {
          return;
        }
        setObservability(payload);
        setError("");
      } catch (reason: unknown) {
        if (cancelled) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Živi resursi trenutno nisu dostupni.");
      }
    }

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, REFRESH_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const selectedGpu = useMemo(
    () => observability?.system.gpuDevices.find((item) => item.selected) ?? null,
    [observability],
  );

  if (!observability && !error) {
    return null;
  }

  return (
    <section className="live-resource-strip" aria-label="Živi resursi sistema">
      <div className="live-resource-strip-main">
        <span className="status-label">Živi resursi</span>
        <div className="live-resource-chip-row">
          <div className="live-resource-chip">
            <span className="live-resource-chip-label">CPU</span>
            <strong>{formatPercent(observability?.system.cpuPercent)}</strong>
          </div>
          <div className="live-resource-chip">
            <span className="live-resource-chip-label">RAM</span>
            <strong>
              {formatGiB(observability?.system.ramUsedGiB)} / {formatGiB(observability?.system.ramTotalGiB)}
            </strong>
          </div>
          <div className="live-resource-chip">
            <span className="live-resource-chip-label">VRAM</span>
            <strong>
              {formatGiB(observability?.system.vramUsedGiB)} / {formatGiB(observability?.system.vramTotalGiB)}
            </strong>
          </div>
          <div className={`live-resource-chip ${buildModeTone(observability?.runtime.executionModeId)}`}>
            <span className="live-resource-chip-label">Režim</span>
            <strong>{observability?.runtime.executionModeLabel || "Čeka potvrdu"}</strong>
          </div>
          <div className={`live-resource-chip ${buildModeTone(observability?.runtime.executionModeId)}`}>
            <span className="live-resource-chip-label">Offload</span>
            <strong>{observability?.runtime.offloadLabel || "Čeka potvrdu"}</strong>
          </div>
          <div className="live-resource-chip">
            <span className="live-resource-chip-label">Model proces</span>
            <strong>{formatMiB(observability?.runtime.runtimeProcessRamMiB)}</strong>
          </div>
        </div>
      </div>
      <div className="live-resource-strip-side">
        <span>{selectedGpu?.name || observability?.system.gpuName || "GPU nije dostupan"}</span>
        {selectedGpu?.totalGiB ? <span>{formatGiB(selectedGpu.totalGiB)} ukupno</span> : null}
        {error ? <span>{error}</span> : null}
      </div>
    </section>
  );
}
