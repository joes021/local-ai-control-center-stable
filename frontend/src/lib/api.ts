import type {
  ActionResult,
  BrowserAddToLocalResult,
  BrowserCatalogPayload,
  BrowserCatalogItem,
  BrowserCompatibilityPayload,
  BrowserRefreshResult,
  BenchmarkBattery,
  BenchmarkPayload,
  BenchmarkScenario,
  BenchmarkRunStatusPayload,
  DownloadProgressPayload,
  CompatibilityApplyResponse,
  CompatibilityCheckRequest,
  ModelActionStatusPayload,
  ModelsPayload,
  OpenCodeStatusPayload,
  OpenCodeStepSchemaPayload,
  OpenCodeStepValues,
  ServerStatusPayload,
  SettingsProfileValues,
  SettingsPayload,
  StatusPayload,
  TurboQuantConfig,
  TurboQuantSchemaPayload,
  UpdateProgressPayload,
} from "./types";

export type BrowserCatalogQuery = {
  source?: string;
  search?: string;
  family?: string;
  quant?: string;
  size?: string;
  mtp?: string;
  date?: string;
  sort?: string;
  limit?: number;
};

export async function fetchStatus(): Promise<StatusPayload> {
  const response = await fetch("/api/status");
  if (!response.ok) {
    throw new Error(`Status request failed: ${response.status}`);
  }
  return response.json() as Promise<StatusPayload>;
}

export async function fetchBenchmark(): Promise<BenchmarkPayload> {
  const response = await fetch("/api/benchmark");
  if (!response.ok) {
    throw new Error(`Benchmark request failed: ${response.status}`);
  }
  return response.json() as Promise<BenchmarkPayload>;
}

export async function runSelectedBenchmark(scenarioId: string): Promise<{ status: string; summary: string; runId?: string }> {
  return postJson("/api/benchmark/run-selected", { scenarioId });
}

export async function runBatteryBenchmark(batteryId: string): Promise<{ status: string; summary: string; runId?: string }> {
  return postJson("/api/benchmark/run-battery", { batteryId });
}

export async function fetchBenchmarkRunStatus(): Promise<BenchmarkRunStatusPayload> {
  const response = await fetch("/api/benchmark/run-status");
  if (!response.ok) {
    throw new Error(`Benchmark run status request failed: ${response.status}`);
  }
  return response.json() as Promise<BenchmarkRunStatusPayload>;
}

export async function saveBenchmarkBattery(
  name: string,
  scenarios: BenchmarkScenario[],
): Promise<{ status: string; summary: string; battery?: BenchmarkBattery }> {
  return postJson("/api/benchmark/batteries/save", { name, scenarios });
}

export async function loadBenchmarkBattery(
  batteryId: string,
): Promise<{ status: string; summary: string; battery?: BenchmarkBattery }> {
  return postJson("/api/benchmark/batteries/load", { batteryId });
}

export async function restoreDefaultBenchmarkTests(): Promise<{ status: string; summary: string; battery?: BenchmarkBattery }> {
  return postJson("/api/benchmark/batteries/restore-defaults", {});
}

export async function clearBenchmarkHistory(): Promise<{ status: string; summary: string }> {
  return postJson("/api/benchmark/clear-history", {});
}

export async function fetchServerStatus(): Promise<ServerStatusPayload> {
  const response = await fetch("/api/server/status");
  if (!response.ok) {
    throw new Error(`Server status request failed: ${response.status}`);
  }
  return response.json() as Promise<ServerStatusPayload>;
}

export async function fetchModels(): Promise<ModelsPayload> {
  const response = await fetch("/api/models");
  if (!response.ok) {
    throw new Error(`Models request failed: ${response.status}`);
  }
  return response.json() as Promise<ModelsPayload>;
}

export async function fetchBrowserCatalog(query?: BrowserCatalogQuery): Promise<BrowserCatalogPayload> {
  const params = new URLSearchParams();
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }
      params.set(key, String(value));
    }
  }

  const endpoint = "/api/browser/catalog";
  const response = await fetch(params.size ? `${endpoint}?${params.toString()}` : endpoint, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`GET ${endpoint} failed: ${response.status}`);
  }
  return response.json() as Promise<BrowserCatalogPayload>;
}

export async function refreshBrowserCatalog(source?: string): Promise<BrowserRefreshResult> {
  const payload = source ? { source } : {};
  return postJson<typeof payload, BrowserRefreshResult>("/api/browser/catalog/refresh", payload);
}

export async function addBrowserModelToLocal(payload: {
  source: string;
  repoId: string;
  filename: string;
  label: string;
  family: string;
}): Promise<BrowserAddToLocalResult> {
  return postJson<typeof payload, BrowserAddToLocalResult>("/api/browser/catalog/add", payload);
}

export async function downloadBrowserModel(modelId: string): Promise<ActionResult> {
  return postJson<{ modelId: string }, ActionResult>("/api/models/download", { modelId });
}

export async function downloadBrowserCatalogModel(payload: {
  source: string;
  repoId: string;
  filename: string;
  label: string;
  family: string;
}): Promise<ActionResult> {
  return postJson<typeof payload, ActionResult>("/api/browser/catalog/download", payload);
}

export async function checkBrowserCompatibility(modelId: string): Promise<BrowserCompatibilityPayload> {
  return postJson<CompatibilityCheckRequest, BrowserCompatibilityPayload>("/api/compatibility/check", {
    catalogModelId: modelId,
  });
}

export async function checkModelCompatibility(
  payload: CompatibilityCheckRequest,
): Promise<BrowserCompatibilityPayload> {
  return postJson<CompatibilityCheckRequest, BrowserCompatibilityPayload>("/api/compatibility/check", payload);
}

export async function applyCompatibilityAction(payload: {
  catalogModelId?: string;
  model?: BrowserCatalogItem | Record<string, unknown>;
  overrides?: CompatibilityCheckRequest["overrides"];
  action: {
    kind: string;
    value?: string | number;
    ctk?: string;
    ctv?: string;
    actions?: Array<Record<string, unknown>>;
    requiresConfirmation?: boolean;
  };
}): Promise<CompatibilityApplyResponse> {
  return postJson<typeof payload, CompatibilityApplyResponse>("/api/compatibility/apply", payload);
}

export async function fetchDownloadProgress(): Promise<DownloadProgressPayload> {
  const response = await fetch("/api/models/download-progress", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Download progress request failed: ${response.status}`);
  }
  return response.json() as Promise<DownloadProgressPayload>;
}

export async function fetchModelActionStatus(actionId: string): Promise<ModelActionStatusPayload> {
  const response = await fetch(`/api/models/action-status/${encodeURIComponent(actionId)}`);
  if (!response.ok) {
    throw new Error(`Model action status request failed: ${response.status}`);
  }
  return response.json() as Promise<ModelActionStatusPayload>;
}

export async function awaitModelActionResult(
  initial: ActionResult,
  onUpdate?: (result: ActionResult) => void,
  maxAttempts = 60,
  delayMs = 1000,
): Promise<ActionResult> {
  if (initial.status !== "accepted" || !initial.actionId) {
    return initial;
  }

  onUpdate?.(initial);
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    const statusPayload = await fetchModelActionStatus(initial.actionId);
    const nextResult =
      statusPayload.result ??
      ({
        status: statusPayload.status,
        action: "models-action-status",
        actionId: statusPayload.actionId,
        summary: statusPayload.summary,
        details: { returncode: statusPayload.status === "error" ? 1 : 0, stdout: "", stderr: "" },
      } satisfies ActionResult);
    onUpdate?.(nextResult);
    if (statusPayload.isDone) {
      return nextResult;
    }
  }

  return {
    status: "error",
    action: "models-action-timeout",
    actionId: initial.actionId,
    summary: "Model akcija nije zavrsena na vreme. Probaj refresh liste.",
    details: {
      returncode: 1,
      stdout: "",
      stderr: "Model akcija nije zavrsena na vreme. Probaj refresh liste.",
    },
  };
}

export async function fetchSettings(): Promise<SettingsPayload> {
  const response = await fetch("/api/settings");
  if (!response.ok) {
    throw new Error(`Settings request failed: ${response.status}`);
  }
  return response.json() as Promise<SettingsPayload>;
}

export async function applySettings(payload: SettingsPayload): Promise<ActionResult> {
  return postJson("/api/settings/apply", payload);
}

export async function saveSettingsProfile(payload: {
  name: string;
  settings: SettingsProfileValues;
}): Promise<ActionResult> {
  return postJson("/api/settings/profiles/save", payload);
}

export async function deleteSettingsProfile(profileId: string): Promise<ActionResult> {
  return postJson("/api/settings/profiles/delete", { profileId });
}

export async function fetchTurboQuantSchema(): Promise<TurboQuantSchemaPayload> {
  const response = await fetch("/api/settings/turboquant");
  if (!response.ok) {
    throw new Error(`TurboQuant schema request failed: ${response.status}`);
  }
  return response.json() as Promise<TurboQuantSchemaPayload>;
}

export async function fetchOpenCodeStatus(): Promise<OpenCodeStatusPayload> {
  const response = await fetch("/api/opencode/status");
  if (!response.ok) {
    throw new Error(`OpenCode status request failed: ${response.status}`);
  }
  return response.json() as Promise<OpenCodeStatusPayload>;
}

export async function fetchOpenCodeStepSchema(): Promise<OpenCodeStepSchemaPayload> {
  const response = await fetch("/api/opencode/steps");
  if (!response.ok) {
    throw new Error(`OpenCode step schema request failed: ${response.status}`);
  }
  return response.json() as Promise<OpenCodeStepSchemaPayload>;
}

export async function applyOpenCodeSettings(payload: {
  profile: string;
  context: number;
  outputTokens: number;
  workingDirectory: string;
  buildSteps: number;
  planSteps: number;
  generalSteps: number;
  exploreSteps: number;
  securityMode: string;
  capabilityMode: string;
}): Promise<ActionResult> {
  return postJson("/api/opencode/settings/apply", payload);
}

export async function openOpenCode(profile: string): Promise<ActionResult> {
  return postJson("/api/opencode/open", { profile });
}

export async function saveOpenCodeStepPreset(payload: {
  name: string;
  steps: OpenCodeStepValues;
}): Promise<ActionResult> {
  return postJson("/api/opencode/steps/presets/save", payload);
}

export async function deleteOpenCodeStepPreset(presetId: string): Promise<ActionResult> {
  return postJson("/api/opencode/steps/presets/delete", { presetId });
}

export async function saveTurboQuantConfig(payload: TurboQuantConfig): Promise<ActionResult> {
  return postJson("/api/settings/turboquant-config", payload);
}

export async function saveTurboQuantPreset(payload: {
  name: string;
  description: string;
  targetModelPattern: string;
  notes: string;
  settings: TurboQuantConfig;
}): Promise<ActionResult> {
  return postJson("/api/settings/turboquant-presets/save", payload);
}

export async function deleteTurboQuantPreset(presetId: string): Promise<ActionResult> {
  return postJson("/api/settings/turboquant-presets/delete", { presetId });
}

async function postJson<TRequest, TResponse>(
  url: string,
  body: TRequest,
  timeoutMs?: number,
): Promise<TResponse> {
  const controller = typeof AbortController !== "undefined" ? new AbortController() : undefined;
  const timeoutId =
    controller && timeoutMs
      ? window.setTimeout(() => controller.abort(), timeoutMs)
      : undefined;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: controller?.signal,
    });
    if (!response.ok) {
      throw new Error(`POST ${url} failed: ${response.status}`);
    }
    return response.json() as Promise<TResponse>;
  } finally {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
  }
}

async function getJsonFromCandidates<TResponse>(urls: string[]): Promise<TResponse> {
  let lastError: Error | null = null;

  for (const url of urls) {
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`GET ${url} failed: ${response.status}`);
      }
      return response.json() as Promise<TResponse>;
    } catch (reason: unknown) {
      lastError = reason instanceof Error ? reason : new Error(`GET ${url} failed`);
    }
  }

  throw lastError ?? new Error("No GET endpoint candidates were available.");
}

export async function activateModel(modelId: string): Promise<ActionResult> {
  return postJson("/api/models/activate", { modelId });
}

export async function downloadModel(modelId: string): Promise<ActionResult> {
  return postJson("/api/models/download", { modelId });
}

export async function addLocalModel(
  path: string,
  label: string,
  family: string,
): Promise<ActionResult> {
  return postJson("/api/models/add-local", { path, label, family });
}

export async function addHfModel(
  repo: string,
  filename: string,
  label: string,
  family: string,
): Promise<ActionResult> {
  return postJson("/api/models/add-hf", { repo, filename, label, family });
}

export async function addUnslothModel(
  repo: string,
  filename: string,
  label: string,
  family: string,
): Promise<ActionResult> {
  return postJson("/api/models/add-unsloth", { repo, filename, label, family });
}

export async function deleteModel(
  modelId: string,
  removeFile: boolean,
  removeRegistry: boolean,
): Promise<ActionResult> {
  return postJson("/api/models/delete", { modelId, removeFile, removeRegistry });
}

export async function fetchLogs(): Promise<ActionResult> {
  const response = await fetch("/api/logs");
  if (!response.ok) {
    throw new Error(`Logs request failed: ${response.status}`);
  }
  return response.json() as Promise<ActionResult>;
}

export async function runRepair(kind: string): Promise<ActionResult> {
  return postJson(`/api/repair/${kind}`, {});
}

export async function checkUpdates(): Promise<ActionResult> {
  const response = await fetch("/api/updates/check");
  if (!response.ok) {
    throw new Error(`Updates request failed: ${response.status}`);
  }
  return response.json() as Promise<ActionResult>;
}

export async function installUpdate(): Promise<ActionResult> {
  return postJson("/api/updates/install", {});
}

export async function fetchUpdateProgress(): Promise<UpdateProgressPayload> {
  const response = await fetch("/api/updates/progress", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Update progress request failed: ${response.status}`);
  }
  return response.json() as Promise<UpdateProgressPayload>;
}

export async function pickLocalGguf(): Promise<{ status: string; summary: string; path: string }> {
  return postJson("/api/system/pick-local-gguf", {});
}

export async function pickWorkingDirectory(): Promise<{ status: string; summary: string; path: string }> {
  return postJson("/api/system/pick-working-directory", {});
}

export async function selectRuntime(runtime: string): Promise<ActionResult> {
  return postJson("/api/runtime/select", { runtime });
}

export async function startServer(): Promise<ActionResult> {
  return postJson("/api/server/start", {});
}

export async function stopServer(): Promise<ActionResult> {
  return postJson("/api/server/stop", {});
}

export async function openServerWeb(): Promise<ActionResult> {
  return postJson("/api/server/open-web", {});
}
