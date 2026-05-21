import json
from importlib.resources import files


def load_runtime_manifest(manifest_path=None) -> dict:
    if manifest_path is None:
        manifest_path = files("local_ai_control_center_installer.manifests").joinpath(
            "windows-stable-runtime.json"
        )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "runtime_artifact" not in payload or "starter_models" not in payload:
        raise ValueError("Runtime manifest is missing required top-level fields.")
    runtime_artifact = payload["runtime_artifact"]
    for key in (
        "id",
        "url",
        "sha256",
        "archive_type",
        "required_files",
        "install_subdir",
    ):
        if key not in runtime_artifact:
            raise ValueError(f"Runtime artifact entry is missing required field: {key}")
    return payload


def resolve_requested_starter_model(manifest: dict, requested_model_id: str) -> dict:
    try:
        return manifest["starter_models"][requested_model_id]
    except KeyError as exc:
        raise ValueError(f"Missing starter model entry for {requested_model_id}") from exc
