from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.browser_catalog_service import (
    load_catalog_payload,
    refresh_catalog,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
)
from local_ai_control_center_installer.control_center_backend.services.models_service import (
    add_hf_model,
    add_unsloth_model,
    download_model,
    load_models_payload,
)


router = APIRouter()


@router.get("/api/browser/catalog")
def browser_catalog(
    source: str = "all",
    search: str = "",
    family: str = "all",
    quant: str = "all",
    size: str = "all",
    mtp: str = "all",
    date: str = "all",
    sort: str = "updated-desc",
    limit: int | None = None,
) -> dict[str, object]:
    return load_catalog_payload(
        source=source,
        search=search,
        family=family,
        quant=quant,
        size=size,
        mtp=mtp,
        date=date,
        sort=sort,
        limit=limit,
    )


class RefreshCatalogRequest(BaseModel):
    source: str = "all"


@router.post("/api/browser/catalog/refresh")
def browser_refresh(payload: RefreshCatalogRequest) -> dict[str, object]:
    return refresh_catalog(source=payload.source)


class AddCatalogModelRequest(BaseModel):
    source: str
    repoId: str
    filename: str
    label: str = ""
    family: str = "Custom"


def add_catalog_model(*, source: str, repo_id: str, filename: str, label: str, family: str) -> dict[str, object]:
    normalized_source = (source or "").strip().lower()
    if normalized_source == "unsloth":
        result = add_unsloth_model(repo_id, filename, label, family or "Unsloth")
    else:
        result = add_hf_model(repo_id, filename, label, family or "Custom")
    local_model_id = str(result.get("localModelId", "") or "")
    if not local_model_id:
        local_model_id = _resolve_local_model_id(normalized_source, repo_id, filename)
    if local_model_id:
        result["localModelId"] = local_model_id
    result.setdefault("promptDownload", True)
    return result


@router.post("/api/browser/catalog/add")
def browser_add(payload: AddCatalogModelRequest) -> dict[str, object]:
    return add_catalog_model(
        source=payload.source,
        repo_id=payload.repoId,
        filename=payload.filename,
        label=payload.label,
        family=payload.family,
    )


class DownloadCatalogModelRequest(BaseModel):
    source: str
    repoId: str
    filename: str
    label: str = ""
    family: str = "Custom"


@router.post("/api/browser/catalog/download")
def browser_download(payload: DownloadCatalogModelRequest) -> dict[str, object]:
    add_result = add_catalog_model(
        source=payload.source,
        repo_id=payload.repoId,
        filename=payload.filename,
        label=payload.label,
        family=payload.family,
    )
    local_model_id = str(add_result.get("localModelId", "") or "")
    if not local_model_id:
        return action_result(
            "error",
            "browser-download",
            "Model je dodat u katalog, ali lokalni model ID nije razresen za download.",
            stderr="localModelId missing",
        )
    return download_model(local_model_id)


def _resolve_local_model_id(source: str, repo_id: str, filename: str) -> str:
    payload = load_models_payload()
    normalized_repo = str(repo_id or "").strip().lower()
    filename = str(filename or "")

    fallback_by_filename = ""
    for group_name in ("local", "huggingFace", "unsloth", "curated"):
        for item in payload.get(group_name, []):
            if not isinstance(item, dict):
                continue
            item_filename = str(item.get("filename", "") or "")
            if item_filename != filename:
                continue
            item_source = str(item.get("source", "") or "").lower()
            item_repo = str(item.get("repo", "") or item.get("repoId", "") or "").strip().lower()
            if normalized_repo and item_repo == normalized_repo:
                return str(item.get("id", "") or "")
            if item_source == source:
                return str(item.get("id", "") or "")
            if not fallback_by_filename:
                fallback_by_filename = str(item.get("id", "") or "")
    return fallback_by_filename
