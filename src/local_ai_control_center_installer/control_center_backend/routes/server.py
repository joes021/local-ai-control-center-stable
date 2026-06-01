from fastapi import APIRouter

from local_ai_control_center_installer.control_center_backend.services.server_service import (
    load_server_status,
    open_server_web,
    restart_server,
    start_server,
    stop_server,
)


router = APIRouter()


@router.get("/api/server/status")
def server_status() -> dict[str, object]:
    return load_server_status()


@router.post("/api/server/start")
def server_start() -> dict[str, object]:
    return start_server()


@router.post("/api/server/stop")
def server_stop() -> dict[str, object]:
    return stop_server()


@router.post("/api/server/restart")
def server_restart() -> dict[str, object]:
    return restart_server()


@router.post("/api/server/open-web")
def server_open_web() -> dict[str, object]:
    return open_server_web()
