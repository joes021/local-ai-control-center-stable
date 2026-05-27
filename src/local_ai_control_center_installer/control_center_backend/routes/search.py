from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.search_provider_service import (
    bootstrap_search_provider,
    load_search_provider_status,
)
from local_ai_control_center_installer.control_center_backend.services.search_service import (
    answer_with_local_model,
    load_search_history,
    load_web_search_settings,
    perform_search_query,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    load_web_search_provider_options,
)


router = APIRouter()


@router.get("/api/search")
def search_summary() -> dict[str, object]:
    return {
        "settings": load_web_search_settings(),
        "availableProviders": load_web_search_provider_options(),
        "history": load_search_history(),
        "providerStatus": load_search_provider_status(),
    }


class SearchQueryRequest(BaseModel):
    query: str = ""
    provider: str = ""


class SearchProviderRequest(BaseModel):
    provider: str = ""


@router.post("/api/search/query")
def search_query(payload: SearchQueryRequest) -> dict[str, object]:
    return perform_search_query(
        payload.query,
        provider_override=payload.provider or None,
        mode_label="manual",
        record_history=True,
    )


@router.post("/api/search/answer")
def search_answer(payload: SearchQueryRequest) -> dict[str, object]:
    return answer_with_local_model(
        payload.query,
        provider_override=payload.provider or None,
    )


@router.post("/api/search/provider/check")
def search_provider_check(payload: SearchProviderRequest | None = None) -> dict[str, object]:
    provider = payload.provider if payload else ""
    return load_search_provider_status(provider_override=provider or None)


@router.post("/api/search/provider/bootstrap")
def search_provider_bootstrap(payload: SearchProviderRequest | None = None) -> dict[str, object]:
    provider = payload.provider if payload else ""
    return bootstrap_search_provider(provider_override=provider or None)
