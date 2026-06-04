from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from local_ai_control_center_installer.control_center_backend.services.project_memory_service import (
    get_project_memory,
    save_project_memory,
    seed_project_memory_from_task,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
)


router = APIRouter()


class ProjectMemorySeedRequest(BaseModel):
    goal: str = ""
    taskPrompt: str = ""


class ProjectMemorySaveRequest(BaseModel):
    goal: dict[str, Any] = Field(default_factory=dict)
    rules: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    progress: list[dict[str, Any]] = Field(default_factory=list)
    nextSteps: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/api/project-memory")
def project_memory_document() -> dict[str, Any]:
    return get_project_memory()


@router.post("/api/project-memory/seed")
def project_memory_seed(payload: ProjectMemorySeedRequest) -> dict[str, Any]:
    seeded = seed_project_memory_from_task(payload.goal, payload.taskPrompt)
    return save_project_memory(seeded, updated_by="system")


@router.post("/api/project-memory/save")
def project_memory_save(payload: ProjectMemorySaveRequest) -> dict[str, Any]:
    saved = save_project_memory(payload.model_dump(), updated_by="user")
    result = action_result(
        "ok",
        "save-project-memory",
        "Project Memory je sačuvan.",
    )
    result["memory"] = saved
    return result
