from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.tuning_lab_service import (
    apply_tuning_lab_winner,
    delete_tuning_lab_history,
    enqueue_tuning_batch,
    enqueue_tuning_experiment,
    export_tuning_lab_run,
    import_tuning_snippet,
    load_tuning_lab_history_page,
    load_tuning_lab_run_status,
    load_tuning_lab_summary,
    resolve_tuning_playable_file,
)


router = APIRouter()


@router.get("/api/tuning-lab")
def tuning_lab_summary(page: int = Query(default=1, ge=1)) -> dict[str, object]:
    return load_tuning_lab_summary(history_page=page)


@router.get("/api/tuning-lab/run-status")
def tuning_lab_run_status() -> dict[str, object]:
    return load_tuning_lab_run_status()


@router.get("/api/tuning-lab/history")
def tuning_lab_history(page: int = Query(default=1, ge=1)) -> dict[str, object]:
    return load_tuning_lab_history_page(page=page)


@router.get("/api/tuning-lab/play/{run_id}/{slot_id}/{asset_path:path}")
def tuning_lab_play_asset(run_id: str, slot_id: str, asset_path: str) -> FileResponse:
    target_path = resolve_tuning_playable_file(run_id, slot_id, asset_path)
    if target_path is None:
        raise HTTPException(status_code=404, detail="Playable artifact nije pronađen.")
    return FileResponse(target_path)


class QueueTuningExperimentRequest(BaseModel):
    name: str = ""
    goal: str = "code"
    taskPrompt: str = ""
    expectedArtifact: str = ""
    difficulty: str = ""
    workingDirectory: str = ""
    successChecks: list[dict[str, object]] = []
    slots: list[dict[str, object]] = []


@router.post("/api/tuning-lab/queue")
def tuning_lab_queue(payload: QueueTuningExperimentRequest) -> dict[str, object]:
    return enqueue_tuning_experiment(payload.model_dump())


class QueueTuningBatchRequest(BaseModel):
    presetId: str = ""
    workingDirectory: str = ""
    slots: list[dict[str, object]] = []


@router.post("/api/tuning-lab/queue-batch")
def tuning_lab_queue_batch(payload: QueueTuningBatchRequest) -> dict[str, object]:
    return enqueue_tuning_batch(payload.model_dump())


class ApplyTuningWinnerRequest(BaseModel):
    runId: str = ""
    slotId: str = ""


@router.post("/api/tuning-lab/apply-winner")
def tuning_lab_apply_winner(payload: ApplyTuningWinnerRequest) -> dict[str, object]:
    return apply_tuning_lab_winner(payload.runId, slot_id=payload.slotId or None)


class ExportTuningRunRequest(BaseModel):
    runId: str = ""


@router.post("/api/tuning-lab/export")
def tuning_lab_export(payload: ExportTuningRunRequest) -> dict[str, object]:
    return export_tuning_lab_run(payload.runId)


class DeleteTuningHistoryRequest(BaseModel):
    runIds: list[str] = []
    deleteAll: bool = False
    deleteFailed: bool = False
    deleteArtifacts: bool = False


@router.post("/api/tuning-lab/history/delete")
def tuning_lab_delete_history(payload: DeleteTuningHistoryRequest) -> dict[str, object]:
    return delete_tuning_lab_history(
        run_ids=payload.runIds,
        delete_all=payload.deleteAll,
        delete_failed=payload.deleteFailed,
        delete_artifacts=payload.deleteArtifacts,
    )


class ImportTuningSnippetRequest(BaseModel):
    snippet: str = ""


@router.post("/api/tuning-lab/import-snippet")
def tuning_lab_import_snippet(payload: ImportTuningSnippetRequest) -> dict[str, object]:
    return import_tuning_snippet(payload.snippet)
