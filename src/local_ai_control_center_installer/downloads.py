from dataclasses import dataclass
import hashlib
import json
from json import JSONDecodeError
from pathlib import Path
import time
from urllib.request import urlopen
import zipfile


@dataclass(frozen=True)
class DownloadProgress:
    key: str | None
    label: str | None
    current_index: int | None
    total_items: int | None
    bytes_downloaded: int
    total_bytes: int | None
    eta_seconds: float | None


def verify_sha256(path: Path, expected_sha256: str) -> bool:
    return _sha256_digest(path) == expected_sha256.lower()


def verify_required_files(root: Path, required_files: list[str]) -> bool:
    return all((root / relative_path).is_file() for relative_path in required_files)


def verify_required_file_checksums(
    root: Path,
    required_file_sha256: dict[str, str],
) -> bool:
    try:
        return all(
            isinstance(expected_sha256, str)
            and _sha256_digest(root / relative_path) == expected_sha256.lower()
            for relative_path, expected_sha256 in required_file_sha256.items()
        )
    except OSError:
        return False


def write_runtime_metadata(
    metadata_path: Path,
    *,
    artifact_id: str,
    source_sha256: str,
    root: Path | None = None,
    required_files: list[str] | None = None,
) -> Path:
    payload = {
        "artifact_id": artifact_id,
        "source_sha256": source_sha256,
    }

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return metadata_path


def verify_runtime_metadata(
    metadata_path: Path,
    *,
    artifact_id: str,
    source_sha256: str,
    root: Path | None = None,
    required_files: list[str] | None = None,
) -> bool:
    if not metadata_path.exists():
        return False

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (JSONDecodeError, OSError, UnicodeDecodeError):
        return False

    if not isinstance(payload, dict):
        return False

    if (
        payload.get("artifact_id") != artifact_id
        or payload.get("source_sha256") != source_sha256
    ):
        return False

    return True


def _sha256_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_archive(
    archive_path: Path,
    destination_root: Path,
    *,
    archive_type: str = "zip",
) -> Path:
    if archive_type != "zip":
        raise ValueError(f"Unsupported archive type: {archive_type}")

    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination_root)

    return destination_root


def promote_tree(staging_root: Path, final_root: Path) -> None:
    promotion_records: list[dict[str, Path | bool]] = []
    created_directories: list[Path] = []
    created_directory_paths: set[Path] = set()
    staged_files = sorted(path for path in staging_root.rglob("*") if path.is_file())

    try:
        for staged_file in staged_files:
            relative_path = staged_file.relative_to(staging_root)
            final_path = final_root / relative_path
            parent_directory = final_path.parent

            if not parent_directory.exists():
                missing_directories: list[Path] = []
                current_directory = parent_directory
                while not current_directory.exists():
                    missing_directories.append(current_directory)
                    current_directory = current_directory.parent
                parent_directory.mkdir(parents=True, exist_ok=True)
                for directory in reversed(missing_directories):
                    if directory not in created_directory_paths:
                        created_directory_paths.add(directory)
                        created_directories.append(directory)

            backup_path = staging_root / ".backups" / relative_path
            record: dict[str, Path | bool] = {
                "final_path": final_path,
                "backup_path": backup_path,
                "had_existing_target": final_path.exists(),
                "backup_created": False,
                "promoted": False,
            }
            promotion_records.append(record)

            if record["had_existing_target"]:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                final_path.replace(backup_path)
                record["backup_created"] = True

            staged_file.replace(final_path)
            record["promoted"] = True
    except OSError:
        for record in reversed(promotion_records):
            final_path = record["final_path"]
            backup_path = record["backup_path"]

            if record["promoted"]:
                try:
                    final_path.unlink()
                except FileNotFoundError:
                    pass

            if record["backup_created"]:
                backup_path.replace(final_path)

        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass

        raise


def download_file(
    url: str,
    destination: Path,
    *,
    progress_callback=None,
    plan_item=None,
    chunk_size: int = 64 * 1024,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = _resolve_total_bytes(plan_item)
    start_time = time.monotonic()
    bytes_downloaded = 0

    with urlopen(url) as response:
        header_length = response.headers.get("Content-Length")
        if total_bytes is None and isinstance(header_length, str) and header_length.isdigit():
            total_bytes = int(header_length)

        with destination.open("wb") as handle:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
                bytes_downloaded += len(chunk)
                _emit_download_progress(
                    progress_callback,
                    plan_item,
                    bytes_downloaded=bytes_downloaded,
                    total_bytes=total_bytes,
                    start_time=start_time,
                )

    if bytes_downloaded == 0:
        _emit_download_progress(
            progress_callback,
            plan_item,
            bytes_downloaded=0,
            total_bytes=total_bytes,
            start_time=start_time,
        )

    return destination


def _emit_download_progress(
    progress_callback,
    plan_item,
    *,
    bytes_downloaded: int,
    total_bytes: int | None,
    start_time: float,
) -> None:
    if progress_callback is None:
        return
    current_time = time.monotonic()
    elapsed = max(current_time - start_time, 0.0)
    eta_seconds = None
    if total_bytes is not None:
        remaining_bytes = max(total_bytes - bytes_downloaded, 0)
        if remaining_bytes == 0:
            eta_seconds = 0.0
        elif elapsed > 0 and bytes_downloaded > 0:
            bytes_per_second = bytes_downloaded / elapsed
            if bytes_per_second > 0:
                eta_seconds = remaining_bytes / bytes_per_second
    progress_callback(
        DownloadProgress(
            key=_resolve_plan_item_value(plan_item, "key"),
            label=_resolve_plan_item_value(plan_item, "label"),
            current_index=_resolve_optional_int(plan_item, "queue_index"),
            total_items=_resolve_optional_int(plan_item, "queue_total"),
            bytes_downloaded=bytes_downloaded,
            total_bytes=total_bytes,
            eta_seconds=eta_seconds,
        )
    )


def _resolve_total_bytes(plan_item) -> int | None:
    if plan_item is None:
        return None
    if hasattr(plan_item, "size_bytes"):
        value = getattr(plan_item, "size_bytes")
    elif isinstance(plan_item, dict):
        value = plan_item.get("size_bytes")
    else:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _resolve_plan_item_value(plan_item, key: str) -> str | None:
    if plan_item is None:
        return None
    if hasattr(plan_item, key):
        value = getattr(plan_item, key)
    elif isinstance(plan_item, dict):
        value = plan_item.get(key)
    else:
        return None
    if not isinstance(value, str) or not value:
        return None
    return value


def _resolve_optional_int(plan_item, key: str) -> int | None:
    if plan_item is None:
        return None
    if hasattr(plan_item, key):
        value = getattr(plan_item, key)
    elif isinstance(plan_item, dict):
        value = plan_item.get(key)
    else:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
