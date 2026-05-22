import json
from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class StarterModelOption:
    model_id: str
    prompt_label: str
    prompt_order: int
    recommended_default: bool


def load_runtime_manifest(manifest_path=None) -> dict:
    if manifest_path is None:
        manifest_path = files("local_ai_control_center_installer.manifests").joinpath(
            "windows-stable-runtime.json"
        )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "runtime_artifact" not in payload or "starter_models" not in payload:
        raise ValueError("Runtime manifest is missing required top-level fields.")

    _validate_runtime_artifact(payload["runtime_artifact"])
    _validate_starter_models_container(payload["starter_models"])
    list_prompt_starter_models(payload)
    return payload


def list_prompt_starter_models(manifest: dict) -> list[StarterModelOption]:
    starter_models = manifest.get("starter_models")
    _validate_starter_models_container(starter_models)

    options: list[StarterModelOption] = []
    default_count = 0
    seen_prompt_orders: set[int] = set()
    for requested_model_id, starter_model in starter_models.items():
        validated_model_id = _validate_starter_model_entry(
            starter_model,
            requested_model_id=requested_model_id,
        )
        prompt_label = _validate_manifest_string_field(
            starter_model,
            "prompt_label",
            context=f"Starter model entry for {requested_model_id}",
        )
        prompt_order = starter_model.get("prompt_order")
        if not isinstance(prompt_order, int) or prompt_order < 1:
            raise ValueError(
                f"Starter model entry for {requested_model_id} field must be a positive integer: prompt_order"
            )
        if prompt_order in seen_prompt_orders:
            raise ValueError(f"Duplicate starter model prompt_order: {prompt_order}")
        seen_prompt_orders.add(prompt_order)
        recommended_default = starter_model.get("recommended_default")
        if not isinstance(recommended_default, bool):
            raise ValueError(
                f"Starter model entry for {requested_model_id} field must be a boolean: recommended_default"
            )
        default_count += int(recommended_default)
        options.append(
            StarterModelOption(
                model_id=validated_model_id,
                prompt_label=prompt_label,
                prompt_order=prompt_order,
                recommended_default=recommended_default,
            )
        )

    if default_count != 1:
        raise ValueError(
            "Runtime manifest starter_models must define exactly one recommended_default entry."
        )
    return sorted(options, key=lambda item: (item.prompt_order, item.model_id))


def resolve_requested_starter_model(manifest: dict, requested_model_id: str) -> dict:
    starter_models = manifest.get("starter_models")
    _validate_starter_models_container(starter_models)

    try:
        starter_model = starter_models[requested_model_id]
    except KeyError as exc:
        raise ValueError(f"Missing starter model entry for {requested_model_id}") from exc

    _validate_starter_model_entry(
        starter_model,
        requested_model_id=requested_model_id,
    )
    return starter_model


def _validate_runtime_artifact(runtime_artifact: dict) -> None:
    if not isinstance(runtime_artifact, dict):
        raise ValueError("Runtime artifact entry must be an object.")

    for key in ("id", "url", "sha256", "archive_type", "install_subdir"):
        _validate_manifest_string_field(
            runtime_artifact,
            key,
            context="Runtime artifact entry",
        )

    required_files = runtime_artifact.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        raise ValueError("Runtime artifact entry required_files must be a non-empty list.")
    for relative_path in required_files:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError(
                "Runtime artifact entry required_files must contain non-empty string paths."
            )

    required_file_sha256 = runtime_artifact.get("required_file_sha256")
    if not isinstance(required_file_sha256, dict):
        raise ValueError(
            "Runtime artifact entry required_file_sha256 must be an object."
        )
    for relative_path in required_files:
        if relative_path not in required_file_sha256:
            raise ValueError(
                f"Runtime artifact entry required_file_sha256 is missing required field: {relative_path}"
            )
        if (
            not isinstance(required_file_sha256[relative_path], str)
            or not required_file_sha256[relative_path].strip()
        ):
            raise ValueError(
                f"Runtime artifact entry required_file_sha256 has invalid value for: {relative_path}"
            )


def _validate_starter_models_container(starter_models: object) -> None:
    if not isinstance(starter_models, dict):
        raise ValueError("Runtime manifest starter_models entry must be an object.")


def _validate_starter_model_entry(
    starter_model: object,
    *,
    requested_model_id: str,
) -> str:
    if not isinstance(starter_model, dict):
        raise ValueError(
            f"Starter model entry for {requested_model_id} must be an object."
        )

    model_id = _validate_manifest_string_field(
        starter_model,
        "id",
        context=f"Starter model entry for {requested_model_id}",
    )
    if model_id != requested_model_id:
        raise ValueError(
            f"Starter model manifest key {requested_model_id} must match entry id {model_id}."
        )
    for key in ("url", "sha256", "target_filename", "install_subdir"):
        _validate_manifest_string_field(
            starter_model,
            key,
            context=f"Starter model entry for {requested_model_id}",
        )

    size_bytes = starter_model.get("size_bytes")
    if not isinstance(size_bytes, int) or size_bytes < 1:
        raise ValueError(
            f"Starter model entry for {requested_model_id} field must be a positive integer: size_bytes"
        )
    return model_id


def _validate_manifest_string_field(
    payload: dict,
    key: str,
    *,
    context: str,
) -> str:
    if key not in payload:
        raise ValueError(f"{context} is missing required field: {key}")
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} field must be a non-empty string: {key}")
    return value
