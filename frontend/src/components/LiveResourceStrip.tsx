import { useEffect, useMemo, useState } from "react";

import { RuntimePilotIcon } from "./RuntimePilotIcon";
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
  icon: "cpu" | "memory" | "telemetry" | "runtime" | "control" | "models";
  value: string;
  meterPercent?: number | null;
  title: string;
  detailTitle: string;
  detailValue: string;
  detailDescription: string;
  toneClassName?: string;
};

export type LiveResourceStripSharedState = {
  error: string;
  observability: ObservabilityPayload | null;
  selectedMetricKey: ResourceMetricKey | null;
  setSelectedMetricKey: (
    value:
      | ResourceMetricKey
      | null
      | ((current: ResourceMetricKey | null) => ResourceMetricKey | null),
  ) => void;
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
  return `${formatGiBCompact(used)}/${formatGiBCompact(total)}`;
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

function clampPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return Math.max(0, Math.min(100, value));
}

function toUsagePercent(used: number | null | undefined, total: number | null | undefined) {
  if (
    typeof used !== "number" ||
    !Number.isFinite(used) ||
    typeof total !== "number" ||
    !Number.isFinite(total) ||
    total <= 0
  ) {
    return null;
  }
  return clampPercent((used / total) * 100);
}

function sumFiniteMiB(...values: Array<number | null | undefined>) {
  let total = 0;
  let found = false;
  for (const value of values) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      continue;
    }
    total += value;
    found = true;
  }
  return found ? total : null;
}

function formatGpuLayerShare(
  diagnostics: ObservabilityPayload["runtime"]["runtimeDiagnostics"] | null | undefined,
) {
  const gpuLayers = diagnostics?.confirmedGpuLayers;
  const totalLayers = diagnostics?.confirmedTotalLayers;
  if (
    typeof gpuLayers !== "number" ||
    !Number.isFinite(gpuLayers) ||
    typeof totalLayers !== "number" ||
    !Number.isFinite(totalLayers) ||
    totalLayers <= 0
  ) {
    return null;
  }
  return `${Math.round(gpuLayers)}/${Math.round(totalLayers)}`;
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
  compact?: boolean;
  state?: LiveResourceStripSharedState;
};

type LiveResourceStripViewProps = {
  compact: boolean;
  onOpenSettingsSection?: (sectionId: string) => void;
  state: LiveResourceStripSharedState;
};

export function useLiveResourceStripState(): LiveResourceStripSharedState {
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

  return {
    error,
    observability,
    selectedMetricKey,
    setSelectedMetricKey,
  };
}

function LiveResourceStripView({
  compact,
  onOpenSettingsSection,
  state,
}: LiveResourceStripViewProps) {
  const { error, observability, selectedMetricKey, setSelectedMetricKey } = state;

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

    const diagnostics = observability.runtime.runtimeDiagnostics;
    const simplifiedGpuName = simplifyGpuName(selectedGpu?.name || observability.system.gpuName);
    const detailedGpuName = selectedGpu?.name || observability.system.gpuName || "GPU nije dostupan";
    const configuredContext = diagnostics?.configuredContext ?? null;
    const effectiveProcessContext = diagnostics?.effectiveProcessContext ?? null;
    const contextMismatch = diagnostics?.contextMismatch === true;
    const contextAlignmentLabel = diagnostics?.contextAlignmentLabel || "Čeka proveru";
    const contextAlignmentSummary =
      diagnostics?.contextAlignmentSummary ||
      "Ovde vidiš da li zapisani config i živi runtime proces zaista rade sa istim context brojem.";
    const contextStatusLabel = buildContextStatusLabel(
      contextMismatch,
      configuredContext,
      effectiveProcessContext,
    );
    const gpuLayerShare = formatGpuLayerShare(diagnostics);
    const gpuLayerShareLabel = gpuLayerShare ? `${gpuLayerShare} na GPU-u` : "Čeka potvrdu";
    const totalGpuFootprintMiB = sumFiniteMiB(
      diagnostics?.modelBufferMiB,
      diagnostics?.kvBufferMiB,
      diagnostics?.computeBufferMiB,
    );
    const selectedGpuTotalMiB =
      typeof (observability.runtime.selectedGpuTotalGiB ?? selectedGpu?.totalGiB ?? null) === "number" &&
      Number.isFinite(observability.runtime.selectedGpuTotalGiB ?? selectedGpu?.totalGiB ?? null)
        ? (observability.runtime.selectedGpuTotalGiB ?? selectedGpu?.totalGiB ?? 0) * 1024
        : null;
    const cpuMappedMiB = diagnostics?.cpuMappedModelBufferMiB ?? null;
    const kvBufferMiB = diagnostics?.kvBufferMiB ?? null;
    const totalGpuFootprintLabel = formatCompactMemoryMiB(totalGpuFootprintMiB);
    const selectedGpuTotalLabel = formatGiB(observability.runtime.selectedGpuTotalGiB ?? selectedGpu?.totalGiB ?? null);
    const fullRuntimeFitsVram =
      totalGpuFootprintMiB != null && selectedGpuTotalMiB != null
        ? totalGpuFootprintMiB <= selectedGpuTotalMiB + 64
        : null;
    const gpuHoldsWholeModelButNotFullRuntime =
      observability.runtime.executionModeId === "gpu-vram" && fullRuntimeFitsVram === false;
    const offloadPercent =
      typeof diagnostics?.confirmedGpuLayers === "number" &&
      Number.isFinite(diagnostics.confirmedGpuLayers) &&
      typeof diagnostics?.confirmedTotalLayers === "number" &&
      Number.isFinite(diagnostics.confirmedTotalLayers) &&
      diagnostics.confirmedTotalLayers > 0
        ? clampPercent((diagnostics.confirmedGpuLayers / diagnostics.confirmedTotalLayers) * 100)
        : observability.runtime.executionModeId === "gpu-vram"
          ? 100
          : observability.runtime.executionModeId === "hybrid-vram-ram"
            ? 62
            : observability.runtime.executionModeId === "cpu-ram"
              ? 12
              : null;
    const modePercent =
      observability.runtime.executionModeId === "gpu-vram" && !gpuHoldsWholeModelButNotFullRuntime
        ? 92
        : gpuHoldsWholeModelButNotFullRuntime
          ? 61
        : observability.runtime.executionModeId === "hybrid-vram-ram"
          ? 58
          : observability.runtime.executionModeId === "cpu-ram"
            ? 24
            : 40;
    const contextPercent = contextMismatch
      ? 38
      : typeof configuredContext === "number" &&
          Number.isFinite(configuredContext) &&
          typeof effectiveProcessContext === "number" &&
          Number.isFinite(effectiveProcessContext)
        ? 86
        : 48;
    const processPercent = toUsagePercent(
      observability.runtime.runtimeProcessRamMiB,
      typeof observability.system.ramTotalGiB === "number" && Number.isFinite(observability.system.ramTotalGiB)
        ? observability.system.ramTotalGiB * 1024
        : null,
    );
    const gpuPercent = clampPercent(selectedGpu?.utilizationPercent ?? null) ?? toUsagePercent(selectedGpu?.usedGiB, selectedGpu?.totalGiB);

    let modeValue = observability.runtime.executionModeLabel || "Čeka potvrdu";
    let modeTitle = `Režim: ${observability.runtime.executionModeLabel || "Čeka potvrdu"}`;
    let modeDetailTitle = observability.runtime.executionModeLabel || "Čeka potvrdu";
    let modeDetailValue = observability.runtime.executionModeLabel || "Čeka potvrdu";
    let modeDetailDescription =
      observability.runtime.executionModeSummary || "RuntimePilot još čeka dovoljno signala za preciznu klasifikaciju.";

    if (observability.runtime.executionModeId === "gpu-vram" && gpuHoldsWholeModelButNotFullRuntime) {
      modeValue = `Ne staje • ${totalGpuFootprintLabel}/${selectedGpuTotalLabel}`;
      modeTitle = "Režim: GPU drži model, ali ceo runtime ne staje u VRAM";
      modeDetailTitle = "Ne staje kompletan runtime u VRAM";
      modeDetailValue =
        totalGpuFootprintMiB != null
          ? `${totalGpuFootprintLabel} / ${selectedGpuTotalLabel} VRAM u radu`
          : "GPU drži model, ali brojke ne potvrđuju pun VRAM fit";
      modeDetailDescription = [
        "Svi slojevi modela jesu potvrđeni na GPU-u, ali ukupan radni otisak ne staje u raspoloživi VRAM.",
        totalGpuFootprintMiB != null
          ? `Trenutni model + KV cache + compute buffer traže oko ${totalGpuFootprintLabel} VRAM-a, a mašina trenutno ima ${selectedGpuTotalLabel}.`
          : null,
        kvBufferMiB != null
          ? `KV cache je prijavljen na GPU-u i trenutno zauzima oko ${formatCompactMemoryMiB(kvBufferMiB)}.`
          : null,
        "To znači: težine modela jesu na GPU-u, ali ceo runtime nije čist VRAM fit.",
        cpuMappedMiB != null
          ? `Sistemski RAM koji vidiš (~${formatCompactMemoryMiB(cpuMappedMiB)}) i dalje je samo mapiranje i pomoćni baferi, ali glavni problem ovde je što prijavljeni GPU otisak prelazi kapacitet VRAM-a.`
          : "Glavni problem ovde nije mapiranje u RAM, nego to što prijavljeni GPU otisak prelazi kapacitet VRAM-a.",
      ]
        .filter(Boolean)
        .join(" ");
    } else if (observability.runtime.executionModeId === "gpu-vram") {
      modeValue = "Staje u VRAM";
      modeTitle = gpuLayerShare
        ? `Režim: model staje u VRAM | ${gpuLayerShareLabel}`
        : "Režim: model staje u VRAM";
      modeDetailTitle = "Model staje u VRAM";
      modeDetailValue =
        totalGpuFootprintMiB != null
          ? `${totalGpuFootprintLabel} / ${selectedGpuTotalLabel} VRAM u radu`
          : "Svi slojevi modela su na GPU-u";
      modeDetailDescription = [
        "Svi slojevi modela su potvrđeni na GPU-u, pa jezgro modela staje u VRAM.",
        totalGpuFootprintMiB != null
          ? `Trenutni model + KV cache + compute buffer zauzimaju oko ${totalGpuFootprintLabel} VRAM-a.`
          : null,
        kvBufferMiB != null ? `KV cache je prijavljen na GPU-u i trenutno zauzima oko ${formatCompactMemoryMiB(kvBufferMiB)}.` : null,
        cpuMappedMiB != null
          ? `Sistemski RAM se i dalje koristi samo za mapiranje i pomoćne bafere. Trenutno je to oko ${formatCompactMemoryMiB(cpuMappedMiB)}, ali to nije znak da je deo modela ispao iz VRAM-a.`
          : "Sistemski RAM se i dalje koristi samo za mapiranje i pomoćne bafere.",
      ]
        .filter(Boolean)
        .join(" ");
    } else if (observability.runtime.executionModeId === "hybrid-vram-ram" && hybridEstimate) {
      modeValue = `Ne staje • +${formatCompactMemoryMiB(hybridEstimate.estimatedRamSpillMiB)} RAM`;
      modeTitle = `Režim: nije sve stalo u VRAM | RAM preliv ${formatCompactMemoryMiB(hybridEstimate.estimatedRamSpillMiB)}`;
      modeDetailTitle = "Ne staje u VRAM";
      modeDetailValue = gpuLayerShare ? `${gpuLayerShareLabel} • +${formatCompactMemoryMiB(hybridEstimate.estimatedRamSpillMiB)} RAM` : `+${formatCompactMemoryMiB(hybridEstimate.estimatedRamSpillMiB)} RAM`;
      modeDetailDescription = [
        `Nije sve stalo u VRAM. Deo modela ili radnih bafera trenutno se oslanja na sistemski RAM, a procena preliva je oko ${formatCompactMemoryMiB(hybridEstimate.estimatedRamSpillMiB)}.`,
        hybridEstimate.estimatedAdditionalVramToFitMiB != null
          ? `Za čist GPU fit trebalo bi još približno ${formatCompactMemoryMiB(hybridEstimate.estimatedAdditionalVramToFitMiB)} VRAM-a.`
          : null,
        kvBufferMiB != null ? `KV cache je već prijavljen na GPU-u i trenutno zauzima oko ${formatCompactMemoryMiB(kvBufferMiB)}.` : null,
      ]
        .filter(Boolean)
        .join(" ");
    } else if (observability.runtime.executionModeId === "cpu-ram") {
      modeValue = "Van VRAM-a";
      modeTitle = "Režim: model nije potvrđen na GPU-u";
      modeDetailTitle = "Model nije na GPU-u";
      modeDetailValue = "CPU + RAM";
      modeDetailDescription =
        "Runtime trenutno nema potvrđen GPU offload, pa model radi preko CPU-a i sistemskog RAM-a.";
    }

    let offloadValue = observability.runtime.offloadLabel || "Čeka potvrdu";
    let offloadTitle = `Offload: ${observability.runtime.offloadLabel || "Čeka potvrdu"}`;
    let offloadDetailTitle = observability.runtime.offloadLabel || "Čeka potvrdu";
    let offloadDetailValue = observability.runtime.offloadSummary || observability.runtime.offloadLabel || "Čeka potvrdu";
    let offloadDetailDescription =
      diagnostics?.confirmedSummary || observability.runtime.offloadSummary || "Nema dodatnog offload detalja.";

    if (observability.runtime.executionModeId === "gpu-vram" && gpuHoldsWholeModelButNotFullRuntime) {
      offloadValue = gpuLayerShareLabel;
      offloadTitle = "Offload: svi slojevi jesu na GPU-u, ali nema punog VRAM fit-a";
      offloadDetailTitle = "GPU drži model, ali VRAM je premali";
      offloadDetailValue =
        totalGpuFootprintMiB != null
          ? `${totalGpuFootprintLabel} traženo / ${selectedGpuTotalLabel} dostupno`
          : "Svi slojevi jesu na GPU-u";
      offloadDetailDescription = [
        gpuLayerShare
          ? `Na GPU-u je potvrđeno svih ${gpuLayerShare} slojeva modela.`
          : "GPU offload je potvrđen i model težine jesu na GPU-u.",
        kvBufferMiB != null
          ? `KV cache je takođe na GPU-u (~${formatCompactMemoryMiB(kvBufferMiB)}).`
          : null,
        totalGpuFootprintMiB != null
          ? `Ali model + KV cache + compute buffer po prijavljenim brojkama prelaze raspoloživi VRAM (${totalGpuFootprintLabel} naspram ${selectedGpuTotalLabel}), pa ovo nije pun VRAM fit.`
          : "Ali runtime brojke ne potvrđuju da ceo radni otisak staje u VRAM.",
        cpuMappedMiB != null
          ? `Sistemski RAM (~${formatCompactMemoryMiB(cpuMappedMiB)}) ovde nije glavni signal problema; glavni signal je sam GPU otisak.`
          : null,
      ]
        .filter(Boolean)
        .join(" ");
    } else if (observability.runtime.executionModeId === "gpu-vram") {
      offloadValue = gpuLayerShareLabel;
      offloadTitle = `Offload: ${gpuLayerShareLabel}`;
      offloadDetailTitle = "GPU drži ceo model";
      offloadDetailValue = gpuLayerShare ? `${gpuLayerShare} slojeva na GPU-u` : "GPU offload potvrđen";
      offloadDetailDescription = [
        gpuLayerShare
          ? `GPU offload je potvrđen i svih ${gpuLayerShare} slojeva modela su na GPU-u.`
          : "GPU offload je potvrđen i model je na GPU-u.",
        kvBufferMiB != null ? `KV cache je takođe prijavljen na GPU-u (~${formatCompactMemoryMiB(kvBufferMiB)}).` : null,
        cpuMappedMiB != null
          ? `Sistemski RAM pomaže samo kroz mapiranje i pomoćne bafere (~${formatCompactMemoryMiB(cpuMappedMiB)}), ne zato što je deo modela ostao van VRAM-a.`
          : "Sistemski RAM pomaže samo kroz mapiranje i pomoćne bafere, ne zato što je deo modela ostao van VRAM-a.",
      ]
        .filter(Boolean)
        .join(" ");
    } else if (observability.runtime.executionModeId === "hybrid-vram-ram" && hybridEstimate) {
      offloadValue = gpuLayerShareLabel;
      offloadTitle = `Offload: ${gpuLayerShareLabel} | RAM preliv ${formatCompactMemoryMiB(hybridEstimate.estimatedRamSpillMiB)}`;
      offloadDetailTitle = "GPU + RAM zajedno";
      offloadDetailValue = gpuLayerShare ? `${gpuLayerShare} slojeva na GPU-u` : "RAM pomaže GPU-u";
      offloadDetailDescription = [
        gpuLayerShare
          ? `Na GPU-u je potvrđeno ${gpuLayerShare} slojeva, ali nije sve stalo u VRAM.`
          : "GPU učestvuje u radu modela, ali nije sve stalo u VRAM.",
        `Trenutni RAM preliv procenjen je na oko ${formatCompactMemoryMiB(hybridEstimate.estimatedRamSpillMiB)}.`,
        hybridEstimate.estimatedAdditionalVramToFitMiB != null
          ? `Za čist GPU fit nedostaje još približno ${formatCompactMemoryMiB(hybridEstimate.estimatedAdditionalVramToFitMiB)} VRAM-a.`
          : null,
      ]
        .filter(Boolean)
        .join(" ");
    } else if (observability.runtime.executionModeId === "cpu-ram") {
      offloadValue = "GPU ne drži model";
      offloadTitle = "Offload: GPU ne drži model";
      offloadDetailTitle = "GPU nije uključen u model";
      offloadDetailValue = "CPU + RAM";
      offloadDetailDescription =
        "GPU offload nije potvrđen, pa se model oslanja na CPU i sistemski RAM.";
    }

    const result: ResourceMetric[] = [
      {
        key: "cpu",
        label: "CPU",
        icon: "cpu",
        value: formatPercentCompact(observability.system.cpuPercent),
        meterPercent: clampPercent(observability.system.cpuPercent),
        title: `CPU: ${formatPercent(observability.system.cpuPercent)}`,
        detailTitle: "CPU uživo",
        detailValue: formatPercent(observability.system.cpuPercent),
        detailDescription: "Ukupna iskorišćenost procesora cele mašine u ovom trenutku.",
      },
      {
        key: "ram",
        label: "RAM",
        icon: "memory",
        value: formatUsedTotalGiBCompact(observability.system.ramUsedGiB, observability.system.ramTotalGiB),
        meterPercent: toUsagePercent(observability.system.ramUsedGiB, observability.system.ramTotalGiB),
        title: `RAM: ${formatGiB(observability.system.ramUsedGiB)} / ${formatGiB(observability.system.ramTotalGiB)}`,
        detailTitle: "Sistemski RAM",
        detailValue: `${formatGiB(observability.system.ramUsedGiB)} / ${formatGiB(observability.system.ramTotalGiB)}`,
        detailDescription: "Ukupna zauzetost fizičkog RAM-a cele mašine, ne samo model procesa.",
      },
      {
        key: "vram",
        label: "VRAM",
        icon: "memory",
        value: formatUsedTotalGiBCompact(observability.system.vramUsedGiB, observability.system.vramTotalGiB),
        meterPercent: toUsagePercent(observability.system.vramUsedGiB, observability.system.vramTotalGiB),
        title: `VRAM: ${formatGiB(observability.system.vramUsedGiB)} / ${formatGiB(observability.system.vramTotalGiB)}`,
        detailTitle: "Dedicated GPU memorija",
        detailValue: `${formatGiB(observability.system.vramUsedGiB)} / ${formatGiB(observability.system.vramTotalGiB)}`,
        detailDescription: "Zauzetost dedicated GPU memorije izabranog GPU-a.",
      },
      {
        key: "mode",
        label: "Režim",
        icon: "runtime",
        value: modeValue,
        meterPercent: modePercent,
        title: modeTitle,
        detailTitle: modeDetailTitle,
        detailValue: modeDetailValue,
        detailDescription: modeDetailDescription,
        toneClassName: gpuHoldsWholeModelButNotFullRuntime
          ? "resource-chip-tone-warm"
          : buildModeTone(observability.runtime.executionModeId),
      },
      {
        key: "offload",
        label: "Offload",
        icon: "control",
        value: offloadValue,
        meterPercent: offloadPercent,
        title: offloadTitle,
        detailTitle: offloadDetailTitle,
        detailValue: offloadDetailValue,
        detailDescription: offloadDetailDescription,
        toneClassName: gpuHoldsWholeModelButNotFullRuntime
          ? "resource-chip-tone-warm"
          : buildModeTone(observability.runtime.executionModeId),
      },
      {
        key: "context",
        label: "Context",
        icon: "control",
        value: `${contextStatusLabel} • ${formatContext(configuredContext)} / ${formatContext(
          effectiveProcessContext,
        )}`,
        meterPercent: contextPercent,
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
        icon: "models",
        value: formatMiB(observability.runtime.runtimeProcessRamMiB),
        meterPercent: processPercent,
        title: `Model proces: ${formatMiB(observability.runtime.runtimeProcessRamMiB)}`,
        detailTitle: "RAM aktivnog model procesa",
        detailValue: formatMiB(observability.runtime.runtimeProcessRamMiB),
        detailDescription: "Radni set aktivnog runtime procesa koji je sistem uspešno očitao.",
      },
      {
        key: "gpu",
        label: "GPU",
        icon: "telemetry",
        value: `${simplifiedGpuName} • ${formatGiB(selectedGpu?.totalGiB ?? null)}`,
        meterPercent: gpuPercent,
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
        icon: "telemetry",
        value: "Problem",
        meterPercent: 18,
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
      ? observability?.runtime.executionModeId === "gpu-vram"
        ? observability.runtime.runtimeDiagnostics?.kvBufferMiB != null
          ? "Trenutni KV buffer je već prijavljen, pa ovde vidiš realan GPU fit za ovaj runtime."
          : "KV buffer još nije prijavljen, pa će procena GPU zauzeća biti preciznija posle prve ozbiljnije generacije."
        : contextFitEstimate?.suggestedContext
          ? `Ako želiš manji RAM preliv, sledeći razuman pokušaj je context oko ${contextFitEstimate.suggestedContext} tokena.`
          : contextFitEstimate?.contextOnlyCanFit === false
            ? "Ni samo manji context verovatno nije dovoljan; tada treba još VRAM-a ili lakši quant/model."
            : "KV buffer još nije prijavljen, pa će procena biti preciznija kada runtime napravi čitljiv GPU trag."
      : null;

  if (!observability && !error) {
    return null;
  }

  return (
    <section
      className={`live-resource-strip live-resource-rack runtimepilot-command-deck${
        compact ? " live-resource-strip-compact" : ""
      }`}
      aria-label="Živi resursi sistema"
    >
      <div className="live-resource-rack-head">
        <span className="status-label live-resource-strip-heading">Živi resursi</span>
        <span className="live-resource-rack-helper">Instrument tabla sistema</span>
      </div>
      <div className="live-resource-inline-row live-resource-rack-row">
        {metrics.map((metric) => {
          const isSelected = selectedMetric?.key === metric.key;
          const usesCompactNumericValue = metric.key === "ram" || metric.key === "vram";
          return (
            <button
              key={metric.key}
              type="button"
              className={`live-resource-inline-item live-resource-inline-button ${
                usesCompactNumericValue ? "live-resource-inline-item-compact-numeric" : ""
              } ${metric.toneClassName || ""} ${isSelected ? "live-resource-inline-item-active" : ""}`}
              title={metric.title}
              aria-pressed={isSelected}
              onClick={() => {
                setSelectedMetricKey((current) => (current === metric.key ? null : metric.key));
              }}
            >
              <span className="live-resource-inline-label">
                <RuntimePilotIcon className="live-resource-inline-icon" name={metric.icon} />
                <span>{metric.label}</span>
              </span>
              <strong className="live-resource-inline-value">{metric.value}</strong>
              <span className="live-resource-inline-meter" aria-hidden="true">
                <span className="live-resource-inline-meter-scale" />
                <span
                  className="live-resource-inline-meter-fill"
                  style={{ width: `${metric.meterPercent ?? 0}%` }}
                />
              </span>
            </button>
          );
        })}
      </div>
      <div
        className={`resource-chip-detail-panel live-resource-rack-detail ${
          selectedMetric ? "resource-chip-detail-panel-expanded" : "resource-chip-detail-panel-idle"
        }`}
      >
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
            <p className="helper-text resource-chip-detail-idle-copy">
              Izaberi CPU, RAM, VRAM, režim, offload ili GPU kada želiš pun kontekst.
            </p>
          </>
        )}
      </div>
    </section>
  );
}

function LiveResourceStripWithInternalState({
  compact = false,
  onOpenSettingsSection,
}: Omit<LiveResourceStripProps, "state">) {
  const liveResourceStripState = useLiveResourceStripState();

  return (
    <LiveResourceStripView
      compact={compact}
      onOpenSettingsSection={onOpenSettingsSection}
      state={liveResourceStripState}
    />
  );
}

export function LiveResourceStrip({
  compact = false,
  onOpenSettingsSection,
  state,
}: LiveResourceStripProps) {
  if (state) {
    return (
      <LiveResourceStripView
        compact={compact}
        onOpenSettingsSection={onOpenSettingsSection}
        state={state}
      />
    );
  }

  return (
    <LiveResourceStripWithInternalState
      compact={compact}
      onOpenSettingsSection={onOpenSettingsSection}
    />
  );
}
