import hashlib
import json
from json import JSONDecodeError
from pathlib import Path
import zipfile


def verify_sha256(path: Path, expected_sha256: str) -> bool:
    return _sha256_digest(path) == expected_sha256.lower()


def verify_required_files(root: Path, required_files: list[str]) -> bool:
    return all((root / relative_path).is_file() for relative_path in required_files)


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
    if root is not None and required_files is not None:
        payload["required_file_sha256"] = {
            relative_path: _sha256_digest(root / relative_path)
            for relative_path in required_files
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

    if root is None or required_files is None:
        return True

    required_file_sha256 = payload.get("required_file_sha256")
    if not isinstance(required_file_sha256, dict):
        return False

    try:
        return all(
            isinstance(required_file_sha256.get(relative_path), str)
            and _sha256_digest(root / relative_path)
            == required_file_sha256[relative_path].lower()
            for relative_path in required_files
        )
    except OSError:
        return False


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
