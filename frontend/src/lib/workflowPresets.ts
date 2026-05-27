import type { SettingsPayload, WorkflowPreset } from "./types";

export const FALLBACK_WORKFLOW_PRESETS: WorkflowPreset[] = [
  {
    id: "research",
    label: "Research",
    summary: "Web + docs tok za istrazivanje i sintezu.",
    badges: ["web", "docs", "balanced"],
    settingsPatch: {
      profile: "balanced",
      context: 262144,
      outputTokens: 8192,
      thinkingMode: "mid",
      webSearchMode: "on-demand",
      webSearchProvider: "searxng",
    },
    searchDefaults: {
      provider: "searxng",
      suggestedAction: "answer",
      queryHint: "Upisi istrazivacko pitanje ili temu koju treba proveriti na web-u.",
    },
    knowledgeDefaults: {
      mode: "documents+web",
      queryHint: "Pitaj nesto sto treba ukrstiti kroz lokalne dokumente i web izvore.",
    },
    benchmarkDefaults: {
      batteryId: "default",
      launchTarget: "selected",
      runLabel: "Pokreni jedan proverni benchmark za istrazivacki tok.",
    },
  },
  {
    id: "code",
    label: "Code",
    summary: "Kraci output i fokus na kod, bez agresivnog web sloja.",
    badges: ["code", "fast", "docs"],
    settingsPatch: {
      profile: "speed",
      context: 131072,
      outputTokens: 4096,
      thinkingMode: "low",
      webSearchMode: "off",
      webSearchProvider: "duckduckgo",
    },
    searchDefaults: {
      provider: "duckduckgo",
      suggestedAction: "search",
      queryHint: "Upisi biblioteku, error ili API temu koju treba brzo proveriti.",
    },
    knowledgeDefaults: {
      mode: "documents-only",
      queryHint: "Postavi pitanje za lokalni kod, beleške ili dokumentaciju.",
    },
    benchmarkDefaults: {
      batteryId: "default",
      launchTarget: "selected",
      runLabel: "Pokreni kratak benchmark za coding setup.",
    },
  },
  {
    id: "low-vram",
    label: "Low VRAM",
    summary: "Stedljiv preset za manje GPU budzete i laksi runtime.",
    badges: ["safe", "low-vram", "fast"],
    settingsPatch: {
      profile: "speed",
      context: 65536,
      outputTokens: 2048,
      thinkingMode: "low",
      webSearchMode: "on-demand",
      webSearchProvider: "duckduckgo",
    },
    searchDefaults: {
      provider: "duckduckgo",
      suggestedAction: "answer",
      queryHint: "Pitaj nesto gde je bitan sto laksi runtime i kraci odgovor.",
    },
    knowledgeDefaults: {
      mode: "documents-only",
      queryHint: "Pitaj nesto iz lokalnih dokumenata bez dodatnog web opterecenja.",
    },
    benchmarkDefaults: {
      batteryId: "default",
      launchTarget: "selected",
      runLabel: "Pokreni lagani benchmark za low VRAM put.",
    },
  },
  {
    id: "long-context",
    label: "Long context",
    summary: "Naglasak na velikom context-u i duzem kontinuitetu.",
    badges: ["262k", "analysis", "balanced"],
    settingsPatch: {
      profile: "balanced",
      context: 262144,
      outputTokens: 8192,
      thinkingMode: "mid",
      webSearchMode: "on-demand",
      webSearchProvider: "searxng",
    },
    searchDefaults: {
      provider: "searxng",
      suggestedAction: "answer",
      queryHint: "Pitaj nesto sto trazi puno konteksta i vise koraka objasnjenja.",
    },
    knowledgeDefaults: {
      mode: "documents+web",
      queryHint: "Pitaj nesto gde se vise dokumenata i izvora spaja u jednu sliku.",
    },
    benchmarkDefaults: {
      batteryId: "default",
      launchTarget: "battery",
      runLabel: "Pokreni battery benchmark za duzi context.",
    },
  },
  {
    id: "docs-plus-web",
    label: "Docs + web",
    summary: "Knowledge-first tok sa obaveznim citanjem lokalnih izvora i web dopunom.",
    badges: ["knowledge", "citations", "web"],
    settingsPatch: {
      profile: "balanced",
      context: 131072,
      outputTokens: 6144,
      thinkingMode: "mid",
      webSearchMode: "on-demand",
      webSearchProvider: "searxng",
    },
    searchDefaults: {
      provider: "searxng",
      suggestedAction: "search",
      queryHint: "Prvo prikupi web izvore, pa onda odgovori uz lokalne dokumente.",
    },
    knowledgeDefaults: {
      mode: "documents+web",
      queryHint: "Pitaj nesto gde zelis i lokalne dokumente i web izvore u istom odgovoru.",
    },
    benchmarkDefaults: {
      batteryId: "default",
      launchTarget: "selected",
      runLabel: "Pokreni proveru za docs + web tok.",
    },
  },
  {
    id: "benchmark-battery",
    label: "Benchmark battery",
    summary: "Preset za telemetriju, merenje i ponovljiv benchmark tok.",
    badges: ["benchmark", "telemetry", "compare"],
    settingsPatch: {
      profile: "speed",
      context: 32768,
      outputTokens: 2048,
      thinkingMode: "no-thinking",
      webSearchMode: "off",
      webSearchProvider: "duckduckgo",
    },
    searchDefaults: {
      provider: "duckduckgo",
      suggestedAction: "compare",
      queryHint: "Pitaj nesto samo ako hoces da proveris search signal pre benchmark-a.",
    },
    knowledgeDefaults: {
      mode: "documents-only",
      queryHint: "Koristi lokalne dokumente samo kada benchmark notes traze dodatni kontekst.",
    },
    benchmarkDefaults: {
      batteryId: "default",
      launchTarget: "battery",
      runLabel: "Pokreni celu benchmark battery sekvencu.",
    },
  },
];

export function resolveWorkflowPresets(settings: SettingsPayload | null): WorkflowPreset[] {
  if (!settings) {
    return FALLBACK_WORKFLOW_PRESETS;
  }
  return settings.availableWorkflowPresets.length
    ? settings.availableWorkflowPresets
    : FALLBACK_WORKFLOW_PRESETS;
}

export function resolveSelectedWorkflowPreset(settings: SettingsPayload | null): WorkflowPreset | null {
  const presets = resolveWorkflowPresets(settings);
  if (!presets.length) {
    return null;
  }
  const selectedId = settings?.selectedWorkflowPresetId || settings?.workflowPresetId || presets[0].id;
  return presets.find((preset) => preset.id === selectedId) ?? presets[0] ?? null;
}
