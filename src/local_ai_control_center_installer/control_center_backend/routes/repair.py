from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.repair_service import (
    run_repair,
)


router = APIRouter()


@router.post("/api/repair/{kind}")
def repair(kind: str) -> dict[str, object]:
    return run_repair(kind)
