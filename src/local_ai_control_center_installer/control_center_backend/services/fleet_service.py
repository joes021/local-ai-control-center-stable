from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from local_ai_control_center_installer.control_center_backend.config import ControlCenterConfig, get_config
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
    atomic_write_json,
    read_json_object,
    slugify_token,
)


def load_fleet_summary(config: ControlCenterConfig | None = None) -> dict[str, object]:
    resolved_config = config or get_config()
    machines = _load_registry(resolved_config)
    return {
        "machineCount": len(machines),
        "machines": machines,
        "generatedAt": _now_iso(),
    }


def add_fleet_machine(
    name: str,
    base_url: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    resolved_config = config or get_config()
    normalized_name = str(name or "").strip() or "Remote machine"
    normalized_base_url = _normalize_base_url(base_url)
    machines = _load_registry(resolved_config)

    existing = next((item for item in machines if item.get("baseUrl") == normalized_base_url), None)
    if existing:
        refreshed = _refresh_machine_snapshot(existing, resolved_config)
        _save_registry(resolved_config, machines)
        return {
            "status": "ok",
            "summary": f"Mašina {normalized_name} je već postojala i osvežena je.",
            "machine": refreshed,
        }

    machine = {
        "id": _build_machine_id(normalized_name),
        "name": normalized_name,
        "baseUrl": normalized_base_url,
        "addedAt": _now_iso(),
        "lastCheckedAt": "",
        "snapshot": {},
        "lastError": "",
    }
    refreshed = _refresh_machine_snapshot(machine, resolved_config)
    machines.append(refreshed)
    _save_registry(resolved_config, machines)
    return {
        "status": "ok",
        "summary": f"Dodata je remote mašina {normalized_name}.",
        "machine": refreshed,
    }


def refresh_fleet_machine(
    machine_id: str | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    resolved_config = config or get_config()
    machines = _load_registry(resolved_config)
    if not machines:
        return {
            "status": "ok",
            "summary": "Fleet je prazan, nema mašina za osvežavanje.",
            "machines": [],
        }

    if machine_id:
        target = next((item for item in machines if item.get("id") == machine_id), None)
        if not target:
            return action_result(
                "error",
                "refresh-fleet-machine",
                f"Remote mašina {machine_id} nije pronađena.",
            )
        refreshed = _refresh_machine_snapshot(target, resolved_config)
        _save_registry(resolved_config, machines)
        return {
            "status": "ok",
            "summary": f"Osvežen je {refreshed.get('name', 'remote host')}.",
            "machine": refreshed,
        }

    refreshed_machines = [_refresh_machine_snapshot(machine, resolved_config) for machine in machines]
    _save_registry(resolved_config, machines)
    return {
        "status": "ok",
        "summary": f"Osveženo je {len(refreshed_machines)} udaljenih mašina.",
        "machines": refreshed_machines,
    }


def remove_fleet_machine(
    machine_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    resolved_config = config or get_config()
    machines = _load_registry(resolved_config)
    filtered = [machine for machine in machines if machine.get("id") != machine_id]
    if len(filtered) == len(machines):
        return action_result(
            "error",
            "remove-fleet-machine",
            f"Remote mašina {machine_id} nije pronađena.",
        )
    _save_registry(resolved_config, filtered)
    return {
        "status": "ok",
        "summary": f"Uklonjena je remote mašina {machine_id}.",
        "machineId": machine_id,
    }


def _load_registry(config: ControlCenterConfig) -> list[dict[str, object]]:
    payload = read_json_object(config.fleet_registry_path)
    machines = payload.get("machines", [])
    if not isinstance(machines, list):
        return []
    return [machine for machine in machines if isinstance(machine, dict)]


def _save_registry(config: ControlCenterConfig, machines: list[dict[str, object]]) -> Path:
    return atomic_write_json(config.fleet_registry_path, {"machines": machines})


def _refresh_machine_snapshot(
    machine: dict[str, object],
    config: ControlCenterConfig,
) -> dict[str, object]:
    base_url = str(machine.get("baseUrl", "")).strip()
    now_iso = _now_iso()
    machine["lastCheckedAt"] = now_iso
    try:
        status_payload = _fetch_remote_json(base_url, "/api/status")
        server_payload = _fetch_remote_json(base_url, "/api/server/status")
        benchmark_payload = _fetch_remote_json(base_url, "/api/benchmark")
        health_payload = _fetch_remote_json(base_url, "/health")
        machine["snapshot"] = {
            "version": str(status_payload.get("version", "--")),
            "health": str(health_payload.get("status", "--")),
            "activeModel": str(status_payload.get("activeModel", "--")),
            "activeRuntime": str(
                status_payload.get("activeRuntimeLabel")
                or server_payload.get("runtime")
                or server_payload.get("activeRuntime")
                or "--"
            ),
            "runtimeLiveStatus": str(
                status_payload.get("runtimeLiveStatus") or server_payload.get("status") or "--"
            ),
            "runtimeSummary": str(
                status_payload.get("runtimeSummary") or server_payload.get("health") or "--"
            ),
            "uiUrl": str(status_payload.get("uiUrl") or f"{base_url}/"),
            "webUrl": str(server_payload.get("webUrl") or f"{base_url}/"),
            "liveNowTokensPerSecond": _coerce_float(
                ((benchmark_payload.get("telemetry") or {}) if isinstance(benchmark_payload, dict) else {}).get(
                    "liveNowTokensPerSecond"
                )
            ),
            "flowStateLabel": str(
                ((benchmark_payload.get("telemetry") or {}) if isinstance(benchmark_payload, dict) else {}).get(
                    "flowStateLabel"
                )
                or "--"
            ),
            "input24h": _coerce_int(
                ((benchmark_payload.get("telemetry") or {}) if isinstance(benchmark_payload, dict) else {}).get(
                    "input24h"
                )
            ),
            "output24h": _coerce_int(
                ((benchmark_payload.get("telemetry") or {}) if isinstance(benchmark_payload, dict) else {}).get(
                    "output24h"
                )
            ),
        }
        machine["lastError"] = ""
    except Exception as exc:  # noqa: BLE001 - fleet should stay resilient to remote errors
        machine["lastError"] = str(exc)
        machine["snapshot"] = {
            "version": "--",
            "health": "error",
            "activeModel": "--",
            "activeRuntime": "--",
            "runtimeLiveStatus": "error",
            "runtimeSummary": str(exc),
            "uiUrl": f"{base_url}/",
            "webUrl": f"{base_url}/",
            "liveNowTokensPerSecond": None,
            "flowStateLabel": "unreachable",
            "input24h": 0,
            "output24h": 0,
        }
    return machine


def _fetch_remote_json(base_url: str, path: str) -> dict[str, object]:
    normalized_base_url = _normalize_base_url(base_url)
    request_url = urljoin(f"{normalized_base_url}/", path.lstrip("/"))
    request = Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LocalAIControlCenter-Fleet/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        raise RuntimeError(f"{request_url} vratio je HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"{request_url} nije dostupan: {exc.reason}.") from exc
    except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"{request_url} nije vratio validan JSON odgovor.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{request_url} nije vratio JSON objekat.")
    return payload


def _normalize_base_url(value: str) -> str:
    normalized = str(value or "").strip().rstrip("/")
    if not normalized:
        raise ValueError("Remote mašina mora da ima base URL.")
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    return normalized.rstrip("/")


def _build_machine_id(name: str) -> str:
    return f"fleet-{slugify_token(name, fallback='machine')}-{uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _coerce_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_int(value: object) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    return 0
