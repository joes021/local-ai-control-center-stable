from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from fastapi.responses import JSONResponse, PlainTextResponse

from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
    clear_benchmark_history,
    export_benchmark_runs,
    list_batteries,
    load_battery_selection,
    load_benchmark_compare,
    load_benchmark_run_status,
    load_benchmark_summary,
    restore_default_batteries,
    save_battery,
    start_battery_benchmark,
    start_selected_benchmark,
)


router = APIRouter()


@router.get("/api/benchmark")
def benchmark_summary() -> dict[str, object]:
    return load_benchmark_summary()


@router.get("/api/benchmark/run-status")
def benchmark_run_status() -> dict[str, object]:
    return load_benchmark_run_status()


@router.get("/api/benchmark/compare")
def benchmark_compare(runIds: list[str] = Query(default=[])) -> dict[str, object]:
    payload = load_benchmark_compare(_normalize_query_run_ids(runIds))
    if payload.get("status") != "ok":
        status_code = 404 if "nije pronađen" in str(payload.get("summary", "")).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(payload.get("summary", "Benchmark compare nije uspeo.")))
    return payload


@router.get("/api/benchmark/export")
def benchmark_export(
    format: str = Query(default="json"),
    runIds: list[str] = Query(default=[]),
):
    normalized_ids = _normalize_query_run_ids(runIds)
    try:
        payload = export_benchmark_runs(format, normalized_ids or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if str(format or "").strip().lower() == "csv":
        return PlainTextResponse(str(payload), media_type="text/csv; charset=utf-8")
    return JSONResponse(content=payload)


class RunSelectedRequest(BaseModel):
    scenarioId: str = ""


@router.post("/api/benchmark/run-selected")
def benchmark_run_selected(payload: RunSelectedRequest) -> dict[str, object]:
    return start_selected_benchmark(payload.scenarioId)


class RunBatteryRequest(BaseModel):
    batteryId: str = ""
    repeatCount: int = 1


@router.post("/api/benchmark/run-battery")
def benchmark_run_battery(payload: RunBatteryRequest) -> dict[str, object]:
    return start_battery_benchmark(payload.batteryId, repeat_count=payload.repeatCount)


class SaveBatteryRequest(BaseModel):
    name: str = ""
    scenarios: list[dict[str, object]] = []


@router.post("/api/benchmark/batteries/save")
def benchmark_save_battery(payload: SaveBatteryRequest) -> dict[str, object]:
    return save_battery(payload.name, payload.scenarios)


class LoadBatteryRequest(BaseModel):
    batteryId: str = ""


@router.post("/api/benchmark/batteries/load")
def benchmark_load_battery(payload: LoadBatteryRequest) -> dict[str, object]:
    return load_battery_selection(payload.batteryId)


@router.post("/api/benchmark/batteries/restore-defaults")
def benchmark_restore_defaults() -> dict[str, object]:
    return restore_default_batteries()


@router.get("/api/benchmark/batteries")
def benchmark_batteries() -> dict[str, object]:
    return list_batteries()


@router.post("/api/benchmark/clear-history")
def benchmark_clear_history() -> dict[str, object]:
    return clear_benchmark_history()


def _normalize_query_run_ids(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        parts = [part.strip() for part in str(value or "").split(",")]
        normalized.extend(part for part in parts if part)
    return normalized
