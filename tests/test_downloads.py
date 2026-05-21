from pathlib import Path

import pytest

from local_ai_control_center_installer.downloads import (
    extract_archive,
    promote_tree,
    verify_required_files,
    verify_runtime_metadata,
    verify_sha256,
    write_runtime_metadata,
)


def test_verify_sha256_accepts_matching_digest(tmp_path: Path):
    artifact_path = tmp_path / "runtime.zip"
    artifact_path.write_bytes(b"runtime-payload")

    assert verify_sha256(
        artifact_path,
        "84dd393eb57d462b8b3ba6c2c76b6b79a77f38fddc79399a8271650b9241d48d",
    ) is True


def test_verify_required_files_returns_false_when_expected_file_is_missing(tmp_path: Path):
    install_root = tmp_path / "llama.cpp"
    install_root.mkdir()
    (install_root / "llama-server.exe").write_text("ok", encoding="utf-8")

    assert verify_required_files(
        install_root,
        ["llama-server.exe", "ggml-base.dll"],
    ) is False


def test_runtime_metadata_marker_round_trip(tmp_path: Path):
    metadata_path = tmp_path / "runtime-artifact.json"
    write_runtime_metadata(
        metadata_path,
        artifact_id="windows-llama-cpp-runtime",
        source_sha256="abc123",
    )

    assert verify_runtime_metadata(
        metadata_path,
        artifact_id="windows-llama-cpp-runtime",
        source_sha256="abc123",
    ) is True


def test_extract_archive_raises_for_unsupported_archive_type(tmp_path: Path):
    archive_path = tmp_path / "runtime.tar"
    archive_path.write_bytes(b"not-a-zip")

    with pytest.raises(ValueError, match="Unsupported archive type"):
        extract_archive(archive_path, tmp_path / "output", archive_type="tar")


def test_promote_tree_restores_preexisting_file_when_second_replace_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    staging_root = tmp_path / "staging"
    final_root = tmp_path / "final"
    (staging_root / "logs").mkdir(parents=True)
    (staging_root / "config").mkdir(parents=True)
    (staging_root / "logs" / "install.log").write_text("new", encoding="utf-8")
    (staging_root / "config" / "runtime-artifact.json").write_text("new", encoding="utf-8")
    (final_root / "logs").mkdir(parents=True)
    (final_root / "logs" / "install.log").write_text("old", encoding="utf-8")

    original_replace = Path.replace

    def fail_on_second_promote(self: Path, target: Path) -> Path:
        if target == final_root / "config" / "runtime-artifact.json":
            raise OSError("replace failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_on_second_promote)

    with pytest.raises(OSError):
        promote_tree(staging_root, final_root)

    assert (final_root / "logs" / "install.log").read_text(encoding="utf-8") == "old"
