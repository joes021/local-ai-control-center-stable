from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


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
    return {"status": "ok"}
