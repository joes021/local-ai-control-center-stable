from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.logs_service import (
    load_logs_result,
)


router = APIRouter()


@router.get("/api/logs")
def logs() -> dict[str, object]:
    return load_logs_result()
