from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.runtime_service import (
    select_runtime,
)


router = APIRouter()


class SelectRuntimeRequest(BaseModel):
    runtime: str


@router.post("/api/runtime/select")
def runtime_select(payload: SelectRuntimeRequest) -> dict[str, object]:
    return select_runtime(payload.runtime)
