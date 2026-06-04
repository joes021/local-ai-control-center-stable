from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    atomic_write_json,
    read_json_object,
    slugify_token,
)


def get_project_memory(config: ControlCenterConfig | None = None) -> dict[str, Any]:
    config = config or get_config()
    payload = read_json_object(_project_memory_path(config))
    if not payload:
        return _default_project_memory()
    return _normalize_project_memory(payload)


def save_project_memory(
    payload: dict[str, object],
    *,
    config: ControlCenterConfig | None = None,
    updated_by: str = "user",
) -> dict[str, Any]:
    config = config or get_config()
    current = get_project_memory(config)
    next_payload = _normalize_project_memory(
        {
            **current,
            **payload,
            "updatedBy": updated_by,
            "updatedAt": _utc_now_iso(),
        }
    )
    atomic_write_json(_project_memory_path(config), next_payload)
    return next_payload


def update_project_memory_section(
    section: str,
    payload: dict[str, object],
    *,
    config: ControlCenterConfig | None = None,
    updated_by: str = "user",
) -> dict[str, Any]:
    current = get_project_memory(config)
    current[section] = payload
    return save_project_memory(current, config=config, updated_by=updated_by)


def seed_project_memory_from_task(
    goal: str,
    task_prompt: str,
) -> dict[str, Any]:
    normalized_goal = str(goal or "").strip()
    prompt_lines = [
        line.strip()
        for line in str(task_prompt or "").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    rules: list[dict[str, Any]] = []
    next_steps: list[dict[str, Any]] = []
    seen_rule_texts: set[str] = set()
    seen_next_texts: set[str] = set()

    for line in prompt_lines:
        lowered = line.lower()
        if _looks_like_rule(lowered):
            _append_memory_item(rules, seen_rule_texts, line, lock=False)
        if _looks_like_next_step(lowered):
            _append_memory_item(next_steps, seen_next_texts, line, lock=False)

    payload = _default_project_memory()
    payload["goal"] = {
        "text": normalized_goal,
        "locked": bool(normalized_goal),
    }
    payload["rules"] = rules
    payload["nextSteps"] = next_steps
    payload["status"] = _derive_status(payload)
    payload["updatedBy"] = "system"
    payload["updatedAt"] = _utc_now_iso()
    return payload


def _default_project_memory() -> dict[str, Any]:
    return {
        "status": "idle",
        "goal": {"text": "", "locked": False},
        "rules": [],
        "decisions": [],
        "progress": [],
        "nextSteps": [],
        "updatedAt": "",
        "updatedBy": "system",
    }


def _normalize_project_memory(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(_default_project_memory())
    goal_payload = payload.get("goal")
    if isinstance(goal_payload, dict):
        normalized["goal"] = {
            "text": str(goal_payload.get("text", "") or "").strip(),
            "locked": bool(goal_payload.get("locked", False)),
        }

    for section in ("rules", "decisions", "progress", "nextSteps"):
        normalized[section] = _normalize_memory_items(payload.get(section), include_locked=section == "rules")

    updated_at = str(payload.get("updatedAt", "") or "").strip()
    updated_by = str(payload.get("updatedBy", "") or "").strip()
    normalized["updatedAt"] = updated_at
    normalized["updatedBy"] = updated_by or "system"
    status = str(payload.get("status", "") or "").strip().lower()
    normalized["status"] = status if status in {"idle", "active"} else _derive_status(normalized)
    return normalized


def _normalize_memory_items(
    raw_items: object,
    *,
    include_locked: bool,
) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "") or "").strip()
        if not text:
            continue
        item_id = str(item.get("id", "") or "").strip() or f"{slugify_token(text)}-{index + 1}"
        if item_id in seen_ids:
            item_id = f"{item_id}-{index + 1}"
        seen_ids.add(item_id)
        normalized_item: dict[str, Any] = {
            "id": item_id,
            "text": text,
        }
        if include_locked:
            normalized_item["locked"] = bool(item.get("locked", False))
        items.append(normalized_item)
    return items


def _derive_status(payload: dict[str, Any]) -> str:
    if payload["goal"]["text"] or payload["rules"] or payload["decisions"] or payload["progress"] or payload["nextSteps"]:
        return "active"
    return "idle"


def _project_memory_path(config: ControlCenterConfig) -> Path:
    return config.control_center_config_root / "project-memory" / "current-memory.json"


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _looks_like_rule(line: str) -> bool:
    return bool(
        re.match(r"^(mora|moraju|treba|trebalo bi|obavezno|bez)\b", line)
    ) or "jednom fajlu" in line


def _looks_like_next_step(line: str) -> bool:
    return bool(
        re.match(r"^(prvo|slede[ćc]e|zatim|onda)\b", line)
    )


def _append_memory_item(
    bucket: list[dict[str, Any]],
    seen: set[str],
    text: str,
    *,
    lock: bool,
) -> None:
    normalized_text = text.strip()
    key = normalized_text.lower()
    if not normalized_text or key in seen:
        return
    seen.add(key)
    item: dict[str, Any] = {
        "id": slugify_token(normalized_text, fallback="item"),
        "text": normalized_text,
    }
    if lock:
        item["locked"] = True
    bucket.append(item)
