from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.fleet_service import (
    add_fleet_machine,
    load_fleet_summary,
    refresh_fleet_machine,
    remove_fleet_machine,
)


router = APIRouter()


@router.get("/api/fleet")
def fleet_summary() -> dict[str, object]:
    return load_fleet_summary()


class AddFleetMachineRequest(BaseModel):
    name: str = ""
    baseUrl: str = ""


@router.post("/api/fleet/add")
def fleet_add(payload: AddFleetMachineRequest) -> dict[str, object]:
    return add_fleet_machine(payload.name, payload.baseUrl)


class RefreshFleetMachineRequest(BaseModel):
    machineId: str | None = None


@router.post("/api/fleet/refresh")
def fleet_refresh(payload: RefreshFleetMachineRequest) -> dict[str, object]:
    return refresh_fleet_machine(payload.machineId)


class RemoveFleetMachineRequest(BaseModel):
    machineId: str = ""


@router.post("/api/fleet/remove")
def fleet_remove(payload: RemoveFleetMachineRequest) -> dict[str, object]:
    return remove_fleet_machine(payload.machineId)
