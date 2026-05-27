import type { SettingsPayload, WorkflowPreset } from "./types";

export const FALLBACK_WORKFLOW_PRESETS: WorkflowPreset[] = [
  {
    id: "research",
    label: "Research",
    summary: "Web + docs tok za istraživanje i sintezu.",
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
      queryHint: "Upiši istraživačko pitanje ili temu koju treba proveriti na vebu.",
    },
    knowledgeDefaults: {
      mode: "documents+web",
      queryHint: "Pitaj nešto što treba ukrstiti kroz lokalne dokumente i veb izvore.",
    },
    benchmarkDefaults: {
      batteryId: "default",
      launchTarget: "selected",
      runLabel: "Pokreni jedan proverni benchmark za istraživački tok.",
    },
  },
  {
    id: "code",
    label: "Code",
    summary: "Kraći output i fokus na kod, bez agresivnog veb sloja.",
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
      queryHint: "Upiši biblioteku, error ili API temu koju treba brzo proveriti.",
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
    summary: "Štedljiv preset za manje GPU budžete i lakši runtime.",
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
      queryHint: "Pitaj nešto gde je bitan što lakši runtime i kraći odgovor.",
    },
    knowledgeDefaults: {
      mode: "documents-only",
      queryHint: "Pitaj nešto iz lokalnih dokumenata bez dodatnog veb opterećenja.",
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
    summary: "Naglasak na velikom context-u i dužem kontinuitetu.",
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
      queryHint: "Pitaj nešto što traži puno konteksta i više koraka objašnjenja.",
    },
    knowledgeDefaults: {
      mode: "documents+web",
      queryHint: "Pitaj nešto gde se više dokumenata i izvora spaja u jednu sliku.",
    },
    benchmarkDefaults: {
      batteryId: "default",
      launchTarget: "battery",
      runLabel: "Pokreni battery benchmark za duži context.",
    },
  },
  {
    id: "docs-plus-web",
    label: "Docs + web",
    summary: "Knowledge-first tok sa obaveznim čitanjem lokalnih izvora i veb dopunom.",
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
      queryHint: "Prvo prikupi veb izvore, pa onda odgovori uz lokalne dokumente.",
    },
    knowledgeDefaults: {
      mode: "documents+web",
      queryHint: "Pitaj nešto gde želiš i lokalne dokumente i veb izvore u istom odgovoru.",
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
      queryHint: "Pitaj nešto samo ako hoćeš da proveriš search signal pre benchmark-a.",
    },
    knowledgeDefaults: {
      mode: "documents-only",
      queryHint: "Koristi lokalne dokumente samo kada benchmark notes traže dodatni kontekst.",
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
