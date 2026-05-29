from pathlib import Path
import ssl
from urllib.error import URLError
import zipfile

import pytest

from local_ai_control_center_installer.downloads import (
    DownloadProgress,
    download_file,
    extract_archive,
    promote_tree,
    verify_required_file_checksums,
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


def test_verify_sha256_streams_file_instead_of_reading_all_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    artifact_path = tmp_path / "runtime.zip"
    artifact_path.write_bytes(b"runtime-payload")

    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda self: (_ for _ in ()).throw(AssertionError("read_bytes should not be used")),
    )

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


def test_verify_required_files_returns_false_when_expected_path_is_directory(
    tmp_path: Path,
):
    install_root = tmp_path / "llama.cpp"
    install_root.mkdir()
    (install_root / "llama-server.exe").mkdir()

    assert verify_required_files(install_root, ["llama-server.exe"]) is False


def test_verify_required_file_checksums_accepts_matching_manifest_pinned_hashes(
    tmp_path: Path,
):
    install_root = tmp_path / "llama.cpp"
    install_root.mkdir()
    (install_root / "llama-server.exe").write_text("ok", encoding="utf-8")

    assert verify_required_file_checksums(
        install_root,
        {
            "llama-server.exe": "2689367b205c16ce32ed4200942b8b8b1e262dfc70d9bc9fbc77c49699a4f1df"
        },
    ) is True


def test_verify_required_file_checksums_returns_false_for_hash_mismatch(tmp_path: Path):
    install_root = tmp_path / "llama.cpp"
    install_root.mkdir()
    (install_root / "llama-server.exe").write_text("tampered", encoding="utf-8")

    assert verify_required_file_checksums(
        install_root,
        {
            "llama-server.exe": "2689367b205c16ce32ed4200942b8b8b1e262dfc70d9bc9fbc77c49699a4f1df"
        },
    ) is False


def test_runtime_metadata_marker_round_trip(tmp_path: Path):
    metadata_path = tmp_path / "runtime-artifact.json"
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
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


def test_verify_runtime_metadata_returns_false_for_corrupt_json(tmp_path: Path):
    metadata_path = tmp_path / "runtime-artifact.json"
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    metadata_path.write_text("{not-json", encoding="utf-8")

    assert verify_runtime_metadata(
        metadata_path,
        artifact_id="windows-llama-cpp-runtime",
        source_sha256="abc123",
    ) is False


def test_verify_runtime_metadata_returns_false_for_undecodable_utf8_bytes(
    tmp_path: Path,
):
    metadata_path = tmp_path / "runtime-artifact.json"
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "llama-server.exe").write_text("ok", encoding="utf-8")
    metadata_path.write_bytes(b"\xff\xfe\x00\x80")

    assert verify_runtime_metadata(
        metadata_path,
        artifact_id="windows-llama-cpp-runtime",
        source_sha256="abc123",
    ) is False


def test_extract_archive_raises_for_unsupported_archive_type(tmp_path: Path):
    archive_path = tmp_path / "runtime.tar"
    archive_path.write_bytes(b"not-a-zip")

    with pytest.raises(ValueError, match="Unsupported archive type"):
        extract_archive(archive_path, tmp_path / "output", archive_type="tar")


def test_extract_archive_defaults_to_zip(tmp_path: Path):
    archive_path = tmp_path / "runtime.zip"
    destination_root = tmp_path / "output"
    source_file = tmp_path / "llama-server.exe"
    source_file.write_text("ready", encoding="utf-8")

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(source_file, arcname="runtime/llama-server.exe")

    extracted_root = extract_archive(archive_path, destination_root)

    assert extracted_root == destination_root
    assert (destination_root / "runtime" / "llama-server.exe").read_text(
        encoding="utf-8"
    ) == "ready"


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


def test_promote_tree_removes_nested_created_directories_when_first_replace_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    staging_root = tmp_path / "staging"
    final_root = tmp_path / "final"
    (staging_root / "runtime" / "llama.cpp").mkdir(parents=True)
    (staging_root / "runtime" / "llama.cpp" / "llama-server.exe").write_text(
        "new",
        encoding="utf-8",
    )

    def fail_on_first_promote(self: Path, target: Path) -> Path:
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_on_first_promote)

    with pytest.raises(OSError):
        promote_tree(staging_root, final_root)

    assert not (final_root / "runtime").exists()
    assert not final_root.exists()


def test_download_file_emits_streaming_progress_with_queue_position_and_eta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    captured: dict[str, object] = {}

    class FakeResponse:
        def __init__(self):
            self.headers = {"Content-Length": "6"}
            self._chunks = [b"abc", b"def"]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, amount: int) -> bytes:
            if self._chunks:
                return self._chunks.pop(0)
            return b""

    timestamps = iter([0.0, 1.0, 2.0, 3.0])
    events: list[DownloadProgress] = []

    monkeypatch.setattr(
        "local_ai_control_center_installer.downloads.urlopen",
        lambda url, timeout, context=None: captured.update(
            {"url": url, "timeout": timeout, "context": context}
        )
        or FakeResponse(),
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.downloads.time.monotonic",
        lambda: next(timestamps),
    )

    destination = download_file(
        "https://example.invalid/runtime.zip",
        tmp_path / "runtime.zip",
        progress_callback=events.append,
        plan_item={
            "key": "runtime-artifact",
            "label": "llama.cpp runtime",
            "queue_index": 1,
            "queue_total": 3,
            "size_bytes": 6,
        },
    )

    assert destination.read_bytes() == b"abcdef"
    assert events
    assert events[0] == DownloadProgress(
        key="runtime-artifact",
        label="llama.cpp runtime",
        current_index=1,
        total_items=3,
        bytes_downloaded=0,
        total_bytes=6,
        eta_seconds=None,
    )
    assert events[-1] == DownloadProgress(
        key="runtime-artifact",
        label="llama.cpp runtime",
        current_index=1,
        total_items=3,
        bytes_downloaded=6,
        total_bytes=6,
        eta_seconds=0.0,
    )
    assert captured["url"] == "https://example.invalid/runtime.zip"
    assert captured["timeout"] == 120.0
    assert captured["context"] is not None


def test_download_file_uses_certifi_backed_ssl_context_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    captured: dict[str, object] = {}

    class FakeResponse:
        def __init__(self):
            self.headers = {}
            self._chunks = [b"abc"]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, amount: int) -> bytes:
            if self._chunks:
                return self._chunks.pop(0)
            return b""

    ssl_context = object()

    class FakeCertifi:
        @staticmethod
        def where() -> str:
            return "C:/certifi/cacert.pem"

    monkeypatch.setattr("local_ai_control_center_installer.downloads.certifi", FakeCertifi)
    monkeypatch.setattr(
        "local_ai_control_center_installer.downloads.ssl.create_default_context",
        lambda cafile=None: captured.update({"cafile": cafile}) or ssl_context,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.downloads.urlopen",
        lambda url, timeout, context=None: captured.update(
            {"url": url, "timeout": timeout, "context": context}
        )
        or FakeResponse(),
    )

    destination = download_file(
        "https://example.invalid/runtime.zip",
        tmp_path / "runtime.zip",
    )

    assert destination.read_bytes() == b"abc"
    assert captured["cafile"] == "C:/certifi/cacert.pem"
    assert captured["context"] is ssl_context


def test_download_file_falls_back_to_windows_web_request_on_certificate_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    captured: dict[str, object] = {}

    def fake_urlopen(url, timeout, context=None):
        raise URLError(ssl.SSLCertVerificationError("boom"))

    def fake_windows_download(url: str, destination: Path) -> Path:
        captured["url"] = url
        captured["destination"] = destination
        destination.write_bytes(b"fallback-download")
        return destination

    monkeypatch.setattr("local_ai_control_center_installer.downloads.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "local_ai_control_center_installer.downloads._download_file_via_windows_web_request",
        fake_windows_download,
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.downloads._can_fallback_to_windows_web_request",
        lambda exc: True,
    )

    destination = download_file(
        "https://example.invalid/opencode.zip",
        tmp_path / "opencode.zip",
    )

    assert destination.read_bytes() == b"fallback-download"
    assert captured["url"] == "https://example.invalid/opencode.zip"
