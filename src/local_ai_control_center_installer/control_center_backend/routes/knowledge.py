from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.knowledge_service import (
    add_knowledge_source,
    answer_with_knowledge,
    load_knowledge_summary,
    remove_knowledge_source,
    reindex_knowledge_sources,
    run_knowledge_query,
)


router = APIRouter()


@router.get("/api/knowledge")
def knowledge_summary() -> dict[str, object]:
    return load_knowledge_summary()


class KnowledgeSourceRequest(BaseModel):
    path: str = ""


@router.post("/api/knowledge/sources/add")
def knowledge_source_add(payload: KnowledgeSourceRequest) -> dict[str, object]:
    return add_knowledge_source(payload.path)


class KnowledgeSourceRemoveRequest(BaseModel):
    sourceId: str = ""


@router.post("/api/knowledge/sources/remove")
def knowledge_source_remove(payload: KnowledgeSourceRemoveRequest) -> dict[str, object]:
    return remove_knowledge_source(payload.sourceId)


@router.post("/api/knowledge/reindex")
def knowledge_reindex() -> dict[str, object]:
    return reindex_knowledge_sources()


class KnowledgeQueryRequest(BaseModel):
    query: str = ""
    mode: str = "documents-only"


@router.post("/api/knowledge/query")
def knowledge_query(payload: KnowledgeQueryRequest) -> dict[str, object]:
    return run_knowledge_query(payload.query)


@router.post("/api/knowledge/answer")
def knowledge_answer(payload: KnowledgeQueryRequest) -> dict[str, object]:
    return answer_with_knowledge(payload.query, mode=payload.mode)
