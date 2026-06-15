import { useEffect, useMemo, useRef, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import {
  RuntimePilotActionDeck,
  type RuntimePilotActionDeckItem,
} from "../components/shell/RuntimePilotActionDeck";
import {
  RuntimePilotStatusDeck,
  type RuntimePilotStatusDeckItem,
} from "../components/shell/RuntimePilotStatusDeck";
import {
  applySettings,
  bootstrapManagedSearchProvider,
  cleanupOpenCodeWorkspaceHygiene,
  deleteSettingsProfile,
  deleteTurboQuantPreset,
  fetchObservability,
  fetchOpenCodeWorkspaceHygiene,
  fetchSearchProviderStatus,
  fetchSettings,
  fetchTurboQuantSchema,
  peekSettingsCache,
  pickWorkingDirectory,
  saveSettingsProfile,
  saveTurboQuantConfig,
  saveTurboQuantPreset,
  startServer,
} from "../lib/api";
import {
  estimateAutoGpuLayersFromTotalGiB,
  estimateContextFitFromKvBuffer,
  estimateHybridRuntimeUsage,
  estimateRuntimeFitPreview,
} from "../lib/runtimeDiagnostics";
import { applyTheme } from "../lib/theme";
import { resolveSelectedWorkflowPreset, resolveWorkflowPresets } from "../lib/workflowPresets";
import type {
  ActionResult,
  OpenCodeWorkspaceHygienePayload,
  ObservabilityPayload,
  SearchProviderStatusPayload,
  SettingsPayload,
  SettingsProfilePreset,
  SettingsProfileValues,
  ThemeOption,
  TurboQuantConfig,
  TurboQuantPreset,
  TurboQuantSchemaPayload,
  WorkflowPreset,
} from "../lib/types";

const TURBOQUANT_DRAFT_STORAGE_KEY = "local-ai-control-center:turboquant-draft";
const FALLBACK_THEME_OPTIONS: ThemeOption[] = [
  {
    id: "dark-chocolate",
    label: "Dark Chocolate",
    summary: "Topla tamna podloga sa bronzanim i cijan akcentima.",
    accent: "#f2b84b",
    textColor: "#f7dfb0",
  },
  {
    id: "light",
    label: "Light",
    summary: "Svetla radna tema sa toplim zlatnim akcentom.",
    accent: "#d59b2f",
    textColor: "#7f5a12",
  },
  {
    id: "dark",
    label: "Dark",
    summary: "Neutralna tamna tema sa hladnijim plavo-sivim tonom.",
    accent: "#6f8fd8",
    textColor: "#bfd4ff",
  },
  {
    id: "neon-green",
    label: "Neon Green",
    summary: "Visokokontrastna terminalsko-neonska tema za jak signal.",
    accent: "#58ff8f",
    textColor: "#c8ffd9",
  },
  {
    id: "marine-blue",
    label: "Marine Blue",
    summary: "Duboki plavi komandni most sa morskim cijan akcentom.",
    accent: "#39b7ff",
    textColor: "#cbe8ff",
  },
];
const TOKEN_STEP_OPTIONS = [
  { value: "1024", label: "1024" },
  { value: "2048", label: "2048" },
  { value: "4096", label: "4096" },
  { value: "8192", label: "8192" },
  { value: "16384", label: "16384" },
  { value: "32768", label: "32768" },
  { value: "65536", label: "65536" },
  { value: "131072", label: "131072" },
  { value: "262144", label: "262144" },
] as const;
const SETTINGS_PROFILE_COMPARE_KEYS: Array<keyof SettingsProfileValues> = [
  "profile",
  "context",
  "outputTokens",
  "temperature",
  "topK",
  "topP",
  "minP",
  "repeatPenalty",
  "repeatLastN",
  "presencePenalty",
  "frequencyPenalty",
  "seed",
  "gpuLayersMode",
  "gpuLayersOverride",
  "workingDirectory",
  "thinkingMode",
  "buildSteps",
  "planSteps",
  "generalSteps",
  "exploreSteps",
  "accessMode",
];
const INFERENCE_PRIMARY_LABELS = ["Temp", "Top-k", "Top-p", "Seed"] as const;
type InferenceParameterKey =
  | "temperature"
  | "topK"
  | "topP"
  | "minP"
  | "repeatPenalty"
  | "repeatLastN"
  | "presencePenalty"
  | "frequencyPenalty"
  | "seed";

type InferenceParameterDefinition = {
  key: InferenceParameterKey;
  label: string;
  step: string;
  description: string;
  quickHint: string;
  coding: string;
  creative: string;
  benchmark: string;
};

const INFERENCE_PARAMETER_DEFINITIONS: InferenceParameterDefinition[] = [
  {
    key: "temperature",
    label: "Temperature",
    step: "0.05",
    description:
      "Kontroliše koliko je generacija mirna ili razigrana. Niže vrednosti daju stabilnije i predvidljivije odgovore.",
    quickHint: "Niže = mirnije, više = kreativnije.",
    coding: "0.1 - 0.3 za preciznije kodiranje i manje lutanja.",
    creative: "0.7 - 0.9 za opušteniji chat i više varijacija.",
    benchmark: "0.0 - 0.2 kada hoćeš stabilno poređenje između run-ova.",
  },
  {
    key: "topK",
    label: "Top-k",
    step: "1",
    description:
      "Ograničava koliko sledećih kandidata model uopšte razmatra pre izbora tokena.",
    quickHint: "Manje = fokus, više = širi izbor.",
    coding: "20 - 40 za fokusiraniji i disciplinovan izlaz.",
    creative: "40 - 100 kada želiš širi izbor reči i ideja.",
    benchmark: "20 - 40 da signal ostane uporediv i miran.",
  },
  {
    key: "topP",
    label: "Top-p",
    step: "0.01",
    description:
      "Seče raspodelu verovatnoća na najverovatniji deo. Niže vrednosti smiruju sampling.",
    quickHint: "Niže = stroži sampling i manje lutanja.",
    coding: "0.8 - 0.95 za dobar balans tačnosti i fleksibilnosti.",
    creative: "0.9 - 0.98 za širi i življi stil odgovora.",
    benchmark: "0.8 - 0.95 da ostaneš bliže realnom svakodnevnom radu.",
  },
  {
    key: "minP",
    label: "Min-p",
    step: "0.01",
    description:
      "Odbacuje veoma slabe kandidate čak i kada su upali u top-p skup. Dobar je za čišći izlaz.",
    quickHint: "Seče slabe kandidate i čisti izlaz.",
    coding: "0.03 - 0.08 za manje šuma u odgovoru.",
    creative: "0.02 - 0.06 ako želiš više prostora za neočekivane izbore.",
    benchmark: "0.05 - 0.1 kada hoćeš mirniji i stabilniji tok tokena.",
  },
  {
    key: "repeatPenalty",
    label: "Repeat penalty",
    step: "0.05",
    description:
      "Kažnjava ponavljanje istih tokena. Više vrednosti smanjuju petljanje, ali mogu da ukoče izlaz.",
    quickHint: "Smanjuje petljanje i dosadno ponavljanje.",
    coding: "1.0 - 1.1 da ne uguši tehničku preciznost.",
    creative: "1.05 - 1.15 za manje dosadnog ponavljanja.",
    benchmark: "1.0 ako meriš čist runtime bez dodatnog stilskog pritiska.",
  },
  {
    key: "repeatLastN",
    label: "Repeat last N",
    step: "1",
    description:
      "Kaže koliko poslednjih tokena ulazi u proveru za repeat penalty. Veći broj gleda duži rep istorije.",
    quickHint: "Veće vrednosti gledaju duži rep istorije.",
    coding: "64 - 128 je praktičan i lagan izbor.",
    creative: "128 - 256 kad želiš da model duže pamti šta je već rekao.",
    benchmark: "64 da test ostane lagan i dosledan.",
  },
  {
    key: "presencePenalty",
    label: "Presence penalty",
    step: "0.05",
    description:
      "Gura model da uvodi nove pojmove umesto da se vrti oko istih tema.",
    quickHint: "Više = lakše uvodi nove teme i ideje.",
    coding: "0.0 - 0.2 jer kod obično traži fokus, ne širenje teme.",
    creative: "0.2 - 0.6 za brainstorming i raznovrsniji razgovor.",
    benchmark: "0.0 kada želiš što manje dodatnih uticaja na rezultat.",
  },
  {
    key: "frequencyPenalty",
    label: "Frequency penalty",
    step: "0.05",
    description:
      "Smanjuje šansu da se isti tokeni često ponavljaju. Deluje blaže i finije od repeat penalty.",
    quickHint: "Pegla često ponavljanje bez velikog nasilja.",
    coding: "0.0 - 0.15 za čiste i tehničke odgovore.",
    creative: "0.1 - 0.4 kada želiš raznovrsniji izraz.",
    benchmark: "0.0 da se merenje ne muti dodatnim stilskim filtrom.",
  },
  {
    key: "seed",
    label: "Seed",
    step: "1",
    description:
      "Kontroliše reproduktivnost sampling-a. -1 znači nasumično, a fiksan broj daje ponovljiviji izlaz.",
    quickHint: "Fiksan broj = ponovljivije, -1 = svežije.",
    coding: "42 ili 1234 kada porediš rezultate i želiš ponovljivost.",
    creative: "-1 za svežije i manje predvidljive odgovore.",
    benchmark: "42 ili drugi fiksan broj za poštenu uporedivost.",
  },
];

function applyPresetToConfig(preset: TurboQuantPreset): TurboQuantConfig {
  return { ...preset.settings };
}

function readDraft<T>(key: string): Partial<T> | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<T>;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function writeDraft<T>(key: string, value: T | null) {
  if (typeof window === "undefined") {
    return;
  }
  if (!value) {
    window.localStorage.removeItem(key);
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}

function clearDraft(key: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(key);
}

function resolveTokenChoice(value: number): string {
  const matched = TOKEN_STEP_OPTIONS.find((option) => Number(option.value) === value);
  return matched?.value ?? "custom";
}

function formatGenerationStarterValues(
  starter: SettingsPayload["availableGenerationStarters"][number]["settings"],
): string {
  return [
    `temp ${starter.temperature}`,
    `top-k ${starter.topK}`,
    `top-p ${starter.topP}`,
    `min-p ${starter.minP}`,
    `repeat ${starter.repeatPenalty}`,
  ].join(" | ");
}

function formatInferenceMetric(value: number, fractionDigits = 2): string {
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(fractionDigits).replace(/\.?0+$/, "");
}

function buildInferenceSummaryItems(settings: {
  temperature: number;
  topK: number;
  topP: number;
  minP: number;
  repeatPenalty: number;
  repeatLastN: number;
  presencePenalty: number;
  frequencyPenalty: number;
  seed: number;
}) {
  return [
    { label: "Temp", value: formatInferenceMetric(settings.temperature) },
    { label: "Top-k", value: formatInferenceMetric(settings.topK, 0) },
    { label: "Top-p", value: formatInferenceMetric(settings.topP) },
    { label: "Min-p", value: formatInferenceMetric(settings.minP) },
    { label: "Repeat", value: formatInferenceMetric(settings.repeatPenalty) },
    { label: "Last N", value: formatInferenceMetric(settings.repeatLastN, 0) },
    { label: "Presence", value: formatInferenceMetric(settings.presencePenalty) },
    { label: "Frequency", value: formatInferenceMetric(settings.frequencyPenalty) },
    { label: "Seed", value: formatInferenceMetric(settings.seed, 0) },
  ];
}

function resolveInferenceDefinitionForSummaryLabel(
  label: string,
): InferenceParameterDefinition | null {
  const keyByLabel: Record<string, InferenceParameterKey> = {
    Temp: "temperature",
    "Top-k": "topK",
    "Top-p": "topP",
    "Min-p": "minP",
    Repeat: "repeatPenalty",
    "Last N": "repeatLastN",
    Presence: "presencePenalty",
    Frequency: "frequencyPenalty",
    Seed: "seed",
  };
  const key = keyByLabel[label];
  return key
    ? INFERENCE_PARAMETER_DEFINITIONS.find((definition) => definition.key === key) ?? null
    : null;
}

function matchesGenerationStarter(
  settings: SettingsPayload,
  starter: SettingsPayload["availableGenerationStarters"][number],
): boolean {
  return (
    settings.temperature === starter.settings.temperature &&
    settings.topK === starter.settings.topK &&
    settings.topP === starter.settings.topP &&
    settings.minP === starter.settings.minP &&
    settings.repeatPenalty === starter.settings.repeatPenalty &&
    settings.repeatLastN === starter.settings.repeatLastN &&
    settings.presencePenalty === starter.settings.presencePenalty &&
    settings.frequencyPenalty === starter.settings.frequencyPenalty &&
    settings.seed === starter.settings.seed
  );
}

function matchesSettingsProfile(
  settings: SettingsPayload,
  profile: SettingsProfilePreset,
): boolean {
  return SETTINGS_PROFILE_COMPARE_KEYS.every(
    (key) => settings[key] === profile.settings[key],
  );
}

function mergeSettingsProfile(
  settings: SettingsPayload,
  profile: SettingsProfilePreset,
): SettingsPayload {
  return {
    ...settings,
    ...profile.settings,
  };
}

function buildSettingsProfileDraft(settings: SettingsPayload): SettingsProfileValues {
  return {
    profile: settings.profile,
    context: settings.context,
    outputTokens: settings.outputTokens,
    temperature: settings.temperature,
    topK: settings.topK,
    topP: settings.topP,
    minP: settings.minP,
    repeatPenalty: settings.repeatPenalty,
    repeatLastN: settings.repeatLastN,
    presencePenalty: settings.presencePenalty,
    frequencyPenalty: settings.frequencyPenalty,
    seed: settings.seed,
    gpuLayersMode: settings.gpuLayersMode,
    gpuLayersOverride: settings.gpuLayersOverride,
    workingDirectory: settings.workingDirectory,
    thinkingMode: settings.thinkingMode,
    buildSteps: settings.buildSteps,
    planSteps: settings.planSteps,
    generalSteps: settings.generalSteps,
    exploreSteps: settings.exploreSteps,
    accessMode: settings.accessMode,
  };
}

function formatMiB(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(2)} GiB`;
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} MiB`;
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function formatTokenCount(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return `${value} tokena`;
}

function formatGpuLayersModeLabel(mode: string, override: number, autoRecommendation: number) {
  if (mode === "manual") {
    return `Ručno ${override || 0}`;
  }
  return `Auto ${autoRecommendation || 0}`;
}

function formatWorkspaceHygieneKind(kind: string) {
  if (kind === "scratch") {
    return "Scratch workspace";
  }
  if (kind === "git-worktree") {
    return "Git worktree";
  }
  return "Kopija workspace-a";
}

function formatWorkspaceHygieneModifiedAt(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return "--";
  }
  return new Date(value * 1000).toLocaleString("sr-RS");
}

function formatAutoCleanupCompletedAt(value: string) {
  if (!value) {
    return "--";
  }
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    return value;
  }
  return new Date(timestamp).toLocaleString("sr-RS");
}

type VramFitComparisonRow = {
  label: string;
  saved: string;
  editor: string;
  changed: boolean;
};

type SettingsPageProps = {
  focusSectionId?: string | null;
  onFocusHandled?: () => void;
};

export function SettingsPage({ focusSectionId = null, onFocusHandled }: SettingsPageProps) {
  const [settings, setSettings] = useState<SettingsPayload | null>(() => peekSettingsCache());
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsPayload | null>(() =>
    peekSettingsCache(),
  );
  const [schema, setSchema] = useState<TurboQuantSchemaPayload | null>(null);
  const [turboConfig, setTurboConfig] = useState<TurboQuantConfig | null>(null);
  const [turboConfigDefaults, setTurboConfigDefaults] = useState<TurboQuantConfig | null>(null);
  const [observability, setObservability] = useState<ObservabilityPayload | null>(null);
  const [workspaceHygiene, setWorkspaceHygiene] = useState<OpenCodeWorkspaceHygienePayload | null>(null);
  const [settingsProfileName, setSettingsProfileName] = useState("");
  const [presetName, setPresetName] = useState("");
  const [presetDescription, setPresetDescription] = useState("");
  const [presetTargetPattern, setPresetTargetPattern] = useState("");
  const [presetNotes, setPresetNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [providerBusy, setProviderBusy] = useState<"" | "check" | "setup">("");
  const [hygieneBusy, setHygieneBusy] = useState<"" | "refresh" | "cleanup">("");
  const [vramFitBusy, setVramFitBusy] = useState(false);
  const [showTurboQuantGuidance, setShowTurboQuantGuidance] = useState(false);
  const profileSectionRef = useRef<HTMLElement | null>(null);
  const contextSectionRef = useRef<HTMLElement | null>(null);
  const vramFitSectionRef = useRef<HTMLElement | null>(null);
  const searchSectionRef = useRef<HTMLElement | null>(null);
  const turboSectionRef = useRef<HTMLElement | null>(null);

  async function reload() {
    const [settingsPayload, schemaPayload, observabilityPayload, workspaceHygienePayload] = await Promise.all([
      fetchSettings({ preferCache: true }),
      fetchTurboQuantSchema(),
      fetchObservability(),
      fetchOpenCodeWorkspaceHygiene(),
    ]);
    const turboDraft = readDraft<TurboQuantConfig>(TURBOQUANT_DRAFT_STORAGE_KEY);
    const savedTurboConfig = schemaPayload.currentConfig;

    setSettings(settingsPayload);
    setSettingsDefaults(settingsPayload);
    setSchema(schemaPayload);
    setTurboConfigDefaults(savedTurboConfig);
    setTurboConfig(turboDraft ? { ...savedTurboConfig, ...turboDraft } : savedTurboConfig);
    setObservability(observabilityPayload);
    setWorkspaceHygiene(workspaceHygienePayload);
  }

  useEffect(() => {
    reload().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Nepoznata greška");
    });
  }, []);

  useEffect(() => {
    if (turboConfig) {
      writeDraft(TURBOQUANT_DRAFT_STORAGE_KEY, turboConfig);
    }
  }, [turboConfig]);

  useEffect(() => {
    if (focusSectionId === "profile" && settings) {
      profileSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      onFocusHandled?.();
      return;
    }
    if (focusSectionId === "context" && settings) {
      contextSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      onFocusHandled?.();
      return;
    }
    if (focusSectionId !== "vram-fit" || !settings || !turboConfig) {
      return;
    }
    vramFitSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    onFocusHandled?.();
  }, [focusSectionId, onFocusHandled, settings, turboConfig]);

  const settingsProfiles = useMemo(
    () => (settings ? [...settings.builtInSettingsProfiles, ...settings.userSettingsProfiles] : []),
    [settings],
  );
  const selectedSettingsProfileId = useMemo(() => {
    if (!settings) {
      return "custom";
    }
    const matched = settingsProfiles.find((profile) => matchesSettingsProfile(settings, profile));
    return matched?.id ?? "custom";
  }, [settings, settingsProfiles]);
  const selectedSettingsProfile = useMemo(
    () => settingsProfiles.find((profile) => profile.id === selectedSettingsProfileId) ?? null,
    [selectedSettingsProfileId, settingsProfiles],
  );
  const currentSearchProviderOption = useMemo(
    () =>
      settings
        ? settings.availableSearchProviders.find((provider) => provider.id === settings.webSearchProvider) ??
          null
        : null,
    [settings],
  );
  const availableThemeOptions = useMemo<ThemeOption[]>(
    () => (settings?.availableThemes?.length ? settings.availableThemes : FALLBACK_THEME_OPTIONS),
    [settings],
  );
  const currentThemeOption = useMemo<ThemeOption | null>(
    () => (settings ? availableThemeOptions.find((theme) => theme.id === settings.themeId) ?? null : null),
    [availableThemeOptions, settings],
  );
  const workflowPresets = useMemo<WorkflowPreset[]>(
    () => resolveWorkflowPresets(settings),
    [settings],
  );
  const currentWorkflowPreset = useMemo<WorkflowPreset | null>(
    () => resolveSelectedWorkflowPreset(settings),
    [settings],
  );
  const activeInferenceStarter = useMemo(
    () =>
      settings
        ? settings.availableGenerationStarters.find((starter) =>
            matchesGenerationStarter(settings, starter),
          ) ?? null
        : null,
    [settings],
  );

  if (!settings || !schema || !turboConfig || !workspaceHygiene) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam podešavanja..."
        onRetry={() => {
          setError(null);
          void reload();
        }}
      />
    );
  }

  const allTurboPresets = [...schema.builtInPresets, ...schema.userPresets];
  const profileOptions = [
    ...settings.builtInSettingsProfiles.map((profile) => ({
      value: profile.id,
      label: `${profile.name} (${profile.summary})`,
    })),
    ...settings.userSettingsProfiles.map((profile) => ({
      value: profile.id,
      label: `${profile.name} (${profile.summary})`,
    })),
    { value: "custom", label: "Prilagođeno (trenutne vrednosti)" },
  ];
  const contextChoice = resolveTokenChoice(settings.context);
  const outputTokensChoice = resolveTokenChoice(settings.outputTokens);
  const activeSettings = settings;
  const activeTurboConfig = turboConfig;
  const turboContextChoice = resolveTokenChoice(activeTurboConfig.context);
  const activeInferenceSummary = buildInferenceSummaryItems(settings);
  const activeInferenceSummaryCards = activeInferenceSummary.map((item) => ({
    ...item,
    definition: resolveInferenceDefinitionForSummaryLabel(item.label),
  }));
  const savedInferenceSummary = buildInferenceSummaryItems(settingsDefaults ?? settings);
  const primaryInferenceSummary = activeInferenceSummaryCards.filter((item) =>
    INFERENCE_PRIMARY_LABELS.includes(item.label as (typeof INFERENCE_PRIMARY_LABELS)[number]),
  );
  const secondaryInferenceSummary = activeInferenceSummaryCards.filter(
    (item) =>
      !INFERENCE_PRIMARY_LABELS.includes(item.label as (typeof INFERENCE_PRIMARY_LABELS)[number]),
  );
  const selectedGpuTotalGiB =
    observability?.runtime.selectedGpuTotalGiB ??
    observability?.system.gpuDevices.find((device) => device.selected)?.totalGiB ??
    null;
  const hybridEstimate = estimateHybridRuntimeUsage(
    observability?.runtime.runtimeDiagnostics,
    selectedGpuTotalGiB,
  );
  const autoGpuLayersRecommendation = estimateAutoGpuLayersFromTotalGiB(selectedGpuTotalGiB);
  const activeRuntimeContext =
    observability?.runtime.activeRuntime === "turboquant" ? activeTurboConfig.context : activeSettings.context;
  const previewGpuLayersValue =
    activeSettings.gpuLayersMode === "manual" && activeSettings.gpuLayersOverride > 0
      ? activeSettings.gpuLayersOverride
      : autoGpuLayersRecommendation;
  const previewContextValue =
    observability?.runtime.activeRuntime === "turboquant" ? activeTurboConfig.context : activeSettings.context;
  const runtimeFitPreview = estimateRuntimeFitPreview(
    observability?.runtime.runtimeDiagnostics,
    activeRuntimeContext,
    selectedGpuTotalGiB,
    previewGpuLayersValue,
    previewContextValue,
  );
  const contextFitEstimate = estimateContextFitFromKvBuffer(
    observability?.runtime.runtimeDiagnostics,
    previewContextValue,
    selectedGpuTotalGiB,
    runtimeFitPreview?.estimatedAdditionalVramToFitMiB,
  );
  const suggestedGpuLayers =
    observability?.runtime.runtimeDiagnostics?.confirmedTotalLayers &&
    observability.runtime.runtimeDiagnostics.confirmedTotalLayers > 0
      ? observability.runtime.runtimeDiagnostics.confirmedTotalLayers
      : null;
  const activeGpuLayersValue = previewGpuLayersValue;
  const totalModelLayers = observability?.runtime.runtimeDiagnostics?.confirmedTotalLayers ?? null;
  const canTryToFitInVram = Boolean(totalModelLayers || suggestedGpuLayers || contextFitEstimate?.suggestedContext);
  const fitBaselineSettings = settingsDefaults ?? activeSettings;
  const fitBaselineTurboConfig = turboConfigDefaults ?? activeTurboConfig;
  const runtimeUsesTurboQuant = observability?.runtime.activeRuntime === "turboquant";
  const savedGpuLayersValue =
    fitBaselineSettings.gpuLayersMode === "manual" && fitBaselineSettings.gpuLayersOverride > 0
      ? fitBaselineSettings.gpuLayersOverride
      : autoGpuLayersRecommendation;
  const savedRuntimeContext = runtimeUsesTurboQuant ? fitBaselineTurboConfig.context : fitBaselineSettings.context;
  const savedRuntimeFitPreview = estimateRuntimeFitPreview(
    observability?.runtime.runtimeDiagnostics,
    savedRuntimeContext,
    selectedGpuTotalGiB,
    savedGpuLayersValue,
    savedRuntimeContext,
  );
  const savedContextFitEstimate = estimateContextFitFromKvBuffer(
    observability?.runtime.runtimeDiagnostics,
    savedRuntimeContext,
    selectedGpuTotalGiB,
    savedRuntimeFitPreview?.estimatedAdditionalVramToFitMiB,
  );
  const vramFitComparisonRows: VramFitComparisonRow[] = [
    {
      label: "GPU layers",
      saved: formatGpuLayersModeLabel(
        fitBaselineSettings.gpuLayersMode,
        fitBaselineSettings.gpuLayersOverride,
        autoGpuLayersRecommendation,
      ),
      editor: formatGpuLayersModeLabel(
        activeSettings.gpuLayersMode,
        activeSettings.gpuLayersOverride,
        autoGpuLayersRecommendation,
      ),
      changed:
        fitBaselineSettings.gpuLayersMode !== activeSettings.gpuLayersMode ||
        fitBaselineSettings.gpuLayersOverride !== activeSettings.gpuLayersOverride,
    },
    {
      label: runtimeUsesTurboQuant ? "TurboQuant context" : "Context",
      saved: formatTokenCount(savedRuntimeContext),
      editor: formatTokenCount(activeRuntimeContext),
      changed: savedRuntimeContext !== activeRuntimeContext,
    },
    {
      label: "Model preliv",
      saved: formatMiB(savedRuntimeFitPreview?.estimatedModelRamSpillMiB),
      editor: formatMiB(runtimeFitPreview?.estimatedModelRamSpillMiB),
      changed:
        savedRuntimeFitPreview?.estimatedModelRamSpillMiB !== runtimeFitPreview?.estimatedModelRamSpillMiB,
    },
    {
      label: "Još VRAM-a",
      saved: formatMiB(savedRuntimeFitPreview?.estimatedAdditionalVramToFitMiB),
      editor: formatMiB(runtimeFitPreview?.estimatedAdditionalVramToFitMiB),
      changed:
        savedRuntimeFitPreview?.estimatedAdditionalVramToFitMiB !==
        runtimeFitPreview?.estimatedAdditionalVramToFitMiB,
    },
    {
      label: "Procena context fit",
      saved: savedContextFitEstimate?.suggestedContext
        ? formatTokenCount(savedContextFitEstimate.suggestedContext)
        : savedContextFitEstimate?.contextOnlyCanFit === false
          ? "Context sam nije dovoljan"
          : "--",
      editor: contextFitEstimate?.suggestedContext
        ? formatTokenCount(contextFitEstimate.suggestedContext)
        : contextFitEstimate?.contextOnlyCanFit === false
          ? "Context sam nije dovoljan"
          : "--",
      changed: savedContextFitEstimate?.suggestedContext !== contextFitEstimate?.suggestedContext,
    },
  ];
  if (runtimeUsesTurboQuant) {
    vramFitComparisonRows.splice(
      2,
      0,
      {
        label: "ctv",
        saved: fitBaselineTurboConfig.ctv,
        editor: activeTurboConfig.ctv,
        changed: fitBaselineTurboConfig.ctv !== activeTurboConfig.ctv,
      },
      {
        label: "ctk",
        saved: fitBaselineTurboConfig.ctk,
        editor: activeTurboConfig.ctk,
        changed: fitBaselineTurboConfig.ctk !== activeTurboConfig.ctk,
      },
    );
  }
  const hasUnsavedVramFitChanges = vramFitComparisonRows.some((row) => row.changed);
  const vramFitLocalResult =
    result &&
    (result.action === "try-fit-in-vram" ||
      result.action === "apply-saved-vram-tuning" ||
      result.action === "save-and-apply-vram-tuning" ||
      result.action === "save-vram-tuning-without-apply")
      ? result
      : null;
  const vramFitLocalLines = (vramFitLocalResult?.details.stdout || vramFitLocalResult?.details.stderr || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const vramFitSavedInConfig =
    !hasUnsavedVramFitChanges ||
    (vramFitLocalResult?.action === "apply-saved-vram-tuning" && vramFitLocalResult.status === "ok") ||
    (vramFitLocalResult?.action === "save-and-apply-vram-tuning" && vramFitLocalResult.status === "ok") ||
    (vramFitLocalResult?.action === "save-vram-tuning-without-apply" && vramFitLocalResult.status === "ok");
  const vramFitAppliedToLiveSystem =
    (vramFitLocalResult?.action === "save-and-apply-vram-tuning" ||
      vramFitLocalResult?.action === "apply-saved-vram-tuning") &&
    vramFitLocalResult.status === "ok";
  const formatInferenceStrip = (
    items: Array<{
      label: string;
      value: string;
    }>,
  ) =>
    items
      .filter((item) =>
        INFERENCE_PRIMARY_LABELS.includes(item.label as (typeof INFERENCE_PRIMARY_LABELS)[number]),
      )
      .map((item) => `${item.label} ${item.value}`)
      .join(" | ");
  const findThemeLabel = (themeId: string) =>
    availableThemeOptions.find((theme) => theme.id === themeId)?.label ?? themeId;
  const generalComparisonRows: VramFitComparisonRow[] = [
    {
      label: "Profil",
      saved: fitBaselineSettings.profile,
      editor: activeSettings.profile,
      changed: fitBaselineSettings.profile !== activeSettings.profile,
    },
    {
      label: "Thinking",
      saved: fitBaselineSettings.thinkingMode,
      editor: activeSettings.thinkingMode,
      changed: fitBaselineSettings.thinkingMode !== activeSettings.thinkingMode,
    },
    {
      label: "Context",
      saved: formatTokenCount(fitBaselineSettings.context),
      editor: formatTokenCount(activeSettings.context),
      changed: fitBaselineSettings.context !== activeSettings.context,
    },
    {
      label: "Output",
      saved: formatTokenCount(fitBaselineSettings.outputTokens),
      editor: formatTokenCount(activeSettings.outputTokens),
      changed: fitBaselineSettings.outputTokens !== activeSettings.outputTokens,
    },
    {
      label: "Tema",
      saved: findThemeLabel(fitBaselineSettings.themeId),
      editor: findThemeLabel(activeSettings.themeId),
      changed: fitBaselineSettings.themeId !== activeSettings.themeId,
    },
    {
      label: "Inference core",
      saved: formatInferenceStrip(savedInferenceSummary),
      editor: formatInferenceStrip(activeInferenceSummary),
      changed:
        fitBaselineSettings.temperature !== activeSettings.temperature ||
        fitBaselineSettings.topK !== activeSettings.topK ||
        fitBaselineSettings.topP !== activeSettings.topP ||
        fitBaselineSettings.seed !== activeSettings.seed,
    },
    {
      label: "Radni direktorijum",
      saved: fitBaselineSettings.workingDirectory || "--",
      editor: activeSettings.workingDirectory || "--",
      changed: fitBaselineSettings.workingDirectory !== activeSettings.workingDirectory,
    },
  ];
  const hasUnsavedGeneralChanges = generalComparisonRows.some((row) => row.changed);
  const searchComparisonRows: VramFitComparisonRow[] = [
    {
      label: "Provider",
      saved: fitBaselineSettings.webSearchProvider,
      editor: activeSettings.webSearchProvider,
      changed: fitBaselineSettings.webSearchProvider !== activeSettings.webSearchProvider,
    },
    {
      label: "Režim",
      saved: fitBaselineSettings.webSearchMode,
      editor: activeSettings.webSearchMode,
      changed: fitBaselineSettings.webSearchMode !== activeSettings.webSearchMode,
    },
    {
      label: "Base URL",
      saved: fitBaselineSettings.webSearchBaseUrl || "managed / default",
      editor: activeSettings.webSearchBaseUrl || "managed / default",
      changed: fitBaselineSettings.webSearchBaseUrl !== activeSettings.webSearchBaseUrl,
    },
    {
      label: "Max rezultata",
      saved: String(fitBaselineSettings.webSearchMaxResults),
      editor: String(activeSettings.webSearchMaxResults),
      changed: fitBaselineSettings.webSearchMaxResults !== activeSettings.webSearchMaxResults,
    },
    {
      label: "Timeout",
      saved: `${fitBaselineSettings.webSearchTimeoutSeconds}s`,
      editor: `${activeSettings.webSearchTimeoutSeconds}s`,
      changed:
        fitBaselineSettings.webSearchTimeoutSeconds !== activeSettings.webSearchTimeoutSeconds,
    },
    {
      label: "Prefiks",
      saved: fitBaselineSettings.webSearchPromptPrefix || "--",
      editor: activeSettings.webSearchPromptPrefix || "--",
      changed:
        fitBaselineSettings.webSearchPromptPrefix !== activeSettings.webSearchPromptPrefix,
    },
  ];
  const hasUnsavedSearchChanges = searchComparisonRows.some((row) => row.changed);
  const turboComparisonRows: VramFitComparisonRow[] = [
    {
      label: "Context",
      saved: formatTokenCount(fitBaselineTurboConfig.context),
      editor: formatTokenCount(activeTurboConfig.context),
      changed: fitBaselineTurboConfig.context !== activeTurboConfig.context,
    },
    {
      label: "ctk",
      saved: fitBaselineTurboConfig.ctk,
      editor: activeTurboConfig.ctk,
      changed: fitBaselineTurboConfig.ctk !== activeTurboConfig.ctk,
    },
    {
      label: "ctv",
      saved: fitBaselineTurboConfig.ctv,
      editor: activeTurboConfig.ctv,
      changed: fitBaselineTurboConfig.ctv !== activeTurboConfig.ctv,
    },
    {
      label: "ncmoe",
      saved: String(fitBaselineTurboConfig.ncmoe),
      editor: String(activeTurboConfig.ncmoe),
      changed: fitBaselineTurboConfig.ncmoe !== activeTurboConfig.ncmoe,
    },
    {
      label: "Flash attention",
      saved: fitBaselineTurboConfig.flashAttention ? "Uključeno" : "Isključeno",
      editor: activeTurboConfig.flashAttention ? "Uključeno" : "Isključeno",
      changed: fitBaselineTurboConfig.flashAttention !== activeTurboConfig.flashAttention,
    },
    {
      label: "mlock",
      saved: fitBaselineTurboConfig.mlock ? "Uključeno" : "Isključeno",
      editor: activeTurboConfig.mlock ? "Uključeno" : "Isključeno",
      changed: fitBaselineTurboConfig.mlock !== activeTurboConfig.mlock,
    },
  ];
  const hasUnsavedTurboChanges = turboComparisonRows.some((row) => row.changed);
  const activeTurboPreset = allTurboPresets.find((preset) =>
    Object.entries(preset.settings).every(
      ([key, value]) => activeTurboConfig[key as keyof TurboQuantConfig] === value,
    ),
  );
  const settingsSaveResult =
    result && (result.action === "apply-settings" || result.action === "restore-model-settings")
      ? result
      : null;
  const turboSaveResult =
    result &&
    (result.action === "save-turboquant-config" ||
      result.action === "save-turboquant-preset" ||
      result.action === "delete-turboquant-preset" ||
      result.action === "restore-turboquant-config")
      ? result
      : null;

  function updateInferenceSetting(key: InferenceParameterKey, value: number) {
    setSettings({
      ...activeSettings,
      [key]: value,
    } as SettingsPayload);
  }

  function tryToFitInVramInEditor() {
    const currentRuntime = observability?.runtime.activeRuntime;
    const baselineGpuLayers =
      fitBaselineSettings.gpuLayersMode === "manual" && fitBaselineSettings.gpuLayersOverride > 0
        ? fitBaselineSettings.gpuLayersOverride
        : autoGpuLayersRecommendation;
    const targetGpuLayers =
      totalModelLayers ??
      suggestedGpuLayers ??
      baselineGpuLayers ??
      0;
    const currentContextValue =
      currentRuntime === "turboquant" ? fitBaselineTurboConfig.context : fitBaselineSettings.context;
    const fallbackContextChoices = [262144, 131072, 65536, 32768, 16384, 8192, 4096];
    const fallbackContextTarget =
      fallbackContextChoices.find((value) => value < currentContextValue) ?? currentContextValue;
    const fitBaselinePreview = estimateRuntimeFitPreview(
      observability?.runtime.runtimeDiagnostics,
      currentContextValue,
      selectedGpuTotalGiB,
      targetGpuLayers,
      currentContextValue,
    );
    const fitBaselineContextEstimate = estimateContextFitFromKvBuffer(
      observability?.runtime.runtimeDiagnostics,
      currentContextValue,
      selectedGpuTotalGiB,
      fitBaselinePreview?.estimatedAdditionalVramToFitMiB,
    );
    const targetContext =
      fitBaselineContextEstimate?.suggestedContext ??
      ((fitBaselinePreview?.estimatedAdditionalVramToFitMiB ?? 0) > 0 ? fallbackContextTarget : currentContextValue);
    const nextPreview = estimateRuntimeFitPreview(
      observability?.runtime.runtimeDiagnostics,
      currentContextValue,
      selectedGpuTotalGiB,
      targetGpuLayers,
      targetContext,
    );
    const nextGpuLayerSettings: SettingsPayload = {
      ...activeSettings,
      gpuLayersMode: "manual",
      gpuLayersOverride: targetGpuLayers,
      context: currentRuntime === "turboquant" ? activeSettings.context : targetContext,
    };
    let nextTurboConfig: TurboQuantConfig = activeTurboConfig;
    if (currentRuntime === "turboquant") {
      const deficitMiB = fitBaselinePreview?.estimatedAdditionalVramToFitMiB ?? 0;
      nextTurboConfig = {
        ...activeTurboConfig,
        context: targetContext,
        flashAttention: true,
        runtimePreference: "turboquant",
        ctv: deficitMiB > 256 ? "turbo2" : activeTurboConfig.ctv === "turbo4" ? "turbo3" : activeTurboConfig.ctv,
        ctk:
          deficitMiB > 768
            ? "turbo2"
            : deficitMiB > 256
              ? activeTurboConfig.ctk === "turbo4"
                ? "turbo3"
                : activeTurboConfig.ctk
              : activeTurboConfig.ctk,
      };
    }

    setSettings(nextGpuLayerSettings);
    if (nextTurboConfig !== activeTurboConfig) {
      setTurboConfig(nextTurboConfig);
    }

    const turboChanges: string[] = [];
    if (currentRuntime === "turboquant") {
      if (nextTurboConfig.context !== activeTurboConfig.context) {
        turboChanges.push(`TurboQuant context: ${activeTurboConfig.context} → ${nextTurboConfig.context}`);
      }
      if (nextTurboConfig.ctv !== activeTurboConfig.ctv) {
        turboChanges.push(`ctv: ${activeTurboConfig.ctv} → ${nextTurboConfig.ctv}`);
      }
      if (nextTurboConfig.ctk !== activeTurboConfig.ctk) {
        turboChanges.push(`ctk: ${activeTurboConfig.ctk} → ${nextTurboConfig.ctk}`);
      }
    }

    setResult({
      status: "ok",
      action: "try-fit-in-vram",
      summary:
        "Predlog za VRAM fit je upisan u editor. Još nije sačuvan ni aktivan u runtime-u; pregledaj razlike pa klikni `Sačuvaj i primeni na runtime` kada želiš da postanu aktivne.",
      details: {
        returncode: 0,
        stdout: [
          `GPU layers: ${formatGpuLayersModeLabel(fitBaselineSettings.gpuLayersMode, fitBaselineSettings.gpuLayersOverride, autoGpuLayersRecommendation)} → Ručno ${targetGpuLayers}`,
          targetContext !== currentContextValue
            ? currentRuntime === "turboquant"
              ? `TurboQuant context: ${currentContextValue} → ${targetContext}`
              : `Context: ${currentContextValue} → ${targetContext}`
            : "",
          `Model preliv procena: ${formatMiB(fitBaselinePreview?.estimatedModelRamSpillMiB)} → ${formatMiB(nextPreview?.estimatedModelRamSpillMiB)}`,
          `Još VRAM-a procena: ${formatMiB(fitBaselinePreview?.estimatedAdditionalVramToFitMiB)} → ${formatMiB(nextPreview?.estimatedAdditionalVramToFitMiB)}`,
          ...turboChanges,
        ]
          .filter(Boolean)
          .join("\n"),
        stderr: "",
      },
    });
  }

  async function saveAndApplyCurrentVramTuning() {
    setVramFitBusy(true);
    try {
      const settingsResult = await applySettings(activeSettings);
      if (settingsResult.status !== "ok") {
        setResult(settingsResult);
        return;
      }

      let turboResult: ActionResult | null = null;
      if (observability?.runtime.activeRuntime === "turboquant") {
        turboResult = await saveTurboQuantConfig(activeTurboConfig);
        if (turboResult.status !== "ok") {
          setResult(turboResult);
          return;
        }
      }

      setSettingsDefaults({ ...activeSettings });
      if (observability?.runtime.activeRuntime === "turboquant") {
        setTurboConfigDefaults({ ...activeTurboConfig });
      }

      const restartResult = await startServer();
      setResult({
        status:
          restartResult.status === "ok" && (!turboResult || turboResult.status === "ok") ? "ok" : restartResult.status,
        action: "save-and-apply-vram-tuning",
        summary: [
          `Trenutno VRAM tuning podešavanje je sačuvano i poslato na runtime.`,
          `Ako je runtime već aktivan, RuntimePilot ga restartuje; ako nije, pokreće ga sa novim vrednostima.`,
          `GPU layers režim: ${activeSettings.gpuLayersMode === "manual" ? `ručno ${activeSettings.gpuLayersOverride || 0}` : `auto ${autoGpuLayersRecommendation || 0}`}.`,
          observability?.runtime.activeRuntime === "turboquant"
            ? `TurboQuant context: ${activeTurboConfig.context}.`
            : `Context: ${activeSettings.context}.`,
          restartResult.summary,
        ]
          .filter(Boolean)
          .join(" "),
        details: {
          returncode: restartResult.details.returncode,
          stdout: [settingsResult.summary, turboResult?.summary, restartResult.summary].filter(Boolean).join("\n"),
          stderr: restartResult.details.stderr || turboResult?.details.stderr || settingsResult.details.stderr,
        },
      });
      await reload();
    } finally {
      setVramFitBusy(false);
    }
  }

  async function saveCurrentVramTuningWithoutApply() {
    setVramFitBusy(true);
    try {
      const settingsResult = await applySettings(activeSettings);
      if (settingsResult.status !== "ok") {
        setResult(settingsResult);
        return;
      }

      let turboResult: ActionResult | null = null;
      if (observability?.runtime.activeRuntime === "turboquant") {
        turboResult = await saveTurboQuantConfig(activeTurboConfig);
        if (turboResult.status !== "ok") {
          setResult(turboResult);
          return;
        }
      }

      setSettingsDefaults({ ...activeSettings });
      if (observability?.runtime.activeRuntime === "turboquant") {
        setTurboConfigDefaults({ ...activeTurboConfig });
      }

      setResult({
        status: "ok",
        action: "save-vram-tuning-without-apply",
        summary:
          "VRAM tuning je sačuvan u configu, ali nije još primenjen na živi sistem. Sledeći korak je `Sačuvaj i primeni na runtime` kada želiš restart/pokretanje sa novim vrednostima.",
        details: {
          returncode: 0,
          stdout: [settingsResult.summary, turboResult?.summary].filter(Boolean).join("\n"),
          stderr: turboResult?.details.stderr || settingsResult.details.stderr,
        },
      });
      await reload();
    } finally {
      setVramFitBusy(false);
    }
  }

  async function saveAndApplySavedVramTuning() {
    setVramFitBusy(true);
    try {
      const savedSettings = settingsDefaults ?? activeSettings;
      const savedTurboConfig = turboConfigDefaults ?? activeTurboConfig;
      const restartResult = await startServer();
      setResult({
        status: restartResult.status,
        action: "apply-saved-vram-tuning",
        summary: [
          "Poslednje sačuvano VRAM tuning stanje je poslato na runtime.",
          `GPU layers režim: ${savedSettings.gpuLayersMode === "manual" ? `ručno ${savedSettings.gpuLayersOverride || 0}` : `auto ${autoGpuLayersRecommendation || 0}`}.`,
          observability?.runtime.activeRuntime === "turboquant"
            ? `TurboQuant context: ${savedTurboConfig.context}.`
            : `Context: ${savedSettings.context}.`,
          restartResult.summary,
        ]
          .filter(Boolean)
          .join(" "),
        details: {
          returncode: restartResult.details.returncode,
          stdout: restartResult.summary,
          stderr: restartResult.details.stderr,
        },
      });
      await reload();
    } finally {
      setVramFitBusy(false);
    }
  }

  function applyWorkflowPreset(preset: WorkflowPreset) {
    setSettings({
      ...activeSettings,
      workflowPresetId: preset.id,
      profile: preset.settingsPatch.profile ?? activeSettings.profile,
      context: preset.settingsPatch.context ?? activeSettings.context,
      outputTokens: preset.settingsPatch.outputTokens ?? activeSettings.outputTokens,
      thinkingMode: preset.settingsPatch.thinkingMode ?? activeSettings.thinkingMode,
      temperature: preset.settingsPatch.temperature ?? activeSettings.temperature,
      topK: preset.settingsPatch.topK ?? activeSettings.topK,
      topP: preset.settingsPatch.topP ?? activeSettings.topP,
      minP: preset.settingsPatch.minP ?? activeSettings.minP,
      repeatPenalty: preset.settingsPatch.repeatPenalty ?? activeSettings.repeatPenalty,
      repeatLastN: preset.settingsPatch.repeatLastN ?? activeSettings.repeatLastN,
      presencePenalty: preset.settingsPatch.presencePenalty ?? activeSettings.presencePenalty,
      frequencyPenalty: preset.settingsPatch.frequencyPenalty ?? activeSettings.frequencyPenalty,
      seed: preset.settingsPatch.seed ?? activeSettings.seed,
      webSearchMode: preset.settingsPatch.webSearchMode ?? activeSettings.webSearchMode,
      webSearchProvider: preset.settingsPatch.webSearchProvider ?? activeSettings.webSearchProvider,
    });
  }

  async function saveGeneralSettingsAction() {
    const actionResult = await applySettings(activeSettings);
    setResult(actionResult);
    await reload();
  }

  function restoreSavedGeneralSettings() {
    if (!settingsDefaults) {
      return;
    }
    setSettings({ ...settingsDefaults });
    applyTheme(settingsDefaults.themeId);
    setResult({
      status: "ok",
      action: "restore-model-settings",
      summary: "Opšta podešavanja i pretraga su vraćeni na poslednje sačuvane vrednosti.",
      details: { returncode: 0, stdout: "", stderr: "" },
    });
  }

  async function checkSearchProviderAction() {
    setProviderBusy("check");
    try {
      const providerStatus = await fetchSearchProviderStatus(activeSettings.webSearchProvider);
      updateProviderStatus(providerStatus);
      setResult({
        status: providerStatus.status === "healthy" ? "ok" : "error",
        action: "check-search-provider",
        summary: providerStatus.summary,
        details: {
          returncode: providerStatus.status === "healthy" ? 0 : 1,
          stdout: providerStatus.status === "healthy" ? providerStatus.summary : "",
          stderr: providerStatus.status === "healthy" ? "" : providerStatus.summary,
        },
      });
    } finally {
      setProviderBusy("");
    }
  }

  async function bootstrapSearchProviderAction() {
    setProviderBusy("setup");
    try {
      const payload = await bootstrapManagedSearchProvider(activeSettings.webSearchProvider);
      updateProviderStatus(payload.providerStatus);
      setResult(payload.result);
      await reload();
    } finally {
      setProviderBusy("");
    }
  }

  async function saveTurboQuantConfigAction() {
    const actionResult = await saveTurboQuantConfig(activeTurboConfig);
    setResult(actionResult);
    if (actionResult.status === "ok") {
      clearDraft(TURBOQUANT_DRAFT_STORAGE_KEY);
    }
    await reload();
  }

  function restoreSavedTurboConfig() {
    if (!turboConfigDefaults) {
      return;
    }
    clearDraft(TURBOQUANT_DRAFT_STORAGE_KEY);
    setTurboConfig({ ...turboConfigDefaults });
    setResult({
      status: "ok",
      action: "restore-turboquant-config",
      summary: "TurboQuant editor je vraćen na poslednje sačuvano stanje.",
      details: { returncode: 0, stdout: "", stderr: "" },
    });
  }

  function updateProviderStatus(nextStatus: SearchProviderStatusPayload) {
    setSettings((current) =>
      current
        ? {
            ...current,
            searchProviderStatus: nextStatus,
          }
        : current,
    );
  }

  async function refreshWorkspaceHygieneAction() {
    setHygieneBusy("refresh");
    try {
      const payload = await fetchOpenCodeWorkspaceHygiene();
      setWorkspaceHygiene(payload);
      setResult({
        status: "ok",
        action: "refresh-opencode-hygiene",
        summary: "Disk higijena procena je osvežena.",
        details: { returncode: 0, stdout: "", stderr: "" },
      });
    } catch (reason: unknown) {
      const summary = reason instanceof Error ? reason.message : "Disk higijena procena nije uspela.";
      setResult({
        status: "error",
        action: "refresh-opencode-hygiene",
        summary,
        details: { returncode: 1, stdout: "", stderr: summary },
      });
    } finally {
      setHygieneBusy("");
    }
  }

  async function cleanupWorkspaceHygieneAction() {
    setHygieneBusy("cleanup");
    try {
      const actionResult = await cleanupOpenCodeWorkspaceHygiene();
      setResult(actionResult);
      setWorkspaceHygiene(actionResult.hygiene);
    } catch (reason: unknown) {
      const summary = reason instanceof Error ? reason.message : "Čišćenje OpenCode workspace-a nije uspelo.";
      setResult({
        status: "error",
        action: "cleanup-opencode-workspaces",
        summary,
        details: { returncode: 1, stdout: "", stderr: summary },
      });
    } finally {
      setHygieneBusy("");
    }
  }

  const settingsStatusItems: RuntimePilotStatusDeckItem[] = [
    {
      id: "profile",
      label: "Profil",
      value: selectedSettingsProfile?.name ?? activeSettings.profile,
      detail: `Opseg ${activeSettings.settingsScope === "global" ? "globalni" : "override modela"} | aktivni model ${
        settings.activeModelLabel || "nema"
      }`,
      action: "Idi na profile",
      icon: "settings",
      accent: "rgba(109, 172, 255, 0.34)",
      onClick: () => profileSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "context",
      label: "Context",
      value: formatTokenCount(activeSettings.context),
      detail: `Output ${formatTokenCount(activeSettings.outputTokens)} | workflow ${
        currentWorkflowPreset?.label || "ručno"
      }`,
      action: "Idi na context i VRAM fit",
      icon: "memory",
      accent: "rgba(156, 126, 255, 0.34)",
      onClick: () => vramFitSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "search",
      label: "Search",
      value: settings.searchProviderStatus.providerLabel,
      detail: `${settings.searchProviderStatus.label} | režim ${activeSettings.webSearchMode}`,
      action: "Idi na search provider",
      icon: "search",
      accent: "rgba(88, 222, 193, 0.36)",
      onClick: () => searchSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "theme",
      label: "Tema",
      value: currentThemeOption?.label ?? activeSettings.themeId,
      detail: hasUnsavedGeneralChanges
        ? "Opšti editor ima promene koje još nisu snimljene."
        : "Opšti editor je usklađen sa poslednjim sačuvanim stanjem.",
      action: "Idi na opšti editor",
      icon: "control",
      accent: "rgba(242, 184, 75, 0.38)",
      onClick: () => contextSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "turboquant",
      label: "TurboQuant",
      value: activeTurboPreset?.name ?? "Custom kombinacija",
      detail: `${hasUnsavedTurboChanges ? "Editor ima nesnimljene promene" : "Config je usklađen"} | ${
        observability?.runtime.activeRuntime === "turboquant" ? "runtime aktivan" : "čeka TurboQuant runtime"
      }`,
      action: "Idi na TurboQuant",
      icon: "runtime",
      accent: "rgba(255, 129, 177, 0.34)",
      onClick: () => turboSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
  ];

  const settingsActionItems: RuntimePilotActionDeckItem[] = [
    {
      id: "general",
      code: "GEN",
      title: "Opšta podešavanja",
      subtitle: "PROFIL + TEMA + INFERENCE",
      icon: "settings",
      tone: "primary",
      onClick: () => profileSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "vram",
      code: "CTX",
      title: "Context i VRAM fit",
      subtitle: "TOKENI + GPU FIT",
      icon: "memory",
      onClick: () => vramFitSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "search",
      code: "WEB",
      title: "Search provider",
      subtitle: "PROVIDER + HEALTH",
      icon: "search",
      onClick: () => searchSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
    {
      id: "turboquant",
      code: "TQ",
      title: "TurboQuant",
      subtitle: "PRESET + CONFIG",
      icon: "runtime",
      onClick: () => turboSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
    },
  ];

  return (
    <div className="settings-page runtimepilot-rack-page">
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Settings tok"
        summary="Ova strana je najlakša kada je koristiš redom: prvo izaberi scope i preset, zatim sredi opšta podešavanja i search, pa tek onda sačuvaj opšti ili TurboQuant deo."
        steps={[
          {
            title: "Izaberi scope i preset",
            detail: "Prvo odluči da li menjaš globalna pravila ili override aktivnog modela, pa onda učitaj profil ili workflow preset.",
          },
          {
            title: "Podesi generaciju, search i temu",
            detail: "Kada je scope jasan, menjaj inference, provider pretrage, temu i ostala opšta podešavanja.",
          },
          {
            title: "Sačuvaj opšta podešavanja",
            detail: "Opšti deo i TurboQuant se čuvaju odvojeno, pa pazi da klikneš pravo dugme za deo koji si menjao.",
          },
        ]}
      />
      <RuntimePilotStatusDeck
        eyebrow="Status dashboard"
        title="Brzi signal podešavanja"
        helper="Pet kartica ti odmah pokazuje koji profil, context, search provider, temu i TurboQuant kombinaciju trenutno drži editor."
        items={settingsStatusItems}
      />
      <RuntimePilotActionDeck
        eyebrow="Akcije"
        title="Skokovi kroz glavne zone"
        helper="Na vrhu ostaju samo četiri jasna skoka: opšta podešavanja, context i VRAM fit, search provider i TurboQuant."
        items={settingsActionItems}
      />
      <ActionResultPanel result={result} />

      <section
        ref={profileSectionRef}
        className="status-card wide-card settings-cluster-card runtimepilot-faceplate-module settings-rack-module"
      >
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Disk higijena OpenCode workspace-a</span>
            <strong className="status-value">
              Čistimo samo disposable izolovane workspace foldere, nikad tvoje modele ili regularne projekte
            </strong>
          </div>
        </div>
        <p className="helper-text">
          Posle klika gledaj odmah ovde: broj kandidata i zauzeće padaju ispod, a gore u poslednjoj akciji
          dobijaš potvrdu šta se stvarno desilo. Auto-cleanup u pozadini proverava isto ovo periodično dok je
          portal aktivan.
        </p>
        <div className="settings-hygiene-grid">
          <article className="settings-explainer-card">
            <span className="settings-field-label">Spremno za čišćenje</span>
            <strong className="status-value">
              {workspaceHygiene.cleanupCandidateCount} foldera · {workspaceHygiene.cleanupCandidateSizeLabel}
            </strong>
            <p className="helper-text">{workspaceHygiene.summary}</p>
          </article>
          <article className="settings-explainer-card">
            <span className="settings-field-label">Zaštićeno</span>
            <strong className="status-value">
              {workspaceHygiene.activeWorkspaceCount} aktivno · {workspaceHygiene.recentFallbackProtectedCount} privremeno zaštićeno
            </strong>
            <p className="helper-text">
              Aktivni OpenCode workspace nikad ne brišemo. Ako proces radi ali putanja nije jasno vidljiva, čuvamo i
              najskoriji disposable workspace dok se sesija ne ugasi.
            </p>
          </article>
          <article className="settings-explainer-card">
            <span className="settings-field-label">Lokacija</span>
            <strong className="status-value">OpenCode scratch i copy workspace-i</strong>
            <code className="settings-hygiene-path">{workspaceHygiene.workspaceRoot}</code>
          </article>
          <article className="settings-explainer-card">
            <span className="settings-field-label">Auto-cleanup</span>
            <strong className="status-value">
              {workspaceHygiene.lastAutoCleanup.hasRun
                ? `${workspaceHygiene.lastAutoCleanup.removedCount} obrisano · ${workspaceHygiene.lastAutoCleanup.freedSizeLabel}`
                : "Još nije radio"}
            </strong>
            <p className="helper-text">
              {workspaceHygiene.lastAutoCleanup.summary}
              {" "}
              {workspaceHygiene.lastAutoCleanup.hasRun
                ? `Poslednji ciklus: ${formatAutoCleanupCompletedAt(workspaceHygiene.lastAutoCleanup.completedAt)}.`
                : "Kada portal ostane aktivan, auto-cleanup sam proverava disposable workspace-e u pozadini."}
            </p>
          </article>
        </div>
        <div className="settings-action-row">
          <button
            type="button"
            onClick={() => {
              void refreshWorkspaceHygieneAction();
            }}
            disabled={hygieneBusy !== ""}
          >
            {hygieneBusy === "refresh" ? "Osvežavam procenu..." : "Osveži procenu"}
          </button>
          <button
            type="button"
            onClick={() => {
              void cleanupWorkspaceHygieneAction();
            }}
            disabled={hygieneBusy !== "" || !workspaceHygiene.canCleanup}
          >
            {hygieneBusy === "cleanup" ? "Čistim disposable workspace-e..." : "Očisti sada"}
          </button>
        </div>
        <div className="settings-hygiene-item-list">
          {workspaceHygiene.items.length ? (
            workspaceHygiene.items.slice(0, 6).map((item) => (
              <article key={item.path} className="settings-hygiene-item">
                <div className="settings-hygiene-item-head">
                  <strong>{item.name}</strong>
                  <span
                    className={`compat-badge ${
                      item.isActive
                        ? "compat-badge-ok"
                        : item.cleanupEligible
                          ? "compat-badge-warn"
                          : "compat-badge"
                    }`}
                  >
                    {item.isActive
                      ? "Aktivno / zaštićeno"
                      : item.cleanupEligible
                        ? "Spremno za čišćenje"
                        : "Privremeno zaštićeno"}
                  </span>
                </div>
                <p className="helper-text">
                  {formatWorkspaceHygieneKind(item.kind)} · {item.sizeLabel} · poslednja izmena{" "}
                  {formatWorkspaceHygieneModifiedAt(item.modifiedAt)}
                </p>
                <code className="settings-hygiene-path">{item.path}</code>
              </article>
            ))
          ) : (
            <article className="compat-empty-state">
              <strong className="status-value">Nema disposable OpenCode workspace foldera</strong>
              <p className="helper-text">
                Kada koristiš izolovani OpenCode, ovde ćeš videti samo scratch, copy i worktree foldere koje je
                RuntimePilot sam napravio.
              </p>
            </article>
          )}
        </div>
        {workspaceHygiene.items.length > 6 ? (
          <p className="helper-text">
            Prikazano je prvih 6 stavki. Procena i čišćenje i dalje važe za sve disposable workspace foldere iz ove
            lokacije.
          </p>
        ) : null}
        {workspaceHygiene.manualReviewLocations.length ? (
          <div className="settings-hygiene-manual">
            <span className="settings-field-label">Ručno proveri i ove spoljne lokacije</span>
            <div className="settings-hygiene-manual-list">
              {workspaceHygiene.manualReviewLocations.map((item) => (
                <article key={`${item.label}-${item.path}`} className="settings-explainer-card">
                  <strong className="status-value">{item.label}</strong>
                  <p className="helper-text">{item.summary}</p>
                  <code className="settings-hygiene-path">{item.path}</code>
                </article>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section
        ref={searchSectionRef}
        className="status-card wide-card settings-cluster-card runtimepilot-faceplate-module settings-rack-module"
      >
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Profili i opseg</span>
            <strong className="status-value">
              Aktivni model: {settings.activeModelLabel || "nema"} ({settings.activeModelId || "--"})
            </strong>
          </div>
        </div>
        <div className="settings-cluster-grid settings-cluster-grid-profiles">
          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Opseg podešavanja</span>
            <p className="helper-text">
              Globalna podrazumevana važe za sve modele bez posebnog override-a. Override aktivnog modela važi
              samo za trenutno aktivni model.
            </p>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.settingsScope}
                options={[
                  { value: "global", label: "Globalna podrazumevana" },
                  { value: "model", label: "Override aktivnog modela" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    settingsScope: value,
                  })
                }
                ariaLabel="Izaberi opseg podešavanja"
              />
            </div>
            <p className="helper-text">
              {settings.modelOverrideExists
                ? "Za aktivni model već postoji poseban override."
                : "Za aktivni model trenutno nema posebnog override-a."}
            </p>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Profil</span>
            <div className="settings-control-block settings-control-block-wide">
              <CustomSelect
                value={selectedSettingsProfileId}
                options={profileOptions}
                onChange={(value) => {
                  if (value === "custom") {
                    setResult({
                      status: "ok",
                      action: "select-settings-profile",
                      summary: "Editor je ostao na prilagođenim vrednostima.",
                      details: { returncode: 0, stdout: "", stderr: "" },
                    });
                    return;
                  }
                  const profile = settingsProfiles.find((item) => item.id === value);
                  if (!profile) {
                    return;
                  }
                  setSettings(mergeSettingsProfile(settings, profile));
                  setResult({
                    status: "ok",
                    action: "load-settings-profile",
                    summary: `Profil ${profile.name} je učitan u editor.`,
                    details: { returncode: 0, stdout: "", stderr: "" },
                  });
                }}
                ariaLabel="Izaberi settings profil"
              />
            </div>
            <p className="helper-text">
              Profil puni editor za context, output tokens, režim pristupa i OpenCode profil.
            </p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Radni preseti</span>
            <div className="settings-option-grid">
              {workflowPresets.map((preset) => {
                const active = currentWorkflowPreset?.id === preset.id;
                const presetInferenceSummary = buildInferenceSummaryItems({
                  temperature: preset.settingsPatch.temperature ?? settings.temperature,
                  topK: preset.settingsPatch.topK ?? settings.topK,
                  topP: preset.settingsPatch.topP ?? settings.topP,
                  minP: preset.settingsPatch.minP ?? settings.minP,
                  repeatPenalty: preset.settingsPatch.repeatPenalty ?? settings.repeatPenalty,
                  repeatLastN: preset.settingsPatch.repeatLastN ?? settings.repeatLastN,
                  presencePenalty:
                    preset.settingsPatch.presencePenalty ?? settings.presencePenalty,
                  frequencyPenalty:
                    preset.settingsPatch.frequencyPenalty ?? settings.frequencyPenalty,
                  seed: preset.settingsPatch.seed ?? settings.seed,
                });
                return (
                  <button
                    key={preset.id}
                    type="button"
                    className={`theme-option-card ${active ? "theme-option-card-active" : ""}`}
                    onClick={() => applyWorkflowPreset(preset)}
                  >
                    <span className="theme-option-name">{preset.label}</span>
                    <span className="theme-option-copy">{preset.summary}</span>
                    <span className="muted-line">{preset.badges.join(" | ")}</span>
                    <span className="muted-line">
                      Inference sažetak:{" "}
                      {presetInferenceSummary
                        .filter((item) =>
                          ["Temp", "Top-k", "Top-p", "Seed"].includes(item.label),
                        )
                        .map((item) => `${item.label.toLowerCase()} ${item.value}`)
                        .join(" | ")}
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="helper-text">
              Aktivni radni preset: {currentWorkflowPreset?.label || "Istraživanje"}.
            </p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Sačuvaj trenutni custom profil</span>
            <div className="settings-action-row">
              <input
                className="settings-profile-name-input"
                placeholder="Ime novog profila"
                value={settingsProfileName}
                onChange={(event) => setSettingsProfileName(event.target.value)}
              />
              <button
                type="button"
                onClick={async () => {
                  const actionResult = await saveSettingsProfile({
                    name: settingsProfileName,
                    settings: buildSettingsProfileDraft(settings),
                  });
                  setResult(actionResult);
                  if (actionResult.status === "ok") {
                    setSettingsProfileName("");
                  }
                  await reload();
                }}
              >
                Sačuvaj profil
              </button>
              {selectedSettingsProfile && selectedSettingsProfile.kind === "user" ? (
                <button
                  type="button"
                  className="danger-button"
                  onClick={async () => {
                    const actionResult = await deleteSettingsProfile(selectedSettingsProfile.id);
                    setResult(actionResult);
                    await reload();
                  }}
                >
                  Obriši izabrani profil
                </button>
              ) : null}
            </div>
            <p className="helper-text">
              Trenutno aktivan izbor:{" "}
              {selectedSettingsProfile
                ? `${selectedSettingsProfile.name} (${selectedSettingsProfile.summary})`
                : "custom"}
            </p>
          </article>
        </div>
      </section>

      <section
        ref={turboSectionRef}
        className="status-card wide-card settings-cluster-card runtimepilot-faceplate-module settings-rack-module"
      >
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Opšta podešavanja</span>
            <strong className="status-value">Glavni radni profil za RuntimePilot i lokalni model</strong>
          </div>
        </div>
        <div className="settings-general-hifi-stack">
          <section className="settings-general-mixer-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">1. Menjanje</span>
                <strong className="status-value">Kontrole, miks i radni profil</strong>
              </div>
              <p className="helper-text">
                Ovaj deo je sada pravi faceplate: prvo biraš radni profil, context, output i inferencu, pa tek onda odlučuješ kada ćeš to upisati u živi sistem.
              </p>
            </div>

            <div className="settings-general-mixer-grid">
              <article className="settings-field settings-field-wide inference-spotlight-card settings-general-panel">
                <div className="inference-spotlight-shell">
                  <div className="inference-spotlight-main">
                    <span className="settings-field-label">Aktivna inference podešavanja</span>
                    <strong className="status-value inference-spotlight-value">
                      {primaryInferenceSummary.map((item) => `${item.label} ${item.value}`).join(" | ")}
                    </strong>
                    <div className="inference-spotlight-tips">
                      <span>Brzi orijentiri</span>
                      <span>Za kod: niža `temperature`, niži `top-k`, fiksan `seed`.</span>
                      <span>Za chat: viša `temperature` i širi `top-k` / `top-p`.</span>
                      <span>Za benchmark: fiksan `seed` i mirniji sampling.</span>
                    </div>
                    <p className="helper-text">
                      Ove vrednosti trenutno ulaze u `llama.cpp` ili `TurboQuant` start komandu i postaju local-lacc podrazumevana inference podešavanja kada klijent ne pošalje svoje sampling argumente.
                    </p>
                    <p className="helper-text">
                      Workflow preset: {currentWorkflowPreset?.label || "--"} | Starter orijentir:{" "}
                      {activeInferenceStarter?.label || "custom kombinacija"}
                    </p>
                  </div>
                  <div className="inference-spotlight-rail">
                    <div className="inference-primary-grid">
                      {primaryInferenceSummary.map((item) => (
                        <div className="inference-primary-card" key={item.label}>
                          <span className="inference-primary-card-label">{item.label}</span>
                          <strong className="inference-primary-card-value">{item.value}</strong>
                          {item.definition ? (
                            <span className="inference-summary-chip-note">{item.definition.quickHint}</span>
                          ) : null}
                        </div>
                      ))}
                    </div>
                    <div className="inference-summary-grid">
                      {secondaryInferenceSummary.map((item) => (
                        <div className="inference-summary-chip" key={item.label}>
                          <span className="inference-summary-chip-label">{item.label}</span>
                          <strong className="inference-summary-chip-value">{item.value}</strong>
                          {item.definition ? (
                            <span className="inference-summary-chip-note">{item.definition.quickHint}</span>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </article>

              <div className="settings-general-mini-grid">
                <article className="settings-field settings-general-panel">
                  <span className="settings-field-label">Režim pristupa</span>
                  <div className="settings-control-block">
                    <CustomSelect
                      value={settings.accessMode}
                      options={[
                        { value: "local-only", label: "Samo lokalno" },
                        { value: "tailscale", label: "Tailscale" },
                      ]}
                      onChange={(value) =>
                        setSettings({
                          ...settings,
                          accessMode: value,
                        })
                      }
                      ariaLabel="Izaberi režim pristupa"
                    />
                  </div>
                  <p className="helper-text">Lokalno ili Tailscale izlaganje backend-a.</p>
                </article>

                <article className="settings-field settings-general-panel">
                  <span className="settings-field-label">OpenCode profil</span>
                  <div className="settings-control-block">
                    <CustomSelect
                      value={settings.profile}
                      options={[
                        { value: "speed", label: "speed" },
                        { value: "balanced", label: "balanced" },
                        { value: "video", label: "video" },
                      ]}
                      onChange={(value) =>
                        setSettings({
                          ...settings,
                          profile: value,
                        })
                      }
                      ariaLabel="Izaberi OpenCode profil"
                    />
                  </div>
                </article>

                <article className="settings-field settings-general-panel">
                  <span className="settings-field-label">Thinking režim</span>
                  <div className="settings-control-block">
                    <CustomSelect
                      value={settings.thinkingMode}
                      options={[
                        { value: "no-thinking", label: "Bez thinking-a" },
                        { value: "low", label: "Nisko" },
                        { value: "mid", label: "Srednje" },
                        { value: "high", label: "Visoko" },
                        { value: "extra-high", label: "Vrlo visoko" },
                      ]}
                      onChange={(value) =>
                        setSettings({
                          ...settings,
                          thinkingMode: value,
                        })
                      }
                      ariaLabel="Izaberi thinking režim"
                    />
                  </div>
                </article>

                <article
                  className="settings-field settings-general-panel"
                  ref={contextSectionRef}
                >
                  <span className="settings-field-label">Context</span>
                  <div className="settings-number-row">
                    <CustomSelect
                      value={contextChoice}
                      options={[
                        ...TOKEN_STEP_OPTIONS.map((option) => ({
                          value: option.value,
                          label: option.label,
                        })),
                        { value: "custom", label: "custom" },
                      ]}
                      onChange={(value) => {
                        if (value === "custom") {
                          return;
                        }
                        setSettings({
                          ...settings,
                          context: Number(value),
                        });
                      }}
                      ariaLabel="Izaberi context veličinu"
                    />
                    {contextChoice === "custom" ? (
                      <input
                        type="number"
                        value={settings.context}
                        aria-label="Unesi context veličinu"
                        onChange={(event) =>
                          setSettings({
                            ...settings,
                            context: Number(event.target.value || 0),
                          })
                        }
                      />
                    ) : null}
                  </div>
                </article>

                <article className="settings-field settings-general-panel">
                  <span className="settings-field-label">Output tokens</span>
                  <div className="settings-number-row">
                    <CustomSelect
                      value={outputTokensChoice}
                      options={[
                        ...TOKEN_STEP_OPTIONS.map((option) => ({
                          value: option.value,
                          label: option.label,
                        })),
                        { value: "custom", label: "custom" },
                      ]}
                      onChange={(value) => {
                        if (value === "custom") {
                          return;
                        }
                        setSettings({
                          ...settings,
                          outputTokens: Number(value),
                        });
                      }}
                      ariaLabel="Izaberi output token limit"
                    />
                    {outputTokensChoice === "custom" ? (
                      <input
                        type="number"
                        value={settings.outputTokens}
                        aria-label="Unesi output token limit"
                        onChange={(event) =>
                          setSettings({
                            ...settings,
                            outputTokens: Number(event.target.value || 0),
                          })
                        }
                      />
                    ) : null}
                  </div>
                </article>
              </div>

              <article className="settings-field settings-field-wide settings-general-panel">
                <span className="settings-field-label">Tema boja</span>
                <div className="settings-option-grid">
                  {availableThemeOptions.map((theme) => {
                    const active = settings.themeId === theme.id;
                    return (
                      <button
                        key={theme.id}
                        type="button"
                        className={`theme-option-card ${active ? "theme-option-card-active" : ""}`}
                        onClick={() => {
                          setSettings({
                            ...settings,
                            themeId: theme.id,
                          });
                          applyTheme(theme.id);
                        }}
                      >
                        <span
                          className="theme-option-name"
                          style={{
                            color: theme.textColor,
                            borderColor: `${theme.accent}55`,
                            background: `${theme.accent}18`,
                          }}
                        >
                          {theme.label}
                        </span>
                        <span className="theme-option-copy">{theme.summary}</span>
                      </button>
                    );
                  })}
                </div>
                <p className="helper-text">
                  Trenutna tema: {currentThemeOption?.label || "Dark Chocolate"}.
                </p>
              </article>

              <article className="settings-field settings-field-wide settings-general-panel">
                <span className="settings-field-label">Generacija i sampling</span>
                <p className="helper-text">
                  Ovo su inference argumenti koji najviše utiču na ponašanje `llama.cpp`, lokalnog modela i `OpenCode local-lacc` toka. Iste vrednosti se koriste i za start komandu servera i kao podrazumevani runtime-proxy fallback kada klijent ne pošalje svoje sampling parametre.
                </p>
                <div className="settings-option-grid">
                  {settings.availableGenerationStarters.map((starter) => (
                    <button
                      key={starter.id}
                      type="button"
                      className="theme-option-card"
                      onClick={() =>
                        setSettings({
                          ...settings,
                          temperature: starter.settings.temperature,
                          topK: starter.settings.topK,
                          topP: starter.settings.topP,
                          minP: starter.settings.minP,
                          repeatPenalty: starter.settings.repeatPenalty,
                          repeatLastN: starter.settings.repeatLastN,
                          presencePenalty: starter.settings.presencePenalty,
                          frequencyPenalty: starter.settings.frequencyPenalty,
                          seed: starter.settings.seed,
                        })
                      }
                    >
                      <span className="theme-option-name">{starter.label}</span>
                      <span className="theme-option-copy">{starter.summary}</span>
                      <span className="muted-line">{starter.source}</span>
                      <span className="muted-line">{formatGenerationStarterValues(starter.settings)}</span>
                    </button>
                  ))}
                </div>
                <div className="inference-guide-head">
                  <span className="settings-field-label">Šta radi i kada da ga menjaš</span>
                  <p className="helper-text">
                    Kratke smernice ispod služe kao praktičan početak. Za ozbiljno poređenje run-ova drži se fiksnog `seed`-a i niže `temperature`, a za opušteniji razgovor pomeraj `temperature`, `top-k` i `top-p`.
                  </p>
                </div>
                <div className="inference-parameter-grid">
                  {INFERENCE_PARAMETER_DEFINITIONS.map((field) => (
                    <article className="settings-field inference-parameter-card" key={field.key}>
                      <span className="settings-field-label">{field.label}</span>
                      <input
                        type="number"
                        step={field.step}
                        value={settings[field.key]}
                        onChange={(event) =>
                          updateInferenceSetting(field.key, Number(event.target.value || 0))
                        }
                      />
                      <p className="inference-parameter-note">{field.description}</p>
                      <div className="inference-parameter-ranges">
                        <span>Za kodiranje: {field.coding}</span>
                        <span>Za kreativniji chat: {field.creative}</span>
                        <span>Za stabilne benchmarke: {field.benchmark}</span>
                      </div>
                    </article>
                  ))}
                </div>
                <p className="helper-text">
                  Qwen instruct preporuke često idu oko `temp 0.7`, `top-p 0.8`, `top-k 20`, dok je za coding i reprodukciju korisno spustiti temperaturu i koristiti fiksiran seed.
                </p>
              </article>

              <article className="settings-field settings-field-wide settings-general-panel">
                <span className="settings-field-label">Radni direktorijum</span>
                <div className="settings-path-row">
                  <input
                    className="settings-path-input"
                    value={settings.workingDirectory}
                    onChange={(event) =>
                      setSettings({
                        ...settings,
                        workingDirectory: event.target.value,
                      })
                    }
                  />
                  <button
                    type="button"
                    onClick={() =>
                      pickWorkingDirectory().then((payload) => {
                        if (payload.path) {
                          setSettings({
                            ...settings,
                            workingDirectory: payload.path,
                          });
                        }
                      })
                    }
                  >
                    Pregledaj
                  </button>
                </div>
                <p className="helper-text">
                  Ovo važi za opšti radni kontekst RuntimePilot-a, OpenCode integraciju i lokalne workflow tokove.
                </p>
              </article>
            </div>
          </section>

          <section className="settings-general-transport-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">2. Primena i snimanje</span>
                <strong className="status-value">Sačuvaj, vrati i profiliši opšti deo</strong>
              </div>
              <p className="helper-text">
                Ovaj transport deck upisuje opšti config, search deo i inference podrazumevane vrednosti. Ako je runtime već aktivan, RuntimePilot ga restartuje sa novim profilom kada to zahteva backend.
              </p>
            </div>

            <div className="settings-vram-transport-actions settings-general-transport-actions">
              <button
                type="button"
                className="action-button-soft settings-vram-transport-button"
                onClick={restoreSavedGeneralSettings}
              >
                <span className="settings-vram-transport-symbol" aria-hidden="true">▣</span>
                <span>Vrati sačuvano stanje</span>
              </button>
              <button
                type="button"
                className="action-button"
                onClick={() => {
                  void saveGeneralSettingsAction();
                }}
              >
                <span className="settings-vram-transport-symbol" aria-hidden="true">▶</span>
                <span>Sačuvaj opšta podešavanja</span>
              </button>
            </div>

            <div className="settings-action-route-grid">
              <article className="settings-action-route-card">
                <span className="settings-field-label">Klik i ishod</span>
                <strong className="status-value">Editor odmah pokazuje šta si promenio.</strong>
                <p className="helper-text">
                  Menjanje context-a, output-a, teme ili sampling-a vidiš čim napraviš izmenu u gornjem deck-u.
                </p>
              </article>
              <article className="settings-action-route-card">
                <span className="settings-field-label">Sačuvaj opšta podešavanja</span>
                <strong className="status-value">Poslednja akcija potvrđuje da je config upisan.</strong>
                <p className="helper-text">
                  Kad klikneš snimanje, potvrdu prvo čitaš u panelu poslednje akcije, pa onda ispod proveravaš poređenje sačuvano vs editor.
                </p>
              </article>
              <article className="settings-action-route-card">
                <span className="settings-field-label">Monitoring</span>
                <strong className="status-value">Monitoring ispod kaže da li živi sistem stvarno prati sačuvano stanje.</strong>
                <p className="helper-text">
                  Ako ima razlike između editora, config-a i aktivnog rada, ovde odmah vidiš gde je tok stao.
                </p>
              </article>
            </div>

            <div className="settings-vram-transport-actions settings-vram-transport-actions-aux">
              <article className="settings-field settings-general-panel settings-general-profile-save">
                <span className="settings-field-label">Sačuvaj trenutni custom profil</span>
                <div className="settings-action-row">
                  <input
                    className="settings-profile-name-input"
                    placeholder="Ime novog profila"
                    value={settingsProfileName}
                    onChange={(event) => setSettingsProfileName(event.target.value)}
                  />
                  <button
                    type="button"
                    onClick={async () => {
                      const actionResult = await saveSettingsProfile({
                        name: settingsProfileName,
                        settings: buildSettingsProfileDraft(settings),
                      });
                      setResult(actionResult);
                      if (actionResult.status === "ok") {
                        setSettingsProfileName("");
                      }
                      await reload();
                    }}
                  >
                    Sačuvaj profil
                  </button>
                  {selectedSettingsProfile && selectedSettingsProfile.kind === "user" ? (
                    <button
                      type="button"
                      className="danger-button"
                      onClick={async () => {
                        const actionResult = await deleteSettingsProfile(selectedSettingsProfile.id);
                        setResult(actionResult);
                        await reload();
                      }}
                    >
                      Obriši izabrani profil
                    </button>
                  ) : null}
                </div>
              </article>
            </div>
          </section>

          <section className="settings-general-monitor-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">3. Monitoring</span>
                <strong className="status-value">Šta je u editoru, šta je sačuvano i šta vodi sistem</strong>
              </div>
              <p className="helper-text">
                Ovde vidiš da li se editor odvojio od poslednjeg sačuvanog stanja i koji preset ili starter trenutno vodi ostatak sistema.
              </p>
            </div>

            <div className="apply-state-panel settings-vram-transport-status">
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Editor</span>
                <strong className="apply-state-chip-value">
                  {hasUnsavedGeneralChanges ? "Ima nesnimljenih promena" : "Usklađen sa configom"}
                </strong>
              </article>
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Profil</span>
                <strong className="apply-state-chip-value">
                  {selectedSettingsProfile ? selectedSettingsProfile.name : "custom"}
                </strong>
              </article>
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Starter</span>
                <strong className="apply-state-chip-value">
                  {activeInferenceStarter?.label || "custom kombinacija"}
                </strong>
              </article>
            </div>

            <div className="settings-action-route-grid settings-action-route-grid-compact">
              <article className="settings-action-route-card settings-action-route-card-compact">
                <span className="settings-field-label">Editor</span>
                <p className="helper-text">Ovde prvo vidiš da li izmena još živi samo u editoru.</p>
              </article>
              <article className="settings-action-route-card settings-action-route-card-compact">
                <span className="settings-field-label">Config</span>
                <p className="helper-text">Ako je sačuvano, poređenje ispod mora da se poravna sa editorom.</p>
              </article>
              <article className="settings-action-route-card settings-action-route-card-compact">
                <span className="settings-field-label">Živi sistem</span>
                <p className="helper-text">Ako runtime ili drugi tok još ne prati config, ovde to ispliva bez nagađanja.</p>
              </article>
            </div>

            <article className="settings-field settings-field-wide settings-vram-monitor-card">
              <span className="settings-field-label">Sačuvano i editor</span>
              <strong className="status-value">
                {hasUnsavedGeneralChanges
                  ? "Opšti editor ima promene koje još nisu upisane u config"
                  : "Opšti editor je usklađen sa poslednjim sačuvanim stanjem"}
              </strong>
              <div className="settings-vram-compare-grid settings-general-compare-grid">
                {generalComparisonRows.map((row) => (
                  <article
                    key={row.label}
                    className={`settings-vram-compare-card ${row.changed ? "settings-vram-compare-card-changed" : ""}`}
                  >
                    <span className="settings-vram-compare-label">{row.label}</span>
                    <span className="settings-vram-compare-side">Sačuvano: {row.saved}</span>
                    <span className="settings-vram-compare-side">Editor: {row.editor}</span>
                  </article>
                ))}
              </div>
            </article>

            <div className="compat-empty-state settings-general-status-card">
              <strong>Aktivni orijentiri</strong>
              <div className="summary-metrics">
                <span>Tema: {currentThemeOption?.label || "Dark Chocolate"}</span>
                <span>Workflow preset: {currentWorkflowPreset?.label || "--"}</span>
                <span>Inference starter: {activeInferenceStarter?.label || "custom kombinacija"}</span>
                <span>Poslednja akcija: {settingsSaveResult?.summary || "Nema nove potvrde"}</span>
              </div>
            </div>
          </section>
        </div>
      </section>

      <section className="status-card wide-card settings-cluster-card runtimepilot-faceplate-module settings-rack-module">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">VRAM fit tuning</span>
            <strong className="status-value">Direktan put do cilja da model stane što više u GPU VRAM</strong>
          </div>
        </div>
        <p className="helper-text">
          Ovaj blok sada radi kao hi-fi tok u tri reda: prvo menjaš glavne parametre, zatim biraš da li samo čuvaš ili stvarno primenjuješ, pa tek onda čitaš monitoring i razlike.
        </p>

        <div className="settings-vram-hifi-stack">
          <section
            className="settings-vram-mixer-deck runtimepilot-faceplate-module"
            id="settings-vram-fit"
            ref={vramFitSectionRef}
          >
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">1. Menjanje</span>
                <strong className="status-value">Glavni parametri za VRAM fit</strong>
              </div>
              <p className="helper-text">
                Prvo diraj GPU layers i context. Tek kad to ne pomaže dovoljno, gledaj agresivnije kompromise.
              </p>
            </div>

            <div className="settings-vram-mixer-grid">
              <article className="settings-field settings-vram-channel-card settings-vram-channel-card-wide">
                <span className="settings-field-label">Aktivni runtime signal</span>
                <strong className="status-value">
                  {observability?.runtime.activeRuntime || "--"} | {observability?.runtime.executionModeLabel || "čeka potvrdu"}
                </strong>
                <div className="summary-metrics">
                  <span>GPU: {observability?.runtime.selectedGpuName || observability?.system.gpuName || "--"}</span>
                  <span>Offload: {observability?.runtime.offloadLabel || "--"}</span>
                  <span>Model buffer: {formatMiB(observability?.runtime.runtimeDiagnostics?.modelBufferMiB)}</span>
                  <span>KV buffer: {formatMiB(observability?.runtime.runtimeDiagnostics?.kvBufferMiB)}</span>
                  <span>Compute buffer: {formatMiB(observability?.runtime.runtimeDiagnostics?.computeBufferMiB)}</span>
                </div>
                <p className="helper-text">
                  Ovo je trenutni živi signal. Ako je režim i dalje hibridan, pritisak ide najviše na GPU layers, context i TurboQuant KV kompresiju.
                </p>
              </article>

              <article className="settings-field settings-vram-channel-card">
                <span className="settings-field-label">GPU layers override</span>
                <strong className="status-value">
                  {activeSettings.gpuLayersMode === "manual"
                    ? `Ručno: ${activeSettings.gpuLayersOverride || 0} slojeva`
                    : `Auto: ${autoGpuLayersRecommendation || 0} slojeva`}
                </strong>
                <div className="settings-number-row">
                  <CustomSelect
                    value={settings.gpuLayersMode}
                    options={[
                      { value: "auto", label: "Auto" },
                      { value: "manual", label: "Ručno" },
                    ]}
                    onChange={(value) =>
                      setSettings({
                        ...settings,
                        gpuLayersMode: value,
                      })
                    }
                    ariaLabel="Izaberi GPU layers režim"
                  />
                  {settings.gpuLayersMode === "manual" ? (
                    <input
                      type="number"
                      value={settings.gpuLayersOverride}
                      aria-label="Unesi GPU layers override"
                      onChange={(event) =>
                        setSettings({
                          ...settings,
                          gpuLayersOverride: Number(event.target.value || 0),
                        })
                      }
                    />
                  ) : null}
                </div>
                <div className="summary-metrics">
                  <span>Auto trenutno cilja: {autoGpuLayersRecommendation || 0}</span>
                  <span>Aktivno u editoru: {activeGpuLayersValue || 0}</span>
                  <span>Runtime trenutno traži: {observability?.runtime.runtimeDiagnostics?.requestedGpuLayers ?? "--"}</span>
                  <span>Ukupno slojeva modela: {totalModelLayers ?? "--"}</span>
                </div>
                <p className="helper-text">
                  `Auto` prati procenu po VRAM-u. `Ručno` ti daje direktnu kontrolu kada želiš da guraš čvršći GPU fit.
                </p>
                <p className="helper-text">
                  Više GPU slojeva = više VRAM, ali i veći deo modela ostaje na GPU-u umesto da preliva u RAM.
                </p>
                <p className="helper-text">
                  Runtime se tada još ne restartuje dok ne klikneš neku od komandi u srednjem deck-u.
                </p>
              </article>

              <article className="settings-field settings-vram-channel-card">
                <span className="settings-field-label">Procenjeni context za puni GPU fit</span>
                <strong className="status-value">
                  {contextFitEstimate?.suggestedContext
                    ? `${contextFitEstimate.suggestedContext} tokena`
                    : contextFitEstimate?.contextOnlyCanFit === false
                      ? "Samo spuštanje context-a verovatno nije dovoljno"
                      : "Nema dovoljnog signala za procenu"}
                </strong>
                <p className="helper-text">
                  {contextFitEstimate?.suggestedContext
                    ? `Na osnovu trenutnog KV buffer-a procena je da bi oko ${contextFitEstimate.suggestedContext} tokena oslobodilo približno ${formatMiB(contextFitEstimate.estimatedFreedVramMiB)} VRAM-a.`
                    : contextFitEstimate?.contextOnlyCanFit === false
                      ? "KV buffer nije dovoljan da sam od sebe oslobodi sav nedostajući VRAM. Tada treba i manji quant/model ili agresivniji TurboQuant kompromis."
                      : "Procena postaje korisna tek kada runtime već radi i prijavi čitljiv KV buffer."}
                </p>
                <div className="summary-metrics">
                  <span>Aktivni context: {activeRuntimeContext}</span>
                  <span>Smanjenje: {formatPercent(contextFitEstimate?.estimatedReductionPercent)}</span>
                  <span>Aktivni runtime: {observability?.runtime.activeRuntime || "--"}</span>
                </div>
              </article>
            </div>

            <div className="settings-vram-monitor-strip">
              <article className="settings-vram-meter-card">
                <span className="settings-field-label">Model preliv za editor</span>
                <strong className="status-value">{formatMiB(runtimeFitPreview?.estimatedModelRamSpillMiB)}</strong>
                <p className="helper-text">
                  Ovaj broj se najviše menja kada menjaš `GPU layers`. Pokazuje koliko bi sam model deo i dalje ostao van VRAM-a.
                </p>
              </article>
              <article className="settings-vram-meter-card">
                <span className="settings-field-label">Još VRAM-a za editor</span>
                <strong className="status-value">{formatMiB(runtimeFitPreview?.estimatedAdditionalVramToFitMiB)}</strong>
                <div className="summary-metrics">
                  <span>Trenutni runtime preliv: {formatMiB(hybridEstimate?.estimatedRamSpillMiB)}</span>
                  <span>Editor GPU slojevi: {runtimeFitPreview?.targetGpuLayers ?? "--"}</span>
                  <span>Editor context: {previewContextValue}</span>
                </div>
              </article>
            </div>
          </section>

          <section className="settings-vram-transport-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">2. Primena i snimanje</span>
                <strong className="status-value">Transport deck za config i runtime</strong>
              </div>
              <p className="helper-text">
                `Sačuvaj bez primene` upisuje config. `Primeni postojeće` tera runtime da uzme poslednje sačuvano stanje. `Sačuvaj i primeni` radi oba koraka odjednom.
              </p>
            </div>

            <div className="settings-vram-transport-actions">
              <button
                type="button"
                className="action-button-soft settings-vram-transport-button"
                onClick={() => {
                  void saveCurrentVramTuningWithoutApply();
                }}
                disabled={vramFitBusy}
              >
                <span className="settings-vram-transport-symbol" aria-hidden="true">▣</span>
                <span>{vramFitBusy ? "Čuvam..." : "Sačuvaj bez primene"}</span>
              </button>
              <button
                type="button"
                className="action-button-soft settings-vram-transport-button"
                onClick={() => {
                  void saveAndApplySavedVramTuning();
                }}
                disabled={vramFitBusy}
              >
                <span className="settings-vram-transport-symbol" aria-hidden="true">▶</span>
                <span>{vramFitBusy ? "Primenjujem..." : "Primeni postojeće"}</span>
              </button>
              <button
                type="button"
                className="action-button settings-vram-transport-button settings-vram-transport-button-primary"
                onClick={() => {
                  void saveAndApplyCurrentVramTuning();
                }}
                disabled={vramFitBusy}
              >
                <span className="settings-vram-transport-symbol-group" aria-hidden="true">
                  <span className="settings-vram-transport-symbol">▣</span>
                  <span className="settings-vram-transport-symbol">▶</span>
                </span>
                <span>{vramFitBusy ? "Čuvam i primenjujem..." : "Sačuvaj i primeni"}</span>
              </button>
            </div>

            <div className="settings-vram-transport-actions settings-vram-transport-actions-aux">
              <button
                type="button"
                title="Pokušaj VRAM fit"
                aria-label="Pokušaj VRAM fit"
                className="secondary-button settings-vram-transport-button"
                onClick={tryToFitInVramInEditor}
                disabled={!canTryToFitInVram}
              >
                <span>Pokušaj VRAM fit</span>
              </button>
              {observability?.runtime.activeRuntime === "turboquant" ? (
                <button
                  type="button"
                  className="secondary-button settings-vram-transport-button"
                  onClick={() => setShowTurboQuantGuidance((current) => !current)}
                >
                  <span>{showTurboQuantGuidance ? "Sakrij TurboQuant smernice" : "Prikaži TurboQuant smernice"}</span>
                </button>
              ) : null}
            </div>
          </section>

          <section className="settings-vram-monitor-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">3. Monitoring</span>
                <strong className="status-value">Sačuvano, editor i živi runtime</strong>
              </div>
              <p className="helper-text">
                Ovde vidiš šta je samo promenjeno u editoru, šta je upisano u config i šta je stvarno stiglo do živog runtime-a.
              </p>
            </div>

            <div className="apply-state-panel settings-vram-transport-status">
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Izmenjeno u editoru</span>
                <strong className="apply-state-chip-value">
                  {hasUnsavedVramFitChanges ? "Da, čeka potvrdu" : "Ne, editor je usklađen"}
                </strong>
              </article>
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Sačuvano u configu</span>
                <strong className="apply-state-chip-value">{vramFitSavedInConfig ? "Da" : "Još nije"}</strong>
              </article>
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Primenjeno na živi sistem</span>
                <strong className="apply-state-chip-value">{vramFitAppliedToLiveSystem ? "Da" : "Čeka primenu"}</strong>
              </article>
            </div>

            <article className="settings-field settings-field-wide settings-vram-monitor-card">
              <span className="settings-field-label">Sačuvano i editor</span>
              <strong className="status-value">
                {hasUnsavedVramFitChanges
                  ? "Editor ima nesnimljene VRAM tuning promene"
                  : "Editor je usklađen sa poslednjim sačuvanim VRAM tuning stanjem"}
              </strong>
              <div className="settings-vram-compare-grid">
                {vramFitComparisonRows.map((row) => (
                  <article
                    key={row.label}
                    className={`settings-vram-compare-card ${row.changed ? "settings-vram-compare-card-changed" : ""}`}
                  >
                    <span className="settings-vram-compare-label">{row.label}</span>
                    <span className="settings-vram-compare-side">Sačuvano: {row.saved}</span>
                    <span className="settings-vram-compare-side">Editor: {row.editor}</span>
                  </article>
                ))}
              </div>
            </article>

            <p className="helper-text settings-vram-monitor-copy">
              `Pokušaj VRAM fit` samo popunjava editor smislenijim VRAM-fit vrednostima. `Primeni postojeće` ne dira editor, nego restartuje ili pokreće runtime po poslednjem sačuvanom stanju.
            </p>

            {vramFitLocalResult ? (
              <div className="compat-empty-state settings-vram-local-status">
                <strong>
                  {vramFitLocalResult.action === "try-fit-in-vram"
                    ? "Poslednji VRAM fit predlog"
                    : vramFitLocalResult.action === "save-vram-tuning-without-apply"
                      ? "Poslednje čuvanje bez primene"
                      : "Poslednja primena runtime-a"}
                </strong>
                <p className="helper-text">
                  {vramFitLocalResult.action === "try-fit-in-vram"
                    ? "Ovo još nije sačuvano ni aktivno u runtime-u."
                    : vramFitLocalResult.action === "save-vram-tuning-without-apply"
                      ? "Config je ažuriran, ali runtime još radi po starom dok ne klikneš `Primeni postojeće` ili `Sačuvaj i primeni`."
                      : "Posle primene, živi resursi mogu da kasne nekoliko sekundi dok novi runtime signal ne stigne."}
                </p>
                <p className="helper-text">{vramFitLocalResult.summary}</p>
                {vramFitLocalLines.length ? (
                  <div className="summary-metrics">
                    {vramFitLocalLines.map((line) => (
                      <span key={line}>{line}</span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            {showTurboQuantGuidance && observability?.runtime.activeRuntime === "turboquant" ? (
              <div className="compat-empty-state settings-vram-turbo-guidance">
                <strong>TurboQuant smernice za čistiji VRAM fit</strong>
                <p className="helper-text">
                  Ako hoćeš da sve stane u VRAM, redosled je obično: prvo spusti `context`, zatim proveri `GPU layers`, pa tek onda idi na agresivnije TurboQuant kompromise.
                </p>
                <div className="summary-metrics">
                  <span>Prvo probaj: ctv turbo3</span>
                  <span>Zatim po potrebi: ctk turbo3</span>
                  <span>flashAttention: ostavi uključeno</span>
                  <span>ncmoe: koristi samo ako prihvataš više hibrida</span>
                </div>
              </div>
            ) : null}
          </section>
        </div>
      </section>

      <section className="status-card wide-card settings-cluster-card runtimepilot-faceplate-module settings-rack-module">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Pretraga i izvori</span>
            <strong className="status-value">Kako Search, Knowledge i local-lacc dolaze do web rezultata</strong>
          </div>
        </div>
        <div className="settings-search-hifi-stack">
          <section className="settings-search-mixer-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">1. Menjanje</span>
                <strong className="status-value">Provider, režim i granice pretrage</strong>
              </div>
              <p className="helper-text">
                Ovde biraš odakle Search, Knowledge i local-lacc vuku rezultate. Tek posle toga odlučuješ da li prvo proveravaš stanje ili odmah čuvaš opšti config.
              </p>
            </div>

            <div className="settings-search-mixer-grid">
              <article className="settings-field settings-field-wide settings-general-panel">
                <span className="settings-field-label">Provider pretrage</span>
                <div className="settings-control-block settings-control-block-wide">
                  <CustomSelect
                    value={settings.webSearchProvider}
                    options={settings.availableSearchProviders.map((provider) => ({
                      value: provider.id,
                      label: provider.label,
                    }))}
                    onChange={(value) => {
                      const nextSettings = {
                        ...settings,
                        webSearchProvider: value,
                        webSearchBaseUrl: value === "searxng" ? settings.webSearchBaseUrl : "",
                      };
                      setSettings(nextSettings);
                      void fetchSearchProviderStatus(value).then(updateProviderStatus);
                    }}
                    ariaLabel="Izaberi provider pretrage"
                  />
                </div>
                <p className="helper-text">
                  {currentSearchProviderOption?.summary || "Izaberi provider za Pretragu, Znanje i local-lacc sloj pretrage."}
                </p>
                <p className="helper-text">
                  Ako hoćeš javni provider bez API ključa, biraj DuckDuckGo (public web, no key).
                </p>
              </article>

              <article className="settings-field settings-general-panel">
                <span className="settings-field-label">Režim veb pretrage</span>
                <div className="settings-control-block">
                  <CustomSelect
                    value={settings.webSearchMode}
                    options={[
                      { value: "off", label: "Isključeno" },
                      { value: "on-demand", label: "Na zahtev" },
                      { value: "always", label: "Uvek" },
                    ]}
                    onChange={(value) =>
                      setSettings({
                        ...settings,
                        webSearchMode: value,
                      })
                    }
                    ariaLabel="Izaberi režim veb pretrage"
                  />
                </div>
                <p className="helper-text">
                  Ovo važi za Search tab i za OpenCode kada koristi lokalni `local-lacc` provider.
                </p>
              </article>

              {settings.webSearchProvider === "searxng" ? (
                <article className="settings-field settings-field-wide settings-general-panel">
                  <span className="settings-field-label">Ručni SearxNG base URL (opciono, bez WSL-a)</span>
                  <div className="settings-path-row">
                    <input
                      className="settings-path-input"
                      value={settings.webSearchBaseUrl}
                      onChange={(event) =>
                        setSettings({
                          ...settings,
                          webSearchBaseUrl: event.target.value,
                        })
                      }
                    />
                  </div>
                  <p className="helper-text">
                    Ostavi prazno ako hoćeš da Search koristi managed lokalni SearxNG koji aplikacija sama podigne preko WSL-a.
                  </p>
                </article>
              ) : null}

              <div className="settings-general-mini-grid">
                <article className="settings-field settings-general-panel">
                  <span className="settings-field-label">Limit rezultata pretrage</span>
                  <div className="settings-number-row">
                    <input
                      type="number"
                      value={settings.webSearchMaxResults}
                      onChange={(event) =>
                        setSettings({
                          ...settings,
                          webSearchMaxResults: Number(event.target.value || 0),
                        })
                      }
                    />
                  </div>
                </article>

                <article className="settings-field settings-general-panel">
                  <span className="settings-field-label">Timeout pretrage (s)</span>
                  <div className="settings-number-row">
                    <input
                      type="number"
                      value={settings.webSearchTimeoutSeconds}
                      onChange={(event) =>
                        setSettings({
                          ...settings,
                          webSearchTimeoutSeconds: Number(event.target.value || 0),
                        })
                      }
                    />
                  </div>
                </article>

                <article className="settings-field settings-general-panel">
                  <span className="settings-field-label">Prefiks za zahtev</span>
                  <div className="settings-number-row">
                    <input
                      value={settings.webSearchPromptPrefix}
                      onChange={(event) =>
                        setSettings({
                          ...settings,
                          webSearchPromptPrefix: event.target.value,
                        })
                      }
                    />
                  </div>
                </article>
              </div>
            </div>
          </section>

          <section className="settings-search-transport-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">2. Primena i alati</span>
                <strong className="status-value">Proveri, podigni provider i sačuvaj opšti config</strong>
              </div>
              <p className="helper-text">
                Search deo se čuva zajedno sa opštim podešavanjima. Ako radiš sa SearxNG, najpre proveri stanje ili podigni managed instancu, pa onda sačuvaj opšti config.
              </p>
            </div>

            <div className="settings-vram-transport-actions settings-search-transport-actions">
              <button
                type="button"
                className="action-button-soft settings-vram-transport-button"
                disabled={providerBusy !== ""}
                onClick={() => {
                  void checkSearchProviderAction();
                }}
              >
                <span className="settings-vram-transport-symbol" aria-hidden="true">▶</span>
                <span>{providerBusy === "check" ? "Proveravam..." : "Proveri stanje"}</span>
              </button>
              {settings.webSearchProvider === "searxng" ? (
                <button
                  type="button"
                  className="action-button-soft settings-vram-transport-button"
                  disabled={providerBusy !== "" || settings.searchProviderStatus.canBootstrap === false}
                  title={
                    settings.searchProviderStatus.canBootstrap
                      ? undefined
                      : settings.searchProviderStatus.bootstrapSummary
                  }
                  onClick={() => {
                    void bootstrapSearchProviderAction();
                  }}
                >
                  <span className="settings-vram-transport-symbol" aria-hidden="true">▣</span>
                  <span>
                    {providerBusy === "setup"
                      ? "Podešavam managed SearxNG..."
                      : "Podesi managed SearxNG (Windows + WSL)"}
                  </span>
                </button>
              ) : null}
              <button
                type="button"
                className="action-button"
                onClick={() => {
                  void saveGeneralSettingsAction();
                }}
              >
                <span className="settings-vram-transport-symbol" aria-hidden="true">▶</span>
                <span>Sačuvaj opšta podešavanja</span>
              </button>
            </div>
          </section>

          <section className="settings-search-monitor-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">3. Monitoring</span>
                <strong className="status-value">Health, URL i editor naspram sačuvanog stanja</strong>
              </div>
              <p className="helper-text">
                Ovaj panel ti odmah pokazuje da li provider radi, odakle dolazi URL i da li editor nosi još neupisane promene.
              </p>
            </div>

            <div className="apply-state-panel settings-vram-transport-status">
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Editor</span>
                <strong className="apply-state-chip-value">
                  {hasUnsavedSearchChanges ? "Ima promena" : "Usklađen"}
                </strong>
              </article>
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Provider</span>
                <strong className="apply-state-chip-value">
                  {settings.searchProviderStatus.providerLabel}
                </strong>
              </article>
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Health</span>
                <strong className="apply-state-chip-value">{settings.searchProviderStatus.label}</strong>
              </article>
            </div>

            <article className="settings-field settings-field-wide settings-vram-monitor-card">
              <span className="settings-field-label">
                {settings.webSearchProvider === "searxng"
                  ? "Managed lokalni SearxNG (Windows + WSL)"
                  : "DuckDuckGo javni veb (bez ključa)"}
              </span>
              <strong className="status-value">
                {settings.searchProviderStatus.providerLabel}: {settings.searchProviderStatus.label}
              </strong>
              <p className="helper-text">{settings.searchProviderStatus.summary}</p>
              <div className="summary-metrics">
                <span>Izvor: {settings.searchProviderStatus.source || "--"}</span>
                <span>Podešeni URL: {settings.searchProviderStatus.configuredBaseUrl || "--"}</span>
                <span>Efektivni URL: {settings.searchProviderStatus.effectiveBaseUrl || "--"}</span>
                <span>Servis: {settings.searchProviderStatus.serviceLabel || "--"}</span>
              </div>
              {settings.webSearchProvider === "searxng" ? (
                <p className="helper-text">
                  Ovaj automatski setup koristi WSL da lokalno podigne SearxNG. Manualni URL iznad je odvojeni režim i ne zahteva WSL.
                </p>
              ) : (
                <p className="helper-text">
                  DuckDuckGo radi kao javni provider i ne traži WSL, bootstrap ni manualni endpoint.
                </p>
              )}
            </article>

            <article className="settings-field settings-field-wide settings-vram-monitor-card">
              <span className="settings-field-label">Sačuvano i editor</span>
              <strong className="status-value">
                {hasUnsavedSearchChanges
                  ? "Search editor ima promene koje još nisu upisane"
                  : "Search editor je usklađen sa poslednjim sačuvanim stanjem"}
              </strong>
              <div className="settings-vram-compare-grid settings-search-compare-grid">
                {searchComparisonRows.map((row) => (
                  <article
                    key={row.label}
                    className={`settings-vram-compare-card ${row.changed ? "settings-vram-compare-card-changed" : ""}`}
                  >
                    <span className="settings-vram-compare-label">{row.label}</span>
                    <span className="settings-vram-compare-side">Sačuvano: {row.saved}</span>
                    <span className="settings-vram-compare-side">Editor: {row.editor}</span>
                  </article>
                ))}
              </div>
            </article>
          </section>
        </div>
      </section>

      <section className="status-card wide-card settings-cluster-card runtimepilot-faceplate-module settings-rack-module">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">TurboQuant podešavanja</span>
            <strong className="status-value">Odvojeni preset i parametri samo za TurboQuant runtime</strong>
          </div>
        </div>
        <p className="helper-text">
          `safe` je najbezbedniji, `daily` je preporučeni balans, a `max-context` je agresivniji
          kada juriš što duži kontekst.
        </p>
        <p className="helper-text">
          TurboQuant editor ne menja opšta podešavanja. Njegove promene se čuvaju samo kroz posebno
          dugme <code>Sačuvaj TurboQuant podešavanja</code>.
        </p>
        <div className="settings-turbo-hifi-stack">
          <section className="settings-turbo-mixer-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">1. Menjanje</span>
                <strong className="status-value">Preseti, editor i kanali TurboQuant-a</strong>
              </div>
              <p className="helper-text">
                Najprirodniji tok je: prvo učitaj preset ili ručno promeni kanale, zatim sačuvaj TurboQuant config, pa tek onda prati monitoring šta je stvarno ostalo u editoru.
              </p>
            </div>

            <div className="settings-turbo-mixer-grid">
              <article className="settings-field settings-field-wide settings-general-panel">
                <span className="settings-field-label">TurboQuant preseti</span>
                <div className="model-list">
                  {allTurboPresets.map((preset) => (
                    <article className="model-item" key={preset.id}>
                      <div className="model-item-header">
                        <div>
                          <strong>{preset.name}</strong>
                          <div className="muted-line">{preset.description}</div>
                          <div className="muted-line">
                            Context {preset.settings.context} | ctk {preset.settings.ctk} | ctv{" "}
                            {preset.settings.ctv} | ncmoe {preset.settings.ncmoe}
                          </div>
                          {preset.notes ? <p className="helper-text">{preset.notes}</p> : null}
                        </div>
                        <div className="inline-actions">
                          <button
                            type="button"
                            onClick={() => {
                              setTurboConfig(applyPresetToConfig(preset));
                              setResult({
                                status: "ok",
                                action: "apply-preset-local",
                                summary: `Preset ${preset.name} je učitan u editor.`,
                                details: { returncode: 0, stdout: "", stderr: "" },
                              });
                            }}
                          >
                            Učitaj preset
                          </button>
                          {schema.userPresets.some((item) => item.id === preset.id) ? (
                            <button
                              type="button"
                              className="danger-button"
                              onClick={async () => {
                                const actionResult = await deleteTurboQuantPreset(preset.id);
                                setResult(actionResult);
                                await reload();
                              }}
                            >
                              Obriši
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </article>

              <article className="settings-field settings-field-wide settings-general-panel">
                <span className="settings-field-label">Sačuvaj trenutni preset</span>
                <div className="form-grid">
                  <input
                    placeholder="Ime preset-a"
                    value={presetName}
                    onChange={(event) => setPresetName(event.target.value)}
                  />
                  <input
                    placeholder="Kratak opis"
                    value={presetDescription}
                    onChange={(event) => setPresetDescription(event.target.value)}
                  />
                  <input
                    placeholder="Model pattern, npr qwen36-*"
                    value={presetTargetPattern}
                    onChange={(event) => setPresetTargetPattern(event.target.value)}
                  />
                  <input
                    placeholder="Napomena"
                    value={presetNotes}
                    onChange={(event) => setPresetNotes(event.target.value)}
                  />
                  <button
                    type="button"
                    onClick={async () => {
                      const actionResult = await saveTurboQuantPreset({
                        name: presetName,
                        description: presetDescription,
                        targetModelPattern: presetTargetPattern,
                        notes: presetNotes,
                        settings: turboConfig,
                      });
                      setResult(actionResult);
                      setPresetName("");
                      setPresetDescription("");
                      setPresetTargetPattern("");
                      setPresetNotes("");
                      await reload();
                    }}
                  >
                    Sačuvaj preset
                  </button>
                </div>
              </article>

              <article className="settings-field settings-field-wide settings-general-panel">
                <span className="status-label">TurboQuant parametri</span>
                <div className="model-list">
                  {schema.parameters.map((parameter) => (
                    <article className="model-item" key={parameter.id}>
                      <div className="model-item-header">
                        <div>
                          <strong>{parameter.label}</strong>
                          <p className="helper-text">{parameter.whatIsIt}</p>
                          <p className="helper-text">Učinak: {parameter.effect}</p>
                          <p className="helper-text">Preporuka: {parameter.recommendation}</p>
                          <div className="muted-line">
                            Safe: {parameter.safeChoices.join(", ") || "--"} | Advanced:{" "}
                            {parameter.advancedChoices.join(", ") || "--"}
                          </div>
                        </div>
                        <div className="inline-actions">
                          {parameter.id === "context" ? (
                            <div className="settings-number-row">
                              <CustomSelect
                                value={turboContextChoice}
                                options={[
                                  ...TOKEN_STEP_OPTIONS.map((option) => ({
                                    value: option.value,
                                    label: option.label,
                                  })),
                                  { value: "custom", label: "custom" },
                                ]}
                                onChange={(value) => {
                                  if (value === "custom") {
                                    return;
                                  }
                                  setTurboConfig({
                                    ...turboConfig,
                                    context: Number(value),
                                  });
                                }}
                                ariaLabel="Izaberi TurboQuant context veličinu"
                              />
                              {turboContextChoice === "custom" ? (
                                <input
                                  type="number"
                                  value={turboConfig.context}
                                  aria-label="Unesi TurboQuant context veličinu"
                                  onChange={(event) =>
                                    setTurboConfig({
                                      ...turboConfig,
                                      context: Number(event.target.value || 0),
                                    })
                                  }
                                />
                              ) : null}
                            </div>
                          ) : parameter.id === "ncmoe" ? (
                            <input
                              type="number"
                              value={Number(turboConfig[parameter.id as keyof TurboQuantConfig])}
                              onChange={(event) =>
                                setTurboConfig({
                                  ...turboConfig,
                                  [parameter.id]: Number(event.target.value || 0),
                                })
                              }
                            />
                          ) : parameter.id === "flashAttention" || parameter.id === "mlock" ? (
                            <label>
                              <input
                                type="checkbox"
                                checked={Boolean(turboConfig[parameter.id as keyof TurboQuantConfig])}
                                onChange={(event) =>
                                  setTurboConfig({
                                    ...turboConfig,
                                    [parameter.id]: event.target.checked,
                                  })
                                }
                              />{" "}
                              uključeno
                            </label>
                          ) : (
                            <CustomSelect
                              value={String(turboConfig[parameter.id as keyof TurboQuantConfig])}
                              options={[...parameter.safeChoices, ...parameter.advancedChoices].map((choice) => ({
                                value: choice,
                                label: choice,
                              }))}
                              onChange={(value) =>
                                setTurboConfig({
                                  ...turboConfig,
                                  [parameter.id]: value,
                                })
                              }
                              ariaLabel={`Izaberi ${parameter.label}`}
                            />
                          )}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </article>
            </div>
          </section>

          <section className="settings-turbo-transport-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">2. Primena i snimanje</span>
                <strong className="status-value">Sačuvaj TurboQuant config ili vrati sačuvano stanje</strong>
              </div>
              <p className="helper-text">
                TurboQuant editor je odvojen od opštih podešavanja. Ovde odlučuješ da li vraćaš editor na poslednji sačuvani config ili upisuješ novi TurboQuant config.
              </p>
            </div>

            <div className="settings-vram-transport-actions settings-turbo-transport-actions">
              <button
                type="button"
                className="action-button-soft settings-vram-transport-button"
                onClick={restoreSavedTurboConfig}
              >
                <span className="settings-vram-transport-symbol" aria-hidden="true">▣</span>
                <span>Vrati sačuvano stanje</span>
              </button>
              <button
                type="button"
                className="action-button"
                onClick={() => {
                  void saveTurboQuantConfigAction();
                }}
              >
                <span className="settings-vram-transport-symbol" aria-hidden="true">▣</span>
                <span>Sačuvaj TurboQuant podešavanja</span>
              </button>
            </div>
          </section>

          <section className="settings-turbo-monitor-deck runtimepilot-faceplate-module">
            <div className="settings-vram-deck-head">
              <div>
                <span className="settings-field-label">3. Monitoring</span>
                <strong className="status-value">Preset, editor i sačuvani TurboQuant config</strong>
              </div>
              <p className="helper-text">
                Monitoring ti kaže da li editor odstupa od sačuvanog configa i da li trenutna kombinacija liči na neki poznat preset ili je potpuno custom.
              </p>
            </div>

            <div className="apply-state-panel settings-vram-transport-status">
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Editor</span>
                <strong className="apply-state-chip-value">
                  {hasUnsavedTurboChanges ? "Ima nesnimljenih promena" : "Usklađen sa configom"}
                </strong>
              </article>
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Preset</span>
                <strong className="apply-state-chip-value">
                  {activeTurboPreset?.name || "Custom kombinacija"}
                </strong>
              </article>
              <article className="apply-state-chip">
                <span className="apply-state-chip-title">Runtime veza</span>
                <strong className="apply-state-chip-value">
                  {observability?.runtime.activeRuntime === "turboquant" ? "TurboQuant aktivan" : "Čeka TurboQuant runtime"}
                </strong>
              </article>
            </div>

            <article className="settings-field settings-field-wide settings-vram-monitor-card">
              <span className="settings-field-label">Sačuvano i editor</span>
              <strong className="status-value">
                {hasUnsavedTurboChanges
                  ? "TurboQuant editor ima promene koje još nisu upisane"
                  : "TurboQuant editor je usklađen sa poslednjim sačuvanim configom"}
              </strong>
              <div className="settings-vram-compare-grid settings-turbo-compare-grid">
                {turboComparisonRows.map((row) => (
                  <article
                    key={row.label}
                    className={`settings-vram-compare-card ${row.changed ? "settings-vram-compare-card-changed" : ""}`}
                  >
                    <span className="settings-vram-compare-label">{row.label}</span>
                    <span className="settings-vram-compare-side">Sačuvano: {row.saved}</span>
                    <span className="settings-vram-compare-side">Editor: {row.editor}</span>
                  </article>
                ))}
              </div>
            </article>

            <div className="compat-empty-state settings-general-status-card">
              <strong>TurboQuant status</strong>
              <div className="summary-metrics">
                <span>Aktivni preset: {activeTurboPreset?.name || "Custom kombinacija"}</span>
                <span>Preseti ukupno: {allTurboPresets.length}</span>
                <span>Runtime: {observability?.runtime.activeRuntime || "--"}</span>
                <span>Poslednja akcija: {turboSaveResult?.summary || "Nema nove potvrde"}</span>
              </div>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
