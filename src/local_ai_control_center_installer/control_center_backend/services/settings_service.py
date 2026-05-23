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
        "whatIsIt": "Koliko tokena razgovora i radnog konteksta drzis u KV cache-u.",
        "effect": "Veci context trosi vise memorije, ali drzi duze sesije.",
        "recommendation": "Prvo menjaj context, pa tek onda agresivnije TurboQuant nivoe.",
        "safeChoices": ["65536", "131072"],
        "advancedChoices": ["262144", "327680"],
        "defaultValue": 131072,
    },
    {
        "id": "ctk",
        "label": "ctk",
        "whatIsIt": "Tip kompresije za K deo KV cache-a.",
        "effect": "turbo4 je bezbedniji, turbo3 je balans, turbo2 agresivno stedi memoriju.",
        "recommendation": "Za vecinu masina pocni sa turbo4.",
        "safeChoices": ["turbo4"],
        "advancedChoices": ["turbo3", "turbo2"],
        "defaultValue": "turbo4",
    },
    {
        "id": "ctv",
        "label": "ctv",
        "whatIsIt": "Tip kompresije za V deo KV cache-a.",
        "effect": "Moze mrvu agresivnije od ctk bez prejakog udara po kvalitetu.",
        "recommendation": "Daily balans je turbo3, safe je turbo4.",
        "safeChoices": ["turbo4", "turbo3"],
        "advancedChoices": ["turbo2"],
        "defaultValue": "turbo3",
    },
    {
        "id": "ncmoe",
        "label": "ncmoe",
        "whatIsIt": "Koliko ranih MoE slojeva prebacujes na CPU.",
        "effect": "Visa vrednost stedi VRAM, ali usporava rad.",
        "recommendation": "Kreni sa 20 pa dizaj po potrebi.",
        "safeChoices": ["20"],
        "advancedChoices": ["30", "35"],
        "defaultValue": 20,
    },
    {
        "id": "flashAttention",
        "label": "Flash attention",
        "whatIsIt": "Brzi attention put kada ga runtime podrzava.",
        "effect": "Najcesce povoljan za performanse.",
        "recommendation": "Drzi ukljuceno osim ako imas konkretan bug.",
        "safeChoices": ["on"],
        "advancedChoices": ["off"],
        "defaultValue": True,
    },
    {
        "id": "mlock",
        "label": "mlock",
        "whatIsIt": "Pokusava da drzi model u RAM-u umesto da ga OS lakse swapuje.",
        "effect": "Smanjuje swap rizik, ali je stroziji prema memoriji.",
        "recommendation": "Uglavnom bezbedno za desktop masinu kada juris stabilnost.",
        "safeChoices": ["on"],
        "advancedChoices": ["off"],
        "defaultValue": True,
    },
    {
        "id": "mmapMode",
        "label": "mmap mode",
        "whatIsIt": "Menja nacin ucitavanja modela sa diska u memoriju.",
        "effect": "mmap brze pali model; no-mmap ume da bude stabilniji u edge slucajevima.",
        "recommendation": "Koristi mmap osim ako vec imas konkretan razlog protiv.",
        "safeChoices": ["mmap"],
        "advancedChoices": ["no-mmap"],
        "defaultValue": "mmap",
    },
    {
        "id": "runtimePreference",
        "label": "Runtime preference",
        "whatIsIt": "Koji runtime zelis da preferiras kada su oba dostupna.",
        "effect": "TurboQuant agresivnije stedi memoriju; llama.cpp je jednostavniji fallback.",
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
        "description": "Najbezbedniji preset za duzi rad i najmanji rizik po kvalitet.",
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
        "description": "Preporuceni balans brzine, memorije i svakodnevnog rada.",
        "targetModelPattern": "qwen36-*",
        "notes": "Preporuceni daily izbor za TurboQuant.",
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
        "description": "Agresivniji preset kada juris najduzi context.",
        "targetModelPattern": "qwen36-*",
        "notes": "Jace stedi memoriju uz veci rizik performansi.",
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
        "fitNote": "Stretch izbor kada hoces bolji kvalitet uz veci pritisak.",
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
        "fitNote": "Stretch 27B izbor kada juris veci model po svaku cenu.",
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
) -> dict[str, object]:
    effective = load_effective_settings_state(config)
    return {
        "profile": effective["profile"],
        "context": effective["context"],
        "outputTokens": effective["outputTokens"],
        "workingDirectory": effective["workingDirectory"],
        "thinkingMode": effective["thinkingMode"],
        "buildSteps": effective["buildSteps"],
        "planSteps": effective["planSteps"],
        "generalSteps": effective["generalSteps"],
        "exploreSteps": effective["exploreSteps"],
        "settingsScope": effective["settingsScope"],
        "activeModelId": effective["activeModelId"],
        "activeModelLabel": effective["activeModelLabel"],
        "modelOverrideExists": effective["modelOverrideExists"],
        "accessMode": effective["accessMode"],
    }


def apply_settings(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    scope = str(payload.get("settingsScope", "global") or "global").strip().lower()
    current_global = _normalize_global_settings(
        read_json_object(config.settings_path),
        config=config,
    )
    normalized = _normalize_settings_payload(
        payload,
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
        overrides[active_model_id] = normalized
        atomic_write_json(config.model_overrides_path, {"models": overrides})
        return action_result(
            "ok",
            "apply-settings",
            f"Sacuvan je model override za {active_model_id}.",
        )

    atomic_write_json(config.settings_path, normalized)
    return action_result("ok", "apply-settings", "Global settings su sacuvani.")


def apply_opencode_settings(
    payload: dict[str, object],
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    current_global = _normalize_global_settings(
        read_json_object(config.settings_path),
        config=config,
    )
    normalized = _normalize_settings_payload(
        payload,
        config=config,
        current=current_global,
        respect_explicit_steps=True,
    )
    atomic_write_json(config.settings_path, normalized)
    return action_result(
        "ok",
        "apply-opencode-settings",
        "OpenCode settings su sacuvani.",
    )


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
    baseline = dict(TURBOQUANT_BUILTIN_PRESETS[1]["settings"])
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
    return action_result("ok", "save-turboquant-config", "TurboQuant config je sacuvan.")


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
    return action_result("ok", "save-turboquant-preset", f"Sacuvan TurboQuant preset: {name}")


def delete_turboquant_user_preset(
    preset_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    presets = load_turboquant_user_presets(config)
    filtered = [item for item in presets if str(item.get("id", "") or "") != str(preset_id)]
    if len(filtered) == len(presets):
        return action_result("error", "delete-turboquant-preset", "Preset nije pronadjen.", stderr="Preset nije pronadjen.")
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
    return action_result("ok", "save-opencode-step-preset", f"Sacuvan OpenCode preset: {name}")


def delete_opencode_step_preset(
    preset_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    presets = load_opencode_step_user_presets(config)
    filtered = [item for item in presets if str(item.get("id", "") or "") != str(preset_id)]
    if len(filtered) == len(presets):
        return action_result("error", "delete-opencode-step-preset", "Preset nije pronadjen.", stderr="Preset nije pronadjen.")
    atomic_write_json(config.opencode_step_presets_path, {"presets": filtered})
    return action_result("ok", "delete-opencode-step-preset", "OpenCode preset je obrisan.")


def _normalize_global_settings(
    payload: dict[str, object],
    *,
    config: ControlCenterConfig,
) -> dict[str, object]:
    defaults = {
        "profile": "balanced",
        "context": 262144,
        "outputTokens": 8192,
        "workingDirectory": str(config.install_root),
        "thinkingMode": "mid",
        "buildSteps": 140,
        "planSteps": 100,
        "generalSteps": 110,
        "exploreSteps": 80,
        "accessMode": "local-only",
        "securityMode": "strict",
        "capabilityMode": "confirm-commands",
    }
    return _normalize_settings_payload(
        payload,
        config=config,
        current=defaults,
        respect_explicit_steps=True,
    )


def _normalize_settings_payload(
    payload: dict[str, object],
    *,
    config: ControlCenterConfig,
    current: dict[str, object],
    respect_explicit_steps: bool,
) -> dict[str, object]:
    normalized_profile = str(payload.get("profile", current["profile"]) or current["profile"]).strip().lower()
    if normalized_profile not in ALLOWED_PROFILES:
        normalized_profile = str(current["profile"])

    normalized_access_mode = str(payload.get("accessMode", current["accessMode"]) or current["accessMode"]).strip().lower()
    if normalized_access_mode not in ALLOWED_ACCESS_MODES:
        normalized_access_mode = str(current["accessMode"])

    normalized_security_mode = str(payload.get("securityMode", current.get("securityMode", "strict")) or current.get("securityMode", "strict")).strip().lower()
    if normalized_security_mode not in ALLOWED_SECURITY_MODES:
        normalized_security_mode = str(current.get("securityMode", "strict"))

    normalized_capability_mode = str(payload.get("capabilityMode", current.get("capabilityMode", "confirm-commands")) or current.get("capabilityMode", "confirm-commands")).strip().lower()
    if normalized_capability_mode not in ALLOWED_CAPABILITY_MODES:
        normalized_capability_mode = str(current.get("capabilityMode", "confirm-commands"))

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

    return {
        "profile": normalized_profile,
        "context": _positive_int(payload.get("context"), int(current["context"])),
        "outputTokens": _positive_int(payload.get("outputTokens"), int(current["outputTokens"])),
        "workingDirectory": working_directory,
        "thinkingMode": thinking_mode,
        "buildSteps": build_steps,
        "planSteps": plan_steps,
        "generalSteps": general_steps,
        "exploreSteps": explore_steps,
        "accessMode": normalized_access_mode,
        "securityMode": normalized_security_mode,
        "capabilityMode": normalized_capability_mode,
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


def _positive_int(value: object, fallback: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return fallback
    return candidate if candidate > 0 else fallback


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
