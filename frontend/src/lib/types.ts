export type StatusPayload = {
  hostPlatform: string;
  hostPlatformLabel: string;
  hostShellLabel: string;
  version: string;
  health: string;
  activeModel: string;
  profile: string;
  uiPort: number;
  uiUrl: string;
  localUrl: string;
  tailscaleUrl: string;
  accessMode: string;
  bindHost: string;
  runtimeStatus: string;
  runtimeSummary: string;
  activeRuntimeLabel: string;
  requestedRuntimeLabel: string;
  runtimeSelectionSummary: string;
  runtimeSelectionSource: string;
  availableRuntimes: string[];
  llamaRuntimeAvailable: boolean;
  turboQuantRuntimeAvailable: boolean;
  llamaCppStatus: string;
  turboQuantStatus: string;
  turboQuantReason: string;
  turboQuantDisplayState: string;
  turboQuantSummary: string;
  turboQuantGuidance: string;
  activeRuntimeBinary: string;
  activeRuntimeBinarySource: string;
  runtimeLiveStatus: string;
  runtimeLiveReason: string;
};

export type ServerStatusPayload = {
  status: string;
  lifecycleState: string;
  port: number;
  health: string;
  healthReason: string;
  pid: number | null;
  profile: string;
  activeModel: string;
  activeRuntime: string;
  activeRuntimeLabel: string;
  requestedRuntimeLabel: string;
  runtimeSelectionSummary: string;
  runtimeLiveStatus: string;
  runtimeLiveReason: string;
  lastReason: string;
  updatedAt: string;
  healthUrl: string;
  webUrl: string;
  localWebUrl: string;
  tailscaleWebUrl: string;
  hasWarning?: boolean;
  warningSeverity?: string;
  warningSummary?: string;
  canStart?: boolean;
  startBlockedReason?: string;
  canStop?: boolean;
  stopBlockedReason?: string;
  canOpenWeb?: boolean;
  openWebBlockedReason?: string;
};

export type BenchmarkHistoryItem = {
  measuredAt: string;
  chartLabel?: string;
  label: string;
  source?: string;
  promptTokensPerSecond?: number | null;
  completionTokensPerSecond?: number | null;
  totalTokensPerSecond?: number | null;
  totalMs?: number;
  environment?: BenchmarkEnvironment;
};

export type BenchmarkEnvironment = {
  modelId: string;
  modelLabel: string;
  runtime: string;
  runtimeLabel: string;
  profile: string;
  context: number;
  outputTokens: number;
  thinkingMode: string;
  runtimeLiveStatus: string;
  runtimeLiveReason: string;
};

export type BenchmarkLiveState = {
  status: string;
  hasLiveSignal: boolean;
  reason: string;
};

export type BenchmarkScenario = {
  id: string;
  name: string;
  prompt: string;
  description?: string;
};

export type BenchmarkBattery = {
  id: string;
  name: string;
  source: string;
  updatedAt?: string;
  scenarios: BenchmarkScenario[];
};

export type BenchmarkScenarioStatus = {
  scenarioId: string;
  scenarioName: string;
  status: "queued" | "running" | "done" | "failed";
  summary: string;
};

export type BenchmarkRunStatusPayload = {
  runId: string;
  status: string;
  mode: string;
  batteryId: string;
  batteryName: string;
  scenarioId: string;
  scenarioName: string;
  currentScenarioId: string;
  currentScenarioName: string;
  currentIndex: number;
  totalScenarios: number;
  percent: number;
  startedAt: string;
  finishedAt: string;
  message: string;
  scenarioStatuses: BenchmarkScenarioStatus[];
};

export type SavedBenchmarkRun = {
  runId: string;
  mode: string;
  batteryName: string;
  scenarioName: string;
  modelId: string;
  modelLabel: string;
  runtime: string;
  runtimeLabel: string;
  profile: string;
  context: number;
  outputTokens: number;
  thinkingMode: string;
  status: string;
  startedAt: string;
  finishedAt: string;
  currentMetric?: BenchmarkHistoryItem;
  scenarioResults?: Array<{
    scenarioId: string;
    scenarioName: string;
    status: string;
    summary: string;
    metric?: BenchmarkHistoryItem;
  }>;
};

export type BenchmarkPayload = {
  current: BenchmarkHistoryItem | null;
  liveCurrent: BenchmarkHistoryItem | null;
  history: BenchmarkHistoryItem[];
  liveHistory: BenchmarkHistoryItem[];
  historyCount: number;
  requestCount: number;
  lastMeasuredAt: string | null;
  lastLabel: string | null;
  environment: BenchmarkEnvironment;
  liveState: BenchmarkLiveState;
  activity: {
    averageTotalMs: number;
    sources: {
      testPrompt: number;
      opencode: number;
      other: number;
    };
    recentActivities: BenchmarkHistoryItem[];
    stability: {
      level: string;
      label: string;
      score: number;
      reason: string;
    };
    throughputTrend: {
      direction: string;
      label: string;
      signal: string;
      reason: string;
    };
    latencyTrend: {
      direction: string;
      label: string;
      signal: string;
      reason: string;
    };
  };
  averages: {
    promptTokensPerSecond: number | null;
    completionTokensPerSecond: number | null;
    totalTokensPerSecond: number | null;
  };
  liveLog: {
    path: string;
    lines: string[];
  };
  batteries: BenchmarkBattery[];
  selectedBattery: BenchmarkBattery;
  activeRun: BenchmarkRunStatusPayload;
  savedRuns: SavedBenchmarkRun[];
};

export type BenchmarkCompareRow = {
  runId: string;
  label: string;
  mode: string;
  batteryName: string;
  scenarioName: string;
  modelId: string;
  modelLabel: string;
  runtime: string;
  runtimeLabel: string;
  profile: string;
  context: number;
  outputTokens: number;
  thinkingMode: string;
  status: string;
  startedAt: string;
  finishedAt: string;
  scenarioCount: number;
  metricSource: string;
  promptTokensPerSecond: number | null;
  completionTokensPerSecond: number | null;
  totalTokensPerSecond: number | null;
  totalMs: number | null;
};

export type BenchmarkCompareMetricSummary = {
  bestRunId: string | null;
  bestValue: number | null;
  average: number | null;
};

export type BenchmarkComparePayload = {
  status: string;
  summary: string;
  runIds: string[];
  runs: SavedBenchmarkRun[];
  rows: BenchmarkCompareRow[];
  comparison: {
    promptTokensPerSecond: BenchmarkCompareMetricSummary;
    completionTokensPerSecond: BenchmarkCompareMetricSummary;
    totalTokensPerSecond: BenchmarkCompareMetricSummary;
    totalMs: BenchmarkCompareMetricSummary;
  };
};

export type ModelEntry = {
  id: string;
  label: string;
  source: string;
  active: boolean;
  installed: boolean;
  supportsActivation?: boolean;
  activationSummary?: string;
  lifecycleStatus?: string;
  lifecycleLabel?: string;
  lifecycleSummary?: string;
  downloadActive?: boolean;
  downloadPercent?: number | null;
  canDownload?: boolean;
  downloadSummary?: string;
  mtpStatus?: "no-mtp" | "has-mtp" | "unknown";
  mtpStatusLabel?: string;
  filename?: string;
  family?: string;
  description?: string;
  isCustom?: boolean;
  approxSizeGiB?: number | null;
  minimumGpuMiB?: number | null;
  recommendedGpuMiB?: number | null;
  minimumRamGiB?: number | null;
  installedSizeGiB?: number | null;
  diskNeededGiB?: number | null;
  freeDiskGiB?: number | null;
  hasEnoughDisk?: boolean | null;
};

export type ModelsPayload = {
  curated: ModelEntry[];
  local: ModelEntry[];
  huggingFace: ModelEntry[];
  unsloth: ModelEntry[];
};

export type BrowserCatalogSource = "huggingface" | "unsloth" | "other";

export type BrowserMtpStatus = "has-mtp" | "no-mtp" | "unknown";

export type BrowserFitStatus = "radi" | "granicno" | "ne radi" | "nije provereno";

export type BrowserCatalogItem = {
  id: string;
  model: string;
  family: string;
  source: BrowserCatalogSource | string;
  repoId?: string;
  quantization: string;
  quantFilterKey: string;
  sizeLabel: string;
  sizeBytes: number | null;
  updatedAt: string | null;
  mtpStatus: BrowserMtpStatus;
  mtpLabel: string;
  fitStatus: BrowserFitStatus;
  fitLabel: string;
  sourceUrl: string;
  downloadUrl: string;
  summary: string;
  filename: string;
  repo: string;
  tags: string[];
  contextWindow: number | null;
  downloads: number | null;
  likes: number | null;
  addedToLocal: boolean;
  localModelId: string | null;
};

export type BrowserCatalogPayload = {
  models: Array<Record<string, unknown>>;
  refresh: {
    lastRefresh: string;
    counts: Record<string, number>;
    warnings: string[];
    errors: string[];
    sources: Record<string, Record<string, unknown>>;
  };
};

export type BrowserRefreshResult = ActionResult & {
  source?: string;
};

export type BrowserCompatibilityPayload = {
  status: string;
  checkedAt?: string;
  summary: string;
  fitStatus: BrowserFitStatus;
  fitLabel: string;
  overallFitStatus?: BrowserFitStatus;
  overallFitLabel?: string;
  speedStatus?: string;
  speedLabel?: string;
  bestRuntime?: string;
  bestRuntimeLabel?: string;
  checks: Array<{
    label: string;
    value: string;
    outcome: "pass" | "warn" | "fail" | "info";
  }>;
  reasoning?: Record<string, string>;
  memoryBudget?: {
    vram: {
      requiredGiB: number | null;
      availableGiB: number | null;
      usagePercent: number | null;
      headroomGiB?: number | null;
    };
    ram: {
      requiredGiB: number | null;
      availableGiB: number | null;
      usagePercent: number | null;
      headroomGiB?: number | null;
    };
    contextPressure: {
      level: string;
      label: string;
      currentContext: number | null;
      effectiveCapacity: number | null;
      usagePercent: number | null;
      details: string;
    };
    outputPressure?: {
      level: string;
      label: string;
      currentOutputTokens: number | null;
      defaultOutputTokens: number | null;
      usagePercent: number | null;
      details: string;
    };
  };
  systemSnapshot?: {
    ramGiB?: number;
    vramGiB?: number;
    context?: number;
    outputTokens?: number;
    turboQuantAvailable?: boolean;
    turboQuantConfig?: {
      ctk: string;
      ctv: string;
      ncmoe: number;
      runtimePreference: string;
    };
  };
  runtimeBreakdown?: Record<
    string,
    {
      runtime: string;
      runtimeLabel: string;
      supported: boolean;
      fitStatus: BrowserFitStatus;
      fitLabel: string;
      speedStatus?: string;
      speedLabel?: string;
      summary: string;
      estimated?: {
        requiredVramGiB?: number | null;
        availableVramGiB?: number | null;
        requiredRamGiB?: number | null;
        availableRamGiB?: number | null;
        outputPressureLabel?: string;
        contextPressureLabel?: string;
      };
    }
  >;
  recommendations?: Array<{
    id: string;
    title: string;
    summary: string;
    tradeoff: string;
    severity: string;
    action?: CompatibilityAction;
  }>;
};

export type CompatibilityAction = {
  kind: string;
  value?: string | number;
  ctk?: string;
  ctv?: string;
  actions?: CompatibilityAction[];
  requiresConfirmation?: boolean;
};

export type CompatibilityCheckRequest = {
  catalogModelId?: string;
  model?: Record<string, unknown>;
  overrides?: {
    ramGiB?: number;
    vramGiB?: number;
    context?: number;
    outputTokens?: number;
    turboQuantAvailable?: boolean;
    ctk?: string;
    ctv?: string;
    ncmoe?: number;
    runtimePreference?: string;
  };
};

export type CompatibilityApplyResponse = {
  result: ActionResult;
  compatibility: BrowserCompatibilityPayload;
};

export type BrowserAddToLocalResult = ActionResult & {
  localModelId?: string;
  promptDownload?: boolean;
};

export type DownloadProgressPayload = {
  actionId?: string;
  status: string;
  isActive: boolean;
  modelId: string;
  fileName: string;
  source: string;
  percent: number | null;
  downloadedGiB: number | null;
  totalGiB: number | null;
  speedMBps: number | null;
  etaSeconds: number | null;
  message: string;
  updatedAt: string;
  workerPid?: number | null;
};

export type UpdateProgressPayload = {
  actionId: string;
  status: string;
  phase: string;
  isActive: boolean;
  currentVersion: string;
  latestVersion: string;
  releaseUrl: string;
  targetPath: string;
  percent: number | null;
  downloadedGiB: number | null;
  totalGiB: number | null;
  speedMBps: number | null;
  etaSeconds: number | null;
  message: string;
  updatedAt: string;
};

export type SettingsPayload = {
  profile: string;
  context: number;
  outputTokens: number;
  workingDirectory: string;
  thinkingMode: string;
  buildSteps: number;
  planSteps: number;
  generalSteps: number;
  exploreSteps: number;
  settingsScope: string;
  activeModelId: string;
  activeModelLabel: string;
  modelOverrideExists: boolean;
  accessMode: string;
  webSearchMode: string;
  webSearchProvider: string;
  webSearchBaseUrl: string;
  webSearchMaxResults: number;
  webSearchTimeoutSeconds: number;
  webSearchPromptPrefix: string;
  builtInSettingsProfiles: SettingsProfilePreset[];
  userSettingsProfiles: SettingsProfilePreset[];
  selectedSettingsProfileId: string;
  selectedSettingsProfileName: string;
};

export type SettingsProfileValues = {
  profile: string;
  context: number;
  outputTokens: number;
  workingDirectory: string;
  thinkingMode: string;
  buildSteps: number;
  planSteps: number;
  generalSteps: number;
  exploreSteps: number;
  accessMode: string;
};

export type SettingsProfilePreset = {
  id: string;
  name: string;
  kind: "built-in" | "user";
  summary: string;
  settings: SettingsProfileValues;
};

export type TurboQuantConfig = {
  context: number;
  ctk: string;
  ctv: string;
  ncmoe: number;
  flashAttention: boolean;
  mlock: boolean;
  mmapMode: string;
  runtimePreference: string;
};

export type TurboQuantParameter = {
  id: string;
  label: string;
  whatIsIt: string;
  effect: string;
  recommendation: string;
  safeChoices: string[];
  advancedChoices: string[];
  defaultValue: string | number | boolean;
};

export type TurboQuantPreset = {
  id: string;
  name: string;
  description: string;
  targetModelPattern: string;
  notes: string;
  settings: TurboQuantConfig;
};

export type RecommendedModel = {
  id: string;
  label: string;
  repo: string;
  filename: string;
  quantization: string;
  fitNote: string;
  mtp: boolean;
};

export type TurboQuantSchemaPayload = {
  parameters: TurboQuantParameter[];
  builtInPresets: TurboQuantPreset[];
  userPresets: TurboQuantPreset[];
  currentConfig: TurboQuantConfig;
  recommendedModels: RecommendedModel[];
};

export type OpenCodeStatusPayload = {
  available: boolean;
  active: boolean;
  instanceCount: number;
  runtimeConnected: boolean;
  runtimeLiveStatus: string;
  runtimeLiveReason: string;
  sessionState: string;
  sessionSummary: string;
  canOpen?: boolean;
  openActionLabel?: string;
  openBlockedReason?: string;
  instances: Array<{
    pid?: number | null;
    name?: string;
    commandLine?: string;
  }>;
  configExists: boolean;
  configPath: string;
  configDir: string;
  executablePath: string;
  workingDirectory: string;
  buildSteps: number;
  planSteps: number;
  generalSteps: number;
  exploreSteps: number;
  securityMode: string;
  securityModeLabel: string;
  capabilityMode: string;
  capabilityModeLabel: string;
  profile: string;
  webSearchMode?: string;
  webSearchPromptPrefix?: string;
  localProviderUsesSearchProxy?: boolean;
  localProviderSearchSummary?: string;
  auditRiskLevel: string;
  auditSummary: string;
};

export type SearchResultItem = {
  title: string;
  url: string;
  snippet: string;
  engine: string;
};

export type SearchSettingsSnapshot = {
  mode: string;
  provider: string;
  baseUrl: string;
  maxResults: number;
  timeoutSeconds: number;
  promptPrefix: string;
};

export type SearchHistoryItem = {
  query: string;
  mode: string;
  resultCount: number;
  askedAt: string;
};

export type SearchSummaryPayload = {
  settings: SearchSettingsSnapshot;
  history: SearchHistoryItem[];
};

export type SearchQueryPayload = {
  status: string;
  provider: string;
  mode: string;
  query: string;
  resultCount: number;
  summary: string;
  results: SearchResultItem[];
  history: SearchHistoryItem[];
};

export type SearchAnswerPayload = SearchQueryPayload & {
  answer: string;
  answerModel: string;
  answerRuntime: string;
  usage: {
    promptTokens: number | null;
    completionTokens: number | null;
    totalTokens: number | null;
  };
};

export type KnowledgeSourceItem = {
  id: string;
  path: string;
  kind: string;
  exists: boolean;
  documentCount: number;
  indexedDocumentCount: number;
  errorCount: number;
  skippedCount: number;
  lastIndexedAt: string;
  lastError: string;
};

export type KnowledgeHistoryItem = {
  query: string;
  mode: string;
  documentResultCount: number;
  webResultCount: number;
  askedAt: string;
};

export type KnowledgeDocumentResult = {
  docId: string;
  sourceId: string;
  path: string;
  name: string;
  fileType: string;
  charCount: number;
  score: number;
  snippet: string;
};

export type KnowledgeSummaryPayload = {
  sources: KnowledgeSourceItem[];
  sourceCount: number;
  documentCount: number;
  indexedDocumentCount: number;
  errorCount: number;
  history: KnowledgeHistoryItem[];
  supportedExtensions: string[];
  answerModes: string[];
};

export type KnowledgeSourceActionPayload = {
  status: string;
  summary: string;
  source?: KnowledgeSourceItem;
  removedSourceId?: string;
};

export type KnowledgeReindexPayload = {
  status: string;
  summary: string;
  documentCount: number;
  indexedDocumentCount: number;
  sources?: KnowledgeSourceItem[];
};

export type KnowledgeQueryPayload = {
  status: string;
  query: string;
  resultCount: number;
  summary: string;
  results: KnowledgeDocumentResult[];
  history?: KnowledgeHistoryItem[];
};

export type KnowledgeAnswerPayload = {
  status: string;
  query: string;
  mode: string;
  summary: string;
  answer: string;
  answerModel: string;
  answerRuntime: string;
  usage: {
    promptTokens: number | null;
    completionTokens: number | null;
    totalTokens: number | null;
  };
  documentResultCount: number;
  documentResults: KnowledgeDocumentResult[];
  webResultCount: number;
  webResults: SearchResultItem[];
  history?: KnowledgeHistoryItem[];
};

export type OpenCodeStepValues = {
  buildSteps: number;
  planSteps: number;
  generalSteps: number;
  exploreSteps: number;
};

export type OpenCodeStepPreset = {
  id: string;
  name: string;
  steps: OpenCodeStepValues;
  summary: string;
};

export type OpenCodeStepSchemaPayload = {
  builtInPresets: OpenCodeStepPreset[];
  userPresets: OpenCodeStepPreset[];
  currentSteps: OpenCodeStepValues;
  currentSummary: string;
  defaultSteps: OpenCodeStepValues;
  defaultSummary: string;
};

export type ActionResult = {
  status: string;
  action: string;
  summary: string;
  actionId?: string;
  details: {
    returncode: number;
    stdout: string;
    stderr: string;
  };
};

export type ModelActionStatusPayload = {
  actionId: string;
  status: string;
  summary: string;
  isDone: boolean;
  result: ActionResult | null;
};
