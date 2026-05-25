import type {
  CompatibilityCheckRequest,
  ModelEntry,
  ModelsPayload,
} from "./types";

export type CompatibilityLaunchTarget = {
  title: string;
  request: CompatibilityCheckRequest;
};

export function buildCompatibilityRequestFromModelEntry(
  item: ModelEntry,
): CompatibilityCheckRequest {
  const filename = item.filename || item.id;
  const quantizationMatch = filename.match(
    /(UD-[A-Z0-9_]+|IQ[0-9A-Z_]+|Q[2-9]_[A-Z0-9_]+|Q[2-9][A-Z0-9_]+)/i,
  );
  const quantization = quantizationMatch
    ? quantizationMatch[1].toUpperCase()
    : "unknown";
  const minimumVramGiB =
    item.minimumGpuMiB === null || item.minimumGpuMiB === undefined
      ? null
      : Number((item.minimumGpuMiB / 1024).toFixed(2));
  const recommendedVramGiB =
    item.recommendedGpuMiB === null || item.recommendedGpuMiB === undefined
      ? null
      : Number((item.recommendedGpuMiB / 1024).toFixed(2));
  const joined = `${item.id} ${item.label} ${filename}`.toLowerCase();

  return {
    model: {
      id: item.id,
      label: item.label,
      filename,
      family: item.family ?? "Unknown",
      quantization,
      approxSizeGiB: item.approxSizeGiB ?? null,
      minimumRamGiB: item.minimumRamGiB ?? null,
      minimumVramGiB,
      recommendedVramGiB,
      contextWindow: joined.includes("qwen3.6") ? 262144 : 131072,
      defaultOutputTokens: 4096,
      moe: joined.includes("a3b") || joined.includes("moe"),
      mtp: item.mtpStatus === "has-mtp",
      turboQuantReady: /^(UD-|IQ|Q2|Q3|Q4)/.test(quantization),
    },
  };
}

export function flattenModelsPayload(payload: ModelsPayload): ModelEntry[] {
  return [
    ...payload.curated,
    ...payload.local,
    ...payload.huggingFace,
    ...payload.unsloth,
  ];
}
