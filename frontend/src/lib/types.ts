export type StatusPayload = {
  hostPlatform: string;
  hostPlatformLabel: string;
  hostShellLabel: string;
  version: string;
  installedVersion: string;
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
  runtimeDiagnostics: RuntimeDiagnostics;
  commandPreview: {
    shellLabel: string;
    activeRuntime: string;
    activeRuntimeLabel: string;
    activeCommand: string;
    activeCmdCommand?: string;
    modelPath: string;
    notes: string[];
    variants: Array<{
      runtime: string;
      runtimeLabel: string;
      available: boolean;
      summary: string;
      binaryPath: string;
      modelPath: string;
      context: number | null;
      specType: string;
      samplingSummary?: string;
      command: string;
      cmdCommand?: string;
    }>;
  };
};

export type RuntimeDiagnostics = {
  status: string;
  backend: string;
  deviceLabel: string;
  requestedGpuLayers: number;
  requestedFlashAttention: string;
  requestedMainGpu?: number | null;
  requestedSplitMode?: string;
  projectedDeviceMemoryMiB: number | null;
  projectedHostMemoryMiB: number | null;
  confirmedGpuLayers: number | null;
  confirmedTotalLayers: number | null;
  cpuMappedModelBufferMiB?: number | null;
  modelBufferMiB: number | null;
  kvBufferMiB: number | null;
  computeBufferMiB: number | null;
  executionModeId?: string;
  executionModeLabel?: string;
  executionModeSummary?: string;
  requestedSummary: string;
  confirmedSummary: string;
  summary: string;
  configuredContext?: number | null;
  effectiveProcessContext?: number | null;
  contextMismatch?: boolean;
  contextAlignmentLabel?: string;
  contextAlignmentSummary?: string;
  notes: string[];
};

export type BenchmarkHistoryItem = {
  measuredAt: string;
  chartLabel?: string;
  label: string;
  source?: string;
  promptTokens?: number | null;
  completionTokens?: number | null;
  totalTokens?: number | null;
  activeRoutes?: number | null;
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

export type BenchmarkTelemetrySummary = {
  windowHours: number;
  input24hTokens: number;
  output24hTokens: number;
  total24hTokens: number;
  estimatedCost24hUsd: number;
  activeRoutes: number;
  activeRoutesLabel: string;
  liveNowTokensPerSecond: number | null;
  lastSignalTokensPerSecond: number | null;
  lastSignalLabel: string;
  lastSignalStateLabel: string;
  lastSignalAt: string;
  flowState: string;
  flowStateLabel: string;
  flowStateReason: string;
  lastUpdate: string;
  inputSharePercent: number;
  outputSharePercent: number;
  launchQueueSignal: {
    status: string;
    label: string;
    summary: string;
  };
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
  repeatCount: number;
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
  telemetry: BenchmarkTelemetrySummary;
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

export type ObservabilityPayload = {
  generatedAt: string;
  system: {
    hostname: string;
    platformLabel: string;
    cpuPercent: number | null;
    ramTotalGiB: number | null;
    ramUsedGiB: number | null;
    ramFreeGiB: number | null;
    gpuAvailable: boolean;
    gpuName: string;
    vramTotalGiB: number | null;
    vramUsedGiB: number | null;
    vramFreeGiB: number | null;
    gpuDevices: Array<{
      index: number | null;
      name: string;
      totalGiB: number | null;
      usedGiB: number | null;
      freeGiB: number | null;
      utilizationPercent?: number | null;
      selected: boolean;
    }>;
  };
  runtime: {
    activeRuntime: string;
    activeModel: string;
    runtimeLiveStatus: string;
    runtimeLiveReason: string;
    baseUrl: string;
    port: number | null;
    runtimePid?: number | null;
    runtimeProcessRamMiB?: number | null;
    executionModeId: string;
    executionModeLabel: string;
    executionModeSummary: string;
    offloadStatus: string;
    offloadLabel: string;
    offloadSummary: string;
    selectedGpuIndex?: number | null;
    selectedGpuName?: string;
    selectedGpuTotalGiB?: number | null;
    runtimeDiagnostics?: RuntimeDiagnostics;
  };
  telemetry: {
    input24h: number;
    output24h: number;
    total24h: number;
    cost24hUsd: number;
    activeRoutes: number;
    activeRoutesLabel: string;
    liveNowTokensPerSecond: number | null;
    flowStateLabel: string;
    flowStateReason: string;
    lastUpdatedAt: string;
    promptSharePercent: number;
    completionSharePercent: number;
    launchQueueSignal: {
      label: string;
      summary: string;
    };
  };
  activity: {
    requestCount: number;
    averageTotalMs: number | null;
    lastMeasuredAt: string | null;
    stability: {
      label: string;
      score: number;
      reason: string;
    };
  };
  logSignals: Array<{
    level: string;
    source: string;
    message: string;
    timestamp: string;
  }>;
};

export type FleetMachineSnapshot = {
  version: string;
  health: string;
  activeModel: string;
  activeRuntime: string;
  runtimeLiveStatus: string;
  runtimeSummary: string;
  uiUrl: string;
  webUrl: string;
  liveNowTokensPerSecond: number | null;
  flowStateLabel: string;
  input24h: number;
  output24h: number;
};

export type FleetMachine = {
  id: string;
  name: string;
  baseUrl: string;
  addedAt: string;
  lastCheckedAt: string;
  snapshot: FleetMachineSnapshot;
  lastError: string;
};

export type FleetSummaryPayload = {
  machineCount: number;
  generatedAt: string;
  machines: FleetMachine[];
};

export type JobKindOption = {
  id: string;
  label: string;
  summary: string;
};

export type JobRecord = {
  id: string;
  name: string;
  kind: string;
  intervalMinutes: number;
  enabled: boolean;
  targetId: string;
  workflowPresetId: string;
  createdAt: string;
  updatedAt: string;
  nextRunAt: string;
  lastRunAt: string;
  lastStatus: string;
  lastSummary: string;
  lastDetails: Record<string, unknown>;
};

export type JobsSummaryPayload = {
  generatedAt: string;
  jobCount: number;
  jobs: JobRecord[];
  availableKinds: JobKindOption[];
};

export type TuningLabSettingsPatch = {
  profile: string;
  context: number;
  outputTokens: number;
  thinkingMode: string;
  temperature: number;
  topK: number;
  topP: number;
  minP: number;
  repeatPenalty: number;
  repeatLastN: number;
  presencePenalty: number;
  frequencyPenalty: number;
  seed: number;
  buildSteps?: number;
  planSteps?: number;
  generalSteps?: number;
  exploreSteps?: number;
};

export type TuningLabSuccessCheckSpec = {
  label: string;
  command: string;
  kind: string;
};

export type TuningLabSuccessCheckResult = TuningLabSuccessCheckSpec & {
  returncode?: number;
  passed?: boolean;
  stdoutPath?: string;
  stdoutPreview?: string;
  stderrPreview?: string;
};

export type TuningLabDiffFile = {
  path: string;
  summary?: string;
  diffText?: string;
  isBinary?: boolean;
  isTruncated?: boolean;
};

export type TuningLabSlot = {
  id: string;
  label: string;
  source: string;
  status?: string;
  summary?: string;
  settingsPatch: TuningLabSettingsPatch;
  workspaceMode?: string;
  workspacePath?: string;
  workspaceRetained?: boolean;
  startedAt?: string;
  finishedAt?: string;
  taskCompleted?: boolean;
  successChecksPassed?: boolean;
  successChecks?: TuningLabSuccessCheckResult[];
  changedFiles?: string[];
  diffSummary?: string;
  diffText?: string;
  diffFiles?: TuningLabDiffFile[];
  assistantText?: string;
  processReturncode?: number;
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  costUsd?: number;
  totalDurationMs?: number;
  averageOutputTokensPerSecond?: number;
  averageTotalTokensPerSecond?: number;
  completionMode?: string;
  successChecksVerifiedLive?: boolean;
  completionSummary?: string;
  runtimeCommand?: string;
  runtimeBaseUrl?: string;
  runtimeDiagnostics?: RuntimeDiagnostics;
  runtimePid?: number;
  runtimeLogPath?: string;
  opencodeCommand?: string;
  opencodePid?: number;
  opencodeSessionId?: string;
  activeMessageId?: string;
  stdoutPath?: string;
  stderrPath?: string;
  liveWorkspaceSummary?: string;
  liveWorkspaceFiles?: Array<{
    path: string;
    sizeBytes: number;
    modifiedAt: string;
  }>;
  livePreviewFilePath?: string;
  livePreviewFileName?: string;
  livePreviewText?: string;
  livePreviewModifiedAt?: string;
  liveOutputTokensPerSecond?: number;
  liveTotalTokensPerSecond?: number;
  runtimePromptTokensPerSecond?: number;
  runtimeGenerationTokensPerSecond?: number;
  runtimePromptSummary?: string;
  runtimeGenerationSummary?: string;
  runtimeLatestTimingLine?: string;
  lastLiveMeasuredAt?: string;
  playableEntryPath?: string;
  playableFilesPreserved?: number;
};

export type TuningLabGoalOption = {
  id: string;
  label: string;
};

export type TuningLabSuccessCheckTemplate = {
  id: string;
  label: string;
  command: string;
};

export type TuningLabBatchTask = {
  id: string;
  label: string;
  difficulty: string;
  goal: string;
  summary: string;
  scopeLabel?: string;
  focusLabel?: string;
  expectedArtifact?: string;
  taskPrompt: string;
  successChecks: TuningLabSuccessCheckSpec[];
};

export type TuningLabBatchPreset = {
  id: string;
  label: string;
  summary: string;
  focusAreas?: string[];
  tasks: TuningLabBatchTask[];
};

export type TuningLabRun = {
  runId: string;
  name: string;
  goal: string;
  goalLabel?: string;
  taskPrompt: string;
  workingDirectory: string;
  queuedAt?: string;
  startedAt?: string;
  finishedAt?: string;
  status: string;
  summary?: string;
  recommendedOrigin?: string;
  successChecks?: TuningLabSuccessCheckSpec[];
  slots: TuningLabSlot[];
  suggestedWinnerSlotId?: string | null;
  winnerSummary?: string;
  activeRuntime?: string;
  modelId?: string;
  modelLabel?: string;
  modelFamily?: string;
  currentIndex?: number;
  currentSlotId?: string;
  currentSlotLabel?: string;
  currentPhase?: string;
  currentPhaseLabel?: string;
  currentStepSummary?: string;
  currentCheckLabel?: string;
  currentLogExcerpt?: string;
  currentRawLogExcerpt?: string;
  lastUpdatedAt?: string;
  elapsedMs?: number;
};

export type TuningLabOverviewPayload = {
  status: string;
  activeRun: TuningLabRun | null;
  queue: TuningLabRun[];
  goalOptions: TuningLabGoalOption[];
  successCheckTemplates: TuningLabSuccessCheckTemplate[];
  batchPresets: TuningLabBatchPreset[];
  slots: TuningLabSlot[];
  context: {
    activeModel: string;
    activeModelId: string;
    activeRuntime: string;
    workingDirectory: string;
    configuredWorkingDirectory: string;
    workingDirectoryWasAdjusted: boolean;
    canQueue: boolean;
    runBlockers: string[];
    runtimeBinaryReady: boolean;
    activeModelReady: boolean;
    opencodeReady: boolean;
    modelFamily: string;
    recommendedOrigin: string;
  };
};

export type TuningLabHistoryPagePayload = {
  status: string;
  history: TuningLabRun[];
  historyPage: number;
  historyPageSize: number;
  historyTotalItems: number;
  historyFailedItems: number;
  historyTotalPages: number;
};

export type TuningLabSummaryPayload = TuningLabOverviewPayload & TuningLabHistoryPagePayload;

export type ProjectMemoryGoal = {
  text: string;
  locked: boolean;
};

export type ProjectMemoryItem = {
  id: string;
  text: string;
  locked?: boolean;
};

export type ProjectMemoryPayload = {
  status: string;
  goal: ProjectMemoryGoal;
  rules: ProjectMemoryItem[];
  decisions: ProjectMemoryItem[];
  progress: ProjectMemoryItem[];
  nextSteps: ProjectMemoryItem[];
  updatedAt: string;
  updatedBy: string;
};

export type ProjectMemorySavePayload = {
  goal: ProjectMemoryGoal;
  rules: ProjectMemoryItem[];
  decisions: ProjectMemoryItem[];
  progress: ProjectMemoryItem[];
  nextSteps: ProjectMemoryItem[];
};

export type ModelEntry = {
  id: string;
  label: string;
  source: string;
  active: boolean;
  installed: boolean;
  supportsActivation?: boolean;
  activationSummary?: string;
  activationRiskLevel?: string;
  activationRiskSummary?: string;
  requiresForceConfirmation?: boolean;
  lifecycleStatus?: string;
  lifecycleLabel?: string;
  lifecycleSummary?: string;
  downloadActive: boolean;
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
  resolvedPath?: string;
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
  themeId: string;
  workflowPresetId?: string;
  context: number;
  outputTokens: number;
  temperature: number;
  topK: number;
  topP: number;
  minP: number;
  repeatPenalty: number;
  repeatLastN: number;
  presencePenalty: number;
  frequencyPenalty: number;
  seed: number;
  gpuLayersMode: string;
  gpuLayersOverride: number;
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
  availableThemes: ThemeOption[];
  availableWorkflowPresets: WorkflowPreset[];
  availableGenerationStarters: GenerationStarterPreset[];
  availableSearchProviders: SearchProviderOption[];
  searchProviderStatus: SearchProviderStatusPayload;
  builtInSettingsProfiles: SettingsProfilePreset[];
  userSettingsProfiles: SettingsProfilePreset[];
  selectedSettingsProfileId: string;
  selectedSettingsProfileName: string;
  selectedWorkflowPresetId: string;
};

export type ThemeOption = {
  id: string;
  label: string;
  summary: string;
  accent: string;
  textColor: string;
};

export type GenerationStarterPreset = {
  id: string;
  label: string;
  summary: string;
  source: string;
  settings: Pick<
    SettingsPayload,
    | "temperature"
    | "topK"
    | "topP"
    | "minP"
    | "repeatPenalty"
    | "repeatLastN"
    | "presencePenalty"
    | "frequencyPenalty"
    | "seed"
  >;
};

export type WorkflowPreset = {
  id: string;
  name: string;
  kind: "built-in" | "user";
  label: string;
  summary: string;
  badges: string[];
  settingsPatch: Partial<
    Pick<
      SettingsPayload,
      | "profile"
      | "context"
      | "outputTokens"
      | "thinkingMode"
      | "temperature"
      | "topK"
      | "topP"
      | "minP"
      | "repeatPenalty"
      | "repeatLastN"
      | "presencePenalty"
      | "frequencyPenalty"
      | "seed"
      | "webSearchMode"
      | "webSearchProvider"
    >
  >;
  searchDefaults: {
    provider: string;
    suggestedAction: "search" | "answer" | "compare";
    queryHint: string;
  };
  knowledgeDefaults: {
    mode: "documents-only" | "documents+web" | "web-only";
    queryHint: string;
  };
  benchmarkDefaults: {
    batteryId: string;
    launchTarget: "selected" | "battery";
    runLabel: string;
  };
};

export type SettingsProfileValues = {
  profile: string;
  context: number;
  outputTokens: number;
  temperature: number;
  topK: number;
  topP: number;
  minP: number;
  repeatPenalty: number;
  repeatLastN: number;
  presencePenalty: number;
  frequencyPenalty: number;
  seed: number;
  gpuLayersMode: string;
  gpuLayersOverride: number;
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
  canBootstrap?: boolean;
  bootstrapActionLabel?: string;
  bootstrapBlockedReason?: string;
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
  launchPreview: {
    shellLabel: string;
    launcherPath: string;
    launcherCommand: string;
    powershellCommand: string;
    workingDirectory: string;
    environment: Array<{
      key: string;
      value: string;
    }>;
    managedConfig: {
      model: string;
      selectedProvider: string;
      localProviderBaseUrl: string;
      enabledProviders: string[];
    };
    summary: string;
    generationSummary?: string;
  };
  auditRiskLevel: string;
  auditSummary: string;
};

export type OpenCodeWorkspaceHygieneItem = {
  name: string;
  path: string;
  kind: string;
  sizeBytes: number;
  sizeLabel: string;
  modifiedAt: number;
  isDisposable: boolean;
  isActive: boolean;
  isRecentFallbackProtected: boolean;
  cleanupEligible: boolean;
};

export type OpenCodeAutoCleanupState = {
  hasRun: boolean;
  origin: string;
  status: string;
  summary: string;
  completedAt: string;
  removedCount: number;
  freedBytes: number;
  freedSizeLabel: string;
  failedCount: number;
};

export type OpenCodeWorkspaceHygienePayload = {
  workspaceRoot: string;
  summary: string;
  canCleanup: boolean;
  disposableWorkspaceCount: number;
  activeWorkspaceCount: number;
  recentFallbackProtectedCount: number;
  cleanupCandidateCount: number;
  cleanupCandidateBytes: number;
  cleanupCandidateSizeLabel: string;
  items: OpenCodeWorkspaceHygieneItem[];
  lastAutoCleanup: OpenCodeAutoCleanupState;
  manualReviewLocations: Array<{
    label: string;
    path: string;
    summary: string;
  }>;
};

export type OpenCodeWorkspaceHygieneActionResult = ActionResult & {
  cleanup: {
    removedCount: number;
    freedBytes: number;
    freedSizeLabel: string;
    failedCount: number;
    failedItems: string[];
  };
  hygiene: OpenCodeWorkspaceHygienePayload;
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

export type SearchProviderOption = {
  id: string;
  label: string;
  supportsBootstrap: boolean;
  supportsManualBaseUrl: boolean;
  summary: string;
};

export type SearchProviderStatusPayload = {
  provider: string;
  providerLabel: string;
  status: string;
  label: string;
  summary: string;
  source: string;
  configuredBaseUrl: string;
  effectiveBaseUrl: string;
  serviceLabel: string;
  canQuery: boolean;
  canBootstrap: boolean;
  bootstrapSummary: string;
  managed: {
    enabled: boolean;
    baseUrl: string;
    distro: string;
    port: number;
    repoPath: string;
    venvPath: string;
    settingsPath: string;
    logPath: string;
    pidPath: string;
    lastBootstrapAt: string;
    lastBootstrapStatus: string;
    lastBootstrapMessage: string;
  };
};

export type SearchHistoryItem = {
  query: string;
  mode: string;
  resultCount: number;
  askedAt: string;
};

export type SearchSummaryPayload = {
  settings: SearchSettingsSnapshot;
  availableProviders: SearchProviderOption[];
  history: SearchHistoryItem[];
  providerStatus: SearchProviderStatusPayload;
};

export type SearchProviderActionPayload = {
  result: ActionResult;
  providerStatus: SearchProviderStatusPayload;
};

export type SearchQueryPayload = {
  status: string;
  provider: string;
  providerLabel: string;
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
  collection: string;
  tags: string[];
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
  collection: string;
  tags: string[];
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
  collections: string[];
  tags: string[];
  reindexStatus: {
    lastReindexAt: string;
    summary: string;
  };
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
  collection?: string;
  tag?: string;
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
  collection?: string;
  tag?: string;
  documentResultCount: number;
  documentResults: KnowledgeDocumentResult[];
  usedCollections: string[];
  usedTags: string[];
  citations: Array<{
    index: number;
    name: string;
    path: string;
    collection: string;
    tags: string[];
    snippet: string;
  }>;
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

export type LocalUploadProgress = {
  fileName: string;
  loadedBytes: number;
  totalBytes: number | null;
  percent: number | null;
  speedMBps: number | null;
  etaSeconds: number | null;
  phase: "uploading" | "finalizing";
};

export type ModelActionStatusPayload = {
  actionId: string;
  status: string;
  summary: string;
  isDone: boolean;
  result: ActionResult | null;
};
