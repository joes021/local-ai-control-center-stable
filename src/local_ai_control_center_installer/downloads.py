import hashlib
import json
from pathlib import Path
import zipfile


def verify_sha256(path: Path, expected_sha256: str) -> bool:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == expected_sha256.lower()


def verify_required_files(root: Path, required_files: list[str]) -> bool:
    return all((root / relative_path).exists() for relative_path in required_files)


def write_runtime_metadata(
    metadata_path: Path,
    *,
    artifact_id: str,
    source_sha256: str,
) -> Path:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "artifact_id": artifact_id,
                "source_sha256": source_sha256,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return metadata_path


def verify_runtime_metadata(
    metadata_path: Path,
    *,
    artifact_id: str,
    source_sha256: str,
) -> bool:
    if not metadata_path.exists():
        return False

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    return (
        payload.get("artifact_id") == artifact_id
        and payload.get("source_sha256") == source_sha256
    )


def extract_archive(
    archive_path: Path,
    destination_root: Path,
    *,
    archive_type: str,
) -> Path:
    if archive_type != "zip":
        raise ValueError(f"Unsupported archive type: {archive_type}")

    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination_root)

    return destination_root


def promote_tree(staging_root: Path, final_root: Path) -> None:
    promotion_records: list[dict[str, Path | bool]] = []
    created_directories: list[Path] = []
    staged_files = sorted(path for path in staging_root.rglob("*") if path.is_file())

    try:
        for staged_file in staged_files:
            relative_path = staged_file.relative_to(staging_root)
            final_path = final_root / relative_path
            parent_directory = final_path.parent

            if not parent_directory.exists():
                parent_directory.mkdir(parents=True, exist_ok=True)
                created_directories.append(parent_directory)

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
