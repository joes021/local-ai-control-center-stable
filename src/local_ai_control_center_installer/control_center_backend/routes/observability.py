from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.observability_service import (
    load_observability_payload,
)


router = APIRouter()


@router.get("/api/observability")
def observability_summary() -> dict[str, object]:
    return load_observability_payload()
