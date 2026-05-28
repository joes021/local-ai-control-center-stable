from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    delete_workflow_user_preset,
    apply_settings,
    delete_settings_user_profile,
    delete_turboquant_user_preset,
    load_settings_payload,
    load_turboquant_schema,
    save_settings_user_profile,
    save_turboquant_config,
    save_turboquant_user_preset,
    save_workflow_user_preset,
)


router = APIRouter()


@router.get("/api/settings")
def settings() -> dict[str, object]:
    return load_settings_payload()


@router.post("/api/settings/apply")
def settings_apply(payload: dict[str, object]) -> dict[str, object]:
    return apply_settings(payload)


@router.post("/api/settings/profiles/save")
def settings_profiles_save(payload: dict[str, object]) -> dict[str, object]:
    try:
        return save_settings_user_profile(payload)
    except ValueError as exc:
        return {
            "status": "error",
            "action": "save-settings-profile",
            "summary": str(exc),
            "details": {
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
            },
        }


@router.post("/api/settings/profiles/delete")
def settings_profiles_delete(payload: dict[str, object]) -> dict[str, object]:
    return delete_settings_user_profile(str(payload.get("profileId", "") or ""))


@router.post("/api/settings/workflow-presets/save")
def settings_workflow_presets_save(payload: dict[str, object]) -> dict[str, object]:
    try:
        return save_workflow_user_preset(payload)
    except ValueError as exc:
        return {
            "status": "error",
            "action": "save-workflow-preset",
            "summary": str(exc),
            "details": {
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
            },
        }


@router.post("/api/settings/workflow-presets/delete")
def settings_workflow_presets_delete(payload: dict[str, object]) -> dict[str, object]:
    return delete_workflow_user_preset(str(payload.get("presetId", "") or ""))


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
