import type { RuntimeDiagnostics } from "./types";

export type HybridRuntimeEstimate = {
  estimatedRamSpillMiB: number;
  estimatedFullGpuRequirementMiB: number | null;
  estimatedAdditionalVramToFitMiB: number | null;
};

export type RuntimeFitPreview = {
  currentGpuLayers: number;
  targetGpuLayers: number;
  totalLayers: number;
  estimatedModelBufferMiB: number | null;
  estimatedModelRamSpillMiB: number | null;
  estimatedKvBufferMiB: number | null;
  estimatedTotalGpuRequirementMiB: number | null;
  estimatedAdditionalVramToFitMiB: number | null;
};

export type ContextFitEstimate = {
  currentContext: number;
  suggestedContext: number | null;
  estimatedReductionPercent: number;
  estimatedFreedVramMiB: number;
  contextOnlyCanFit: boolean;
};

export function estimateAutoGpuLayersFromTotalGiB(selectedGpuTotalGiB: number | null | undefined): number {
  if (!isFiniteNumber(selectedGpuTotalGiB) || selectedGpuTotalGiB <= 0) {
    return 0;
  }
  const totalMemoryMiB = selectedGpuTotalGiB * 1024;
  if (totalMemoryMiB >= 24 * 1024) {
    return 99;
  }
  if (totalMemoryMiB >= 16 * 1024) {
    return 60;
  }
  if (totalMemoryMiB >= 12 * 1024) {
    return 40;
  }
  if (totalMemoryMiB >= 8 * 1024) {
    return 28;
  }
  if (totalMemoryMiB >= 6 * 1024) {
    return 20;
  }
  return 0;
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function sumFiniteNumbers(...values: Array<number | null | undefined>) {
  let total = 0;
  let found = false;
  for (const value of values) {
    if (!isFiniteNumber(value)) {
      continue;
    }
    total += value;
    found = true;
  }
  return found ? total : null;
}

export function estimateHybridRuntimeUsage(
  diagnostics: RuntimeDiagnostics | null | undefined,
  selectedGpuTotalGiB: number | null | undefined,
): HybridRuntimeEstimate | null {
  if (!diagnostics || diagnostics.executionModeId !== "hybrid-vram-ram") {
    return null;
  }

  const confirmedGpuLayers = diagnostics.confirmedGpuLayers ?? 0;
  const confirmedTotalLayers = diagnostics.confirmedTotalLayers ?? 0;
  const modelBufferMiB = diagnostics.modelBufferMiB;

  if (
    confirmedGpuLayers <= 0 ||
    confirmedTotalLayers <= confirmedGpuLayers ||
    !isFiniteNumber(modelBufferMiB) ||
    modelBufferMiB <= 0
  ) {
    return null;
  }

  const estimatedFullModelBufferMiB = modelBufferMiB * (confirmedTotalLayers / confirmedGpuLayers);
  const estimatedRamSpillMiB = Math.max(0, estimatedFullModelBufferMiB - modelBufferMiB);
  const currentGpuRequirementMiB = sumFiniteNumbers(
    diagnostics.modelBufferMiB,
    diagnostics.kvBufferMiB,
    diagnostics.computeBufferMiB,
  );
  const estimatedFullGpuRequirementMiB =
    currentGpuRequirementMiB != null ? currentGpuRequirementMiB + estimatedRamSpillMiB : null;
  const selectedGpuTotalMiB =
    isFiniteNumber(selectedGpuTotalGiB) && selectedGpuTotalGiB > 0 ? selectedGpuTotalGiB * 1024 : null;
  const estimatedAdditionalVramToFitMiB =
    estimatedFullGpuRequirementMiB != null && selectedGpuTotalMiB != null
      ? Math.max(0, estimatedFullGpuRequirementMiB - selectedGpuTotalMiB)
      : null;

  return {
    estimatedRamSpillMiB,
    estimatedFullGpuRequirementMiB,
    estimatedAdditionalVramToFitMiB,
  };
}

function normalizeContextValue(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return 0;
  }
  return Math.max(4096, Math.floor(value / 1024) * 1024);
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

export function estimateRuntimeFitPreview(
  diagnostics: RuntimeDiagnostics | null | undefined,
  currentContext: number | null | undefined,
  selectedGpuTotalGiB: number | null | undefined,
  targetGpuLayers: number | null | undefined,
  targetContext: number | null | undefined,
): RuntimeFitPreview | null {
  if (!diagnostics) {
    return null;
  }

  const confirmedGpuLayers = diagnostics.confirmedGpuLayers ?? 0;
  const totalLayers = diagnostics.confirmedTotalLayers ?? 0;
  const modelBufferMiB = diagnostics.modelBufferMiB;
  const currentContextValue = normalizeContextValue(Number(currentContext || 0));
  const targetContextValue = normalizeContextValue(Number(targetContext || currentContextValue || 0));

  if (confirmedGpuLayers <= 0 || totalLayers <= 0 || !isFiniteNumber(modelBufferMiB) || modelBufferMiB <= 0) {
    return null;
  }

  const safeTargetGpuLayers = clamp(Math.round(Number(targetGpuLayers || 0)), 0, totalLayers);
  const estimatedFullModelBufferMiB = modelBufferMiB * (totalLayers / confirmedGpuLayers);
  const estimatedModelBufferMiB = estimatedFullModelBufferMiB * (safeTargetGpuLayers / totalLayers);
  const estimatedModelRamSpillMiB = Math.max(0, estimatedFullModelBufferMiB - estimatedModelBufferMiB);
  const estimatedKvBufferMiB =
    isFiniteNumber(diagnostics.kvBufferMiB) && diagnostics.kvBufferMiB > 0 && currentContextValue > 0
      ? diagnostics.kvBufferMiB * (targetContextValue / currentContextValue)
      : diagnostics.kvBufferMiB;
  const estimatedTotalGpuRequirementMiB = sumFiniteNumbers(
    estimatedModelBufferMiB,
    estimatedKvBufferMiB,
    diagnostics.computeBufferMiB,
  );
  const selectedGpuTotalMiB =
    isFiniteNumber(selectedGpuTotalGiB) && selectedGpuTotalGiB > 0 ? selectedGpuTotalGiB * 1024 : null;
  const estimatedAdditionalVramToFitMiB =
    estimatedTotalGpuRequirementMiB != null && selectedGpuTotalMiB != null
      ? Math.max(0, estimatedTotalGpuRequirementMiB - selectedGpuTotalMiB)
      : null;

  return {
    currentGpuLayers: confirmedGpuLayers,
    targetGpuLayers: safeTargetGpuLayers,
    totalLayers,
    estimatedModelBufferMiB,
    estimatedModelRamSpillMiB,
    estimatedKvBufferMiB,
    estimatedTotalGpuRequirementMiB,
    estimatedAdditionalVramToFitMiB,
  };
}

export function estimateContextFitFromKvBuffer(
  diagnostics: RuntimeDiagnostics | null | undefined,
  currentContext: number | null | undefined,
  selectedGpuTotalGiB: number | null | undefined,
  additionalVramToFitOverrideMiB?: number | null,
): ContextFitEstimate | null {
  const hybridEstimate = estimateHybridRuntimeUsage(diagnostics, selectedGpuTotalGiB);
  const normalizedContext = normalizeContextValue(Number(currentContext || 0));
  const kvBufferMiB = diagnostics?.kvBufferMiB;
  const additionalVramToFitMiB =
    isFiniteNumber(additionalVramToFitOverrideMiB) && additionalVramToFitOverrideMiB >= 0
      ? additionalVramToFitOverrideMiB
      : hybridEstimate?.estimatedAdditionalVramToFitMiB;

  if (
    !hybridEstimate ||
    !isFiniteNumber(kvBufferMiB) ||
    kvBufferMiB <= 0 ||
    !isFiniteNumber(additionalVramToFitMiB) ||
    additionalVramToFitMiB <= 0 ||
    normalizedContext <= 0
  ) {
    return null;
  }

  const estimatedReductionPercent = Math.max(0, additionalVramToFitMiB / kvBufferMiB);
  const contextOnlyCanFit = estimatedReductionPercent < 1;
  const nextContext = contextOnlyCanFit
    ? normalizeContextValue(normalizedContext * (1 - estimatedReductionPercent))
    : null;

  return {
    currentContext: normalizedContext,
    suggestedContext: nextContext && nextContext < normalizedContext ? nextContext : null,
    estimatedReductionPercent,
    estimatedFreedVramMiB: Math.min(kvBufferMiB, additionalVramToFitMiB),
    contextOnlyCanFit,
  };
}
