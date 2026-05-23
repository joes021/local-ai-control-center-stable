from __future__ import annotations

import json
from json import JSONDecodeError
import os
from pathlib import Path
import re
from tempfile import mkstemp
from typing import Any
from uuid import uuid4


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (JSONDecodeError, OSError, UnicodeDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def atomic_write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, staged_path_raw = mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    staged_path = Path(staged_path_raw)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        staged_path.replace(path)
    except Exception:
        try:
            staged_path.unlink()
        except OSError:
            pass
        raise
    return path


def action_result(
    status: str,
    action: str,
    summary: str,
    *,
    stdout: str = "",
    stderr: str = "",
    action_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status,
        "action": action,
        "summary": summary,
        "details": {
            "returncode": 0 if status in {"ok", "accepted", "cancelled"} else 1,
            "stdout": stdout,
            "stderr": stderr,
        },
    }
    if action_id:
        payload["actionId"] = action_id
    return payload


def slugify_token(value: str, *, fallback: str = "item") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or fallback


def build_user_preset_id(name: str) -> str:
    return f"user-{slugify_token(name, fallback='preset')}-{uuid4().hex[:6]}"
