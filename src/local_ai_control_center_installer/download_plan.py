from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .downloads import (
    verify_required_file_checksums,
    verify_required_files,
    verify_runtime_metadata,
    verify_sha256,
)
from .runtime_manifest import load_runtime_manifest, resolve_requested_starter_model
from .session import InstallerSession


RUNTIME_ARTIFACT_DOWNLOAD_KEY = "runtime-artifact"
OPENCODE_ARTIFACT_DOWNLOAD_KEY = "opencode-artifact"
TURBOQUANT_ARTIFACT_DOWNLOAD_KEY = "turboquant-artifact"


@dataclass(frozen=True)
class DownloadPlanItem:
    key: str
    label: str
    url: str
    destination_hint: str
    size_bytes: int | None
    queue_index: int | None = None
    queue_total: int | None = None


@dataclass(frozen=True)
class DownloadPlan:
    items: tuple[DownloadPlanItem, ...]


def build_download_plan(
    session: InstallerSession,
    *,
    load_runtime_manifest=load_runtime_manifest,
    load_opencode_manifest=None,
    resolve_turboquant_strategy=None,
    verify_model_file=verify_sha256,
) -> DownloadPlan:
    if load_opencode_manifest is None:
        from .opencode_bootstrap import load_opencode_manifest as _load_opencode_manifest

        load_opencode_manifest = _load_opencode_manifest
    if resolve_turboquant_strategy is None:
        from .turboquant import (
            resolve_packaged_windows_strategy as _resolve_packaged_windows_strategy,
        )

        resolve_turboquant_strategy = _resolve_packaged_windows_strategy

    if not isinstance(session.install_root, str) or not session.install_root.strip():
        return DownloadPlan(items=())

    install_root = Path(session.install_root).expanduser().resolve()
    runtime_manifest = load_runtime_manifest()
    starter_model = resolve_requested_starter_model(
        runtime_manifest, session.starter_model
    )
    runtime_artifact = runtime_manifest["runtime_artifact"]

    items: list[DownloadPlanItem] = []

    runtime_root = install_root / runtime_artifact["install_subdir"]
    runtime_metadata_path = runtime_root / "runtime-artifact.json"
    if not _runtime_artifact_ready(runtime_root, runtime_metadata_path, runtime_artifact):
        items.append(
            DownloadPlanItem(
                key=RUNTIME_ARTIFACT_DOWNLOAD_KEY,
                label="llama.cpp runtime",
                url=runtime_artifact["url"],
                destination_hint=runtime_artifact["install_subdir"],
                size_bytes=None,
            )
        )

    starter_model_path = (
        install_root
        / starter_model["install_subdir"]
        / starter_model["target_filename"]
    )
    if not starter_model_path.exists() or not verify_model_file(
        starter_model_path, starter_model["sha256"]
    ):
        prompt_label = starter_model.get("prompt_label")
        if not isinstance(prompt_label, str) or not prompt_label.strip():
            prompt_label = starter_model["id"]
        items.append(
            DownloadPlanItem(
                key=starter_model_download_key(starter_model["id"]),
                label=f"starter model {prompt_label.strip()}",
                url=starter_model["url"],
                destination_hint=(
                    f"{starter_model['install_subdir']}/"
                    f"{starter_model['target_filename']}"
                ),
                size_bytes=starter_model.get("size_bytes"),
            )
        )

    if session.install_opencode:
        opencode_manifest = load_opencode_manifest()
        opencode_artifact = opencode_manifest["opencode_artifact"]
        opencode_root = install_root / opencode_artifact["install_subdir"]
        opencode_metadata_path = opencode_root / "opencode-artifact.json"
        if not _opencode_artifact_ready(
            opencode_root,
            opencode_metadata_path,
            opencode_artifact,
        ):
            items.append(
                DownloadPlanItem(
                    key=OPENCODE_ARTIFACT_DOWNLOAD_KEY,
                    label="OpenCode",
                    url=opencode_artifact["url"],
                    destination_hint=opencode_artifact["install_subdir"],
                    size_bytes=None,
                )
            )

    if session.attempt_turboquant:
        try:
            turboquant_strategy = resolve_turboquant_strategy()
        except (OSError, ValueError):
            turboquant_strategy = None
        if isinstance(turboquant_strategy, Mapping):
            turboquant_artifact = turboquant_strategy.get("artifact")
            if isinstance(turboquant_artifact, dict):
                turboquant_root = install_root / turboquant_artifact["install_subdir"]
                turboquant_metadata_path = (
                    turboquant_root / "turboquant-artifact.json"
                )
                if not _turboquant_artifact_ready(
                    turboquant_root,
                    turboquant_metadata_path,
                    turboquant_artifact,
                ):
                    items.append(
                        DownloadPlanItem(
                            key=TURBOQUANT_ARTIFACT_DOWNLOAD_KEY,
                            label="TurboQuant",
                            url=turboquant_artifact["url"],
                            destination_hint=turboquant_artifact["install_subdir"],
                            size_bytes=_coerce_optional_int(
                                turboquant_artifact.get("size_bytes")
                            ),
                        )
                    )

    total = len(items)
    normalized_items = tuple(
        DownloadPlanItem(
            key=item.key,
            label=item.label,
            url=item.url,
            destination_hint=item.destination_hint,
            size_bytes=item.size_bytes,
            queue_index=index,
            queue_total=total,
        )
        for index, item in enumerate(items, start=1)
    )
    return DownloadPlan(items=normalized_items)


def coerce_download_plan(plan: DownloadPlan | Mapping[str, object] | None) -> DownloadPlan | None:
    if plan is None:
        return None
    if isinstance(plan, DownloadPlan):
        return plan
    if not isinstance(plan, Mapping):
        return None

    raw_items = plan.get("items", ())
    if not isinstance(raw_items, list | tuple):
        return None

    items: list[DownloadPlanItem] = []
    for raw_item in raw_items:
        if isinstance(raw_item, DownloadPlanItem):
            items.append(raw_item)
            continue
        if not isinstance(raw_item, Mapping):
            return None
        items.append(
            DownloadPlanItem(
                key=str(raw_item["key"]),
                label=str(raw_item["label"]),
                url=str(raw_item["url"]),
                destination_hint=str(raw_item["destination_hint"]),
                size_bytes=_coerce_optional_int(raw_item.get("size_bytes")),
                queue_index=_coerce_optional_int(raw_item.get("queue_index")),
                queue_total=_coerce_optional_int(raw_item.get("queue_total")),
            )
        )
    return DownloadPlan(items=tuple(items))


def find_download_plan_item(
    plan: DownloadPlan | Mapping[str, object] | None,
    key: str,
) -> DownloadPlanItem | None:
    normalized_plan = coerce_download_plan(plan)
    if normalized_plan is None:
        return None
    for item in normalized_plan.items:
        if item.key == key:
            return item
    return None


def starter_model_download_key(model_id: str) -> str:
    return f"starter-model:{model_id}"


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _runtime_artifact_ready(
    runtime_root: Path,
    metadata_path: Path,
    runtime_artifact: dict,
) -> bool:
    return verify_required_files(
        runtime_root, runtime_artifact["required_files"]
    ) and verify_required_file_checksums(
        runtime_root, runtime_artifact["required_file_sha256"]
    ) and verify_runtime_metadata(
        metadata_path,
        artifact_id=runtime_artifact["id"],
        source_sha256=runtime_artifact["sha256"],
    )


def _opencode_artifact_ready(
    opencode_root: Path,
    metadata_path: Path,
    opencode_artifact: dict,
) -> bool:
    return verify_required_files(
        opencode_root, opencode_artifact["required_files"]
    ) and verify_required_file_checksums(
        opencode_root, opencode_artifact["required_file_sha256"]
    ) and verify_runtime_metadata(
        metadata_path,
        artifact_id=opencode_artifact["id"],
        source_sha256=opencode_artifact["sha256"],
    )


def _turboquant_artifact_ready(
    turboquant_root: Path,
    metadata_path: Path,
    turboquant_artifact: dict,
) -> bool:
    return verify_required_files(
        turboquant_root, turboquant_artifact["required_files"]
    ) and verify_required_file_checksums(
        turboquant_root, turboquant_artifact["required_file_sha256"]
    ) and verify_runtime_metadata(
        metadata_path,
        artifact_id=turboquant_artifact["id"],
        source_sha256=turboquant_artifact["sha256"],
    )
