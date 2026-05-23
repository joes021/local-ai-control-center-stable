from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    apply_settings,
    delete_turboquant_user_preset,
    load_settings_payload,
    load_turboquant_schema,
    save_turboquant_config,
    save_turboquant_user_preset,
)


router = APIRouter()


@router.get("/api/settings")
def settings() -> dict[str, object]:
    return load_settings_payload()


@router.post("/api/settings/apply")
def settings_apply(payload: dict[str, object]) -> dict[str, object]:
    return apply_settings(payload)


@router.get("/api/settings/turboquant")
def settings_turboquant() -> dict[str, object]:
    return load_turboquant_schema()


@router.post("/api/settings/turboquant-config")
def settings_turboquant_config(payload: dict[str, object]) -> dict[str, object]:
    return save_turboquant_config(payload)


@router.post("/api/settings/turboquant-presets/save")
def settings_turboquant_presets_save(payload: dict[str, object]) -> dict[str, object]:
    try:
        return save_turboquant_user_preset(payload)
    except ValueError as exc:
        return {
            "status": "error",
            "action": "save-turboquant-preset",
            "summary": str(exc),
            "details": {
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
            },
        }


@router.post("/api/settings/turboquant-presets/delete")
def settings_turboquant_presets_delete(payload: dict[str, object]) -> dict[str, object]:
    return delete_turboquant_user_preset(str(payload.get("presetId", "") or ""))
