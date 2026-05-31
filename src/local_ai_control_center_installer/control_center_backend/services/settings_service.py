from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
    atomic_write_json,
    read_json_object,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    _load_profile,
)


THINKING_PRESETS: dict[str, dict[str, int | str]] = {
    "no-thinking": {
        "thinkingMode": "no-thinking",
        "buildSteps": 20,
        "planSteps": 20,
        "generalSteps": 20,
        "exploreSteps": 10,
    },
    "low": {
        "thinkingMode": "low",
        "buildSteps": 40,
        "planSteps": 30,
        "generalSteps": 35,
        "exploreSteps": 20,
    },
    "mid": {
        "thinkingMode": "mid",
        "buildSteps": 140,
        "planSteps": 100,
        "generalSteps": 110,
        "exploreSteps": 80,
    },
    "high": {
        "thinkingMode": "high",
        "buildSteps": 160,
        "planSteps": 120,
        "generalSteps": 130,
        "exploreSteps": 90,
    },
    "extra-high": {
        "thinkingMode": "extra-high",
        "buildSteps": 180,
        "planSteps": 160,
        "generalSteps": 160,
        "exploreSteps": 100,
    },
}

TURBOQUANT_PARAMETERS = [
    {
        "id": "context",
        "label": "Context",
        "whatIsIt": "Koliko tokena razgovora i radnog konteksta držiš u KV cache-u.",
        "effect": "Veći context troši više memorije, ali drži duže sesije.",
        "recommendation": "Prvo menjaj context, pa tek onda agresivnije TurboQuant nivoe.",
        "safeChoices": ["65536", "131072"],
        "advancedChoices": ["262144", "327680"],
        "defaultValue": 131072,
    },
    {
        "id": "ctk",
        "label": "ctk",
        "whatIsIt": "Tip kompresije za K deo KV cache-a.",
        "effect": "turbo4 je bezbedniji, turbo3 je balans, a turbo2 agresivno štedi memoriju.",
        "recommendation": "Za većinu mašina počni sa turbo4.",
        "safeChoices": ["turbo4"],
        "advancedChoices": ["turbo3", "turbo2"],
        "defaultValue": "turbo4",
    },
    {
        "id": "ctv",
        "label": "ctv",
        "whatIsIt": "Tip kompresije za V deo KV cache-a.",
        "effect": "Može mrvu agresivnije od ctk bez prejakog udara po kvalitetu.",
        "recommendation": "Daily balans je turbo3, safe je turbo4.",
        "safeChoices": ["turbo4", "turbo3"],
        "advancedChoices": ["turbo2"],
        "defaultValue": "turbo3",
    },
    {
        "id": "ncmoe",
        "label": "ncmoe",
        "whatIsIt": "Koliko ranih MoE slojeva prebacuješ na CPU.",
        "effect": "Viša vrednost štedi VRAM, ali usporava rad.",
        "recommendation": "Kreni sa 20 pa diži po potrebi.",
        "safeChoices": ["20"],
        "advancedChoices": ["30", "35"],
        "defaultValue": 20,
    },
    {
        "id": "flashAttention",
        "label": "Flash attention",
        "whatIsIt": "Brzi attention put kada ga runtime podržava.",
        "effect": "Najčešće povoljan za performanse.",
        "recommendation": "Drži uključeno osim ako imaš konkretan bug.",
        "safeChoices": ["on"],
        "advancedChoices": ["off"],
        "defaultValue": True,
    },
    {
        "id": "mlock",
        "label": "mlock",
        "whatIsIt": "Pokušava da drži model u RAM-u umesto da ga OS lakše swapuje.",
        "effect": "Smanjuje swap rizik, ali je stroži prema memoriji.",
        "recommendation": "Uglavnom bezbedno za desktop mašinu kada juriš stabilnost.",
        "safeChoices": ["on"],
        "advancedChoices": ["off"],
        "defaultValue": True,
    },
    {
        "id": "mmapMode",
        "label": "mmap mode",
        "whatIsIt": "Menja način učitavanja modela sa diska u memoriju.",
        "effect": "mmap brže pali model; no-mmap ume da bude stabilniji u edge slučajevima.",
        "recommendation": "Koristi mmap osim ako već imaš konkretan razlog protiv.",
        "safeChoices": ["mmap"],
        "advancedChoices": ["no-mmap"],
        "defaultValue": "mmap",
    },
    {
        "id": "runtimePreference",
        "label": "Runtime preference",
        "whatIsIt": "Koji runtime želiš da preferiraš kada su oba dostupna.",
        "effect": "TurboQuant agresivnije štedi memoriju; llama.cpp je jednostavniji fallback.",
        "recommendation": "Ako je TurboQuant stabilan, koristi ga kao prvi izbor.",
        "safeChoices": ["turboquant", "llama.cpp"],
        "advancedChoices": [],
        "defaultValue": "turboquant",
    },
]

TURBOQUANT_BUILTIN_PRESETS = [
    {
        "id": "safe",
        "name": "safe",
        "description": "Najbezbedniji preset za duži rad i najmanji rizik po kvalitet.",
        "targetModelPattern": "qwen36-*",
        "notes": "Manje agresivna kompresija i oprezniji context.",
        "settings": {
            "context": 131072,
            "ctk": "turbo4",
            "ctv": "turbo4",
            "ncmoe": 20,
            "flashAttention": True,
            "mlock": True,
            "mmapMode": "mmap",
            "runtimePreference": "turboquant",
        },
    },
    {
        "id": "daily",
        "name": "daily",
        "description": "Preporučeni balans brzine, memorije i svakodnevnog rada.",
        "targetModelPattern": "qwen36-*",
        "notes": "Preporučeni daily izbor za TurboQuant.",
        "settings": {
            "context": 262144,
            "ctk": "turbo4",
            "ctv": "turbo3",
            "ncmoe": 20,
            "flashAttention": True,
            "mlock": True,
            "mmapMode": "mmap",
            "runtimePreference": "turboquant",
        },
    },
    {
        "id": "max-context",
        "name": "max-context",
        "description": "Agresivniji preset kada juriš najduži context.",
        "targetModelPattern": "qwen36-*",
        "notes": "Jače štedi memoriju uz veći rizik performansi.",
        "settings": {
            "context": 327680,
            "ctk": "turbo3",
            "ctv": "turbo3",
            "ncmoe": 35,
            "flashAttention": True,
            "mlock": True,
            "mmapMode": "no-mmap",
            "runtimePreference": "turboquant",
        },
    },
]

UNSLOTH_RECOMMENDED_MODELS = [
    {
        "id": "unsloth-Qwen3.6-35B-A3B-UD-IQ2_M.gguf",
        "label": "Qwen3.6 35B A3B",
        "repo": "unsloth/Qwen3.6-35B-A3B-GGUF",
        "filename": "Qwen3.6-35B-A3B-UD-IQ2_M.gguf",
        "quantization": "UD-IQ2_M",
        "fitNote": "Realan daily izbor za 3060 12 GB uz TurboQuant.",
        "mtp": False,
    },
    {
        "id": "unsloth-Qwen3.6-35B-A3B-UD-IQ3_S.gguf",
        "label": "Qwen3.6 35B A3B",
        "repo": "unsloth/Qwen3.6-35B-A3B-GGUF",
        "filename": "Qwen3.6-35B-A3B-UD-IQ3_S.gguf",
        "quantization": "UD-IQ3_S",
        "fitNote": "Stretch izbor kada hoćeš bolji kvalitet uz veći pritisak.",
        "mtp": False,
    },
    {
        "id": "unsloth-Qwen3.6-27B-UD-IQ3_XXS.gguf",
        "label": "Qwen3.6 27B",
        "repo": "unsloth/Qwen3.6-27B-GGUF",
        "filename": "Qwen3.6-27B-UD-IQ3_XXS.gguf",
        "quantization": "UD-IQ3_XXS",
        "fitNote": "Najzdraviji 27B balans za tvoj hardver.",
        "mtp": False,
    },
    {
        "id": "unsloth-Qwen3.6-27B-UD-Q2_K_XL.gguf",
        "label": "Qwen3.6 27B",
        "repo": "unsloth/Qwen3.6-27B-GGUF",
        "filename": "Qwen3.6-27B-UD-Q2_K_XL.gguf",
        "quantization": "UD-Q2_K_XL",
        "fitNote": "Stretch 27B izbor kada juriš veći model po svaku cenu.",
        "mtp": False,
    },
]

OPENCODE_STEP_BUILTIN_PRESETS = [
    {
        "id": "safe",
        "name": "Safe",
        "steps": {
            "buildSteps": 80,
            "planSteps": 60,
            "generalSteps": 80,
            "exploreSteps": 50,
        },
    },
    {
        "id": "daily",
        "name": "Daily",
        "steps": {
            "buildSteps": 140,
            "planSteps": 100,
            "generalSteps": 110,
            "exploreSteps": 80,
        },
    },
    {
        "id": "deep",
        "name": "Deep",
        "steps": {
            "buildSteps": 160,
            "planSteps": 120,
            "generalSteps": 130,
            "exploreSteps": 90,
        },
    },
    {
        "id": "max",
        "name": "Max",
        "steps": {
            "buildSteps": 180,
            "planSteps": 160,
            "generalSteps": 160,
            "exploreSteps": 100,
        },
    },
]

ALLOWED_ACCESS_MODES = {"local-only", "tailscale"}
ALLOWED_SECURITY_MODES = {"strict", "workspace-write", "open"}
ALLOWED_CAPABILITY_MODES = {
    "read-only",
    "read-write",
    "confirm-commands",
    "auto-commands",
}
ALLOWED_PROFILES = {"speed", "balanced", "video"}
ALLOWED_THEMES = {
    "dark-chocolate",
    "light",
    "dark",
    "neon-green",
    "marine-blue",
}
THEME_OPTIONS = [
    {
        "id": "dark-chocolate",
        "label": "Dark Chocolate",
        "summary": "Topla tamna podloga sa bronzanim i cijan akcentima.",
        "accent": "#f2b84b",
        "textColor": "#f7dfb0",
    },
    {
        "id": "light",
        "label": "Light",
        "summary": "Svetla radna tema sa toplim zlatnim akcentom.",
        "accent": "#d59b2f",
        "textColor": "#7f5a12",
    },
    {
        "id": "dark",
        "label": "Dark",
        "summary": "Neutralna tamna tema sa hladnijim plavo-sivim tonom.",
        "accent": "#6f8fd8",
        "textColor": "#bfd4ff",
    },
    {
        "id": "neon-green",
        "label": "Neon Green",
        "summary": "Visokokontrastna terminalsko-neonska tema za jak signal.",
        "accent": "#58ff8f",
        "textColor": "#c8ffd9",
    },
    {
        "id": "marine-blue",
        "label": "Marine Blue",
        "summary": "Duboki plavi komandni most sa morskim cijan akcentom.",
        "accent": "#39b7ff",
        "textColor": "#cbe8ff",
    },
]
WORKFLOW_PRESET_SPECS = [
    {
        "id": "research",
        "label": "Research",
        "summary": "Web + docs tok za istraživanje i sintezu.",
        "badges": ["web", "docs", "balanced"],
        "settingsPatch": {
            "profile": "balanced",
            "context": 262144,
            "outputTokens": 8192,
            "thinkingMode": "mid",
            "temperature": 0.7,
            "topK": 20,
            "topP": 0.8,
            "minP": 0.0,
            "repeatPenalty": 1.05,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
            "webSearchMode": "on-demand",
            "webSearchProvider": "searxng",
        },
        "searchDefaults": {
            "provider": "searxng",
            "suggestedAction": "answer",
            "queryHint": "Upiši istraživačko pitanje ili temu koju treba proveriti na vebu.",
        },
        "knowledgeDefaults": {
            "mode": "documents+web",
            "queryHint": "Pitaj nešto što treba ukrstiti kroz lokalne dokumente i veb izvore.",
        },
        "benchmarkDefaults": {
            "batteryId": "default",
            "launchTarget": "selected",
            "runLabel": "Pokreni jedan proverni benchmark za istraživački tok.",
        },
    },
    {
        "id": "code",
        "label": "Code",
        "summary": "Kraći output i fokus na kod, bez agresivnog veb sloja.",
        "badges": ["code", "fast", "docs"],
        "settingsPatch": {
            "profile": "speed",
            "context": 131072,
            "outputTokens": 4096,
            "thinkingMode": "low",
            "temperature": 0.2,
            "topK": 20,
            "topP": 0.9,
            "minP": 0.0,
            "repeatPenalty": 1.03,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": 7,
            "webSearchMode": "off",
            "webSearchProvider": "duckduckgo",
        },
        "searchDefaults": {
            "provider": "duckduckgo",
            "suggestedAction": "search",
            "queryHint": "Upiši biblioteku, error ili API temu koju treba brzo proveriti.",
        },
        "knowledgeDefaults": {
            "mode": "documents-only",
            "queryHint": "Postavi pitanje za lokalni kod, beleške ili dokumentaciju.",
        },
        "benchmarkDefaults": {
            "batteryId": "default",
            "launchTarget": "selected",
            "runLabel": "Pokreni kratak benchmark za coding setup.",
        },
    },
    {
        "id": "low-vram",
        "label": "Low VRAM",
        "summary": "Štedljiv preset za manje GPU budžete i lakši runtime.",
        "badges": ["safe", "low-vram", "fast"],
        "settingsPatch": {
            "profile": "speed",
            "context": 65536,
            "outputTokens": 2048,
            "thinkingMode": "low",
            "temperature": 0.6,
            "topK": 20,
            "topP": 0.9,
            "minP": 0.0,
            "repeatPenalty": 1.05,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
            "webSearchMode": "on-demand",
            "webSearchProvider": "duckduckgo",
        },
        "searchDefaults": {
            "provider": "duckduckgo",
            "suggestedAction": "answer",
            "queryHint": "Pitaj nešto gde je bitan što lakši runtime i kraći odgovor.",
        },
        "knowledgeDefaults": {
            "mode": "documents-only",
            "queryHint": "Pitaj nešto iz lokalnih dokumenata bez dodatnog veb opterećenja.",
        },
        "benchmarkDefaults": {
            "batteryId": "default",
            "launchTarget": "selected",
            "runLabel": "Pokreni lagani benchmark za low VRAM put.",
        },
    },
    {
        "id": "long-context",
        "label": "Long context",
        "summary": "Naglasak na velikom context-u i dužem kontinuitetu.",
        "badges": ["262k", "analysis", "balanced"],
        "settingsPatch": {
            "profile": "balanced",
            "context": 262144,
            "outputTokens": 8192,
            "thinkingMode": "mid",
            "temperature": 0.6,
            "topK": 20,
            "topP": 0.95,
            "minP": 0.0,
            "repeatPenalty": 1.05,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
            "webSearchMode": "on-demand",
            "webSearchProvider": "searxng",
        },
        "searchDefaults": {
            "provider": "searxng",
            "suggestedAction": "answer",
            "queryHint": "Pitaj nešto što traži puno konteksta i više koraka objašnjenja.",
        },
        "knowledgeDefaults": {
            "mode": "documents+web",
            "queryHint": "Pitaj nešto gde se više dokumenata i izvora spaja u jednu sliku.",
        },
        "benchmarkDefaults": {
            "batteryId": "default",
            "launchTarget": "battery",
            "runLabel": "Pokreni battery benchmark za duži context.",
        },
    },
    {
        "id": "docs-plus-web",
        "label": "Docs + web",
        "summary": "Knowledge-first tok sa obaveznim čitanjem lokalnih izvora i veb dopunom.",
        "badges": ["knowledge", "citations", "web"],
        "settingsPatch": {
            "profile": "balanced",
            "context": 131072,
            "outputTokens": 6144,
            "thinkingMode": "mid",
            "temperature": 0.7,
            "topK": 20,
            "topP": 0.8,
            "minP": 0.0,
            "repeatPenalty": 1.05,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
            "webSearchMode": "on-demand",
            "webSearchProvider": "searxng",
        },
        "searchDefaults": {
            "provider": "searxng",
            "suggestedAction": "search",
            "queryHint": "Prvo prikupi veb izvore, pa onda odgovori uz lokalne dokumente.",
        },
        "knowledgeDefaults": {
            "mode": "documents+web",
            "queryHint": "Pitaj nešto gde želiš i lokalne dokumente i veb izvore u istom odgovoru.",
        },
        "benchmarkDefaults": {
            "batteryId": "default",
            "launchTarget": "selected",
            "runLabel": "Pokreni proveru za docs + web tok.",
        },
    },
    {
        "id": "benchmark-battery",
        "label": "Benchmark battery",
        "summary": "Preset za telemetriju, merenje i ponovljiv benchmark tok.",
        "badges": ["benchmark", "telemetry", "compare"],
        "settingsPatch": {
            "profile": "speed",
            "context": 32768,
            "outputTokens": 2048,
            "thinkingMode": "no-thinking",
            "temperature": 0.0,
            "topK": 1,
            "topP": 1.0,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": 42,
            "webSearchMode": "off",
            "webSearchProvider": "duckduckgo",
        },
        "searchDefaults": {
            "provider": "duckduckgo",
            "suggestedAction": "compare",
            "queryHint": "Pitaj nešto samo ako hoćeš da proveriš search signal pre benchmark-a.",
        },
        "knowledgeDefaults": {
            "mode": "documents-only",
            "queryHint": "Koristi lokalne dokumente samo kada benchmark notes traže dodatni kontekst.",
        },
        "benchmarkDefaults": {
            "batteryId": "default",
            "launchTarget": "battery",
            "runLabel": "Pokreni celu benchmark battery sekvencu.",
        },
    },
]
ALLOWED_WORKFLOW_SEARCH_ACTIONS = {"search", "answer", "compare"}
ALLOWED_WORKFLOW_KNOWLEDGE_MODES = {"documents-only", "documents+web", "web-only"}
ALLOWED_WORKFLOW_BENCHMARK_TARGETS = {"selected", "battery"}
WORKFLOW_PRESET_SUMMARY_MAX_LENGTH = 220
WORKFLOW_PRESET_BADGE_MAX_COUNT = 6
WORKFLOW_PRESET_BADGE_MAX_LENGTH = 20
ALLOWED_WEB_SEARCH_MODES = {"off", "on-demand", "always"}
ALLOWED_WEB_SEARCH_PROVIDERS = {"searxng", "duckduckgo"}
WEB_SEARCH_PROVIDER_OPTIONS = [
    {
        "id": "searxng",
        "label": "SearxNG (managed or manual)",
        "supportsBootstrap": True,
        "supportsManualBaseUrl": True,
        "summary": "Najfleksibilniji lokalni provider sa managed WSL bootstrap tokom.",
    },
    {
        "id": "duckduckgo",
        "label": "DuckDuckGo (public web, no key)",
        "supportsBootstrap": False,
        "supportsManualBaseUrl": False,
        "summary": "Javna veb pretraga bez API ključa, best-effort HTML integracija.",
    },
]
LEGACY_DEFAULT_WEB_SEARCH_BASE_URL = "http://127.0.0.1:8080"
ALLOWED_WEB_SEARCH_BASE_URL_MODES = {"managed-auto", "manual"}
DEFAULT_WEB_SEARCH_BASE_URL_MODE = "managed-auto"
DEFAULT_WEB_SEARCH_BASE_URL = ""
DEFAULT_WEB_SEARCH_MAX_RESULTS = 5
DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS = 20
DEFAULT_WEB_SEARCH_PROMPT_PREFIX = "/web"
GENERATION_STARTER_PRESETS = [
    {
        "id": "llama-cpp-default",
        "label": "llama.cpp default",
        "summary": "Konzervativni start iz llama.cpp server README podrazumevanih sampling vrednosti.",
        "settings": {
            "temperature": 0.8,
            "topK": 40,
            "topP": 0.95,
            "minP": 0.05,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
        },
    },
    {
        "id": "qwen-instruct",
        "label": "Qwen instruct",
        "summary": "Qwen Quickstart preporuka za instruct put: 0.7 / 0.8 / 20 / 0.",
        "settings": {
            "temperature": 0.7,
            "topK": 20,
            "topP": 0.8,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
        },
    },
    {
        "id": "qwen-thinking",
        "label": "Qwen thinking",
        "summary": "Qwen Quickstart preporuka za thinking put: 0.6 / 0.95 / 20 / 0.",
        "settings": {
            "temperature": 0.6,
            "topK": 20,
            "topP": 0.95,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
        },
    },
    {
        "id": "llama-instruct",
        "label": "Llama instruct",
        "summary": "Meta Llama instruct polazna tacka: temperatura 0.6 i top-p 0.9.",
        "settings": {
            "temperature": 0.6,
            "topK": 40,
            "topP": 0.9,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
        },
    },
    {
        "id": "gemma-default",
        "label": "Gemma default",
        "summary": "Google Gemma generation_config: temperatura 1.0, top-k 64, top-p 0.95.",
        "settings": {
            "temperature": 1.0,
            "topK": 64,
            "topP": 0.95,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
        },
    },
    {
        "id": "deterministic-code",
        "label": "Deterministicki kod",
        "summary": "Niza temperatura za stabilnije code i forum-to-forum poredjenje.",
        "settings": {
            "temperature": 0.2,
            "topK": 40,
            "topP": 0.9,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
        },
    },
]
SETTINGS_PROFILE_COMPARE_KEYS = (
    "profile",
    "context",
    "outputTokens",
    "workingDirectory",
    "thinkingMode",
    "gpuLayersMode",
    "gpuLayersOverride",
    "buildSteps",
    "planSteps",
    "generalSteps",
    "exploreSteps",
    "accessMode",
    "temperature",
    "topK",
    "topP",
    "minP",
    "repeatPenalty",
    "repeatLastN",
    "presencePenalty",
    "frequencyPenalty",
    "seed",
)
SETTINGS_PROFILE_BUILTIN_SPECS = [
    {
        "id": "balanced",
        "name": "balanced",
        "settings": {
            "profile": "balanced",
            "context": 262144,
            "outputTokens": 8192,
            "thinkingMode": "mid",
            "accessMode": "local-only",
        },
    },
    {
        "id": "speed",
        "name": "speed",
        "settings": {
            "profile": "speed",
            "context": 65536,
            "outputTokens": 4096,
            "thinkingMode": "low",
            "accessMode": "local-only",
        },
    },
    {
        "id": "video",
        "name": "video",
        "settings": {
            "profile": "video",
            "context": 131072,
            "outputTokens": 16384,
            "thinkingMode": "high",
            "accessMode": "local-only",
        },
    },
]


def load_effective_settings_state(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    global_settings = _normalize_global_settings(
        read_json_object(config.settings_path),
        config=config,
    )
    active_model_id = _read_active_model_id(config)
    model_overrides = read_json_object(config.model_overrides_path).get("models", {})
    active_override = (
        model_overrides.get(active_model_id)
        if isinstance(model_overrides, dict) and active_model_id
        else None
    )
    model_override_exists = isinstance(active_override, dict)
    effective = dict(global_settings)
    if model_override_exists:
        effective.update(
            _normalize_settings_payload(
                active_override,
                config=config,
                current=global_settings,
                respect_explicit_steps=True,
            )
        )
    effective["activeModelId"] = active_model_id
    effective["activeModelLabel"] = _resolve_active_model_label(config, active_model_id)
    effective["modelOverrideExists"] = model_override_exists
    effective["settingsScope"] = "model" if model_override_exists else "global"
    return effective


def load_settings_payload(
    config: ControlCenterConfig | None = None,
    *,
    include_search_provider_status: bool = True,
) -> dict[str, object]:
    config = config or get_config()
    effective = load_effective_settings_state(config)
    profile_catalog = load_settings_profile_catalog(config, effective_settings=effective)
    payload = {
        "profile": effective["profile"],
        "themeId": effective["themeId"],
        "workflowPresetId": effective["workflowPresetId"],
        "context": effective["context"],
        "outputTokens": effective["outputTokens"],
        "workingDirectory": effective["workingDirectory"],
        "thinkingMode": effective["thinkingMode"],
        "temperature": effective["temperature"],
        "topK": effective["topK"],
        "topP": effective["topP"],
        "minP": effective["minP"],
        "repeatPenalty": effective["repeatPenalty"],
        "repeatLastN": effective["repeatLastN"],
        "presencePenalty": effective["presencePenalty"],
        "frequencyPenalty": effective["frequencyPenalty"],
        "seed": effective["seed"],
        "gpuLayersMode": effective["gpuLayersMode"],
        "gpuLayersOverride": effective["gpuLayersOverride"],
        "buildSteps": effective["buildSteps"],
        "planSteps": effective["planSteps"],
        "generalSteps": effective["generalSteps"],
        "exploreSteps": effective["exploreSteps"],
        "settingsScope": effective["settingsScope"],
        "activeModelId": effective["activeModelId"],
        "activeModelLabel": effective["activeModelLabel"],
        "modelOverrideExists": effective["modelOverrideExists"],
        "accessMode": effective["accessMode"],
        "webSearchMode": effective["webSearchMode"],
        "webSearchProvider": effective["webSearchProvider"],
        "webSearchBaseUrl": effective["webSearchBaseUrl"],
        "webSearchMaxResults": effective["webSearchMaxResults"],
        "webSearchTimeoutSeconds": effective["webSearchTimeoutSeconds"],
        "webSearchPromptPrefix": effective["webSearchPromptPrefix"],
        "availableThemes": load_theme_options(),
        "availableGenerationStarters": load_generation_starter_presets(),
        "availableWorkflowPresets": load_workflow_presets(config),
        "availableSearchProviders": load_web_search_provider_options(),
        "builtInSettingsProfiles": profile_catalog["builtInProfiles"],
        "userSettingsProfiles": profile_catalog["userProfiles"],
        "selectedSettingsProfileId": profile_catalog["selectedProfileId"],
        "selectedSettingsProfileName": profile_catalog["selectedProfileName"],
        "selectedWorkflowPresetId": effective["workflowPresetId"],
    }
    if include_search_provider_status:
        from local_ai_control_center_installer.control_center_backend.services.search_provider_service import (
            load_search_provider_status,
        )

        payload["searchProviderStatus"] = load_search_provider_status(config)
    return payload


def apply_settings(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    normalized_payload = dict(payload)
    if "webSearchBaseUrl" in normalized_payload and "webSearchBaseUrlMode" not in normalized_payload:
        normalized_payload["webSearchBaseUrlMode"] = (
            "manual"
            if str(normalized_payload.get("webSearchBaseUrl", "") or "").strip()
            else DEFAULT_WEB_SEARCH_BASE_URL_MODE
        )
    scope = str(payload.get("settingsScope", "global") or "global").strip().lower()
    current_global = _normalize_global_settings(
        read_json_object(config.settings_path),
        config=config,
    )
    normalized = _normalize_settings_payload(
        normalized_payload,
        config=config,
        current=current_global,
        respect_explicit_steps=False,
    )
    if scope == "model":
        active_model_id = str(payload.get("activeModelId", "") or "").strip()
        if not active_model_id:
            return action_result(
                "error",
                "apply-settings",
                "Aktivni model nije poznat za model override.",
                stderr="Aktivni model nije poznat za model override.",
            )
        overrides_payload = read_json_object(config.model_overrides_path)
        overrides = overrides_payload.get("models")
        if not isinstance(overrides, dict):
            overrides = {}
        overrides[active_model_id] = _project_model_override_settings(normalized)
        atomic_write_json(config.model_overrides_path, {"models": overrides})
        updated_global = dict(current_global)
        updated_global["themeId"] = normalized["themeId"]
        updated_global["workflowPresetId"] = normalized["workflowPresetId"]
        atomic_write_json(config.settings_path, updated_global)
        return action_result(
            "ok",
            "apply-settings",
            f"Sačuvan je model override za {active_model_id}.",
        )

    atomic_write_json(config.settings_path, normalized)
    return action_result("ok", "apply-settings", "Global settings su sačuvani.")


def apply_opencode_settings(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    normalized_payload = dict(payload)
    if "webSearchBaseUrl" in normalized_payload and "webSearchBaseUrlMode" not in normalized_payload:
        normalized_payload["webSearchBaseUrlMode"] = (
            "manual"
            if str(normalized_payload.get("webSearchBaseUrl", "") or "").strip()
            else DEFAULT_WEB_SEARCH_BASE_URL_MODE
        )
    current_global = _normalize_global_settings(
        read_json_object(config.settings_path),
        config=config,
    )
    normalized = _normalize_settings_payload(
        normalized_payload,
        config=config,
        current=current_global,
        respect_explicit_steps=True,
    )
    atomic_write_json(config.settings_path, normalized)
    return action_result(
        "ok",
        "apply-opencode-settings",
        "OpenCode settings su sačuvani.",
    )


def load_settings_profile_catalog(
    config: ControlCenterConfig | None = None,
    *,
    effective_settings: dict[str, object] | None = None,
) -> dict[str, object]:
    config = config or get_config()
    effective_settings = effective_settings or load_effective_settings_state(config)
    built_in_profiles = _build_builtin_settings_profiles(config)
    user_profiles = load_settings_user_profiles(config)
    matched_profile = _match_settings_profile(
        effective_settings,
        [*built_in_profiles, *user_profiles],
    )
    return {
        "builtInProfiles": built_in_profiles,
        "userProfiles": user_profiles,
        "selectedProfileId": matched_profile.get("id", "custom"),
        "selectedProfileName": matched_profile.get("name", "custom"),
    }


def load_settings_user_profiles(
    config: ControlCenterConfig | None = None,
) -> list[dict[str, object]]:
    config = config or get_config()
    payload = read_json_object(config.settings_profiles_path)
    presets = payload.get("profiles")
    if not isinstance(presets, list):
        return []
    normalized: list[dict[str, object]] = []
    baseline = _normalize_global_settings({}, config=config)
    for item in presets:
        if not isinstance(item, dict):
            continue
        preset_id = str(item.get("id", "") or "").strip()
        name = str(item.get("name", "") or "").strip()
        if not preset_id or not name:
            continue
        normalized_settings = _normalize_settings_payload(
            item.get("settings", {}),
            config=config,
            current=baseline,
            respect_explicit_steps=False,
        )
        normalized.append(
            {
                "id": preset_id,
                "name": name,
                "kind": "user",
                "summary": _format_settings_profile_summary(normalized_settings),
                "settings": _project_settings_profile_settings(normalized_settings),
            }
        )
    return normalized


def save_settings_user_profile(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    name = str(payload.get("name", "") or "").strip()
    if not name:
        raise ValueError("Ime profila je obavezno.")
    baseline = _normalize_global_settings({}, config=config)
    normalized_settings = _normalize_settings_payload(
        payload.get("settings", {}),
        config=config,
        current=baseline,
        respect_explicit_steps=False,
    )
    preset = {
        "id": _build_user_preset_id(name),
        "name": name,
        "settings": _project_settings_profile_settings(normalized_settings),
    }
    profiles = [
        item
        for item in load_settings_user_profiles(config)
        if str(item.get("name", "") or "").strip().lower() != name.lower()
    ]
    profiles.append(
        {
            "id": preset["id"],
            "name": preset["name"],
            "settings": preset["settings"],
        }
    )
    atomic_write_json(config.settings_profiles_path, {"profiles": profiles})
    return action_result("ok", "save-settings-profile", f"Sačuvan settings profil: {name}")


def delete_settings_user_profile(
    profile_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    profiles = load_settings_user_profiles(config)
    filtered = [item for item in profiles if str(item.get("id", "") or "") != str(profile_id)]
    if len(filtered) == len(profiles):
        return action_result(
            "error",
            "delete-settings-profile",
            "Profil nije pronađen.",
            stderr="Profil nije pronađen.",
        )
    persisted = [
        {
            "id": str(item.get("id", "") or ""),
            "name": str(item.get("name", "") or ""),
            "settings": item.get("settings", {}),
        }
        for item in filtered
    ]
    atomic_write_json(config.settings_profiles_path, {"profiles": persisted})
    return action_result("ok", "delete-settings-profile", "Settings profil je obrisan.")


def _normalize_workflow_preset_payload(
    payload: object,
    config: ControlCenterConfig | None = None,
) -> dict[str, object] | None:
    config = config or get_config()
    raw = payload if isinstance(payload, dict) else {}
    name = str(raw.get("name", "") or raw.get("label", "") or "").strip()
    if not name:
        return None

    baseline = _normalize_global_settings(
        {},
        config=config,
        allowed_workflow_preset_ids={"research"},
    )
    normalized_settings = _normalize_settings_payload(
        raw.get("settingsPatch", {}),
        config=config,
        current=baseline,
        respect_explicit_steps=False,
    )
    settings_patch = {
        "profile": normalized_settings["profile"],
        "context": normalized_settings["context"],
        "outputTokens": normalized_settings["outputTokens"],
        "thinkingMode": normalized_settings["thinkingMode"],
        "temperature": normalized_settings["temperature"],
        "topK": normalized_settings["topK"],
        "topP": normalized_settings["topP"],
        "minP": normalized_settings["minP"],
        "repeatPenalty": normalized_settings["repeatPenalty"],
        "repeatLastN": normalized_settings["repeatLastN"],
        "presencePenalty": normalized_settings["presencePenalty"],
        "frequencyPenalty": normalized_settings["frequencyPenalty"],
        "seed": normalized_settings["seed"],
        "webSearchMode": normalized_settings["webSearchMode"],
        "webSearchProvider": normalized_settings["webSearchProvider"],
    }

    raw_badges = raw.get("badges", [])
    if isinstance(raw_badges, str):
        badge_candidates = [item.strip() for item in raw_badges.split(",") if item.strip()]
    elif isinstance(raw_badges, list):
        badge_candidates = [
            str(item or "").strip()
            for item in raw_badges
            if str(item or "").strip()
        ]
    else:
        badge_candidates = []
    seen_badges: set[str] = set()
    badges: list[str] = []
    for badge in badge_candidates:
        normalized_badge = badge.lower()
        if normalized_badge in seen_badges:
            continue
        seen_badges.add(normalized_badge)
        badges.append(badge)

    search_raw = raw.get("searchDefaults", {})
    search_defaults = search_raw if isinstance(search_raw, dict) else {}
    search_provider = str(
        search_defaults.get("provider", settings_patch["webSearchProvider"]) or settings_patch["webSearchProvider"]
    ).strip().lower()
    if search_provider not in ALLOWED_WEB_SEARCH_PROVIDERS:
        search_provider = str(settings_patch["webSearchProvider"])
    suggested_action = str(search_defaults.get("suggestedAction", "answer") or "answer").strip().lower()
    if suggested_action not in ALLOWED_WORKFLOW_SEARCH_ACTIONS:
        suggested_action = "answer"
    search_query_hint = str(search_defaults.get("queryHint", "") or "").strip()

    knowledge_raw = raw.get("knowledgeDefaults", {})
    knowledge_defaults = knowledge_raw if isinstance(knowledge_raw, dict) else {}
    knowledge_mode = str(knowledge_defaults.get("mode", "documents+web") or "documents+web").strip().lower()
    if knowledge_mode not in ALLOWED_WORKFLOW_KNOWLEDGE_MODES:
        knowledge_mode = "documents+web"
    knowledge_query_hint = str(knowledge_defaults.get("queryHint", "") or "").strip()

    benchmark_raw = raw.get("benchmarkDefaults", {})
    benchmark_defaults = benchmark_raw if isinstance(benchmark_raw, dict) else {}
    launch_target = str(benchmark_defaults.get("launchTarget", "selected") or "selected").strip().lower()
    if launch_target not in ALLOWED_WORKFLOW_BENCHMARK_TARGETS:
        launch_target = "selected"
    battery_id = str(benchmark_defaults.get("batteryId", "default") or "default").strip() or "default"
    run_label = str(benchmark_defaults.get("runLabel", "") or "").strip()

    summary = str(raw.get("summary", "") or "").strip() or f"{name} workflow preset."
    preset_id = str(raw.get("presetId", "") or raw.get("id", "") or "").strip()

    return {
        "id": preset_id,
        "name": name,
        "label": name,
        "summary": summary,
        "badges": badges,
        "settingsPatch": settings_patch,
        "searchDefaults": {
            "provider": search_provider,
            "suggestedAction": suggested_action,
            "queryHint": search_query_hint,
        },
        "knowledgeDefaults": {
            "mode": knowledge_mode,
            "queryHint": knowledge_query_hint,
        },
        "benchmarkDefaults": {
            "batteryId": battery_id,
            "launchTarget": launch_target,
            "runLabel": run_label,
        },
    }


def _project_workflow_user_preset(preset: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(preset.get("id", "") or "").strip(),
        "name": str(preset.get("name", "") or preset.get("label", "") or "").strip(),
        "summary": str(preset.get("summary", "") or "").strip(),
        "badges": list(preset.get("badges", [])) if isinstance(preset.get("badges", []), list) else [],
        "settingsPatch": dict(preset.get("settingsPatch", {})) if isinstance(preset.get("settingsPatch", {}), dict) else {},
        "searchDefaults": dict(preset.get("searchDefaults", {})) if isinstance(preset.get("searchDefaults", {}), dict) else {},
        "knowledgeDefaults": dict(preset.get("knowledgeDefaults", {})) if isinstance(preset.get("knowledgeDefaults", {}), dict) else {},
        "benchmarkDefaults": dict(preset.get("benchmarkDefaults", {})) if isinstance(preset.get("benchmarkDefaults", {}), dict) else {},
    }


def load_turboquant_schema(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    return {
        "parameters": TURBOQUANT_PARAMETERS,
        "builtInPresets": TURBOQUANT_BUILTIN_PRESETS,
        "userPresets": load_turboquant_user_presets(config),
        "currentConfig": load_turboquant_config(config),
        "recommendedModels": UNSLOTH_RECOMMENDED_MODELS,
    }


def load_turboquant_config(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    baseline = dict(TURBOQUANT_BUILTIN_PRESETS[0]["settings"])
    payload = read_json_object(config.turboquant_config_path)
    if not payload:
        return baseline
    normalized = _normalize_turboquant_settings(payload)
    baseline.update(normalized)
    return baseline


def save_turboquant_config(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    normalized = _normalize_turboquant_settings(payload)
    atomic_write_json(config.turboquant_config_path, normalized)
    return action_result("ok", "save-turboquant-config", "TurboQuant config je sačuvan.")


def load_turboquant_user_presets(
    config: ControlCenterConfig | None = None,
) -> list[dict[str, object]]:
    config = config or get_config()
    payload = read_json_object(config.turboquant_presets_path)
    presets = payload.get("presets")
    if not isinstance(presets, list):
        return []
    return [item for item in presets if isinstance(item, dict)]


def save_turboquant_user_preset(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    name = str(payload.get("name", "") or "").strip()
    if not name:
        raise ValueError("Ime preset-a je obavezno.")
    preset = {
        "id": _build_user_preset_id(name),
        "name": name,
        "description": str(payload.get("description", "") or "").strip(),
        "targetModelPattern": str(payload.get("targetModelPattern", "") or "").strip(),
        "notes": str(payload.get("notes", "") or "").strip(),
        "settings": _normalize_turboquant_settings(payload.get("settings", {})),
    }
    presets = [
        item
        for item in load_turboquant_user_presets(config)
        if str(item.get("name", "") or "").strip().lower() != name.lower()
    ]
    presets.append(preset)
    atomic_write_json(config.turboquant_presets_path, {"presets": presets})
    return action_result("ok", "save-turboquant-preset", f"Sačuvan TurboQuant preset: {name}")


def delete_turboquant_user_preset(
    preset_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    presets = load_turboquant_user_presets(config)
    filtered = [item for item in presets if str(item.get("id", "") or "") != str(preset_id)]
    if len(filtered) == len(presets):
        return action_result("error", "delete-turboquant-preset", "Preset nije pronađen.", stderr="Preset nije pronađen.")
    atomic_write_json(config.turboquant_presets_path, {"presets": filtered})
    return action_result("ok", "delete-turboquant-preset", "TurboQuant preset je obrisan.")


def load_opencode_step_schema(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    settings = load_effective_settings_state(config)
    current_steps = {
        "buildSteps": settings["buildSteps"],
        "planSteps": settings["planSteps"],
        "generalSteps": settings["generalSteps"],
        "exploreSteps": settings["exploreSteps"],
    }
    return {
        "builtInPresets": [
            {**preset, "summary": _format_opencode_step_summary(preset["steps"])}
            for preset in OPENCODE_STEP_BUILTIN_PRESETS
        ],
        "userPresets": [
            {**preset, "summary": _format_opencode_step_summary(preset["steps"])}
            for preset in load_opencode_step_user_presets(config)
        ],
        "currentSteps": current_steps,
        "currentSummary": _format_opencode_step_summary(current_steps),
        "defaultSteps": dict(OPENCODE_STEP_BUILTIN_PRESETS[1]["steps"]),
        "defaultSummary": _format_opencode_step_summary(OPENCODE_STEP_BUILTIN_PRESETS[1]["steps"]),
    }


def load_opencode_step_user_presets(
    config: ControlCenterConfig | None = None,
) -> list[dict[str, object]]:
    config = config or get_config()
    payload = read_json_object(config.opencode_step_presets_path)
    presets = payload.get("presets")
    if not isinstance(presets, list):
        return []
    normalized: list[dict[str, object]] = []
    for item in presets:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "id": str(item.get("id", "") or ""),
                "name": str(item.get("name", "") or ""),
                "steps": _normalize_opencode_step_values(item.get("steps", {})),
            }
        )
    return [item for item in normalized if item["id"] and item["name"]]


def save_opencode_step_preset(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    name = str(payload.get("name", "") or "").strip()
    if not name:
        raise ValueError("Ime OpenCode preset-a je obavezno.")
    preset = {
        "id": _build_user_preset_id(name),
        "name": name,
        "steps": _normalize_opencode_step_values(payload.get("steps", {})),
    }
    presets = [
        item
        for item in load_opencode_step_user_presets(config)
        if str(item.get("name", "") or "").strip().lower() != name.lower()
    ]
    presets.append(preset)
    atomic_write_json(config.opencode_step_presets_path, {"presets": presets})
    return action_result("ok", "save-opencode-step-preset", f"Sačuvan OpenCode preset: {name}")


def delete_opencode_step_preset(
    preset_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    presets = load_opencode_step_user_presets(config)
    filtered = [item for item in presets if str(item.get("id", "") or "") != str(preset_id)]
    if len(filtered) == len(presets):
        return action_result("error", "delete-opencode-step-preset", "Preset nije pronađen.", stderr="Preset nije pronađen.")
    atomic_write_json(config.opencode_step_presets_path, {"presets": filtered})
    return action_result("ok", "delete-opencode-step-preset", "OpenCode preset je obrisan.")


def _normalize_global_settings(
    payload: dict[str, object],
    *,
    config: ControlCenterConfig,
    allowed_workflow_preset_ids: set[str] | None = None,
) -> dict[str, object]:
    defaults = {
        "profile": "balanced",
        "themeId": "dark-chocolate",
        "workflowPresetId": "research",
        "context": 262144,
        "outputTokens": 8192,
        "workingDirectory": str(config.install_root),
        "thinkingMode": "mid",
        "temperature": 0.8,
        "topK": 40,
        "topP": 0.95,
        "minP": 0.05,
        "repeatPenalty": 1.0,
        "repeatLastN": 64,
        "presencePenalty": 0.0,
        "frequencyPenalty": 0.0,
        "seed": -1,
        "gpuLayersMode": "auto",
        "gpuLayersOverride": 0,
        "buildSteps": 140,
        "planSteps": 100,
        "generalSteps": 110,
        "exploreSteps": 80,
        "accessMode": "local-only",
        "securityMode": "strict",
        "capabilityMode": "confirm-commands",
        "webSearchMode": "off",
        "webSearchProvider": "searxng",
        "webSearchBaseUrlMode": DEFAULT_WEB_SEARCH_BASE_URL_MODE,
        "webSearchBaseUrl": DEFAULT_WEB_SEARCH_BASE_URL,
        "webSearchMaxResults": DEFAULT_WEB_SEARCH_MAX_RESULTS,
        "webSearchTimeoutSeconds": DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS,
        "webSearchPromptPrefix": DEFAULT_WEB_SEARCH_PROMPT_PREFIX,
    }
    return _normalize_settings_payload(
        payload,
        config=config,
        current=defaults,
        respect_explicit_steps=True,
        allowed_workflow_preset_ids=allowed_workflow_preset_ids,
    )


def load_web_search_provider_options() -> list[dict[str, object]]:
    return [dict(option) for option in WEB_SEARCH_PROVIDER_OPTIONS]


def load_theme_options() -> list[dict[str, object]]:
    return [dict(option) for option in THEME_OPTIONS]


def load_generation_starter_presets() -> list[dict[str, object]]:
    return [
        {
            **dict(option),
            "settings": dict(option.get("settings", {})),
        }
        for option in GENERATION_STARTER_PRESETS
    ]


def load_workflow_presets(
    config: ControlCenterConfig | None = None,
) -> list[dict[str, object]]:
    config = config or get_config()
    built_in_presets = [
        {
            **dict(option),
            "name": str(option.get("label", "") or option.get("id", "") or "").strip(),
            "kind": "built-in",
        }
        for option in WORKFLOW_PRESET_SPECS
    ]
    user_presets = sorted(
        load_workflow_user_presets(config),
        key=lambda item: str(item.get("name", "") or item.get("label", "") or "").strip().lower(),
    )
    return [*built_in_presets, *user_presets]


def load_workflow_user_presets(
    config: ControlCenterConfig | None = None,
) -> list[dict[str, object]]:
    config = config or get_config()
    payload = read_json_object(config.workflow_presets_path)
    presets = payload.get("presets")
    if not isinstance(presets, list):
        return []
    normalized: list[dict[str, object]] = []
    for item in presets:
        if not isinstance(item, dict):
            continue
        normalized_preset = _normalize_workflow_preset_payload(item)
        if not normalized_preset:
            continue
        normalized_preset["kind"] = "user"
        normalized.append(normalized_preset)
    return normalized


def save_workflow_user_preset(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    normalized = _normalize_workflow_preset_payload(payload)
    if not normalized:
        raise ValueError("Ime workflow preseta je obavezno.")

    requested_id = str(payload.get("presetId", "") or "").strip()
    _validate_workflow_user_preset(
        normalized,
        requested_id=requested_id,
        existing_presets=load_workflow_presets(config),
    )
    existing_presets = load_workflow_user_presets(config)
    if requested_id and any(str(item.get("id", "") or "") == requested_id for item in existing_presets):
        normalized["id"] = requested_id
    else:
        normalized["id"] = _build_user_preset_id(str(normalized["name"]))
    normalized["kind"] = "user"

    persisted: list[dict[str, object]] = []
    for item in existing_presets:
        item_id = str(item.get("id", "") or "")
        item_name = str(item.get("name", "") or "").strip().lower()
        if item_id == normalized["id"] or item_name == str(normalized["name"]).strip().lower():
            continue
        persisted.append(_project_workflow_user_preset(item))
    persisted.append(_project_workflow_user_preset(normalized))
    atomic_write_json(config.workflow_presets_path, {"presets": persisted})
    return action_result("ok", "save-workflow-preset", f"Sačuvan workflow preset: {normalized['name']}")


def delete_workflow_user_preset(
    preset_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    existing_presets = load_workflow_user_presets(config)
    filtered = [item for item in existing_presets if str(item.get("id", "") or "") != str(preset_id)]
    if len(filtered) == len(existing_presets):
        return action_result(
            "error",
            "delete-workflow-preset",
            "Workflow preset nije pronađen.",
            stderr="Workflow preset nije pronađen.",
        )
    atomic_write_json(
        config.workflow_presets_path,
        {"presets": [_project_workflow_user_preset(item) for item in filtered]},
    )
    return action_result("ok", "delete-workflow-preset", "Workflow preset je obrisan.")


def _build_builtin_settings_profiles(
    config: ControlCenterConfig,
) -> list[dict[str, object]]:
    baseline = _normalize_global_settings({}, config=config)
    profiles: list[dict[str, object]] = []
    for spec in SETTINGS_PROFILE_BUILTIN_SPECS:
        raw_payload = {
            **baseline,
            **spec["settings"],
            "workingDirectory": str(config.install_root),
        }
        normalized = _normalize_settings_payload(
            raw_payload,
            config=config,
            current=baseline,
            respect_explicit_steps=False,
        )
        profiles.append(
            {
                "id": str(spec["id"]),
                "name": str(spec["name"]),
                "kind": "built-in",
                "summary": _format_settings_profile_summary(normalized),
                "settings": _project_settings_profile_settings(normalized),
            }
        )
    return profiles


def _normalize_settings_payload(
    payload: dict[str, object],
    *,
    config: ControlCenterConfig,
    current: dict[str, object],
    respect_explicit_steps: bool,
    allowed_workflow_preset_ids: set[str] | None = None,
) -> dict[str, object]:
    normalized_profile = str(payload.get("profile", current["profile"]) or current["profile"]).strip().lower()
    if normalized_profile not in ALLOWED_PROFILES:
        normalized_profile = str(current["profile"])

    normalized_theme_id = str(payload.get("themeId", current.get("themeId", "dark-chocolate")) or current.get("themeId", "dark-chocolate")).strip().lower()
    if normalized_theme_id not in ALLOWED_THEMES:
        normalized_theme_id = str(current.get("themeId", "dark-chocolate"))

    normalized_workflow_preset_id = str(
        payload.get("workflowPresetId", current.get("workflowPresetId", "research"))
        or current.get("workflowPresetId", "research")
    ).strip().lower()
    if allowed_workflow_preset_ids is None:
        allowed_workflow_preset_ids = _load_workflow_preset_ids(config)
    if normalized_workflow_preset_id not in allowed_workflow_preset_ids:
        normalized_workflow_preset_id = str(current.get("workflowPresetId", "research"))

    normalized_access_mode = str(payload.get("accessMode", current["accessMode"]) or current["accessMode"]).strip().lower()
    if normalized_access_mode not in ALLOWED_ACCESS_MODES:
        normalized_access_mode = str(current["accessMode"])

    normalized_security_mode = str(payload.get("securityMode", current.get("securityMode", "strict")) or current.get("securityMode", "strict")).strip().lower()
    if normalized_security_mode not in ALLOWED_SECURITY_MODES:
        normalized_security_mode = str(current.get("securityMode", "strict"))

    normalized_capability_mode = str(payload.get("capabilityMode", current.get("capabilityMode", "confirm-commands")) or current.get("capabilityMode", "confirm-commands")).strip().lower()
    if normalized_capability_mode not in ALLOWED_CAPABILITY_MODES:
        normalized_capability_mode = str(current.get("capabilityMode", "confirm-commands"))

    normalized_temperature = _bounded_float(
        payload.get("temperature", current.get("temperature", 0.8)),
        float(current.get("temperature", 0.8)),
        minimum=0.0,
        maximum=2.0,
    )
    normalized_top_k = _non_negative_int(
        payload.get("topK", current.get("topK", 40)),
        int(current.get("topK", 40) or 40),
    )
    normalized_top_p = _bounded_float(
        payload.get("topP", current.get("topP", 0.95)),
        float(current.get("topP", 0.95)),
        minimum=0.0,
        maximum=1.0,
    )
    normalized_min_p = _bounded_float(
        payload.get("minP", current.get("minP", 0.05)),
        float(current.get("minP", 0.05)),
        minimum=0.0,
        maximum=1.0,
    )
    normalized_repeat_penalty = _bounded_float(
        payload.get("repeatPenalty", current.get("repeatPenalty", 1.0)),
        float(current.get("repeatPenalty", 1.0)),
        minimum=0.0,
        maximum=2.5,
    )
    normalized_repeat_last_n = _repeat_last_n_value(
        payload.get("repeatLastN", current.get("repeatLastN", 64)),
        int(current.get("repeatLastN", 64) or 64),
    )
    normalized_presence_penalty = _bounded_float(
        payload.get("presencePenalty", current.get("presencePenalty", 0.0)),
        float(current.get("presencePenalty", 0.0)),
        minimum=-2.0,
        maximum=2.0,
    )
    normalized_frequency_penalty = _bounded_float(
        payload.get("frequencyPenalty", current.get("frequencyPenalty", 0.0)),
        float(current.get("frequencyPenalty", 0.0)),
        minimum=-2.0,
        maximum=2.0,
    )
    normalized_seed = _integer_value(
        payload.get("seed", current.get("seed", -1)),
        int(current.get("seed", -1) or -1),
    )

    normalized_web_search_mode = str(
        payload.get("webSearchMode", current.get("webSearchMode", "off"))
        or current.get("webSearchMode", "off")
    ).strip().lower()
    if normalized_web_search_mode not in ALLOWED_WEB_SEARCH_MODES:
        normalized_web_search_mode = str(current.get("webSearchMode", "off"))

    normalized_web_search_provider = str(
        payload.get("webSearchProvider", current.get("webSearchProvider", "searxng"))
        or current.get("webSearchProvider", "searxng")
    ).strip().lower()
    if normalized_web_search_provider not in ALLOWED_WEB_SEARCH_PROVIDERS:
        normalized_web_search_provider = str(current.get("webSearchProvider", "searxng"))

    raw_web_search_base_url = str(
        payload.get("webSearchBaseUrl", current.get("webSearchBaseUrl", DEFAULT_WEB_SEARCH_BASE_URL))
        or current.get("webSearchBaseUrl", DEFAULT_WEB_SEARCH_BASE_URL)
    ).strip()
    normalized_web_search_base_url_mode = str(
        payload.get(
            "webSearchBaseUrlMode",
            current.get("webSearchBaseUrlMode", DEFAULT_WEB_SEARCH_BASE_URL_MODE),
        )
        or current.get("webSearchBaseUrlMode", DEFAULT_WEB_SEARCH_BASE_URL_MODE)
    ).strip().lower()
    if normalized_web_search_base_url_mode not in ALLOWED_WEB_SEARCH_BASE_URL_MODES:
        normalized_web_search_base_url_mode = DEFAULT_WEB_SEARCH_BASE_URL_MODE

    if normalized_web_search_provider == "duckduckgo":
        normalized_web_search_base_url_mode = DEFAULT_WEB_SEARCH_BASE_URL_MODE
        web_search_base_url = ""
    elif (
        "webSearchBaseUrlMode" not in payload
        and raw_web_search_base_url.rstrip("/") == LEGACY_DEFAULT_WEB_SEARCH_BASE_URL.rstrip("/")
    ):
        normalized_web_search_base_url_mode = DEFAULT_WEB_SEARCH_BASE_URL_MODE
        web_search_base_url = ""
    else:
        if "webSearchBaseUrl" in payload:
            normalized_web_search_base_url_mode = (
                "manual" if raw_web_search_base_url else DEFAULT_WEB_SEARCH_BASE_URL_MODE
            )
        web_search_base_url = (
            raw_web_search_base_url
            if normalized_web_search_base_url_mode == "manual"
            else ""
        )

    web_search_prompt_prefix = str(
        payload.get("webSearchPromptPrefix", current.get("webSearchPromptPrefix", DEFAULT_WEB_SEARCH_PROMPT_PREFIX))
        or current.get("webSearchPromptPrefix", DEFAULT_WEB_SEARCH_PROMPT_PREFIX)
    ).strip()
    if not web_search_prompt_prefix:
        web_search_prompt_prefix = DEFAULT_WEB_SEARCH_PROMPT_PREFIX

    working_directory = str(payload.get("workingDirectory", current["workingDirectory"]) or current["workingDirectory"]).strip()
    if not working_directory:
        working_directory = str(config.install_root)

    if respect_explicit_steps:
        build_steps = _positive_int(payload.get("buildSteps"), int(current["buildSteps"]))
        plan_steps = _positive_int(payload.get("planSteps"), int(current["planSteps"]))
        general_steps = _positive_int(payload.get("generalSteps"), int(current["generalSteps"]))
        explore_steps = _positive_int(payload.get("exploreSteps"), int(current["exploreSteps"]))
        thinking_mode = str(payload.get("thinkingMode", _infer_thinking_mode(build_steps, plan_steps, general_steps, explore_steps)) or _infer_thinking_mode(build_steps, plan_steps, general_steps, explore_steps)).strip().lower()
        if thinking_mode not in THINKING_PRESETS:
            thinking_mode = _infer_thinking_mode(build_steps, plan_steps, general_steps, explore_steps)
    else:
        thinking_mode = str(payload.get("thinkingMode", current["thinkingMode"]) or current["thinkingMode"]).strip().lower()
        if thinking_mode not in THINKING_PRESETS:
            thinking_mode = str(current["thinkingMode"])
        preset = THINKING_PRESETS[thinking_mode]
        build_steps = int(preset["buildSteps"])
        plan_steps = int(preset["planSteps"])
        general_steps = int(preset["generalSteps"])
        explore_steps = int(preset["exploreSteps"])

    gpu_layers_mode = str(
        payload.get("gpuLayersMode", current.get("gpuLayersMode", "auto"))
        or current.get("gpuLayersMode", "auto")
    ).strip().lower()
    if gpu_layers_mode not in {"auto", "manual"}:
        gpu_layers_mode = str(current.get("gpuLayersMode", "auto") or "auto").strip().lower()
        if gpu_layers_mode not in {"auto", "manual"}:
            gpu_layers_mode = "auto"
    gpu_layers_override = _non_negative_int(
        payload.get("gpuLayersOverride"),
        int(current.get("gpuLayersOverride", 0) or 0),
    )

    return {
        "profile": normalized_profile,
        "themeId": normalized_theme_id,
        "workflowPresetId": normalized_workflow_preset_id,
        "context": _positive_int(payload.get("context"), int(current["context"])),
        "outputTokens": _positive_int(payload.get("outputTokens"), int(current["outputTokens"])),
        "workingDirectory": working_directory,
        "thinkingMode": thinking_mode,
        "temperature": normalized_temperature,
        "topK": normalized_top_k,
        "topP": normalized_top_p,
        "minP": normalized_min_p,
        "repeatPenalty": normalized_repeat_penalty,
        "repeatLastN": normalized_repeat_last_n,
        "presencePenalty": normalized_presence_penalty,
        "frequencyPenalty": normalized_frequency_penalty,
        "seed": normalized_seed,
        "gpuLayersMode": gpu_layers_mode,
        "gpuLayersOverride": gpu_layers_override,
        "buildSteps": build_steps,
        "planSteps": plan_steps,
        "generalSteps": general_steps,
        "exploreSteps": explore_steps,
        "accessMode": normalized_access_mode,
        "securityMode": normalized_security_mode,
        "capabilityMode": normalized_capability_mode,
        "webSearchMode": normalized_web_search_mode,
        "webSearchProvider": normalized_web_search_provider,
        "webSearchBaseUrlMode": normalized_web_search_base_url_mode,
        "webSearchBaseUrl": web_search_base_url,
        "webSearchMaxResults": _positive_int(
            payload.get("webSearchMaxResults"),
            int(current.get("webSearchMaxResults", DEFAULT_WEB_SEARCH_MAX_RESULTS)),
        ),
        "webSearchTimeoutSeconds": _positive_int(
            payload.get("webSearchTimeoutSeconds"),
            int(current.get("webSearchTimeoutSeconds", DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS)),
        ),
        "webSearchPromptPrefix": web_search_prompt_prefix,
    }


def _normalize_turboquant_settings(payload: object) -> dict[str, object]:
    raw = payload if isinstance(payload, dict) else {}
    return {
        "context": _positive_int(raw.get("context"), 131072),
        "ctk": str(raw.get("ctk", "turbo4") or "turbo4"),
        "ctv": str(raw.get("ctv", "turbo3") or "turbo3"),
        "ncmoe": _positive_int(raw.get("ncmoe"), 20),
        "flashAttention": bool(raw.get("flashAttention", True)),
        "mlock": bool(raw.get("mlock", True)),
        "mmapMode": str(raw.get("mmapMode", "mmap") or "mmap"),
        "runtimePreference": str(raw.get("runtimePreference", "turboquant") or "turboquant"),
    }


def _normalize_opencode_step_values(payload: object) -> dict[str, int]:
    raw = payload if isinstance(payload, dict) else {}
    return {
        "buildSteps": _positive_int(raw.get("buildSteps"), 140),
        "planSteps": _positive_int(raw.get("planSteps"), 100),
        "generalSteps": _positive_int(raw.get("generalSteps"), 110),
        "exploreSteps": _positive_int(raw.get("exploreSteps"), 80),
    }


def _format_opencode_step_summary(steps: dict[str, int]) -> str:
    return (
        f"{int(steps['buildSteps'])} / {int(steps['planSteps'])} / "
        f"{int(steps['generalSteps'])} / {int(steps['exploreSteps'])}"
    )


def _format_settings_profile_summary(settings: dict[str, object]) -> str:
    context_value = int(settings["context"]) // 1024
    output_value = int(settings["outputTokens"]) // 1024
    return (
        f"{settings['profile']} | {context_value}k ctx | "
        f"{output_value}k out | {settings['thinkingMode']} | temp {settings['temperature']}"
    )


def _project_settings_profile_settings(settings: dict[str, object]) -> dict[str, object]:
    return {
        key: settings[key]
        for key in SETTINGS_PROFILE_COMPARE_KEYS
    }


def _project_model_override_settings(settings: dict[str, object]) -> dict[str, object]:
    allowed_keys = {
        "profile",
        "context",
        "outputTokens",
        "workingDirectory",
        "thinkingMode",
        "gpuLayersMode",
        "gpuLayersOverride",
        "buildSteps",
        "planSteps",
        "generalSteps",
        "exploreSteps",
        "accessMode",
        "securityMode",
        "capabilityMode",
        "temperature",
        "topK",
        "topP",
        "minP",
        "repeatPenalty",
        "repeatLastN",
        "presencePenalty",
        "frequencyPenalty",
        "seed",
    }
    return {key: settings[key] for key in allowed_keys}


def _match_settings_profile(
    settings: dict[str, object],
    profiles: list[dict[str, object]],
) -> dict[str, object]:
    current_projection = _project_settings_profile_settings(settings)
    for profile in profiles:
        candidate = profile.get("settings")
        if not isinstance(candidate, dict):
            continue
        if all(candidate.get(key) == current_projection.get(key) for key in SETTINGS_PROFILE_COMPARE_KEYS):
            return profile
    return {"id": "custom", "name": "custom"}


def _positive_int(value: object, fallback: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return fallback
    return candidate if candidate > 0 else fallback


def _non_negative_int(value: object, fallback: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return fallback
    return candidate if candidate >= 0 else fallback


def _integer_value(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _repeat_last_n_value(value: object, fallback: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return fallback
    if candidate == -1:
        return -1
    return candidate if candidate >= 0 else fallback


def _bounded_float(
    value: object,
    fallback: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return fallback
    if candidate < minimum:
        return minimum
    if candidate > maximum:
        return maximum
    return candidate


def _infer_thinking_mode(
    build_steps: int,
    plan_steps: int,
    general_steps: int,
    explore_steps: int,
) -> str:
    chosen = "mid"
    chosen_distance: int | None = None
    for name, preset in THINKING_PRESETS.items():
        distance = (
            abs(int(preset["buildSteps"]) - build_steps)
            + abs(int(preset["planSteps"]) - plan_steps)
            + abs(int(preset["generalSteps"]) - general_steps)
            + abs(int(preset["exploreSteps"]) - explore_steps)
        )
        if chosen_distance is None or distance < chosen_distance:
            chosen = name
            chosen_distance = distance
    return chosen


def _read_active_model_id(config: ControlCenterConfig) -> str:
    payload = read_json_object(config.active_model_config_path)
    return str(payload.get("model_id", "") or "")


def _resolve_active_model_label(
    config: ControlCenterConfig,
    active_model_id: str,
) -> str:
    if not active_model_id:
        return "Nema aktivnog modela"
    active_payload = read_json_object(config.active_model_config_path)
    model_path = str(active_payload.get("model_path", "") or "").strip()
    if model_path:
        return Path(model_path).name
    return active_model_id


def _build_user_preset_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "preset"
    return f"user-{slug}-{uuid4().hex[:6]}"


def _validate_workflow_user_preset(
    preset: dict[str, object],
    *,
    requested_id: str,
    existing_presets: list[dict[str, object]],
) -> None:
    name = str(preset.get("name", "") or "").strip()
    if not name:
        raise ValueError("Ime workflow preseta je obavezno.")

    normalized_name = name.lower()
    for item in existing_presets:
        item_id = str(item.get("id", "") or "").strip()
        item_name = str(item.get("name", "") or item.get("label", "") or "").strip().lower()
        if not item_name or item_id == requested_id:
            continue
        if item_name == normalized_name:
            raise ValueError("Workflow preset sa tim imenom već postoji.")

    summary = str(preset.get("summary", "") or "").strip()
    if len(summary) > WORKFLOW_PRESET_SUMMARY_MAX_LENGTH:
        raise ValueError(
            f"Kratak opis workflow preseta može da ima najviše {WORKFLOW_PRESET_SUMMARY_MAX_LENGTH} karaktera."
        )

    badges = preset.get("badges", [])
    normalized_badges = badges if isinstance(badges, list) else []
    if len(normalized_badges) > WORKFLOW_PRESET_BADGE_MAX_COUNT:
        raise ValueError(
            f"Workflow preset može da ima najviše {WORKFLOW_PRESET_BADGE_MAX_COUNT} badge oznaka."
        )

    for badge in normalized_badges:
        if len(str(badge or "").strip()) > WORKFLOW_PRESET_BADGE_MAX_LENGTH:
            raise ValueError(
                f"Svaka badge oznaka može da ima najviše {WORKFLOW_PRESET_BADGE_MAX_LENGTH} karaktera."
            )


def _load_workflow_preset_ids(config: ControlCenterConfig) -> set[str]:
    built_in_ids = {
        str(item.get("id", "") or "").strip().lower()
        for item in WORKFLOW_PRESET_SPECS
        if str(item.get("id", "") or "").strip()
    }
    payload = read_json_object(config.workflow_presets_path)
    stored = payload.get("presets")
    if not isinstance(stored, list):
        return built_in_ids

    user_ids = {
        str(item.get("id", "") or "").strip().lower()
        for item in stored
        if isinstance(item, dict) and str(item.get("id", "") or "").strip()
    }
    return built_in_ids | user_ids
