from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.system_service import (
    pick_local_gguf,
    pick_working_directory,
)


router = APIRouter()


@router.post("/api/system/pick-local-gguf")
def system_pick_local_gguf() -> dict[str, object]:
    return pick_local_gguf()


@router.post("/api/system/pick-working-directory")
def system_pick_working_directory() -> dict[str, object]:
    return pick_working_directory()
