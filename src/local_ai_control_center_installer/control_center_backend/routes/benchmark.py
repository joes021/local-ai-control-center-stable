from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.benchmark_service import (
    clear_benchmark_history,
    list_batteries,
    load_battery_selection,
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


class RunSelectedRequest(BaseModel):
    scenarioId: str = ""


@router.post("/api/benchmark/run-selected")
def benchmark_run_selected(payload: RunSelectedRequest) -> dict[str, object]:
    return start_selected_benchmark(payload.scenarioId)


class RunBatteryRequest(BaseModel):
    batteryId: str = ""


@router.post("/api/benchmark/run-battery")
def benchmark_run_battery(payload: RunBatteryRequest) -> dict[str, object]:
    return start_battery_benchmark(payload.batteryId)


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
