from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_status_payload,
)


router = APIRouter()


@router.get("/api/status")
def status() -> dict[str, object]:
    return load_status_payload()
