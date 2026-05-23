from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    apply_settings,
    load_settings_payload,
    load_turboquant_config,
    save_turboquant_config,
)


FIT_LABELS = {
    "radi": "Radi",
    "granicno": "Granicno",
    "ne radi": "Ne radi",
    "nije provereno": "Nije provereno",
}

SPEED_LABELS = {
    "faster": "Brze",
    "similar": "Slicno",
    "slower": "Sporije",
    "much-slower": "Mnogo sporije",
}

TURBO_FACTORS = {
    "turbo2": 0.58,
    "turbo3": 0.72,
    "turbo4": 0.86,
    "q8_0": 0.93,
    "q4_0": 0.8,
    "q4_1": 0.82,
    "f16": 1.0,
    "bf16": 1.0,
    "f32": 1.1,
}


def run_compatibility_check(
    *,
    catalog_model_id: str = "",
    model: dict[str, object] | None = None,
    overrides: dict[str, object] | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    resolved_model = _resolve_compatibility_model(
        catalog_model_id=catalog_model_id,
        model=model,
        config=config,
    )
    if not resolved_model:
        return _not_checked_result("Model nije pronadjen za compatibility proveru.")

    system_info = detect_local_system_info(config=config)
    merged_system = _merge_system_overrides(system_info, overrides or {})
    return calculate_compatibility(resolved_model, system_info=merged_system)


def apply_compatibility_action(
    *,
    action: dict[str, object],
    catalog_model_id: str = "",
    model: dict[str, object] | None = None,
    overrides: dict[str, object] | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    result = _apply_action(action, config=config)
    compatibility = run_compatibility_check(
        catalog_model_id=catalog_model_id,
        model=model,
        overrides=overrides,
        config=config,
    )
    return {
        "result": result,
        "compatibility": compatibility,
    }


def calculate_compatibility(model: dict[str, object], *, system_info: dict[str, object]) -> dict[str, object]:
    normalized_model = _normalize_model(model)
    normalized_system = _normalize_system(system_info)
    ram_gib = normalized_system["ramGiB"]
    vram_gib = normalized_system["vramGiB"]

    if ram_gib is None or vram_gib is None:
        result = _not_checked_result("Nije bilo dovoljno podataka o lokalnoj masini za proveru kompatibilnosti.")
        result["reasoning"] = {
            "vram": "VRAM nije poznat.",
            "ram": "RAM nije poznat.",
            "context": "Bez lokalnih hardverskih podataka context procena nije pouzdana.",
            "output": "Bez lokalnih hardverskih podataka output procena nije pouzdana.",
            "quantization": f"Kvantizacija modela je {normalized_model['quantization']}.",
            "turboQuantEffect": "TurboQuant efekat nije mogao da se proceni.",
            "moeEffect": "MoE efekat nije mogao da se proceni.",
            "speed": "Brzina nije mogla da se proceni.",
        }
        return result

    estimated = _estimate_budget(normalized_model, normalized_system)
    fit_status = _derive_fit_status(estimated)
    speed_status = _derive_speed_status(normalized_model, normalized_system, estimated)
    recommendations = _build_recommendations(normalized_model, normalized_system, estimated, fit_status)
    if len([item for item in recommendations if item.get("action")]) >= 2:
        recommendations.append(_build_apply_package(recommendations))

    return {
        "status": fit_status,
        "fitStatus": fit_status,
        "fitLabel": FIT_LABELS[fit_status],
        "speedStatus": speed_status,
        "speedLabel": SPEED_LABELS[speed_status],
        "checkedAt": _now_iso(),
        "summary": _build_summary(fit_status, speed_status, estimated),
        "checks": _build_checks(normalized_model, normalized_system, estimated, fit_status, speed_status),
        "reasoning": _build_reasoning(normalized_model, normalized_system, estimated, speed_status),
        "memoryBudget": {
            "vram": _build_budget_payload(estimated["requiredVramGiB"], vram_gib),
            "ram": _build_budget_payload(estimated["requiredRamGiB"], ram_gib),
            "contextPressure": {
                "level": estimated["contextPressureLevel"],
                "label": estimated["contextPressureLabel"],
                "currentContext": normalized_system["context"],
                "effectiveCapacity": estimated["effectiveContextCapacity"],
                "usagePercent": estimated["contextUsagePercent"],
                "details": estimated["contextPressureReason"],
            },
        },
        "systemSnapshot": {
            "ramGiB": ram_gib,
            "vramGiB": vram_gib,
            "context": normalized_system["context"],
            "outputTokens": normalized_system["outputTokens"],
            "turboQuantAvailable": normalized_system["turboQuantAvailable"],
            "turboQuantConfig": dict(normalized_system["turboQuantConfig"]),
        },
        "recommendations": recommendations,
    }


def check_model_compatibility(
    *,
    model_id: str,
    model: dict[str, object] | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    from local_ai_control_center_installer.control_center_backend.services.browser_catalog_service import (
        update_model_fit_status,
    )

    result = run_compatibility_check(
        catalog_model_id=model_id,
        model=model,
        config=config,
    )
    update_model_fit_status(model_id, result, config=config)
    return result


def detect_local_system_info(*, config: ControlCenterConfig | None = None) -> dict[str, object]:
    config = config or get_config()
    settings = load_settings_payload(config)
    turbo_config = load_turboquant_config(config)
    return {
        "ramGiB": detect_ram_gib(),
        "vramGiB": detect_vram_gib(),
        "turboQuantAvailable": True,
        "context": int(settings.get("context", 262144) or 262144),
        "outputTokens": int(settings.get("outputTokens", 8192) or 8192),
        "turboQuantConfig": turbo_config,
    }


def detect_ram_gib() -> float | None:
    try:
        if os.name == "nt":
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if completed.returncode == 0:
                return _as_float(completed.stdout.strip())
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round((pages * page_size) / (1024**3), 2)
    except Exception:  # noqa: BLE001
        return None


def detect_vram_gib() -> float | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            return None
        first_line = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), "")
        mib = _as_float(first_line)
        return round((mib or 0) / 1024, 2) if mib is not None else None
    except Exception:  # noqa: BLE001
        return None


def _resolve_compatibility_model(
    *,
    catalog_model_id: str,
    model: dict[str, object] | None,
    config: ControlCenterConfig | None,
) -> dict[str, object] | None:
    if model:
        return _normalize_model(model)
    if not catalog_model_id:
        return None
    from local_ai_control_center_installer.control_center_backend.services.browser_catalog_service import (
        get_catalog_model,
    )

    payload = get_catalog_model(catalog_model_id, config=config)
    if payload:
        return _normalize_model(payload)
    return None


def _normalize_model(model: dict[str, object]) -> dict[str, object]:
    quantization = str(
        model.get("quantization")
        or model.get("quant")
        or _extract_quantization(str(model.get("filename", "") or str(model.get("label", "") or str(model.get("id", "")))))
        or "unknown"
    )
    family = str(model.get("family", "Unknown") or "Unknown")
    approx_size_gib = _as_float(model.get("approxSizeGiB"))
    min_vram = _as_float(model.get("minimumVramGiB"))
    if min_vram is None:
        min_gpu_mib = _as_float(model.get("minimumGpuMiB"))
        min_vram = round((min_gpu_mib or 0) / 1024, 2) if min_gpu_mib is not None else None
    recommended_vram = _as_float(model.get("recommendedVramGiB"))
    if recommended_vram is None:
        recommended_gpu_mib = _as_float(model.get("recommendedGpuMiB"))
        recommended_vram = round((recommended_gpu_mib or 0) / 1024, 2) if recommended_gpu_mib is not None else None
    minimum_ram = _as_float(model.get("minimumRamGiB"))
    context_window = _as_float(model.get("contextWindow")) or _guess_context_window(
        str(model.get("id", "") or ""),
        str(model.get("filename", "") or ""),
    )
    default_output = _as_float(model.get("defaultOutputTokens")) or 4096
    combined_text = " ".join(
        [
            str(model.get("id", "") or ""),
            str(model.get("filename", "") or ""),
            str(model.get("label", "") or ""),
            str(model.get("repoId", "") or ""),
            str(model.get("repo", "") or ""),
        ]
    ).lower()
    moe = bool(model.get("moe")) or "a3b" in combined_text or "moe" in combined_text
    turboquant_ready = bool(model.get("turboQuantReady")) or quantization.startswith(("IQ", "Q2", "Q3", "Q4"))

    return {
        "id": str(model.get("id", "") or str(model.get("filename", "") or "unknown-model")),
        "label": str(model.get("label", "") or str(model.get("filename", "") or "Unknown model")),
        "family": family,
        "quantization": quantization,
        "approxSizeGiB": approx_size_gib,
        "minimumRamGiB": minimum_ram or _guess_min_ram(approx_size_gib, moe=moe),
        "minimumVramGiB": min_vram or _guess_min_vram(approx_size_gib, turboquant_ready=turboquant_ready),
        "recommendedVramGiB": recommended_vram or _guess_recommended_vram(approx_size_gib, turboquant_ready=turboquant_ready),
        "contextWindow": context_window,
        "defaultOutputTokens": default_output,
        "moe": moe,
        "turboQuantReady": turboquant_ready,
    }


def _normalize_system(system_info: dict[str, object]) -> dict[str, object]:
    turbo_config = dict(system_info.get("turboQuantConfig") or {})
    merged_turbo = {
        "ctk": str(turbo_config.get("ctk", "turbo4") or "turbo4"),
        "ctv": str(turbo_config.get("ctv", "turbo3") or "turbo3"),
        "ncmoe": int(turbo_config.get("ncmoe", 20) or 20),
        "runtimePreference": str(turbo_config.get("runtimePreference", "turboquant") or "turboquant"),
    }
    return {
        "ramGiB": _as_float(system_info.get("ramGiB")),
        "vramGiB": _as_float(system_info.get("vramGiB")),
        "turboQuantAvailable": bool(system_info.get("turboQuantAvailable")),
        "context": int(_as_float(system_info.get("context")) or 32768),
        "outputTokens": int(_as_float(system_info.get("outputTokens")) or 2048),
        "turboQuantConfig": merged_turbo,
    }


def _merge_system_overrides(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    turbo_config = dict(base.get("turboQuantConfig") or {})
    for key in ("ramGiB", "vramGiB", "context", "outputTokens", "turboQuantAvailable"):
        if key in overrides and overrides.get(key) not in (None, ""):
            merged[key] = overrides[key]
    for key in ("ctk", "ctv", "ncmoe", "runtimePreference"):
        if key in overrides and overrides.get(key) not in (None, ""):
            turbo_config[key] = overrides[key]
    merged["turboQuantConfig"] = turbo_config
    return merged


def _estimate_budget(model: dict[str, object], system: dict[str, object]) -> dict[str, object]:
    approx_size_gib = _as_float(model.get("approxSizeGiB")) or 0.0
    minimum_vram = _as_float(model.get("minimumVramGiB")) or max(4.0, round(approx_size_gib * 0.78, 2))
    minimum_ram = _as_float(model.get("minimumRamGiB")) or max(8.0, round(approx_size_gib * 1.45, 2))
    recommended_vram = _as_float(model.get("recommendedVramGiB")) or max(minimum_vram + 1.5, round(approx_size_gib * 1.05, 2))
    moe = bool(model.get("moe"))
    default_output = _as_float(model.get("defaultOutputTokens")) or 4096
    turbo_enabled = bool(system["turboQuantAvailable"]) and str(system["turboQuantConfig"]["runtimePreference"]).lower() == "turboquant"
    ctk = str(system["turboQuantConfig"]["ctk"]).lower()
    ctv = str(system["turboQuantConfig"]["ctv"]).lower()
    ncmoe = int(system["turboQuantConfig"]["ncmoe"])
    compression = _compression_factor(ctk, ctv, turbo_enabled)

    context = int(system["context"])
    output_tokens = int(system["outputTokens"])
    context_multiplier = context / 131072
    output_multiplier = output_tokens / max(default_output, 1024)

    context_vram = max(0.25, context_multiplier * (2.2 if moe else 1.6) * compression)
    output_vram = max(0.1, output_multiplier * 0.55)
    moe_relief = (min(ncmoe, 40) / 10) * 0.28 if moe else 0.0
    runtime_bonus = 0.6 if turbo_enabled and model.get("turboQuantReady") else 0.0
    required_vram = round(max(minimum_vram, minimum_vram + context_vram + output_vram - moe_relief - runtime_bonus), 2)

    required_ram = round(
        max(
            minimum_ram,
            minimum_ram
            + (0.35 if context > 131072 else 0.0)
            + (0.25 if output_tokens > 4096 else 0.0)
            + ((ncmoe / 20) * 1.4 if moe else 0.0),
        ),
        2,
    )

    effective_context_capacity = int(
        max(
            32768,
            round(
                131072
                * (1.15 if turbo_enabled else 1.0)
                * _context_capacity_boost(ctk, ctv)
                * (0.92 if moe else 1.0)
            ),
        )
    )
    context_usage_percent = round(min(100.0, (context / max(effective_context_capacity, 1)) * 100.0), 1)
    context_level = "low"
    if context_usage_percent >= 95:
        context_level = "high"
    elif context_usage_percent >= 70:
        context_level = "medium"
    if required_vram > float(system["vramGiB"]) * 1.15 or required_ram > float(system["ramGiB"]) * 1.15:
        context_level = "high"
        context_usage_percent = max(context_usage_percent, 95.0)

    return {
        "requiredVramGiB": required_vram,
        "availableVramGiB": float(system["vramGiB"]),
        "requiredRamGiB": required_ram,
        "availableRamGiB": float(system["ramGiB"]),
        "recommendedVramGiB": round(recommended_vram, 2),
        "contextPressureLevel": context_level,
        "contextPressureLabel": {"low": "Nizak", "medium": "Srednji", "high": "Visok"}[context_level],
        "contextPressureReason": (
            f"Context {context} koristi efektivni kapacitet oko {effective_context_capacity} tokena uz "
            f"{ctk}/{ctv} i ncmoe={ncmoe}."
        ),
        "effectiveContextCapacity": effective_context_capacity,
        "contextUsagePercent": context_usage_percent,
    }


def _derive_fit_status(estimated: dict[str, object]) -> str:
    required_vram = float(estimated["requiredVramGiB"])
    available_vram = float(estimated["availableVramGiB"])
    required_ram = float(estimated["requiredRamGiB"])
    available_ram = float(estimated["availableRamGiB"])
    context_level = str(estimated["contextPressureLevel"])

    if available_vram < required_vram or available_ram < required_ram:
        return "ne radi"
    if (
        available_vram < float(estimated["recommendedVramGiB"])
        or available_vram - required_vram < 0.8
        or available_ram - required_ram < 2.0
        or context_level != "low"
    ):
        return "granicno"
    return "radi"


def _derive_speed_status(model: dict[str, object], system: dict[str, object], estimated: dict[str, object]) -> str:
    score = 0
    if bool(model.get("moe")):
        score += 1
    if int(system["context"]) >= 262144:
        score += 2
    elif int(system["context"]) >= 131072:
        score += 1
    if int(system["outputTokens"]) >= 8192:
        score += 1
    if int(system["turboQuantConfig"]["ncmoe"]) >= 30:
        score += 2
    elif int(system["turboQuantConfig"]["ncmoe"]) >= 20 and bool(model.get("moe")):
        score += 1
    if str(estimated["contextPressureLevel"]) == "high":
        score += 1
    if score >= 5:
        return "much-slower"
    if score >= 2:
        return "slower"
    if bool(system["turboQuantAvailable"]) and str(system["turboQuantConfig"]["runtimePreference"]).lower() == "turboquant" and int(system["context"]) <= 131072:
        return "faster"
    return "similar"


def _build_summary(fit_status: str, speed_status: str, estimated: dict[str, object]) -> str:
    summaries = {
        "radi": "Model deluje upotrebljivo na ovoj masini.",
        "granicno": "Model je verovatno upotrebljiv, ali uz tesne granice ili dodatna podesavanja.",
        "ne radi": "Model verovatno nije upotrebljiv na ovoj masini bez ozbiljnih kompromisa.",
        "nije provereno": "Kompatibilnost nije proverena.",
    }
    speed_summary = {
        "faster": "Brzina deluje povoljno.",
        "similar": "Brzina deluje normalno za ovu klasu modela.",
        "slower": "Brzina ce verovatno biti sporija.",
        "much-slower": "Brzina ce verovatno biti mnogo sporija.",
    }[speed_status]
    return f"{summaries[fit_status]} {speed_summary} Procena VRAM budzeta je oko {estimated['requiredVramGiB']:.1f} GiB."


def _build_checks(
    model: dict[str, object],
    system: dict[str, object],
    estimated: dict[str, object],
    fit_status: str,
    speed_status: str,
) -> list[dict[str, object]]:
    return [
        {
            "label": "Fit",
            "value": FIT_LABELS[fit_status],
            "outcome": "pass" if fit_status == "radi" else ("warn" if fit_status == "granicno" else "fail"),
        },
        {
            "label": "Speed",
            "value": SPEED_LABELS[speed_status],
            "outcome": "warn" if speed_status in {"slower", "much-slower"} else "pass",
        },
        {
            "label": "VRAM",
            "value": f"{estimated['requiredVramGiB']:.1f} / {system['vramGiB']:.1f} GiB",
            "outcome": "pass" if estimated["requiredVramGiB"] <= system["vramGiB"] else "fail",
        },
        {
            "label": "RAM",
            "value": f"{estimated['requiredRamGiB']:.1f} / {system['ramGiB']:.1f} GiB",
            "outcome": "pass" if estimated["requiredRamGiB"] <= system["ramGiB"] else "fail",
        },
        {
            "label": "TurboQuant",
            "value": f"{system['turboQuantConfig']['ctk']} / {system['turboQuantConfig']['ctv']} | ncmoe {system['turboQuantConfig']['ncmoe']}",
            "outcome": "info",
        },
        {
            "label": "Quant",
            "value": str(model["quantization"]),
            "outcome": "info",
        },
    ]


def _build_reasoning(
    model: dict[str, object],
    system: dict[str, object],
    estimated: dict[str, object],
    speed_status: str,
) -> dict[str, str]:
    available_vram = float(system["vramGiB"])
    available_ram = float(system["ramGiB"])
    runtime_preference = str(system["turboQuantConfig"]["runtimePreference"])
    return {
        "vram": (
            f"VRAM {'nije dovoljan' if available_vram < estimated['requiredVramGiB'] else 'deluje dovoljan'}: "
            f"procena trazi oko {estimated['requiredVramGiB']:.1f} GiB, dostupno je {available_vram:.1f} GiB."
        ),
        "ram": (
            f"RAM {'nije dovoljan' if available_ram < estimated['requiredRamGiB'] else 'deluje dovoljan'}: "
            f"procena trazi oko {estimated['requiredRamGiB']:.1f} GiB, dostupno je {available_ram:.1f} GiB."
        ),
        "context": str(estimated["contextPressureReason"]),
        "output": (
            f"Output od {int(system['outputTokens'])} tokena "
            f"{'je tezi i usporava generaciju' if int(system['outputTokens']) > 4096 else 'deluje razumno za lokalni rad'}."
        ),
        "quantization": (
            f"Kvantizacija modela je {model['quantization']} uz procenjenu velicinu {model['approxSizeGiB'] or 'nepoznato'} GiB."
        ),
        "turboQuantEffect": (
            f"TurboQuant je {'dostupan' if system['turboQuantAvailable'] else 'nedostupan'}, "
            f"a aktivni profil koristi {system['turboQuantConfig']['ctk']}/{system['turboQuantConfig']['ctv']} "
            f"uz runtime preferenciju {runtime_preference}."
        ),
        "moeEffect": (
            "MoE model trazi dodatni oprez oko VRAM-a i CPU offload-a."
            if bool(model.get("moe"))
            else "MoE efekat nije bitan za ovaj model."
        ),
        "speed": (
            f"Ocekivani rezim brzine je {SPEED_LABELS[speed_status].lower()} "
            f"zbog context={system['context']}, output={system['outputTokens']} i ncmoe={system['turboQuantConfig']['ncmoe']}."
        ),
    }


def _build_recommendations(
    model: dict[str, object],
    system: dict[str, object],
    estimated: dict[str, object],
    fit_status: str,
) -> list[dict[str, object]]:
    recommendations: list[dict[str, object]] = []
    context = int(system["context"])
    output_tokens = int(system["outputTokens"])
    turbo_config = dict(system["turboQuantConfig"])
    moe = bool(model.get("moe"))
    turbo_ready = bool(model.get("turboQuantReady"))

    if context > 131072:
        recommendations.append(
            {
                "id": "context-downshift",
                "title": "Smanji context na 131072",
                "summary": "Ovo smanjuje VRAM pritisak i obicno je prvi najbezbedniji potez.",
                "tradeoff": "Kraci razgovori i manje dugacak radni kontekst.",
                "severity": "warn",
                "action": {"kind": "set-context", "value": 131072},
            }
        )
    if output_tokens > 4096:
        recommendations.append(
            {
                "id": "output-downshift",
                "title": "Smanji output na 4096",
                "summary": "Krajnji output manje opterecuje generaciju i smanjuje rizik od dugih sporih odgovora.",
                "tradeoff": "Korisnik dobija kraci maksimalni odgovor po jednom pozivu.",
                "severity": "info",
                "action": {"kind": "set-output", "value": 4096},
            }
        )
    if turbo_ready and system["turboQuantAvailable"] and str(turbo_config["runtimePreference"]).lower() != "turboquant":
        recommendations.append(
            {
                "id": "prefer-turboquant",
                "title": "Prebaci preferenciju na TurboQuant",
                "summary": "Za ovaj model TurboQuant bolje koristi memoriju i povecava sansu da model bude upotrebljiv.",
                "tradeoff": "Agresivnija kompresija moze malo da promeni kvalitet i stabilnost.",
                "severity": "warn",
                "action": {"kind": "set-runtime-preference", "value": "turboquant", "requiresConfirmation": True},
            }
        )
    if moe and int(turbo_config["ncmoe"]) < 30:
        recommendations.append(
            {
                "id": "raise-ncmoe",
                "title": "Povecaj ncmoe na 30",
                "summary": "Visa ncmoe vrednost pomaze MoE modelima da rasterete VRAM.",
                "tradeoff": "Veci CPU teret i sporiji odgovor.",
                "severity": "warn",
                "action": {"kind": "set-ncmoe", "value": 30},
            }
        )
    ctk = str(turbo_config["ctk"]).lower()
    ctv = str(turbo_config["ctv"]).lower()
    if turbo_ready and (fit_status != "radi" or str(estimated["contextPressureLevel"]) != "low"):
        if (ctk, ctv) == ("turbo4", "turbo4"):
            recommendations.append(
                {
                    "id": "stronger-turboquant-balanced",
                    "title": "Probaj turbo4 / turbo3",
                    "summary": "Malo agresivniji V deo cache-a cesto daje najbolji daily balans.",
                    "tradeoff": "Malo jaca kompresija cache-a.",
                    "severity": "info",
                    "action": {"kind": "set-ctk-ctv", "ctk": "turbo4", "ctv": "turbo3"},
                }
            )
        elif (ctk, ctv) in {("turbo4", "turbo3"), ("turbo3", "turbo4")}:
            recommendations.append(
                {
                    "id": "stronger-turboquant-max-context",
                    "title": "Probaj turbo3 / turbo3",
                    "summary": "Jace smanjuje context pressure i VRAM trosak.",
                    "tradeoff": "Manje bezbedna kompresija od turbo4/turbo3.",
                    "severity": "warn",
                    "action": {"kind": "set-ctk-ctv", "ctk": "turbo3", "ctv": "turbo3"},
                }
            )
    if fit_status == "ne radi":
        recommendations.append(
            {
                "id": "smaller-quant",
                "title": "Probaj manju kvantizaciju ili laksi model",
                "summary": "Ovaj model verovatno nije realan bez ozbiljnih kompromisa na trenutnoj masini.",
                "tradeoff": "Moguc pad kvaliteta ili promena modela.",
                "severity": "critical",
            }
        )
    return recommendations


def _build_apply_package(recommendations: list[dict[str, object]]) -> dict[str, object]:
    package_actions = [
        dict(item["action"])
        for item in recommendations
        if isinstance(item.get("action"), dict) and item["action"].get("kind") != "apply-package"
    ][:4]
    return {
        "id": "apply-package",
        "title": "Primeni paket preporuka",
        "summary": "Primeni najvaznije preporuke redom i odmah uradi novu proveru.",
        "tradeoff": "Menja vise runtime/model settings stavki odjednom.",
        "severity": "warn",
        "action": {
            "kind": "apply-package",
            "actions": package_actions,
            "requiresConfirmation": True,
        },
    }


def _apply_action(action: dict[str, object], *, config: ControlCenterConfig | None = None) -> dict[str, object]:
    kind = str(action.get("kind", "") or "").strip().lower()
    if not kind:
        return _action_result("error", "Nedostaje compatibility action kind.")
    if kind == "apply-package":
        latest = None
        for nested in action.get("actions") or []:
            if not isinstance(nested, dict):
                continue
            latest = _apply_action(nested, config=config)
            if latest.get("status") != "ok":
                return latest
        return latest or _action_result("error", "Compatibility paket nije imao primenljive akcije.")
    if kind == "set-context":
        return _apply_settings_patch({"context": int(action.get("value", 131072) or 131072)}, config=config)
    if kind == "set-output":
        return _apply_settings_patch({"outputTokens": int(action.get("value", 4096) or 4096)}, config=config)
    if kind == "set-runtime-preference":
        return _apply_turbo_patch({"runtimePreference": str(action.get("value", "turboquant") or "turboquant")}, summary="TurboQuant runtime preference je sacuvan.", config=config)
    if kind == "set-ncmoe":
        return _apply_turbo_patch({"ncmoe": int(action.get("value", 20) or 20)}, summary="TurboQuant ncmoe je sacuvan.", config=config)
    if kind == "set-ctk-ctv":
        return _apply_turbo_patch(
            {"ctk": str(action.get("ctk", "turbo4") or "turbo4"), "ctv": str(action.get("ctv", "turbo3") or "turbo3")},
            summary="TurboQuant cache tipovi su sacuvani.",
            config=config,
        )
    return _action_result("error", f"Nepoznata compatibility akcija: {kind}")


def _apply_settings_patch(patch: dict[str, object], *, config: ControlCenterConfig | None) -> dict[str, object]:
    current = load_settings_payload(config)
    payload = {
        "profile": str(current.get("profile", "balanced")),
        "context": int(current.get("context", 262144) or 262144),
        "outputTokens": int(current.get("outputTokens", 8192) or 8192),
        "workingDirectory": str(current.get("workingDirectory", Path.home()) or Path.home()),
        "thinkingMode": str(current.get("thinkingMode", "mid") or "mid"),
        "settingsScope": str(current.get("settingsScope", "global") or "global"),
        "activeModelId": str(current.get("activeModelId", "") or ""),
        "accessMode": str(current.get("accessMode", "local-only") or "local-only"),
    }
    payload.update(patch)
    return apply_settings(payload, config)


def _apply_turbo_patch(
    patch: dict[str, object],
    *,
    summary: str,
    config: ControlCenterConfig | None,
) -> dict[str, object]:
    current = load_turboquant_config(config)
    current.update(patch)
    save_turboquant_config(current, config)
    return _action_result("ok", summary)


def _action_result(status: str, summary: str) -> dict[str, object]:
    return {
        "status": status,
        "action": "compatibility-apply",
        "summary": summary,
        "details": {
            "returncode": 0 if status == "ok" else 1,
            "stdout": summary if status == "ok" else "",
            "stderr": "" if status == "ok" else summary,
        },
    }


def _build_budget_payload(required: float, available: float) -> dict[str, object]:
    usage = round(min(100.0, (required / max(available, 0.1)) * 100.0), 1)
    return {"requiredGiB": round(required, 2), "availableGiB": round(available, 2), "usagePercent": usage}


def _context_capacity_boost(ctk: str, ctv: str) -> float:
    average = (TURBO_FACTORS.get(ctk, 1.0) + TURBO_FACTORS.get(ctv, 1.0)) / 2
    if average <= 0:
        return 1.0
    return round(1.0 / average, 2)


def _compression_factor(ctk: str, ctv: str, turbo_enabled: bool) -> float:
    if not turbo_enabled:
        return 1.0
    average = (TURBO_FACTORS.get(ctk, 1.0) + TURBO_FACTORS.get(ctv, 1.0)) / 2
    return round(max(0.5, average), 2)


def _guess_context_window(repo_id: str, filename: str) -> int:
    lowered = f"{repo_id} {filename}".lower()
    if "qwen3.6" in lowered:
        return 262144
    if "qwen3" in lowered:
        return 131072
    return 32768


def _guess_min_ram(size_gib: float | None, *, moe: bool) -> float | None:
    if size_gib is None:
        return None
    base = max(8, round(size_gib * 1.4, 2))
    return round(base + (4 if moe else 0), 2)


def _guess_min_vram(size_gib: float | None, *, turboquant_ready: bool) -> float | None:
    if size_gib is None:
        return None
    multiplier = 0.8 if turboquant_ready else 1.0
    return round(max(4, size_gib * multiplier), 2)


def _guess_recommended_vram(size_gib: float | None, *, turboquant_ready: bool) -> float | None:
    if size_gib is None:
        return None
    multiplier = 1.0 if turboquant_ready else 1.2
    return round(max(6, size_gib * multiplier), 2)


def _extract_quantization(text: str) -> str:
    matches = re.findall(r"(UD-[A-Z0-9_]+|IQ[0-9A-Z_]+|Q[2-9]_[A-Z0-9_]+|Q[2-9][A-Z0-9_]+)", text, re.IGNORECASE)
    if not matches:
        return "unknown"
    return matches[-1].upper()


def _not_checked_result(summary: str) -> dict[str, object]:
    return {
        "status": "nije provereno",
        "fitStatus": "nije provereno",
        "fitLabel": FIT_LABELS["nije provereno"],
        "speedStatus": "similar",
        "speedLabel": SPEED_LABELS["similar"],
        "checkedAt": _now_iso(),
        "summary": summary,
        "checks": [],
        "reasoning": {},
        "memoryBudget": {
            "vram": {"requiredGiB": None, "availableGiB": None, "usagePercent": None},
            "ram": {"requiredGiB": None, "availableGiB": None, "usagePercent": None},
            "contextPressure": {
                "level": "unknown",
                "label": "Nepoznato",
                "currentContext": None,
                "effectiveCapacity": None,
                "usagePercent": None,
                "details": "Context pressure nije mogao da se proceni.",
            },
        },
        "systemSnapshot": {},
        "recommendations": [],
    }


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
