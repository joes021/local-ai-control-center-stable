from fastapi import APIRouter
from pydantic import BaseModel

from local_ai_control_center_installer.control_center_backend.services.models_service import (
    activate_model,
    add_hf_model,
    add_local_model,
    add_unsloth_model,
    delete_model,
    download_model,
    get_model_action_status,
    load_download_progress_payload,
    load_models_payload,
)


router = APIRouter()


@router.get("/api/models")
def models() -> dict[str, object]:
    return load_models_payload()


class ActivateModelRequest(BaseModel):
    modelId: str


@router.post("/api/models/activate")
def models_activate(payload: ActivateModelRequest) -> dict[str, object]:
    return activate_model(payload.modelId)


@router.post("/api/models/download")
def models_download(payload: ActivateModelRequest) -> dict[str, object]:
    return download_model(payload.modelId)


@router.get("/api/models/download-progress")
def models_download_progress() -> dict[str, object]:
    return load_download_progress_payload()


@router.get("/api/models/action-status/{action_id}")
def models_action_status(action_id: str) -> dict[str, object]:
    return get_model_action_status(action_id)


class AddLocalModelRequest(BaseModel):
    path: str
    label: str = ""
    family: str = "Custom"


@router.post("/api/models/add-local")
def models_add_local(payload: AddLocalModelRequest) -> dict[str, object]:
    return add_local_model(payload.path, payload.label, payload.family)


class AddRemoteModelRequest(BaseModel):
    repo: str
    filename: str
    label: str = ""
    family: str = "Custom"


@router.post("/api/models/add-hf")
def models_add_hf(payload: AddRemoteModelRequest) -> dict[str, object]:
    return add_hf_model(payload.repo, payload.filename, payload.label, payload.family)


@router.post("/api/models/add-unsloth")
def models_add_unsloth(payload: AddRemoteModelRequest) -> dict[str, object]:
    return add_unsloth_model(payload.repo, payload.filename, payload.label, payload.family)


class DeleteModelRequest(BaseModel):
    modelId: str
    removeFile: bool = True
    removeRegistry: bool = True


@router.post("/api/models/delete")
def models_delete(payload: DeleteModelRequest) -> dict[str, object]:
    return delete_model(
        payload.modelId,
        remove_file=payload.removeFile,
        remove_registry=payload.removeRegistry,
    )
