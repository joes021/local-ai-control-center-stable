from __future__ import annotations

from pathlib import Path

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.models_service import (
    activate_model,
    load_models_payload,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    load_server_status,
    start_server,
    stop_server,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    load_effective_settings_state,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    atomic_write_json,
    read_json_object,
)
from local_ai_control_center_installer.opencode_bootstrap import _write_managed_config
from local_ai_control_center_installer.runtime_bootstrap import load_runtime_endpoint_config


def run_repair(
    kind: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    normalized = str(kind or "").strip().lower()
    if normalized == "install":
        return repair_install(config)
    if normalized == "model":
        return repair_model(config)
    if normalized == "runtime":
        return repair_runtime(config)
    if normalized == "config":
        return repair_config(config)
    return _repair_result(
        "error",
        normalized or "unknown",
        title="Repair nije uspeo",
        user_message="Nepoznat repair tip.",
        next_step="Izaberi jedan od ponudjenih repair tokova.",
        summary="Nepoznat repair tip.",
        stderr="Nepoznat repair tip.",
    )


def repair_install(
    config: ControlCenterConfig,
) -> dict[str, object]:
    problems: list[str] = []
    if not config.active_model_config_path.is_file():
        problems.append("missing active-model.json")
    if not config.runtime_endpoint_config_path.is_file():
        problems.append("missing runtime-endpoint.json")
    if not config.opencode_managed_config_path.is_file():
        problems.append("missing opencode managed config")

    if not problems:
        return _repair_result(
            "ok",
            "install",
            title="Instalacija izgleda zdravo",
            user_message="Osnovni installer-managed artefakti postoje i deluju konzistentno.",
            next_step="Ako i dalje nešto ne radi, probaj runtime ili model repair.",
            summary="Installer-managed artefakti deluju zdravo.",
            stdout="active-model.json, runtime-endpoint.json i managed-config postoje.",
        )

    return _repair_result(
        "error",
        "install",
        title="Instalacija traži intervenciju",
        user_message="Nedostaje jedan ili više osnovnih installer-managed artefakata.",
        next_step="Pokreni installer ponovo ili probaj Config repair da obnovis konfiguraciju.",
        summary="Install repair je pronasao nedostajucu konfiguraciju.",
        stderr=", ".join(problems),
    )


def repair_model(
    config: ControlCenterConfig,
) -> dict[str, object]:
    active_payload = read_json_object(config.active_model_config_path)
    active_model_id = str(active_payload.get("model_id", "") or "")
    active_model_path = Path(str(active_payload.get("model_path", "") or ""))
    if active_model_id and active_model_path.is_file():
        return _repair_result(
            "ok",
            "model",
            title="Aktivni model izgleda zdravo",
            user_message="Aktivni model postoji na disku i ne traži popravku.",
            next_step="Ako baš taj model daje loš rezultat, probaj drugi model iz Models taba.",
            summary="Aktivni model postoji na disku.",
            stdout=str(active_model_path),
        )

    payload = load_models_payload(config)
    candidates = [
        item
        for group_name in ("curated", "local", "huggingFace", "unsloth")
        for item in payload[group_name]
        if item.get("installed")
    ]
    if not candidates:
        return _repair_result(
            "error",
            "model",
            title="Nema modela za oporavak",
            user_message="Panel nije nasao nijedan instaliran model koji može da postavi kao aktivan.",
            next_step="Idi na Models i skinite ili dodaj novi model.",
            summary="Model repair nije nasao instaliran model.",
            stderr="Nema kandidata za aktivaciju.",
        )

    result = activate_model(str(candidates[0]["id"]), config)
    if result.get("status") == "ok":
        return _repair_result(
            "ok",
            "model",
            title="Aktivni model je obnovljen",
            user_message=f"Panel je prebacio aktivni model na {candidates[0]['label']}.",
            next_step="Ponovo otvori OpenCode session da preuzme novi model.",
            summary=str(result.get("summary", "")),
            stdout=str(result.get("details", {}).get("stdout", "")),
        )
    return _repair_result(
        "error",
        "model",
        title="Model repair nije uspeo",
        user_message="Panel nije uspeo bezbedno da obnovi aktivni model.",
        next_step="Idi na Models i ručno aktiviraj drugi instalirani model.",
        summary=str(result.get("summary", "")),
        stderr=str(result.get("details", {}).get("stderr", "")),
    )


def repair_runtime(
    config: ControlCenterConfig,
) -> dict[str, object]:
    server_status = load_server_status(config)
    if server_status["status"] == "started":
        return _repair_result(
            "ok",
            "runtime",
            title="Runtime je već zdrav",
            user_message="Runtime server već radi i health endpoint odgovara.",
            next_step="Ako imaš problem samo u jednom tool-u, probaj restart servera iz Server taba.",
            summary="Runtime je već started.",
            stdout=server_status["healthUrl"],
        )

    if server_status["status"] == "warming":
        stop_result = stop_server(config)
        if stop_result.get("status") != "ok":
            return _repair_result(
                "error",
                "runtime",
                title="Runtime repair nije uspeo",
                user_message="Runtime nije mogao bezbedno da se zaustavi pre restarta.",
                next_step="Zatvori stare procese i pokušaj ponovo.",
                summary=str(stop_result.get("summary", "")),
                stderr=str(stop_result.get("details", {}).get("stderr", "")),
            )

    start_result = start_server(config)
    if start_result.get("status") == "ok":
        return _repair_result(
            "ok",
            "runtime",
            title="Runtime start je poslat",
            user_message="Runtime je dobio novi start zahtev.",
            next_step="Sačekaj nekoliko sekundi pa proveri Server tab.",
            summary=str(start_result.get("summary", "")),
            stdout=str(start_result.get("details", {}).get("stdout", "")),
        )

    return _repair_result(
        "error",
        "runtime",
        title="Runtime repair nije uspeo",
        user_message="Panel nije uspeo da pokrene aktivni runtime.",
        next_step="Proveri da li postoje runtime binar i aktivni model na disku.",
        summary=str(start_result.get("summary", "")),
        stderr=str(start_result.get("details", {}).get("stderr", "")),
    )


def repair_config(
    config: ControlCenterConfig,
) -> dict[str, object]:
    wrote_anything = False
    if not config.settings_path.is_file():
        defaults = load_effective_settings_state(config)
        atomic_write_json(
            config.settings_path,
            {
                "profile": defaults["profile"],
                "context": defaults["context"],
                "outputTokens": defaults["outputTokens"],
                "workingDirectory": defaults["workingDirectory"],
                "thinkingMode": defaults["thinkingMode"],
                "buildSteps": defaults["buildSteps"],
                "planSteps": defaults["planSteps"],
                "generalSteps": defaults["generalSteps"],
                "exploreSteps": defaults["exploreSteps"],
                "accessMode": defaults["accessMode"],
                "securityMode": defaults["securityMode"],
                "capabilityMode": defaults["capabilityMode"],
            },
        )
        wrote_anything = True

    try:
        endpoint = load_runtime_endpoint_config(config.runtime_endpoint_config_path)
    except Exception:  # noqa: BLE001
        endpoint = None
    active_payload = read_json_object(config.active_model_config_path)
    active_model_id = str(active_payload.get("model_id", "") or "")
    active_model_path = Path(str(active_payload.get("model_path", "") or ""))
    if endpoint is not None and active_model_id and not config.opencode_managed_config_path.is_file():
        _write_managed_config(
            config.opencode_managed_config_path,
            model_id=active_model_id,
            public_model_name=active_model_path.name or active_model_id,
            control_center_base_url=config.ui_url,
        )
        wrote_anything = True

    if wrote_anything:
        return _repair_result(
            "ok",
            "config",
            title="Konfiguracija je obnovljena",
            user_message="Panel je obnovio osnovne config fajlove koji su nedostajali.",
            next_step="Osveži panel i proveri Settings i OpenCode tab.",
            summary="Osnovni config fajlovi su obnovljeni.",
            stdout=str(config.control_center_config_root),
        )

    return _repair_result(
        "ok",
        "config",
        title="Konfiguracija izgleda zdravo",
        user_message="Nema ocigledno nedostajucih control-center config fajlova.",
        next_step="Ako settings i dalje deluju cudno, snimi ih ponovo iz Settings taba.",
        summary="Config repair nije morao nista da menja.",
        stdout=str(config.control_center_config_root),
    )


def _repair_result(
    status: str,
    repair_kind: str,
    *,
    title: str,
    user_message: str,
    next_step: str,
    summary: str,
    stdout: str = "",
    stderr: str = "",
) -> dict[str, object]:
    payload = {
        "status": status,
        "action": f"repair-{repair_kind}",
        "repairKind": repair_kind,
        "title": title,
        "userMessage": user_message,
        "nextStep": next_step,
        "safeForNonTechnicalUsers": True,
        "summary": summary,
        "details": {
            "returncode": 0 if status == "ok" else 1,
            "stdout": stdout,
            "stderr": stderr,
        },
    }
    return payload
