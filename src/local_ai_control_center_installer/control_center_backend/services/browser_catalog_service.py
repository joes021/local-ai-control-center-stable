from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.browser_sources import (
    fetch_source_catalog,
)
from local_ai_control_center_installer.control_center_backend.services.models_service import (
    load_models_payload,
)


def load_catalog_payload(
    *,
    cache_path: Path | None = None,
    config: ControlCenterConfig | None = None,
    source: str = "all",
    search: str = "",
    family: str = "all",
    quant: str = "all",
    size: str = "all",
    mtp: str = "all",
    date: str = "all",
    sort: str = "updated-desc",
    limit: int | None = None,
    now_iso: str | None = None,
) -> dict[str, object]:
    resolved_config = config if config is not None else (get_config() if cache_path is None else None)
    resolved_cache_path = _resolve_cache_path(cache_path=cache_path, config=resolved_config)
    cache = _read_cache(resolved_cache_path)
    all_models = [item for item in cache.get("models", []) if isinstance(item, dict)]
    models = _apply_filters(
        all_models,
        source=source,
        search=search,
        family=family,
        quant=quant,
        size=size,
        mtp=mtp,
        date=date,
        now_iso=now_iso,
    )
    models = _annotate_local_catalog_state(models, config=resolved_config)
    models = _sort_models(models, sort=sort)
    if limit is not None and limit > 0:
        models = models[:limit]
    refresh = _normalize_refresh(cache.get("refresh"), all_models)
    return {"models": models, "refresh": refresh}


def refresh_catalog(
    *,
    source: str = "all",
    cache_path: Path | None = None,
    config: ControlCenterConfig | None = None,
    fetch_source_catalog: Callable[[str], dict[str, object]] = fetch_source_catalog,
    now_iso: str | None = None,
) -> dict[str, object]:
    resolved_cache_path = _resolve_cache_path(cache_path=cache_path, config=config)
    cache = _read_cache(resolved_cache_path)
    current_models = [item for item in cache.get("models", []) if isinstance(item, dict)]
    now = now_iso or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    normalized_source = (source or "all").strip().lower()

    if normalized_source == "all":
        fetched_hf = fetch_source_catalog("huggingface")
        fetched_unsloth = fetch_source_catalog("unsloth")
        incoming_models = _gguf_only((fetched_hf.get("models") or []) + (fetched_unsloth.get("models") or []))
        merged_models = _merge_replaced_sources(current_models, incoming_models, {"huggingface", "unsloth"})
        refresh_sources = {
            "huggingface": _build_source_refresh("huggingface", incoming_models, fetched_hf, now),
            "unsloth": _build_source_refresh("unsloth", incoming_models, fetched_unsloth, now),
        }
    else:
        fetched = fetch_source_catalog(normalized_source)
        incoming_models = _gguf_only(fetched.get("models") or [])
        merged_models = _merge_replaced_sources(current_models, incoming_models, {normalized_source})
        existing_sources = cache.get("refresh", {}).get("sources", {}) if isinstance(cache.get("refresh"), dict) else {}
        refresh_sources = {key: value for key, value in existing_sources.items() if isinstance(value, dict)}
        refresh_sources[normalized_source] = _build_source_refresh(normalized_source, incoming_models, fetched, now)

    payload = {
        "models": sorted(merged_models, key=lambda item: str(item.get("lastUpdated", "") or ""), reverse=True),
        "refresh": {
            "lastRefresh": now,
            "sources": refresh_sources,
        },
    }
    _write_cache(resolved_cache_path, payload)
    return load_catalog_payload(cache_path=resolved_cache_path)


def update_model_fit_status(
    model_id: str,
    fit_payload: dict[str, object],
    *,
    cache_path: Path | None = None,
    config: ControlCenterConfig | None = None,
) -> None:
    resolved_cache_path = _resolve_cache_path(cache_path=cache_path, config=config)
    cache = _read_cache(resolved_cache_path)
    models = [item for item in cache.get("models", []) if isinstance(item, dict)]
    updated = []
    for item in models:
        if str(item.get("id")) == model_id:
            clone = dict(item)
            clone["fit"] = fit_payload
            updated.append(clone)
        else:
            updated.append(item)
    cache["models"] = updated
    _write_cache(resolved_cache_path, cache)


def get_catalog_model(
    model_id: str,
    *,
    cache_path: Path | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, object] | None:
    payload = load_catalog_payload(cache_path=cache_path, config=config)
    for item in payload["models"]:
        if str(item.get("id")) == model_id:
            return item
    return None


def _resolve_cache_path(
    *,
    cache_path: Path | None,
    config: ControlCenterConfig | None,
) -> Path:
    if cache_path is not None:
        return cache_path
    config = config or get_config()
    return config.browser_catalog_cache_path


def _read_cache(cache_path: Path) -> dict[str, object]:
    if not cache_path.exists():
        return {"models": [], "refresh": {"lastRefresh": "", "sources": {}}}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {"models": [], "refresh": {"lastRefresh": "", "sources": {}}}
    return payload if isinstance(payload, dict) else {"models": [], "refresh": {"lastRefresh": "", "sources": {}}}


def _write_cache(cache_path: Path, payload: dict[str, object]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _gguf_only(models: list[object]) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename", "") or "")
        if not filename.lower().endswith(".gguf"):
            continue
        filtered.append(item)
    return filtered


def _merge_replaced_sources(
    current_models: list[dict[str, object]],
    incoming_models: list[dict[str, object]],
    replaced_sources: set[str],
) -> list[dict[str, object]]:
    keep = [item for item in current_models if str(item.get("source")) not in replaced_sources]
    indexed_existing = {str(item.get("id")): item for item in current_models}
    merged = keep[:]
    for item in incoming_models:
        existing = indexed_existing.get(str(item.get("id")))
        if existing and isinstance(existing.get("fit"), dict):
            clone = dict(item)
            clone["fit"] = existing["fit"]
            merged.append(clone)
        else:
            merged.append(item)
    return merged


def _build_source_refresh(
    source: str,
    models: list[dict[str, object]],
    fetched: dict[str, object],
    now: str,
) -> dict[str, object]:
    filtered = [item for item in models if str(item.get("source")) == source]
    return {
        "lastRefresh": now,
        "count": len(filtered),
        "errors": [str(item) for item in (fetched.get("errors") or [])],
        "warnings": [str(item) for item in (fetched.get("warnings") or [])],
    }


def _normalize_refresh(raw_refresh: object, models: list[dict[str, object]]) -> dict[str, object]:
    refresh = raw_refresh if isinstance(raw_refresh, dict) else {}
    sources = refresh.get("sources") if isinstance(refresh.get("sources"), dict) else {}
    counts = {
        "all": len(models),
        "huggingface": len([item for item in models if str(item.get("source")) == "huggingface"]),
        "unsloth": len([item for item in models if str(item.get("source")) == "unsloth"]),
    }
    warnings: list[str] = []
    errors: list[str] = []
    normalized_sources: dict[str, dict[str, object]] = {}
    for source_name in ("huggingface", "unsloth"):
        raw_source = sources.get(source_name) if isinstance(sources, dict) else {}
        source_refresh = raw_source if isinstance(raw_source, dict) else {}
        source_warnings = [str(item) for item in source_refresh.get("warnings", [])]
        source_errors = [str(item) for item in source_refresh.get("errors", [])]
        warnings.extend(source_warnings)
        errors.extend(source_errors)
        normalized_sources[source_name] = {
            "lastRefresh": str(source_refresh.get("lastRefresh", "") or ""),
            "count": int(source_refresh.get("count", counts[source_name]) or counts[source_name]),
            "errors": source_errors,
            "warnings": source_warnings,
        }
    return {
        "lastRefresh": str(refresh.get("lastRefresh", "") or ""),
        "counts": counts,
        "warnings": warnings,
        "errors": errors,
        "sources": normalized_sources,
    }


def _apply_filters(
    models: list[dict[str, object]],
    *,
    source: str,
    search: str,
    family: str,
    quant: str,
    size: str,
    mtp: str,
    date: str,
    now_iso: str | None,
) -> list[dict[str, object]]:
    normalized_source = _normalize_choice(source)
    normalized_family = family.strip()
    normalized_quant = _normalize_quant_filter_key(quant)
    normalized_mtp = _normalize_choice(mtp)
    normalized_size = _normalize_choice(size)
    normalized_date = _normalize_choice(date)
    query = search.strip().lower()
    now = _parse_datetime(now_iso) or datetime.now(timezone.utc)

    filtered: list[dict[str, object]] = []
    for item in models:
        item_source = _normalize_source(str(item.get("source", "") or ""))
        if normalized_source != "all" and item_source != normalized_source:
            continue
        if normalized_family.lower() != "all" and str(item.get("family", "") or "") != normalized_family:
            continue
        if normalized_quant != "ALL" and _normalize_quant_filter_key(str(item.get("quantization", "") or "")) != normalized_quant:
            continue
        if normalized_mtp != "all" and _normalize_mtp_status(item.get("mtpStatus")) != normalized_mtp:
            continue
        if query and query not in _search_haystack(item):
            continue
        if normalized_size != "all" and not _matches_size_filter(item, normalized_size):
            continue
        if normalized_date != "all" and not _matches_date_filter(item, normalized_date, now):
            continue
        filtered.append(item)
    return filtered


def _sort_models(models: list[dict[str, object]], *, sort: str) -> list[dict[str, object]]:
    normalized_sort = _normalize_choice(sort) or "updated-desc"
    return sorted(models, key=lambda item: _sort_key(item, normalized_sort))


def _sort_key(item: dict[str, object], sort: str) -> tuple[object, ...]:
    model_name = str(item.get("model", "") or "")
    family_name = str(item.get("family", "") or "")
    source_name = _normalize_source(str(item.get("source", "") or ""))
    fit_rank = _fit_rank(item.get("fitStatus") or _fit_status_from_fit(item.get("fit")))
    updated_timestamp = _parse_datetime(str(item.get("updatedAt", "") or "")) or datetime.fromtimestamp(0, tz=timezone.utc)
    size_bytes = _size_bytes(item)
    if sort == "updated-asc":
        return (updated_timestamp, model_name)
    if sort == "updated-desc":
        return (-updated_timestamp.timestamp(), model_name)
    if sort == "quant-asc":
        return (*_quant_sort_token(str(item.get("quantization", "") or "")), model_name)
    if sort == "quant-desc":
        token = _quant_sort_token(str(item.get("quantization", "") or ""))
        return (-token[0], -token[1], _invert_sort_label(token[2]), model_name)
    if sort == "size-desc":
        return (-size_bytes, model_name)
    if sort == "size-asc":
        return (size_bytes if size_bytes >= 0 else float("inf"), model_name)
    if sort == "family-asc":
        return (family_name, model_name)
    if sort == "fit-desc":
        return (-fit_rank, model_name)
    return (source_name, model_name)


def _annotate_local_catalog_state(
    models: list[dict[str, object]],
    *,
    config: ControlCenterConfig | None,
) -> list[dict[str, object]]:
    if config is None:
        return models

    payload = load_models_payload(config)
    local_matches: dict[tuple[str, str, str], dict[str, object]] = {}
    for group_name in ("huggingFace", "unsloth"):
        for item in payload.get(group_name, []):
            if not isinstance(item, dict):
                continue
            source = _normalize_source(str(item.get("source", "") or ""))
            repo = str(item.get("repo", "") or item.get("repoId", "") or "").strip().lower()
            filename = str(item.get("filename", "") or "").strip()
            if not source or not repo or not filename:
                continue
            local_matches[(source, repo, filename)] = item

    annotated: list[dict[str, object]] = []
    for item in models:
        source = _normalize_source(str(item.get("source", "") or ""))
        repo = str(item.get("repoId", "") or item.get("repo", "") or "").strip().lower()
        filename = str(item.get("filename", "") or "").strip()
        match = local_matches.get((source, repo, filename))
        clone = dict(item)
        clone["addedToLocal"] = match is not None
        clone["localModelId"] = str(match.get("id", "") or "") if match is not None else None
        annotated.append(clone)
    return annotated


def _normalize_choice(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_source(value: str) -> str:
    lowered = value.strip().lower()
    if "hugging" in lowered:
        return "huggingface"
    if "unsloth" in lowered:
        return "unsloth"
    return lowered or "other"


def _normalize_mtp_status(value: object) -> str:
    lowered = str(value or "unknown").strip().lower()
    if "no" in lowered or "bez" in lowered:
        return "no-mtp"
    if "has" in lowered or "mtp" in lowered:
        return "has-mtp"
    return "unknown"


def _normalize_quant_filter_key(value: str) -> str:
    upper = str(value or "Unknown").strip().upper()
    if not upper:
        return "UNKNOWN"
    segments = upper.split("-")
    quant_index = next(
        (index for index, segment in enumerate(segments) if segment.startswith(("IQ", "Q", "BF16", "F16", "MXFP", "NVFP"))),
        -1,
    )
    if quant_index > 0:
        return "-".join(segments[quant_index:])
    return upper


def _search_haystack(item: dict[str, object]) -> str:
    fields = [
        item.get("model"),
        item.get("family"),
        item.get("source"),
        item.get("quantization"),
        item.get("repo"),
        item.get("repoId"),
        item.get("filename"),
        item.get("summary"),
    ]
    return " ".join(str(field or "") for field in fields).lower()


def _size_bytes(item: dict[str, object]) -> int:
    for key in ("sizeBytes", "fileSizeBytes", "bytes", "approxSizeBytes"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                continue
    return -1


def _matches_size_filter(item: dict[str, object], size: str) -> bool:
    size_bytes = _size_bytes(item)
    if size_bytes < 0:
        return True
    size_gib = size_bytes / (1024 ** 3)
    if size == "small":
        return size_gib < 4
    if size == "medium":
        return 4 <= size_gib <= 16
    if size == "large":
        return size_gib > 16
    return True


def _matches_date_filter(item: dict[str, object], date: str, now: datetime) -> bool:
    updated_at = _parse_datetime(str(item.get("updatedAt", "") or ""))
    if updated_at is None:
        return True
    age_days = (now - updated_at).total_seconds() / (60 * 60 * 24)
    if date == "7d":
        return age_days <= 7
    if date == "30d":
        return age_days <= 30
    if date == "90d":
        return age_days <= 90
    return True


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _quant_sort_token(value: str) -> tuple[int, int, str]:
    normalized = _normalize_quant_filter_key(value)
    if normalized in {"BF16", "F16"}:
        return (16, 3, normalized)
    for prefix, family_rank in (("IQ", 0), ("Q", 1)):
        if normalized.startswith(prefix):
            digits = ""
            for character in normalized[len(prefix) :]:
                if character.isdigit():
                    digits += character
                else:
                    break
            if digits:
                return (int(digits), family_rank, normalized)
    if normalized.startswith(("MXFP", "NVFP")):
        return (4, 2, normalized)
    return (2**31 - 1, 4, normalized)


def _invert_sort_label(label: str) -> str:
    return "".join(chr(255 - ord(character)) for character in label)


def _fit_status_from_fit(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("status", "") or "")
    return ""


def _fit_rank(value: object) -> int:
    lowered = str(value or "").strip().lower()
    if "radi" in lowered:
        return 3
    if "granic" in lowered:
        return 2
    if "ne radi" in lowered:
        return 1
    return 0
