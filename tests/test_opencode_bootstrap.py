import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from local_ai_control_center_installer.opencode_bootstrap import (
    load_opencode_manifest,
)


def test_load_opencode_manifest_reads_pinned_contract(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://github.com/anomalyco/opencode/releases/download/v1.15.7/opencode-windows-x64.zip",
                    "sha256": "8ac96b52692a3daeb84a20295cc7ed43aa3c698078e802926a47aef83748eab2",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe"],
                    "required_file_sha256": {
                        "opencode.exe": "c18594c5368598f242387a2b6f505039a82b628c282101e99cb4452bd7622ed1"
                    },
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": ["--pure", "models"],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    manifest = load_opencode_manifest(manifest_path)

    assert manifest["opencode_artifact"] == {
        "id": "windows-opencode",
        "url": "https://github.com/anomalyco/opencode/releases/download/v1.15.7/opencode-windows-x64.zip",
        "sha256": "8ac96b52692a3daeb84a20295cc7ed43aa3c698078e802926a47aef83748eab2",
        "archive_type": "zip",
        "required_files": ["opencode.exe"],
        "required_file_sha256": {
            "opencode.exe": "c18594c5368598f242387a2b6f505039a82b628c282101e99cb4452bd7622ed1"
        },
        "install_subdir": "tools/opencode",
        "launch": {
            "executable_relative_path": "opencode.exe",
            "verification_args": ["--pure", "models"],
            "extra_env": {},
        },
    }


def test_load_opencode_manifest_uses_packaged_pinned_contract():
    manifest = load_opencode_manifest()

    assert manifest["opencode_artifact"] == {
        "id": "windows-opencode",
        "url": "https://github.com/anomalyco/opencode/releases/download/v1.15.7/opencode-windows-x64.zip",
        "sha256": "8ac96b52692a3daeb84a20295cc7ed43aa3c698078e802926a47aef83748eab2",
        "archive_type": "zip",
        "required_files": ["opencode.exe"],
        "required_file_sha256": {
            "opencode.exe": "c18594c5368598f242387a2b6f505039a82b628c282101e99cb4452bd7622ed1"
        },
        "install_subdir": "tools/opencode",
        "launch": {
            "executable_relative_path": "opencode.exe",
            "verification_args": ["--pure", "models"],
            "extra_env": {},
        },
    }


def test_load_opencode_manifest_rejects_non_object_json_root(tmp_path: Path):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text("123", encoding="utf-8")

    with pytest.raises(ValueError, match="top-level object"):
        load_opencode_manifest(manifest_path)


def test_load_opencode_manifest_rejects_checksum_key_missing_from_required_files(
    tmp_path: Path,
):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe"],
                    "required_file_sha256": {"other.exe": "def456"},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": ["--pure", "models"],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_file_sha256"):
        load_opencode_manifest(manifest_path)


def test_load_opencode_manifest_allows_presence_only_required_file_without_checksum(
    tmp_path: Path,
):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["opencode.exe", "support.dll"],
                    "required_file_sha256": {"opencode.exe": "def456"},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": ["--pure", "models"],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    manifest = load_opencode_manifest(manifest_path)

    assert manifest["opencode_artifact"]["required_files"] == [
        "opencode.exe",
        "support.dll",
    ]
    assert manifest["opencode_artifact"]["required_file_sha256"] == {
        "opencode.exe": "def456"
    }
    assert (
        manifest["opencode_artifact"]["launch"]["executable_relative_path"]
        == "opencode.exe"
    )


def test_load_opencode_manifest_rejects_launch_executable_missing_from_required_files(
    tmp_path: Path,
):
    manifest_path = tmp_path / "windows-stable-opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "opencode_artifact": {
                    "id": "windows-opencode",
                    "url": "https://example.invalid/opencode.zip",
                    "sha256": "abc123",
                    "archive_type": "zip",
                    "required_files": ["support.dll"],
                    "required_file_sha256": {},
                    "install_subdir": "tools/opencode",
                    "launch": {
                        "executable_relative_path": "opencode.exe",
                        "verification_args": ["--pure", "models"],
                        "extra_env": {},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="executable_relative_path"):
        load_opencode_manifest(manifest_path)


def test_built_wheel_contains_opencode_manifest_json(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    wheel_dir = tmp_path / "wheelhouse"
    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(wheel_dir)],
        check=True,
        cwd=repo_root,
        env=env,
    )

    wheel_path = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as wheel_archive:
        assert (
            "local_ai_control_center_installer/manifests/windows-stable-opencode.json"
            in wheel_archive.namelist()
        )
