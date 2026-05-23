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


def load_catalog_payload(
    *,
    cache_path: Path | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    resolved_cache_path = _resolve_cache_path(cache_path=cache_path, config=config)
    cache = _read_cache(resolved_cache_path)
    models = [item for item in cache.get("models", []) if isinstance(item, dict)]
    refresh = _normalize_refresh(cache.get("refresh"), models)
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
