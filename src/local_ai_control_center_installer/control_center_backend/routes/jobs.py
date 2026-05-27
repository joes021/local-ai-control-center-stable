from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.jobs_service import (
    delete_job,
    load_jobs_summary,
    run_job_now,
    save_job,
)


router = APIRouter()


@router.get("/api/jobs")
def jobs_summary() -> dict[str, object]:
    return load_jobs_summary()


class SaveJobRequest(BaseModel):
    id: str | None = None
    name: str = ""
    kind: str = "health-check"
    intervalMinutes: int = 60
    enabled: bool = True
    targetId: str = ""
    workflowPresetId: str = ""


@router.post("/api/jobs/save")
def jobs_save(payload: SaveJobRequest) -> dict[str, object]:
    return save_job(payload.model_dump())


class RunJobRequest(BaseModel):
    jobId: str = ""


@router.post("/api/jobs/run")
def jobs_run(payload: RunJobRequest) -> dict[str, object]:
    return run_job_now(payload.jobId)


class DeleteJobRequest(BaseModel):
    jobId: str = ""


@router.post("/api/jobs/delete")
def jobs_delete(payload: DeleteJobRequest) -> dict[str, object]:
    return delete_job(payload.jobId)
