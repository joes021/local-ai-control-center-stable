from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from local_ai_control_center_installer.control_center_backend.routes.server import (
    router as server_router,
)
from local_ai_control_center_installer.control_center_backend.routes.opencode import (
    router as opencode_router,
)
from local_ai_control_center_installer.control_center_backend.routes.models import (
    router as models_router,
)
from local_ai_control_center_installer.control_center_backend.routes.logs import (
    router as logs_router,
)
from local_ai_control_center_installer.control_center_backend.routes.repair import (
    router as repair_router,
)
from local_ai_control_center_installer.control_center_backend.routes.settings import (
    router as settings_router,
)
from local_ai_control_center_installer.control_center_backend.routes.system import (
    router as system_router,
)
from local_ai_control_center_installer.control_center_backend.routes.runtime import (
    router as runtime_router,
)
from local_ai_control_center_installer.control_center_backend.routes.status import (
    router as status_router,
)
from local_ai_control_center_installer.control_center_backend.routes.browser import (
    router as browser_router,
)
from local_ai_control_center_installer.control_center_backend.routes.compatibility import (
    router as compatibility_router,
)
from local_ai_control_center_installer.control_center_backend.routes.updates import (
    router as updates_router,
)
from local_ai_control_center_installer.control_center_backend.config import get_config

app = FastAPI(title="Local AI Control Center")


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_frontend_index() -> Path:
    packaged = _package_root() / "frontend_dist" / "index.html"
    if packaged.is_file():
        return packaged

    development = _repo_root() / "frontend" / "index.html"
    if development.is_file():
        return development

    raise FileNotFoundError("Control panel frontend index.html is not available.")


@app.get("/")
def frontend_shell() -> FileResponse:
    return FileResponse(_resolve_frontend_index())


@app.get("/health")
def health() -> dict[str, str]:
    config = get_config()
    return {
        "status": "ok",
        "app": "local-ai-control-center-stable",
        "installRoot": str(config.install_root),
    }


app.include_router(status_router)
app.include_router(server_router)
app.include_router(opencode_router)
app.include_router(models_router)
app.include_router(logs_router)
app.include_router(repair_router)
app.include_router(settings_router)
app.include_router(system_router)
app.include_router(runtime_router)
app.include_router(browser_router)
app.include_router(compatibility_router)
app.include_router(updates_router)

_packaged_assets = _package_root() / "frontend_dist" / "assets"
if _packaged_assets.is_dir():
    app.mount("/assets", StaticFiles(directory=_packaged_assets), name="assets")
