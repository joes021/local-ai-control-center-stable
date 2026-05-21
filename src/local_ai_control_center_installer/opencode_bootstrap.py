import json
from importlib.resources import files


def load_opencode_manifest(manifest_path=None) -> dict:
    if manifest_path is None:
        manifest_path = files("local_ai_control_center_installer.manifests").joinpath(
            "windows-stable-opencode.json"
        )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "opencode_artifact" not in payload:
        raise ValueError("OpenCode manifest is missing required top-level fields.")

    _validate_opencode_artifact(payload["opencode_artifact"])
    return payload


def _validate_opencode_artifact(opencode_artifact: dict) -> None:
    if not isinstance(opencode_artifact, dict):
        raise ValueError("OpenCode artifact entry must be an object.")

    for key in ("id", "url", "sha256", "archive_type", "install_subdir"):
        _validate_manifest_string_field(
            opencode_artifact,
            key,
            context="OpenCode artifact entry",
        )

    required_files = opencode_artifact.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        raise ValueError(
            "OpenCode artifact entry required_files must be a non-empty list."
        )
    for relative_path in required_files:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError(
                "OpenCode artifact entry required_files must contain non-empty string paths."
            )

    required_file_sha256 = opencode_artifact.get("required_file_sha256")
    if not isinstance(required_file_sha256, dict):
        raise ValueError(
            "OpenCode artifact entry required_file_sha256 must be an object."
        )
    for relative_path, checksum in required_file_sha256.items():
        if relative_path not in required_files:
            raise ValueError(
                "OpenCode artifact entry required_file_sha256 contains an unknown required file."
            )
        if not isinstance(checksum, str) or not checksum.strip():
            raise ValueError(
                f"OpenCode artifact entry required_file_sha256 has invalid value for: {relative_path}"
            )

    launch = opencode_artifact.get("launch")
    if not isinstance(launch, dict):
        raise ValueError("OpenCode artifact entry launch must be an object.")
    _validate_manifest_string_field(
        launch,
        "executable_relative_path",
        context="OpenCode artifact launch entry",
    )
    executable_relative_path = launch["executable_relative_path"]
    if executable_relative_path not in required_files:
        raise ValueError(
            "OpenCode artifact launch entry executable_relative_path must be listed in required_files."
        )

    verification_args = launch.get("verification_args")
    if verification_args != ["--pure", "models"]:
        raise ValueError(
            "OpenCode artifact launch entry verification_args must equal ['--pure', 'models']."
        )

    extra_env = launch.get("extra_env")
    if not isinstance(extra_env, dict):
        raise ValueError("OpenCode artifact launch entry extra_env must be an object.")


def _validate_manifest_string_field(
    payload: dict,
    key: str,
    *,
    context: str,
) -> None:
    if key not in payload:
        raise ValueError(f"{context} is missing required field: {key}")

    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} field must be a non-empty string: {key}")
