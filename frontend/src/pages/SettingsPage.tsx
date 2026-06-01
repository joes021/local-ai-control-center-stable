import { useEffect, useMemo, useRef, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { CustomSelect } from "../components/CustomSelect";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import {
  applySettings,
  bootstrapManagedSearchProvider,
  deleteSettingsProfile,
  deleteTurboQuantPreset,
  fetchObservability,
  fetchSearchProviderStatus,
  fetchSettings,
  fetchTurboQuantSchema,
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
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [settingsDefaults, setSettingsDefaults] = useState<SettingsPayload | null>(null);
  const [schema, setSchema] = useState<TurboQuantSchemaPayload | null>(null);
  const [turboConfig, setTurboConfig] = useState<TurboQuantConfig | null>(null);
  const [turboConfigDefaults, setTurboConfigDefaults] = useState<TurboQuantConfig | null>(null);
  const [observability, setObservability] = useState<ObservabilityPayload | null>(null);
  const [settingsProfileName, setSettingsProfileName] = useState("");
  const [presetName, setPresetName] = useState("");
  const [presetDescription, setPresetDescription] = useState("");
  const [presetTargetPattern, setPresetTargetPattern] = useState("");
  const [presetNotes, setPresetNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [providerBusy, setProviderBusy] = useState<"" | "check" | "setup">("");
  const [vramFitBusy, setVramFitBusy] = useState(false);
  const [showTurboQuantGuidance, setShowTurboQuantGuidance] = useState(false);
  const vramFitSectionRef = useRef<HTMLElement | null>(null);

  async function reload() {
    const [settingsPayload, schemaPayload, observabilityPayload] = await Promise.all([
      fetchSettings(),
      fetchTurboQuantSchema(),
      fetchObservability(),
    ]);
    const turboDraft = readDraft<TurboQuantConfig>(TURBOQUANT_DRAFT_STORAGE_KEY);
    const savedTurboConfig = schemaPayload.currentConfig;

    setSettings(settingsPayload);
    setSettingsDefaults(settingsPayload);
    setSchema(schemaPayload);
    setTurboConfigDefaults(savedTurboConfig);
    setTurboConfig(turboDraft ? { ...savedTurboConfig, ...turboDraft } : savedTurboConfig);
    setObservability(observabilityPayload);
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

  if (!settings || !schema || !turboConfig) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="Učitavam settings..."
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
    { value: "custom", label: "custom (trenutne vrednosti)" },
  ];
  const contextChoice = resolveTokenChoice(settings.context);
  const outputTokensChoice = resolveTokenChoice(settings.outputTokens);
  const activeSettings = settings;
  const activeTurboConfig = turboConfig;
  const activeInferenceSummary = buildInferenceSummaryItems(settings);
  const activeInferenceSummaryCards = activeInferenceSummary.map((item) => ({
    ...item,
    definition: resolveInferenceDefinitionForSummaryLabel(item.label),
  }));
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
    result && (result.action === "try-fit-in-vram" || result.action === "save-and-apply-vram-tuning")
      ? result
      : null;
  const vramFitLocalLines = (vramFitLocalResult?.details.stdout || vramFitLocalResult?.details.stderr || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

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

  return (
    <div className="settings-page">
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
      <ActionResultPanel result={result} />
      <section className="status-card wide-card settings-cluster-card">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Kako da koristiš ovu stranu</span>
            <strong className="status-value">Jedan ekran, dva odvojena sistema podešavanja</strong>
          </div>
        </div>
        <div className="settings-explainer-grid">
          <article className="settings-explainer-card">
            <span className="settings-field-label">1. Profili i opseg</span>
            <p className="helper-text">
              Ovde biraš da li menjaš globalna podrazumevana ili override za aktivni model, a profil i
              workflow preset samo pune editor preporučenim vrednostima.
            </p>
          </article>
          <article className="settings-explainer-card">
            <span className="settings-field-label">2. Opšta podešavanja i pretraga</span>
            <p className="helper-text">
              Tema, context, output tokens, OpenCode profil i search provider postaju aktivni tek kada
              klikneš na <code>Sačuvaj opšta podešavanja</code>.
            </p>
          </article>
          <article className="settings-explainer-card">
            <span className="settings-field-label">3. TurboQuant</span>
            <p className="helper-text">
              TurboQuant preset i parametri imaju odvojen editor i čuvaju se posebnim dugmetom
              <code>Sačuvaj TurboQuant podešavanja</code>.
            </p>
          </article>
        </div>
      </section>

      <section className="status-card wide-card settings-cluster-card">
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
                ariaLabel="Izaberi settings scope"
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
                      summary: "Editor je ostao na custom vrednostima.",
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
              Profil puni editor za context, output tokens, access mode i OpenCode profil.
            </p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Workflow presets</span>
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
              Aktivni workflow preset: {currentWorkflowPreset?.label || "Research"}.
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

      <section className="status-card wide-card settings-cluster-card">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Opšta podešavanja</span>
            <strong className="status-value">Glavni radni profil za RuntimePilot i lokalni model</strong>
          </div>
        </div>
        <div className="settings-cluster-grid settings-cluster-grid-core">
          <article className="settings-field settings-field-wide inference-spotlight-card">
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
                  Ove vrednosti trenutno ulaze u `llama.cpp` ili `TurboQuant` start komandu i
                  postaju local-lacc podrazumevana inference podešavanja kada klijent ne pošalje
                  svoje sampling argumente.
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
                        <span className="inference-summary-chip-note">
                          {item.definition.quickHint}
                        </span>
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
                        <span className="inference-summary-chip-note">
                          {item.definition.quickHint}
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Access mode</span>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.accessMode}
                options={[
                  { value: "local-only", label: "Local only" },
                  { value: "tailscale", label: "Tailscale" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    accessMode: value,
                  })
                }
                ariaLabel="Izaberi access mode"
              />
            </div>
            <p className="helper-text">Lokalno ili Tailscale izlaganje backend-a.</p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Color theme</span>
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
                      style={{ color: theme.textColor, borderColor: `${theme.accent}55`, background: `${theme.accent}18` }}
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

          <article className="settings-field">
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

          <article className="settings-field">
            <span className="settings-field-label">Thinking mode</span>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.thinkingMode}
                options={[
                  { value: "no-thinking", label: "No thinking" },
                  { value: "low", label: "Low" },
                  { value: "mid", label: "Mid" },
                  { value: "high", label: "High" },
                  { value: "extra-high", label: "Extra high" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    thinkingMode: value,
                  })
                }
                ariaLabel="Izaberi thinking mode"
              />
            </div>
          </article>

          <article className="settings-field">
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

          <article className="settings-field">
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

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Generacija i sampling</span>
            <p className="helper-text">
              Ovo su inference argumenti koji najviše utiču na ponašanje `llama.cpp`, lokalnog modela
              i `OpenCode local-lacc` toka. Iste vrednosti se koriste i za start komandu servera i kao
              podrazumevani runtime-proxy fallback kada klijent ne pošalje svoje sampling parametre.
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
                Kratke smernice ispod služe kao praktičan početak. Za ozbiljno poređenje run-ova
                drži se fiksnog `seed`-a i niže `temperature`, a za opušteniji razgovor pomeraj
                `temperature`, `top-k` i `top-p`.
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
              Qwen instruct preporuke često idu oko `temp 0.7`, `top-p 0.8`, `top-k 20`, dok je za
              coding i reprodukciju korisno spustiti temperaturu i koristiti fiksiran seed.
            </p>
          </article>

          <article className="settings-field settings-field-wide">
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

      <section className="status-card wide-card settings-cluster-card">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">VRAM fit tuning</span>
            <strong className="status-value">Direktan put do cilja da model stane što više u GPU VRAM</strong>
          </div>
        </div>
        <p className="helper-text">
          Ovde podešavaš ručni <code>GPU layers override</code> i vidiš procenu koliko još fali do
          punog GPU fit-a. Ako je aktivan TurboQuant, isti blok ti govori i kada treba da spustiš
          njegov <code>context</code>.
        </p>
        <p className="helper-text">
          Auto trenutno cilja oko <code>{autoGpuLayersRecommendation || 0}</code> GPU slojeva za
          izabrani GPU. Više GPU slojeva = više VRAM i manje RAM preliva. Manje GPU slojeva = manje
          VRAM, ali više oslanjanja na RAM.
        </p>
        <div className="settings-cluster-grid settings-cluster-grid-core">
          <article
            className="settings-field settings-field-wide settings-vram-fit-card"
            id="settings-vram-fit"
            ref={vramFitSectionRef}
          >
            <span className="settings-field-label">Aktivni runtime signal</span>
            <strong className="status-value">
              {observability?.runtime.activeRuntime || "--"} | {observability?.runtime.executionModeLabel || "Čeka potvrdu"}
            </strong>
            <div className="summary-metrics">
              <span>GPU: {observability?.runtime.selectedGpuName || observability?.system.gpuName || "--"}</span>
              <span>Offload: {observability?.runtime.offloadLabel || "--"}</span>
              <span>Model buffer: {formatMiB(observability?.runtime.runtimeDiagnostics?.modelBufferMiB)}</span>
              <span>KV buffer: {formatMiB(observability?.runtime.runtimeDiagnostics?.kvBufferMiB)}</span>
              <span>Compute buffer: {formatMiB(observability?.runtime.runtimeDiagnostics?.computeBufferMiB)}</span>
            </div>
            <p className="helper-text">
              Ako je režim <code>Hibrid VRAM + RAM</code>, gledaj najviše <code>GPU layers</code>,
              <code>context</code> i TurboQuant KV kompresiju. Ako je model i quant pretežak, ni
              agresivan tuning neće garantovati čist GPU fit.
            </p>
          </article>

          <article className="settings-field">
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
            <p className="helper-text">
              `Auto` prati procenu po VRAM-u. `Ručno` ti daje direktnu kontrolu kada želiš da teraš
              puni fit, na primer <code>{suggestedGpuLayers ?? "--"}</code> sloj{suggestedGpuLayers === 1 ? "" : "a"}.
            </p>
            <p className="helper-text">
              Ako ručno promeniš broj ovde, on postaje aktivan tek kada klikneš
              <code>Sačuvaj opšta podešavanja</code> ili <code>Sačuvaj i primeni na runtime</code>.
            </p>
            <div className="summary-metrics">
              <span>Auto trenutno cilja: {autoGpuLayersRecommendation || 0}</span>
              <span>Aktivno u editoru: {activeGpuLayersValue || 0}</span>
              <span>Runtime trenutno traži: {observability?.runtime.runtimeDiagnostics?.requestedGpuLayers ?? "--"}</span>
              <span>Ukupno slojeva modela: {totalModelLayers ?? "--"}</span>
            </div>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Model preliv za editor</span>
            <strong className="status-value">{formatMiB(runtimeFitPreview?.estimatedModelRamSpillMiB)}</strong>
            <p className="helper-text">
              Ovaj broj se najviše menja kada menjaš <code>GPU layers</code>. Pokazuje koliko bi
              sam model deo i dalje ostao van VRAM-a za trenutno podešavanje u editoru.
            </p>
          </article>

          <article className="settings-field">
            <span className="settings-field-label">Još VRAM-a za editor</span>
            <strong className="status-value">{formatMiB(runtimeFitPreview?.estimatedAdditionalVramToFitMiB)}</strong>
            <p className="helper-text">
              Ovaj broj reaguje i na <code>GPU layers</code> i na <code>context</code>. Ako ostaje
              visok, samo spuštanje context-a verovatno nije dovoljno.
            </p>
            <div className="summary-metrics">
              <span>Trenutni runtime preliv: {formatMiB(hybridEstimate?.estimatedRamSpillMiB)}</span>
              <span>Editor GPU slojevi: {runtimeFitPreview?.targetGpuLayers ?? "--"}</span>
              <span>Editor context: {previewContextValue}</span>
            </div>
          </article>

          <article className="settings-field settings-field-wide">
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

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Sačuvano i editor</span>
            <strong className="status-value">
              {hasUnsavedVramFitChanges
                ? "Editor ima nesnimljene VRAM tuning promene"
                : "Editor je usklađen sa poslednjim sačuvanim VRAM tuning stanjem"}
            </strong>
            <p className="helper-text">
              Ovde odmah vidiš stare i nove vrednosti. Kada klikneš `Try to fit in VRAM`, promene se
              prvo vide ovde, pa tek posle `Sačuvaj i primeni na runtime` postaju aktivne.
            </p>
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

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Preporučeni sledeći korak</span>
            <div className="inline-actions">
              <button
                type="button"
                onClick={() => {
                  void saveAndApplyCurrentVramTuning();
                }}
                disabled={vramFitBusy}
              >
                {vramFitBusy ? "Čuvam i primenjujem..." : "Sačuvaj i primeni na runtime"}
              </button>
              <button
                type="button"
                title="Try to fit in VRAM"
                aria-label="Try to fit in VRAM"
                className="secondary-button"
                onClick={tryToFitInVramInEditor}
                disabled={!canTryToFitInVram}
              >
                Try to fit in VRAM
              </button>
              {observability?.runtime.activeRuntime === "turboquant" ? (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setShowTurboQuantGuidance((current) => !current)}
                >
                  {showTurboQuantGuidance ? "Sakrij TurboQuant smernice" : "Prikaži TurboQuant smernice"}
                </button>
              ) : null}
            </div>
            <p className="helper-text">
              `Try to fit in VRAM` samo popunjava editor smislenijim VRAM-fit vrednostima: puni GPU layers,
              manji context po proceni i, kod TurboQuant-a, jaču KV kompresiju kada izgleda korisno.
              Runtime se tada još ne restartuje. `Sačuvaj i primeni na runtime` je zaseban korak koji tek tada stvarno
              snima i primenjuje ono što vidiš. Ako je runtime već aktivan, RuntimePilot ga restartuje; ako nije, pokreće ga.
            </p>
            {vramFitLocalResult ? (
              <div className="compat-empty-state settings-vram-local-status">
                <strong>
                  {vramFitLocalResult.action === "try-fit-in-vram"
                    ? "Poslednji VRAM fit predlog"
                    : "Poslednja primena runtime-a"}
                </strong>
                <p className="helper-text">
                  {vramFitLocalResult.action === "try-fit-in-vram"
                    ? "Ovo još nije sačuvano ni aktivno u runtime-u."
                    : "Posle čuvanja, Živi resursi mogu da kasne nekoliko sekundi dok novi runtime signal ne stigne."}
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
              <div className="compat-empty-state">
                <strong>TurboQuant smernice za čistiji VRAM fit</strong>
                <p className="helper-text">
                  Ako hoćeš da sve stane u VRAM, redosled je obično: prvo spusti <code>context</code>,
                  zatim proveri <code>GPU layers</code>, pa tek onda idi na agresivnije TurboQuant
                  kompromise.
                </p>
                <div className="summary-metrics">
                  <span>Prvo probaj: ctv turbo3</span>
                  <span>Zatim po potrebi: ctk turbo3</span>
                  <span>flashAttention: ostavi uključeno</span>
                  <span>ncmoe: koristi samo ako prihvataš više hibrida</span>
                </div>
              </div>
            ) : null}
          </article>
        </div>
      </section>

      <section className="status-card wide-card settings-cluster-card">
        <div className="section-header settings-cluster-header">
          <div>
            <span className="status-label">Pretraga i izvori</span>
            <strong className="status-value">Kako Search, Knowledge i local-lacc dolaze do web rezultata</strong>
          </div>
        </div>
        <div className="settings-cluster-grid settings-cluster-grid-core">
          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Šta se ovde zapravo čuva</span>
            <p className="helper-text">
              Ovaj blok kontroliše izbor search providera, health proveru, managed SearxNG setup, režim
              pretrage i limite. Sve promene ovde takođe postaju aktivne tek kada klikneš na
              <code>Sačuvaj opšta podešavanja</code>.
            </p>
          </article>

          <article className="settings-field settings-field-wide">
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
                ariaLabel="Izaberi search provider"
              />
            </div>
            <p className="helper-text">
              {currentSearchProviderOption?.summary || "Izaberi provider za Search, Knowledge i local-lacc search augmentation."}
            </p>
            <p className="helper-text">
              Ako hoćeš javni provider bez API ključa, biraj DuckDuckGo (public web, no key).
            </p>
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">
              {settings.webSearchProvider === "searxng"
                ? "Managed local SearxNG (Windows + WSL)"
                : "DuckDuckGo public web (no key)"}
            </span>
            <strong className="status-value">
              {settings.searchProviderStatus.providerLabel}: {settings.searchProviderStatus.label}
            </strong>
            <p className="helper-text">{settings.searchProviderStatus.summary}</p>
            <div className="summary-metrics">
              <span>Source: {settings.searchProviderStatus.source || "--"}</span>
              <span>Configured URL: {settings.searchProviderStatus.configuredBaseUrl || "--"}</span>
              <span>Effective URL: {settings.searchProviderStatus.effectiveBaseUrl || "--"}</span>
              <span>Service: {settings.searchProviderStatus.serviceLabel || "--"}</span>
            </div>
            <div className="settings-action-row">
              <button
                type="button"
                disabled={providerBusy !== ""}
                onClick={async () => {
                  setProviderBusy("check");
                  try {
                    const providerStatus = await fetchSearchProviderStatus(settings.webSearchProvider);
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
                }}
              >
                {providerBusy === "check" ? "Checking..." : "Check health"}
              </button>
              {settings.webSearchProvider === "searxng" ? (
                <button
                  type="button"
                  disabled={providerBusy !== "" || settings.searchProviderStatus.canBootstrap === false}
                  title={
                    settings.searchProviderStatus.canBootstrap
                      ? undefined
                      : settings.searchProviderStatus.bootstrapSummary
                  }
                  onClick={async () => {
                    setProviderBusy("setup");
                    try {
                      const payload = await bootstrapManagedSearchProvider(settings.webSearchProvider);
                      updateProviderStatus(payload.providerStatus);
                      setResult(payload.result);
                      await reload();
                    } finally {
                      setProviderBusy("");
                    }
                  }}
                >
                  {providerBusy === "setup"
                    ? "Setting up managed SearxNG..."
                    : "Setup managed SearxNG (Windows + WSL)"}
                </button>
              ) : null}
            </div>
            {settings.webSearchProvider === "searxng" ? (
              <p className="helper-text">
                Ovaj automatski setup koristi WSL da lokalno podigne SearxNG. Manualni URL ispod je
                odvojeni režim i ne zahteva WSL.
              </p>
            ) : (
              <p className="helper-text">
                DuckDuckGo radi kao javni provider i ne traži WSL, bootstrap ni manualni endpoint.
              </p>
            )}
          </article>

          <article className="settings-field settings-field-wide">
            <span className="settings-field-label">Web search mode</span>
            <div className="settings-control-block">
              <CustomSelect
                value={settings.webSearchMode}
                options={[
                  { value: "off", label: "Off" },
                  { value: "on-demand", label: "On-demand" },
                  { value: "always", label: "Always" },
                ]}
                onChange={(value) =>
                  setSettings({
                    ...settings,
                    webSearchMode: value,
                  })
                }
                ariaLabel="Izaberi web search mode"
              />
            </div>
            <p className="helper-text">
              Ovo važi za Search tab i za OpenCode kada koristi lokalni `local-lacc` provider. Cloud
              `opencode` modeli ne prolaze kroz ovaj lokalni search sloj.
            </p>
          </article>

          {settings.webSearchProvider === "searxng" ? (
            <article className="settings-field settings-field-wide">
              <span className="settings-field-label">Manual SearxNG base URL (optional, no WSL)</span>
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
                Ostavi prazno ako hoćeš da Search koristi managed lokalni SearxNG koji aplikacija sama
                podigne preko WSL-a.
              </p>
            </article>
          ) : null}

          <article className="settings-field">
            <span className="settings-field-label">Search results limit</span>
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

          <article className="settings-field">
            <span className="settings-field-label">Search timeout (s)</span>
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

          <article className="settings-field">
            <span className="settings-field-label">On-demand prefix</span>
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
        <div className="inline-actions settings-footer-actions">
          <button
            type="button"
            onClick={async () => {
              const actionResult = await applySettings(settings);
              setResult(actionResult);
              await reload();
            }}
          >
            Sačuvaj opšta podešavanja
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              if (!settingsDefaults) {
                return;
              }
              setSettings({ ...settingsDefaults });
              setResult({
                status: "ok",
                action: "restore-model-settings",
                summary: "Model settings su vraćeni na poslednje sačuvane vrednosti.",
                details: { returncode: 0, stdout: "", stderr: "" },
              });
            }}
          >
            Vrati podrazumevano
          </button>
        </div>
        <p className="helper-text">
          Ovde se zajedno čuvaju opšta podešavanja i podešavanja pretrage za izabrani opseg.
        </p>
      </section>

      <section className="status-card wide-card settings-cluster-card">
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
      </section>

      <section className="status-card wide-card">
        <div className="section-header">
          <span className="status-label">TurboQuant preseti</span>
        </div>
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
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Sačuvaj trenutni preset</span>
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
      </section>

      <section className="status-card wide-card">
        <span className="status-label">TurboQuant parametri</span>
        <div className="model-list">
          {schema.parameters.map((parameter) => (
            <article className="model-item" key={parameter.id}>
              <div className="model-item-header">
                <div>
                  <strong>{parameter.label}</strong>
                  <p className="helper-text">{parameter.whatIsIt}</p>
                  <p className="helper-text">Ucinak: {parameter.effect}</p>
                  <p className="helper-text">Preporuka: {parameter.recommendation}</p>
                  <div className="muted-line">
                    Safe: {parameter.safeChoices.join(", ") || "--"} | Advanced:{" "}
                    {parameter.advancedChoices.join(", ") || "--"}
                  </div>
                </div>
                <div className="inline-actions">
                  {parameter.id === "context" || parameter.id === "ncmoe" ? (
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
      </section>

      <section className="status-card wide-card">
        <div className="inline-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={async () => {
              const actionResult = await saveTurboQuantConfig(turboConfig);
              setResult(actionResult);
              if (actionResult.status === "ok") {
                clearDraft(TURBOQUANT_DRAFT_STORAGE_KEY);
              }
              await reload();
            }}
          >
            Sačuvaj TurboQuant podešavanja
          </button>
        </div>
      </section>
    </div>
  );
}
