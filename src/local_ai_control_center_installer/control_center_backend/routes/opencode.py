from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.opencode_service import (
    delete_opencode_step_preset_payload,
    load_opencode_step_schema_payload,
    load_opencode_status_payload,
    open_opencode,
    save_opencode_settings_payload,
    save_opencode_step_preset_payload,
)


router = APIRouter()


@router.get("/api/opencode/status")
def opencode_status() -> dict[str, object]:
    return load_opencode_status_payload()


@router.get("/api/opencode/steps")
def opencode_steps() -> dict[str, object]:
    return load_opencode_step_schema_payload()


class OpenOpenCodeRequest(BaseModel):
    profile: str = ""


@router.post("/api/opencode/open")
def opencode_open(payload: OpenOpenCodeRequest) -> dict[str, object]:
    return open_opencode(payload.profile)


@router.post("/api/opencode/settings/apply")
def opencode_settings_apply(payload: dict[str, object]) -> dict[str, object]:
    return save_opencode_settings_payload(payload)


@router.post("/api/opencode/steps/presets/save")
def opencode_steps_presets_save(payload: dict[str, object]) -> dict[str, object]:
    try:
        return save_opencode_step_preset_payload(payload)
    except ValueError as exc:
        return {
            "status": "error",
            "action": "save-opencode-step-preset",
            "summary": str(exc),
            "details": {
                "returncode": 1,
                "stdout": "",
                "stderr": str(exc),
            },
        }


@router.post("/api/opencode/steps/presets/delete")
def opencode_steps_presets_delete(payload: dict[str, object]) -> dict[str, object]:
    return delete_opencode_step_preset_payload(str(payload.get("presetId", "") or ""))
