from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.compatibility_service import (
    apply_compatibility_action,
    run_compatibility_check,
)


router = APIRouter()


class CompatibilityCheckRequest(BaseModel):
    catalogModelId: str = ""
    model: dict[str, object] | None = None
    overrides: dict[str, object] | None = None


class CompatibilityApplyRequest(CompatibilityCheckRequest):
    action: dict[str, object]


@router.post("/api/compatibility/check")
def compatibility_check(payload: CompatibilityCheckRequest) -> dict[str, object]:
    return run_compatibility_check(
        catalog_model_id=payload.catalogModelId,
        model=payload.model,
        overrides=payload.overrides,
    )


@router.post("/api/compatibility/apply")
def compatibility_apply(payload: CompatibilityApplyRequest) -> dict[str, object]:
    return apply_compatibility_action(
        action=payload.action,
        catalog_model_id=payload.catalogModelId,
        model=payload.model,
        overrides=payload.overrides,
    )
