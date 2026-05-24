from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.updates_service import (
    check_for_updates,
    install_update,
    load_update_progress_payload,
)


router = APIRouter()


@router.get("/api/updates/check")
def updates_check() -> dict[str, object]:
    return check_for_updates()


@router.post("/api/updates/install")
def updates_install() -> dict[str, object]:
    return install_update()


@router.get("/api/updates/progress")
def updates_progress() -> dict[str, object]:
    return load_update_progress_payload()
