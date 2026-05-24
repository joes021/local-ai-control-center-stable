import json
from pathlib import Path

from local_ai_control_center_installer.download_plan import build_download_plan
from local_ai_control_center_installer.opencode_bootstrap import load_opencode_manifest
from local_ai_control_center_installer.session import InstallerSession


PINNED_OK_RUNTIME_SHA256 = (
    "2689367b205c16ce32ed4200942b8b8b1e262dfc70d9bc9fbc77c49699a4f1df"
)


def _runtime_manifest() -> dict:
    return {
        "runtime_artifact": {
            "id": "windows-llama-cpp-runtime",
            "url": "https://example.invalid/runtime.zip",
            "sha256": "runtime-sha",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {"llama-server.exe": PINNED_OK_RUNTIME_SHA256},
            "install_subdir": "runtime/llama.cpp",
        },
        "starter_models": {
            "recommended-12gb": {
                "id": "recommended-12gb",
                "url": "https://example.invalid/model.gguf",
                "sha256": "model-sha",
                "target_filename": "recommended-12gb.gguf",
                "install_subdir": "models/recommended-12gb",
                "size_bytes": 123,
                "prompt_order": 2,
                "prompt_label": "12 GB",
                "recommended_default": True,
            }
        },
    }


def _opencode_manifest() -> dict:
    return {
        "opencode_artifact": {
            "id": "windows-opencode",
            "url": "https://example.invalid/opencode.zip",
            "sha256": "opencode-sha",
            "archive_type": "zip",
            "required_files": ["opencode.exe"],
            "required_file_sha256": {"opencode.exe": "2689367b205c16ce32ed4200942b8b8b1e262dfc70d9bc9fbc77c49699a4f1df"},
            "install_subdir": "tools/opencode",
            "launch": {
                "executable_relative_path": "opencode.exe",
                "verification_args": ["--pure", "run", "--format", "json", "--model"],
                "extra_env": {},
            },
        }
    }


def test_load_opencode_manifest_selects_packaged_ubuntu_x64_resource_for_linux_x64():
    manifest = load_opencode_manifest(
        platform_system=lambda: "Linux",
        platform_machine=lambda: "x86_64",
    )

    artifact = manifest["opencode_artifact"]
    assert artifact["id"] == "ubuntu-x64-opencode"
    assert (
        artifact["url"]
        == "https://github.com/anomalyco/opencode/releases/download/v1.15.7/opencode-linux-x64.tar.gz"
    )
    assert artifact["archive_type"] == "tar.gz"
    assert artifact["required_files"] == ["opencode"]
    assert artifact["launch"]["executable_relative_path"] == "opencode"
    assert (
        artifact["required_file_sha256"]["opencode"]
        == "618fceb27432af2ea399f3ba660138c593c31b62a812b9aca63cbaabd136575d"
    )


def _turboquant_strategy() -> dict:
    return {
        "artifact": {
            "id": "windows-turboquant-cuda12.4",
            "url": "https://example.invalid/turboquant.zip",
            "sha256": "turboquant-sha",
            "archive_type": "zip",
            "required_files": ["llama-server.exe"],
            "required_file_sha256": {
                "llama-server.exe": PINNED_OK_RUNTIME_SHA256,
            },
            "install_subdir": "tools/turboquant/windows-x64-cuda12.4",
            "size_bytes": 456,
        },
        "executable_relative_path": "llama-server.exe",
    }


def test_build_download_plan_lists_runtime_model_and_opencode_before_downloads(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-12gb",
        install_opencode=True,
    )

    plan = build_download_plan(
        session,
        load_runtime_manifest=lambda: _runtime_manifest(),
        load_opencode_manifest=lambda: _opencode_manifest(),
    )

    assert [item.label for item in plan.items] == [
        "llama.cpp runtime",
        "starter model 12 GB",
        "OpenCode",
    ]


def test_build_download_plan_skips_opencode_when_not_requested(tmp_path: Path):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-12gb",
        install_opencode=False,
    )

    plan = build_download_plan(
        session,
        load_runtime_manifest=lambda: _runtime_manifest(),
        load_opencode_manifest=lambda: _opencode_manifest(),
    )

    assert [item.label for item in plan.items] == [
        "llama.cpp runtime",
        "starter model 12 GB",
    ]


def test_build_download_plan_includes_turboquant_when_requested_and_supported(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-12gb",
        install_opencode=False,
        attempt_turboquant=True,
    )

    plan = build_download_plan(
        session,
        load_runtime_manifest=lambda: _runtime_manifest(),
        load_opencode_manifest=lambda: _opencode_manifest(),
        resolve_turboquant_strategy=lambda: _turboquant_strategy(),
    )

    assert [item.label for item in plan.items] == [
        "llama.cpp runtime",
        "starter model 12 GB",
        "TurboQuant",
    ]


def test_build_download_plan_skips_turboquant_when_requested_but_unsupported(
    tmp_path: Path,
):
    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(tmp_path / "install-root"),
        starter_model="recommended-12gb",
        install_opencode=False,
        attempt_turboquant=True,
    )

    plan = build_download_plan(
        session,
        load_runtime_manifest=lambda: _runtime_manifest(),
        load_opencode_manifest=lambda: _opencode_manifest(),
        resolve_turboquant_strategy=lambda: None,
    )

    assert [item.label for item in plan.items] == [
        "llama.cpp runtime",
        "starter model 12 GB",
    ]


def test_build_download_plan_skips_starter_model_when_already_present(tmp_path: Path):
    install_root = tmp_path / "install-root"
    model_root = install_root / "models" / "recommended-12gb"
    model_root.mkdir(parents=True)
    (model_root / "recommended-12gb.gguf").write_text("model", encoding="utf-8")

    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-12gb",
        install_opencode=True,
    )

    plan = build_download_plan(
        session,
        load_runtime_manifest=lambda: _runtime_manifest(),
        load_opencode_manifest=lambda: _opencode_manifest(),
        verify_model_file=lambda path, expected_sha256: True,
    )

    assert [item.label for item in plan.items] == [
        "llama.cpp runtime",
        "OpenCode",
    ]


def test_build_download_plan_keeps_runtime_item_when_installed_runtime_was_tampered(
    tmp_path: Path,
):
    install_root = tmp_path / "install-root"
    runtime_root = install_root / "runtime" / "llama.cpp"
    runtime_root.mkdir(parents=True)
    (runtime_root / "llama-server.exe").write_text("tampered", encoding="utf-8")
    (runtime_root / "runtime-artifact.json").write_text(
        json.dumps(
            {
                "artifact_id": "windows-llama-cpp-runtime",
                "source_sha256": "runtime-sha",
            }
        ),
        encoding="utf-8",
    )

    session = InstallerSession(
        bootstrap_status="ready",
        install_root=str(install_root),
        starter_model="recommended-12gb",
        install_opencode=False,
    )

    plan = build_download_plan(
        session,
        load_runtime_manifest=lambda: _runtime_manifest(),
        load_opencode_manifest=lambda: _opencode_manifest(),
    )

    assert [item.label for item in plan.items] == [
        "llama.cpp runtime",
        "starter model 12 GB",
    ]
