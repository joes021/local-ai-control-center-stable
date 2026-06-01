import { useEffect, useMemo, useState } from "react";

import { fetchObservability } from "../lib/api";
import { estimateContextFitFromKvBuffer, estimateHybridRuntimeUsage } from "../lib/runtimeDiagnostics";
import type { ObservabilityPayload } from "../lib/types";

const REFRESH_MS = 5000;

type ResourceMetricKey =
  | "cpu"
  | "ram"
  | "vram"
  | "mode"
  | "offload"
  | "context"
  | "process"
  | "gpu"
  | "signal";

type ResourceMetric = {
  key: ResourceMetricKey;
  label: string;
  value: string;
  title: string;
  detailTitle: string;
  detailValue: string;
  detailDescription: string;
  toneClassName?: string;
};

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(1)}%`;
}

function formatPercentCompact(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(2).replace(".", ",")}%`;
}

function formatGiB(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(2)} GiB`;
}

function formatGiBCompact(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return value.toFixed(2);
}

function formatUsedTotalGiBCompact(used: number | null | undefined, total: number | null | undefined) {
  return `${formatGiBCompact(used)} / ${formatGiB(total)}`;
}

function formatMiB(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} MiB`;
}

function formatCompactMemoryMiB(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} GiB`;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} MiB`;
}

function simplifyGpuName(name: string | null | undefined) {
  const normalized = String(name || "")
    .replace(/nvidia/gi, "")
    .replace(/geforce/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  return normalized || "GPU nije dostupan";
}

function formatContext(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return String(Math.round(value));
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

function buildContextTone(
  contextMismatch: boolean | null | undefined,
  configuredContext: number | null | undefined,
  effectiveProcessContext: number | null | undefined,
) {
  if (contextMismatch) {
    return "resource-chip-tone-context-mismatch";
  }
  if (
    typeof configuredContext === "number" &&
    Number.isFinite(configuredContext) &&
    typeof effectiveProcessContext === "number" &&
    Number.isFinite(effectiveProcessContext)
  ) {
    return "resource-chip-tone-context-ok";
  }
  return "resource-chip-tone-neutral";
}

function buildContextStatusLabel(
  contextMismatch: boolean | null | undefined,
  configuredContext: number | null | undefined,
  effectiveProcessContext: number | null | undefined,
) {
  if (contextMismatch) {
    return "Restart potreban";
  }
  if (
    typeof configuredContext === "number" &&
    Number.isFinite(configuredContext) &&
    typeof effectiveProcessContext === "number" &&
    Number.isFinite(effectiveProcessContext)
  ) {
    return "Usklađeno";
  }
  return "Čeka proveru";
}

type LiveResourceStripProps = {
  onOpenSettingsSection?: (sectionId: string) => void;
};

export function LiveResourceStrip({ onOpenSettingsSection }: LiveResourceStripProps) {
  const [observability, setObservability] = useState<ObservabilityPayload | null>(null);
  const [error, setError] = useState("");
  const [selectedMetricKey, setSelectedMetricKey] = useState<ResourceMetricKey | null>(null);

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
    () => observability?.system.gpuDevices.find((item) => item.selected) ?? observability?.system.gpuDevices[0] ?? null,
    [observability],
  );
  const hybridEstimate = useMemo(
    () =>
      estimateHybridRuntimeUsage(
        observability?.runtime.runtimeDiagnostics,
        observability?.runtime.selectedGpuTotalGiB ?? selectedGpu?.totalGiB ?? null,
      ),
    [observability, selectedGpu],
  );
  const contextFitEstimate = useMemo(
    () =>
      estimateContextFitFromKvBuffer(
        observability?.runtime.runtimeDiagnostics,
        null,
        observability?.runtime.selectedGpuTotalGiB ?? selectedGpu?.totalGiB ?? null,
      ),
    [observability, selectedGpu],
  );

  const metrics = useMemo<ResourceMetric[]>(() => {
    if (!observability) {
      return [];
    }

    const simplifiedGpuName = simplifyGpuName(selectedGpu?.name || observability.system.gpuName);
    const detailedGpuName = selectedGpu?.name || observability.system.gpuName || "GPU nije dostupan";
    const modeValue =
      observability.runtime.executionModeId === "hybrid-vram-ram" && hybridEstimate
        ? `Hibrid • +${formatCompactMemoryMiB(hybridEstimate.estimatedRamSpillMiB)} RAM`
        : observability.runtime.executionModeLabel || "Čeka potvrdu";
    const offloadValue =
      observability.runtime.executionModeId === "hybrid-vram-ram" &&
      hybridEstimate?.estimatedAdditionalVramToFitMiB != null
        ? `${observability.runtime.offloadLabel || "Čeka potvrdu"} • Puni GPU fit +${formatCompactMemoryMiB(
            hybridEstimate.estimatedAdditionalVramToFitMiB,
          )}`
        : observability.runtime.offloadLabel || "Čeka potvrdu";
    const configuredContext = observability.runtime.runtimeDiagnostics?.configuredContext ?? null;
    const effectiveProcessContext = observability.runtime.runtimeDiagnostics?.effectiveProcessContext ?? null;
    const contextMismatch = observability.runtime.runtimeDiagnostics?.contextMismatch === true;
    const contextAlignmentLabel = observability.runtime.runtimeDiagnostics?.contextAlignmentLabel || "Čeka proveru";
    const contextAlignmentSummary =
      observability.runtime.runtimeDiagnostics?.contextAlignmentSummary ||
      "Ovde vidiš da li zapisani config i živi runtime proces zaista rade sa istim context brojem.";
    const contextStatusLabel = buildContextStatusLabel(
      contextMismatch,
      configuredContext,
      effectiveProcessContext,
    );

    const result: ResourceMetric[] = [
      {
        key: "cpu",
        label: "CPU",
        value: formatPercentCompact(observability.system.cpuPercent),
        title: `CPU: ${formatPercent(observability.system.cpuPercent)}`,
        detailTitle: "CPU uživo",
        detailValue: formatPercent(observability.system.cpuPercent),
        detailDescription: "Ukupna iskorišćenost procesora cele mašine u ovom trenutku.",
      },
      {
        key: "ram",
        label: "RAM",
        value: formatUsedTotalGiBCompact(observability.system.ramUsedGiB, observability.system.ramTotalGiB),
        title: `RAM: ${formatGiB(observability.system.ramUsedGiB)} / ${formatGiB(observability.system.ramTotalGiB)}`,
        detailTitle: "Sistemski RAM",
        detailValue: `${formatGiB(observability.system.ramUsedGiB)} / ${formatGiB(observability.system.ramTotalGiB)}`,
        detailDescription: "Ukupna zauzetost fizičkog RAM-a cele mašine, ne samo model procesa.",
      },
      {
        key: "vram",
        label: "VRAM",
        value: formatUsedTotalGiBCompact(observability.system.vramUsedGiB, observability.system.vramTotalGiB),
        title: `VRAM: ${formatGiB(observability.system.vramUsedGiB)} / ${formatGiB(observability.system.vramTotalGiB)}`,
        detailTitle: "Dedicated GPU memorija",
        detailValue: `${formatGiB(observability.system.vramUsedGiB)} / ${formatGiB(observability.system.vramTotalGiB)}`,
        detailDescription: "Zauzetost dedicated GPU memorije izabranog GPU-a.",
      },
      {
        key: "mode",
        label: "Režim",
        value: modeValue,
        title:
          observability.runtime.executionModeId === "hybrid-vram-ram" && hybridEstimate
            ? `Režim: ${observability.runtime.executionModeLabel} | Procena RAM preliva: ${formatCompactMemoryMiB(
                hybridEstimate.estimatedRamSpillMiB,
              )}`
            : `Režim: ${observability.runtime.executionModeLabel || "Čeka potvrdu"}`,
        detailTitle: observability.runtime.executionModeLabel || "Čeka potvrdu",
        detailValue: modeValue,
        detailDescription:
          observability.runtime.executionModeId === "hybrid-vram-ram" && hybridEstimate
            ? `Procena RAM preliva je oko ${formatCompactMemoryMiB(
                hybridEstimate.estimatedRamSpillMiB,
              )}. To je aproksimacija na osnovu odnosa GPU slojeva i učitanog model buffer-a.`
            :
              observability.runtime.executionModeSummary ||
              "RuntimePilot još čeka dovoljno signala za preciznu klasifikaciju.",
        toneClassName: buildModeTone(observability.runtime.executionModeId),
      },
      {
        key: "offload",
        label: "Offload",
        value: offloadValue,
        title:
          observability.runtime.executionModeId === "hybrid-vram-ram" &&
          hybridEstimate?.estimatedAdditionalVramToFitMiB != null
            ? `Offload: ${observability.runtime.offloadLabel || "Čeka potvrdu"} | Još VRAM-a za puni GPU fit: ${formatCompactMemoryMiB(
                hybridEstimate.estimatedAdditionalVramToFitMiB,
              )}`
            : `Offload: ${observability.runtime.offloadLabel || "Čeka potvrdu"}`,
        detailTitle: observability.runtime.offloadLabel || "Čeka potvrdu",
        detailValue: observability.runtime.offloadSummary || observability.runtime.offloadLabel || "Čeka potvrdu",
        detailDescription:
          observability.runtime.executionModeId === "hybrid-vram-ram" &&
          hybridEstimate?.estimatedAdditionalVramToFitMiB != null
            ? `Za isti model i isti context trebalo bi približno još ${formatCompactMemoryMiB(
                hybridEstimate.estimatedAdditionalVramToFitMiB,
              )} VRAM-a da stane potpuno na GPU bez oslanjanja na RAM.`
            : observability.runtime.runtimeDiagnostics?.confirmedSummary ||
              observability.runtime.offloadSummary ||
              "Nema dodatnog offload detalja.",
        toneClassName: buildModeTone(observability.runtime.executionModeId),
      },
      {
        key: "context",
        label: "Context",
        value: `${contextStatusLabel} • ${formatContext(configuredContext)} / ${formatContext(
          effectiveProcessContext,
        )}`,
        title: `Context: Config ctx ${formatContext(configuredContext)} | Živi ctx ${formatContext(
          effectiveProcessContext,
        )}`,
        detailTitle: contextAlignmentLabel,
        detailValue: `Config ctx ${formatContext(configuredContext)} • Živi ctx ${formatContext(
          effectiveProcessContext,
        )}`,
        detailDescription: contextAlignmentSummary,
        toneClassName: buildContextTone(contextMismatch, configuredContext, effectiveProcessContext),
      },
      {
        key: "process",
        label: "Model proces",
        value: formatMiB(observability.runtime.runtimeProcessRamMiB),
        title: `Model proces: ${formatMiB(observability.runtime.runtimeProcessRamMiB)}`,
        detailTitle: "RAM aktivnog model procesa",
        detailValue: formatMiB(observability.runtime.runtimeProcessRamMiB),
        detailDescription: "Radni set aktivnog runtime procesa koji je sistem uspešno očitao.",
      },
      {
        key: "gpu",
        label: "GPU",
        value: `${simplifiedGpuName} • ${formatGiB(selectedGpu?.totalGiB ?? null)}`,
        title: `${detailedGpuName} | ${formatGiB(selectedGpu?.totalGiB ?? null)} ukupno`,
        detailTitle: detailedGpuName,
        detailValue: `${formatGiB(selectedGpu?.usedGiB ?? null)} / ${formatGiB(selectedGpu?.totalGiB ?? null)}`,
        detailDescription:
          selectedGpu?.utilizationPercent != null
            ? `GPU utilization je ${formatPercent(selectedGpu.utilizationPercent)}. Prikazano ime je skraćeno u traci da ostane mesta za druge stavke.`
            : "Prikazano ime je skraćeno u traci da ostane mesta za druge stavke.",
      },
    ];

    if (error) {
      result.push({
        key: "signal",
        label: "Signal",
        value: "Problem",
        title: error,
        detailTitle: "Signal greške",
        detailValue: "Živi resursi trenutno nisu dostupni",
        detailDescription: error,
        toneClassName: "resource-chip-tone-warm",
      });
    }

    return result;
  }, [error, hybridEstimate, observability, selectedGpu]);

  const selectedMetric = metrics.find((metric) => metric.key === selectedMetricKey) ?? null;
  const showVramFitAction =
    selectedMetric != null && ["vram", "mode", "offload", "context", "process", "gpu"].includes(selectedMetric.key);
  const detailHint =
    selectedMetric?.key === "mode" || selectedMetric?.key === "offload" || selectedMetric?.key === "context"
      ? contextFitEstimate?.suggestedContext
        ? `Procena govori da bi context oko ${contextFitEstimate.suggestedContext} tokena bio sledeći razuman pokušaj za čistiji GPU fit.`
        : contextFitEstimate?.contextOnlyCanFit === false
          ? "Samo spuštanje context-a verovatno nije dovoljno; pogledaj GPU layers override i po potrebi lakši quant/model."
          : "Za precizniju VRAM fit procenu pusti runtime da prijavi čitljiv KV buffer."
      : null;

  if (!observability && !error) {
    return null;
  }

  return (
    <section className="live-resource-strip" aria-label="Živi resursi sistema">
      <span className="status-label live-resource-strip-heading">Živi resursi</span>
      <div className="live-resource-inline-row">
        {metrics.map((metric) => {
          const isSelected = selectedMetric?.key === metric.key;
          return (
            <button
              key={metric.key}
              type="button"
              className={`live-resource-inline-item live-resource-inline-button ${metric.toneClassName || ""} ${
                isSelected ? "live-resource-inline-item-active" : ""
              }`}
              title={metric.title}
              aria-pressed={isSelected}
              onClick={() => {
                setSelectedMetricKey((current) => (current === metric.key ? null : metric.key));
              }}
            >
              <span className="live-resource-inline-label">{metric.label}</span>
              <strong className="live-resource-inline-value">{metric.value}</strong>
            </button>
          );
        })}
      </div>
      <div className="resource-chip-detail-panel">
        {selectedMetric ? (
          <>
            <span className="status-label">Detalj izabrane stavke</span>
            <strong className="resource-chip-detail-title">{selectedMetric.detailTitle}</strong>
            <strong className="resource-chip-detail-value">{selectedMetric.detailValue}</strong>
            <p className="helper-text">{selectedMetric.detailDescription}</p>
            {detailHint ? <p className="helper-text resource-chip-detail-hint">{detailHint}</p> : null}
            {showVramFitAction ? (
              <div className="resource-chip-detail-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => onOpenSettingsSection?.("vram-fit")}
                  disabled={!onOpenSettingsSection}
                >
                  Otvori VRAM tuning
                </button>
              </div>
            ) : null}
          </>
        ) : (
          <>
            <span className="status-label">Klikni stavku za pun detalj</span>
            <p className="helper-text">
              Gornji strip ostaje kompaktan, a pun kontekst za CPU, RAM, VRAM, režim, offload i GPU vidiš tek kada
              klikneš željenu stavku.
            </p>
          </>
        )}
      </div>
    </section>
  );
}
