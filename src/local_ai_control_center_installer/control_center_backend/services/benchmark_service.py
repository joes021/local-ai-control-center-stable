from __future__ import annotations

from copy import deepcopy
import csv
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    ensure_runtime_ready,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    load_effective_settings_state,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
    atomic_write_json,
    build_user_preset_id,
    read_json_list,
    read_json_object,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_runtime_state,
)


BENCHMARK_SLOTS_TIMEOUT_SECONDS = 10.0
BENCHMARK_REQUEST_TIMEOUT_SECONDS = 180.0
BENCHMARK_LIVE_HISTORY_MAX_ITEMS = 200
BENCHMARK_LIVE_HISTORY_RETENTION_SECONDS = 3600
BENCHMARK_LIVE_SIGNAL_FRESHNESS_SECONDS = 2.5
BENCHMARK_TELEMETRY_WINDOW_HOURS = 24
BENCHMARK_PROXY_COST_PER_MILLION_TOKENS_USD = 0.10
BENCHMARK_MAX_REPEAT_COUNT = 10
_RUN_LOCK = threading.Lock()
_LIVE_SIGNAL_LOCK = threading.Lock()


DEFAULT_SCENARIOS = [
    {
        "id": "short",
        "name": "Short",
        "prompt": "Reply with exactly OK",
        "description": "Kratak smoke test za osnovni throughput signal.",
    },
    {
        "id": "medium",
        "name": "Medium",
        "prompt": "Summarize in 5 bullet points what local model serving means for a desktop workflow.",
        "description": "Srednji genericki scenario za kratak odgovor.",
    },
    {
        "id": "long",
        "name": "Long",
        "prompt": "Explain how KV cache compression changes memory usage, latency, and quality tradeoffs for local inference in a clear step-by-step format.",
        "description": "Duz i objasnjavajuci scenario za duži odgovor.",
    },
    {
        "id": "code",
        "name": "Code",
        "prompt": "Write a short Python function that retries an HTTP request three times and explain it in one paragraph.",
        "description": "Kod scenario za code-like output.",
    },
]


def load_benchmark_summary(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    settings_state = load_effective_settings_state(config)
    environment = _build_benchmark_environment(runtime_state, settings_state)
    history = _load_history(config)
    active_runtime_live_sample = _load_live_slot_metric(config)
    live_history = _record_live_history_sample(config, active_runtime_live_sample)
    signal_history = history + live_history
    current = signal_history[-1] if signal_history else None
    live_current = active_runtime_live_sample or _select_recent_live_current(live_history)
    latest_history_metric = history[-1] if history else None
    recent_benchmark_fallback = _recent_benchmark_fallback(latest_history_metric)
    recent_activities, source_counts = _build_recent_activities(signal_history)
    batteries_payload = _load_batteries(config)
    selected_battery = _selected_battery(batteries_payload)
    active_run = _load_run_state(config)
    saved_runs = _normalize_saved_runs(_load_saved_runs(config), environment)
    live_state = _build_live_state(
        active_run=active_run,
        live_current=live_current,
        recent_benchmark_fallback=recent_benchmark_fallback,
    )

    chart_history = [_attach_chart_label(_attach_environment(item, environment)) for item in signal_history[-120:]]
    live_chart_history = [_attach_chart_label(_attach_environment(item, environment)) for item in live_history[-120:]]

    return {
        "current": _attach_chart_label(_attach_environment(current, environment)) if current else None,
        "liveCurrent": _attach_chart_label(_attach_environment(live_current, environment)) if live_current else None,
        "history": chart_history,
        "liveHistory": live_chart_history,
        "historyCount": len(history),
        "requestCount": len(history),
        "lastMeasuredAt": current.get("measuredAt") if current else None,
        "lastLabel": current.get("label") if current else None,
        "environment": environment,
        "liveState": live_state,
        "telemetry": _build_telemetry_summary(
            history=history,
            live_history=live_history,
            live_current=live_current,
            latest_history_metric=latest_history_metric,
            recent_benchmark_fallback=recent_benchmark_fallback,
            environment=environment,
            live_state=live_state,
            active_run=active_run,
        ),
        "activity": {
            "averageTotalMs": _average(history, "totalMs") or 0,
            "sources": source_counts,
            "recentActivities": recent_activities,
            "stability": _build_stability(signal_history),
            "throughputTrend": _trend(signal_history[-4:], "totalTokensPerSecond", 1.5, -1.5),
            "latencyTrend": _trend(signal_history[-4:], "totalMs", 400.0, -400.0, inverse=True),
        },
        "averages": {
            "promptTokensPerSecond": _average(history, "promptTokensPerSecond"),
            "completionTokensPerSecond": _average(history, "completionTokensPerSecond"),
            "totalTokensPerSecond": _average(history, "totalTokensPerSecond"),
        },
        "liveLog": {
            "path": str(_latest_log_path(config)) if _latest_log_path(config) else "",
            "lines": _tail_lines(_latest_log_path(config), 30),
        },
        "batteries": batteries_payload.get("batteries", []),
        "selectedBattery": selected_battery,
        "activeRun": active_run,
        "savedRuns": saved_runs[:20],
    }


def load_benchmark_run_status(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    return _load_run_state(config or get_config())


def load_benchmark_compare(
    run_ids: list[str],
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    normalized_ids = [str(item or "").strip() for item in run_ids if str(item or "").strip()]
    if len(normalized_ids) < 2:
        return action_result(
            "error",
            "benchmark-compare",
            "Izaberi najmanje dva benchmark run-a za poredjenje.",
            stderr="Izaberi najmanje dva benchmark run-a za poredjenje.",
        )

    environment = _current_environment(config)
    runs = _normalize_saved_runs(_load_saved_runs(config), environment)
    indexed_runs = {
        str(item.get("runId", "") or ""): item
        for item in runs
        if isinstance(item, dict) and str(item.get("runId", "") or "").strip()
    }

    selected_runs: list[dict[str, Any]] = []
    for run_id in normalized_ids:
        match = indexed_runs.get(run_id)
        if match is None:
            return action_result(
                "error",
                "benchmark-compare",
                f"Benchmark run nije pronađen: {run_id}",
                stderr=f"Benchmark run nije pronađen: {run_id}",
            )
        selected_runs.append(match)

    rows = [_build_compare_row(run) for run in selected_runs]
    return {
        "status": "ok",
        "summary": f"{len(rows)} benchmark run-a su spremna za poredjenje.",
        "runIds": normalized_ids,
        "runs": selected_runs,
        "rows": rows,
        "comparison": _build_compare_summary(rows),
    }


def export_benchmark_runs(
    export_format: str,
    run_ids: list[str] | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any] | str:
    config = config or get_config()
    selected_runs = _select_export_runs(config, run_ids)
    rows = [_build_compare_row(run) for run in selected_runs]
    comparison = _build_compare_summary(rows)
    normalized_format = str(export_format or "").strip().lower()

    if normalized_format == "json":
        return {
            "exportedAt": _now_iso(),
            "runCount": len(selected_runs),
            "runs": selected_runs,
            "rows": rows,
            "comparison": comparison,
        }

    if normalized_format != "csv":
        raise ValueError(f"Nepodrzan benchmark export format: {export_format}")

    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "runId",
            "mode",
            "batteryName",
            "scenarioName",
            "modelId",
            "modelLabel",
            "runtime",
            "runtimeLabel",
            "profile",
            "context",
            "outputTokens",
            "thinkingMode",
            "status",
            "startedAt",
            "finishedAt",
            "metricScope",
            "metricLabel",
            "scenarioId",
            "scenarioMetricStatus",
            "promptTokensPerSecond",
            "completionTokensPerSecond",
            "totalTokensPerSecond",
            "totalMs",
        ],
    )
    writer.writeheader()
    for row in _flatten_export_rows(selected_runs):
        writer.writerow(row)
    return buffer.getvalue()


def list_batteries(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    payload = _load_batteries(config)
    return {
        "batteries": payload.get("batteries", []),
        "selectedBattery": _selected_battery(payload),
    }


def save_battery(
    name: str,
    scenarios: list[dict[str, object]],
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    normalized_name = str(name or "").strip() or "Custom battery"
    normalized_scenarios: list[dict[str, str]] = []
    for index, item in enumerate(scenarios, start=1):
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt", "") or "").strip()
        if not prompt:
            continue
        normalized_scenarios.append(
            {
                "id": str(item.get("id", "") or f"custom-{index}"),
                "name": str(item.get("name", "") or f"Custom {index}"),
                "prompt": prompt,
                "description": str(item.get("description", "") or "").strip(),
            }
        )
    if not normalized_scenarios:
        return action_result("error", "benchmark-save-battery", "Baterija mora imati bar jedan scenario.")

    payload = _load_batteries(config)
    battery_id = build_user_preset_id(normalized_name).replace("preset", "battery", 1)
    battery = {
        "id": battery_id,
        "name": normalized_name,
        "source": "custom",
        "updatedAt": _now_iso(),
        "scenarios": normalized_scenarios,
    }
    payload["batteries"] = [
        item
        for item in payload.get("batteries", [])
        if not (isinstance(item, dict) and str(item.get("name", "")).strip().lower() == normalized_name.lower())
    ]
    payload["batteries"].append(battery)
    payload["activeBatteryId"] = battery_id
    _save_batteries(config, payload)
    return {
        **action_result("ok", "benchmark-save-battery", f"Baterija sačuvana: {normalized_name}"),
        "battery": battery,
    }


def load_battery_selection(
    battery_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    payload = _load_batteries(config)
    match = next(
        (
            item
            for item in payload.get("batteries", [])
            if isinstance(item, dict) and str(item.get("id", "")) == battery_id
        ),
        None,
    )
    if not match:
        return action_result("error", "benchmark-load-battery", f"Baterija nije pronađena: {battery_id}")
    payload["activeBatteryId"] = battery_id
    _save_batteries(config, payload)
    return {
        **action_result("ok", "benchmark-load-battery", f"Ucitana baterija: {match.get('name', battery_id)}"),
        "battery": match,
    }


def restore_default_batteries(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    payload = _default_battery_payload()
    _save_batteries(config, payload)
    return {
        **action_result("ok", "benchmark-restore-defaults", "Podrazumevani benchmark testovi su vraćeni."),
        "battery": payload["batteries"][0],
    }


def clear_benchmark_history(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    for path in (
        config.benchmark_history_path,
        config.benchmark_live_history_path,
        config.benchmark_live_slots_snapshot_path,
        config.benchmark_saved_runs_path,
    ):
        atomic_write_json(path, [])
    atomic_write_json(config.benchmark_run_state_path, _idle_run_state())
    return action_result("ok", "benchmark-clear-history", "Benchmark istorija je obrisana.")


def start_selected_benchmark(
    scenario_id: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    battery_payload = _load_batteries(config)
    battery = _selected_battery(battery_payload)
    scenarios = [item for item in battery.get("scenarios", []) if isinstance(item, dict)]
    selected = next((item for item in scenarios if str(item.get("id", "")) == scenario_id), None)
    if not selected:
        return action_result("error", "benchmark-run-selected", f"Scenario nije pronađen: {scenario_id}")

    readiness = ensure_runtime_ready(config)
    if readiness.get("status") != "ok":
        return action_result(
            "error",
            "benchmark-run-selected",
            str(readiness.get("summary", "") or "Runtime nije spreman za benchmark."),
            stderr=str(readiness.get("summary", "") or "Runtime nije spreman za benchmark."),
        )

    with _RUN_LOCK:
        active = _load_run_state(config)
        if str(active.get("status", "")) in {"queued", "running"}:
            return action_result("error", "benchmark-run-selected", "Benchmark je već pokrenut.")

        run_id = f"bench-{uuid4().hex[:10]}"
        run_state = {
            "runId": run_id,
            "status": "queued",
            "mode": "selected",
            "batteryId": str(battery.get("id", "")),
            "batteryName": str(battery.get("name", "")),
            "scenarioId": str(selected.get("id", "")),
            "scenarioName": str(selected.get("name", "")),
            "currentScenarioId": str(selected.get("id", "")),
            "currentScenarioName": str(selected.get("name", "")),
            "currentIndex": 1,
            "totalScenarios": 1,
            "percent": 0,
            "startedAt": _now_iso(),
            "finishedAt": "",
            "message": f"Pokrećem benchmark scenario: {selected.get('name', scenario_id)}",
            "scenarioStatuses": [
                {
                    "scenarioId": str(selected.get("id", "")),
                    "scenarioName": str(selected.get("name", "")),
                    "status": "queued",
                    "summary": "čeka pokretanje.",
                }
            ],
        }
        _save_run_state(config, run_state)
        thread = threading.Thread(
            target=_run_selected_worker,
            args=(config, run_id, deepcopy(selected)),
            daemon=True,
        )
        thread.start()
    return {
        **action_result("accepted", "benchmark-run-selected", "Benchmark test je pokrenut.", action_id=run_id),
        "runId": run_id,
    }


def start_battery_benchmark(
    battery_id: str,
    *,
    repeat_count: int = 1,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    normalized_repeat_count = _normalize_repeat_count(repeat_count)
    if normalized_repeat_count is None:
        return action_result(
            "error",
            "benchmark-run-battery",
            f"Broj ponavljanja mora biti između 1 i {BENCHMARK_MAX_REPEAT_COUNT}.",
        )
    battery_payload = _load_batteries(config)
    battery = next(
        (
            item
            for item in battery_payload.get("batteries", [])
            if isinstance(item, dict) and str(item.get("id", "")) == battery_id
        ),
        None,
    )
    if not battery:
        return action_result("error", "benchmark-run-battery", f"Baterija nije pronađena: {battery_id}")
    scenarios = [item for item in battery.get("scenarios", []) if isinstance(item, dict)]
    if not scenarios:
        return action_result("error", "benchmark-run-battery", "Baterija nema nijedan scenario.")
    expanded_scenarios = _expand_battery_scenarios(scenarios, normalized_repeat_count)

    readiness = ensure_runtime_ready(config)
    if readiness.get("status") != "ok":
        return action_result(
            "error",
            "benchmark-run-battery",
            str(readiness.get("summary", "") or "Runtime nije spreman za benchmark."),
            stderr=str(readiness.get("summary", "") or "Runtime nije spreman za benchmark."),
        )

    with _RUN_LOCK:
        active = _load_run_state(config)
        if str(active.get("status", "")) in {"queued", "running"}:
            return action_result("error", "benchmark-run-battery", "Benchmark je već pokrenut.")

        run_id = f"bench-{uuid4().hex[:10]}"
        run_state = {
            "runId": run_id,
            "status": "queued",
            "mode": "battery",
            "batteryId": str(battery.get("id", "")),
            "batteryName": str(battery.get("name", "")),
            "repeatCount": normalized_repeat_count,
            "scenarioId": "",
            "scenarioName": "",
            "currentScenarioId": "",
            "currentScenarioName": "",
            "currentIndex": 0,
            "totalScenarios": len(expanded_scenarios),
            "percent": 0,
            "startedAt": _now_iso(),
            "finishedAt": "",
            "message": f"Pokrećem full battery: {battery.get('name', battery_id)}",
            "scenarioStatuses": _scenario_status_payload(expanded_scenarios),
        }
        run_state["message"] = _build_battery_launch_message(str(battery.get("name", battery_id)), normalized_repeat_count)
        _save_run_state(config, run_state)
        thread = threading.Thread(
            target=_run_battery_worker,
            args=(config, run_id, deepcopy(battery), [deepcopy(item) for item in expanded_scenarios]),
            daemon=True,
        )
        thread.start()
    return {
        **action_result(
            "accepted",
            "benchmark-run-battery",
            f"Benchmark baterija x{normalized_repeat_count} je pokrenuta.",
            action_id=run_id,
        ),
        "runId": run_id,
    }


def _load_history(config: ControlCenterConfig) -> list[dict[str, Any]]:
    return read_json_list(config.benchmark_history_path)


def _save_history(config: ControlCenterConfig, payload: list[dict[str, Any]]) -> None:
    atomic_write_json(config.benchmark_history_path, payload)


def _load_saved_runs(config: ControlCenterConfig) -> list[dict[str, Any]]:
    return read_json_list(config.benchmark_saved_runs_path)


def _append_saved_run(config: ControlCenterConfig, payload: dict[str, Any]) -> None:
    runs = _load_saved_runs(config)
    runs.insert(0, payload)
    atomic_write_json(config.benchmark_saved_runs_path, runs[:50])


def _load_run_state(config: ControlCenterConfig) -> dict[str, Any]:
    payload = read_json_object(config.benchmark_run_state_path)
    return {**_idle_run_state(), **payload}


def _save_run_state(config: ControlCenterConfig, payload: dict[str, Any]) -> None:
    atomic_write_json(config.benchmark_run_state_path, payload)


def _load_batteries(config: ControlCenterConfig) -> dict[str, Any]:
    payload = read_json_object(config.benchmark_batteries_path)
    batteries = payload.get("batteries")
    if not isinstance(batteries, list) or not batteries:
        payload = _default_battery_payload()
    if str(payload.get("activeBatteryId", "") or "").strip() == "":
        payload["activeBatteryId"] = "default"
    return payload


def _save_batteries(config: ControlCenterConfig, payload: dict[str, Any]) -> None:
    atomic_write_json(config.benchmark_batteries_path, payload)


def _selected_battery(payload: dict[str, Any]) -> dict[str, Any]:
    active_id = str(payload.get("activeBatteryId", "default") or "default")
    for battery in payload.get("batteries", []):
        if isinstance(battery, dict) and str(battery.get("id", "")) == active_id:
            return battery
    batteries = payload.get("batteries", [])
    return batteries[0] if isinstance(batteries, list) and batteries else _default_battery_payload()["batteries"][0]


def _default_battery_payload() -> dict[str, Any]:
    return {
        "activeBatteryId": "default",
        "batteries": [
            {
                "id": "default",
                "name": "Default battery",
                "source": "default",
                "updatedAt": _now_iso(),
                "scenarios": deepcopy(DEFAULT_SCENARIOS),
            }
        ],
    }


def _idle_run_state() -> dict[str, Any]:
    return {
        "runId": "",
        "status": "idle",
        "mode": "idle",
        "batteryId": "",
        "batteryName": "",
        "repeatCount": 1,
        "scenarioId": "",
        "scenarioName": "",
        "currentScenarioId": "",
        "currentScenarioName": "",
        "currentIndex": 0,
        "totalScenarios": 0,
        "percent": 0,
        "startedAt": "",
        "finishedAt": "",
        "message": "Benchmark nije pokrenut.",
        "scenarioStatuses": [],
    }


def _average(history: list[dict[str, Any]], key: str) -> float | None:
    values: list[float] = []
    for item in history:
        raw_value = item.get(key)
        if raw_value is None:
            continue
        try:
            values.append(float(raw_value))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _trend(
    history: list[dict[str, Any]],
    key: str,
    up_threshold: float,
    down_threshold: float,
    *,
    inverse: bool = False,
) -> dict[str, str]:
    if len(history) < 2:
        return {
            "direction": "flat",
            "label": "stabilan",
            "signal": "=",
            "reason": "Još nema dovoljno podataka za trend.",
        }
    first = float(history[0].get(key, 0.0) or 0.0)
    last = float(history[-1].get(key, 0.0) or 0.0)
    delta = last - first
    if inverse:
        if delta <= -abs(down_threshold):
            return {
                "direction": "up",
                "label": "brze",
                "signal": "^",
                "reason": "Skorasnja latencija deluje bolja nego ranije u uzorku.",
            }
        if delta >= abs(up_threshold):
            return {
                "direction": "down",
                "label": "sporije",
                "signal": "v",
                "reason": "Skorasnja latencija deluje gora nego ranije u uzorku.",
            }
    else:
        if delta >= up_threshold:
            return {
                "direction": "up",
                "label": "raste",
                "signal": "^",
                "reason": "Skorasnji signal deluje bolji nego ranije u uzorku.",
            }
        if delta <= down_threshold:
            return {
                "direction": "down",
                "label": "pada",
                "signal": "v",
                "reason": "Skorasnji signal deluje slabiji nego ranije u uzorku.",
            }
    return {
        "direction": "flat",
        "label": "stabilan",
        "signal": "=",
        "reason": "Signal nema veliku promenu kroz poslednje zahteve.",
    }


def _build_recent_activities(history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    recent_activities: list[dict[str, Any]] = []
    source_counts = {"testPrompt": 0, "opencode": 0, "other": 0}
    for item in reversed(history[-10:]):
        source = _detect_source(str(item.get("label", "")))
        source_counts[source] += 1
        recent_activities.append(
            {
                "measuredAt": item.get("measuredAt"),
                "chartLabel": _chart_label(str(item.get("measuredAt", ""))),
                "label": item.get("label"),
                "source": source,
                "totalMs": round(float(item.get("totalMs", 0.0) or 0.0), 2),
                "totalTokensPerSecond": round(float(item.get("totalTokensPerSecond", 0.0) or 0.0), 2),
            }
        )
    return recent_activities, source_counts


def _build_stability(history: list[dict[str, Any]]) -> dict[str, Any]:
    if len(history) < 3:
        return {
            "level": "warming",
            "label": "zagreva se",
            "score": 50,
            "reason": "Treba još nekoliko zahteva za pouzdaniji signal.",
        }
    return {
        "level": "stable",
        "label": "stabilno",
        "score": 85,
        "reason": "Skorasnji zahtevi deluju ujednaceno.",
    }


def _attach_chart_label(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    payload = dict(item)
    payload["chartLabel"] = _chart_label(str(item.get("measuredAt", "")))
    return payload


def _chart_label(measured_at: str) -> str:
    text = str(measured_at or "").strip()
    if not text:
        return "--:--:--"
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).strftime("%H:%M:%S")
    except ValueError:
        return text[-8:] if len(text) >= 8 else text


def _latest_log_path(config: ControlCenterConfig) -> Path | None:
    candidates = [
        config.install_root / "logs" / "runtime-server.log",
        config.install_root / "logs" / "opencode-launch.log",
        config.install_root / "logs" / "install.log",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _tail_lines(path: Path | None, limit: int = 30) -> list[str]:
    if path is None or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-limit:]


def _detect_source(label: str) -> str:
    normalized = str(label or "").lower()
    if "benchmark" in normalized or "test" in normalized:
        return "testPrompt"
    if "opencode" in normalized:
        return "opencode"
    return "other"


def _load_live_history(config: ControlCenterConfig) -> list[dict[str, Any]]:
    payload = read_json_list(config.benchmark_live_history_path)
    normalized: list[dict[str, Any]] = []
    for item in payload:
        copy_item = dict(item)
        if (
            copy_item.get("promptTokensPerSecond") == 0.0
            and float(copy_item.get("completionTokensPerSecond", 0.0) or 0.0) > 0.0
        ):
            copy_item["promptTokensPerSecond"] = None
        normalized.append(copy_item)
    return normalized


def _record_live_history_sample(
    config: ControlCenterConfig,
    sample: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    with _LIVE_SIGNAL_LOCK:
        history = _load_live_history(config)
        if sample:
            history.append(sample)
        now = datetime.now(timezone.utc)
        normalized: list[dict[str, Any]] = []
        for item in history:
            measured_at = _parse_iso_timestamp(item.get("measuredAt"))
            if measured_at is None:
                continue
            if (now - measured_at).total_seconds() > BENCHMARK_LIVE_HISTORY_RETENTION_SECONDS:
                continue
            normalized.append(item)
        normalized.sort(key=lambda item: str(item.get("measuredAt", "")))
        deduped: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()
        for item in normalized:
            signature = str(item.get("signature", "") or "")
            if signature and signature in seen_signatures:
                continue
            if signature:
                seen_signatures.add(signature)
            deduped.append(item)
        deduped = deduped[-BENCHMARK_LIVE_HISTORY_MAX_ITEMS:]
        atomic_write_json(config.benchmark_live_history_path, deduped)
        return deduped


def record_runtime_live_slot_metric(
    base_url: str,
    *,
    config: ControlCenterConfig | None = None,
    label: str = "runtime-live",
    source: str = "runtime",
    snapshot_key: str = "",
) -> dict[str, Any] | None:
    config = config or get_config()
    sample = _sample_live_slot_metric(
        config,
        base_url=base_url,
        label=label,
        source=source,
        snapshot_key=snapshot_key or base_url,
    )
    _record_live_history_sample(config, sample)
    return sample


def _load_live_slot_metric(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any] | None:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    base_url = str(runtime_state.get("base_url", "") or "").strip()
    if not base_url:
        return None
    return _sample_live_slot_metric(
        config,
        base_url=base_url,
        label="runtime-live",
        source="runtime",
        snapshot_key="active-runtime",
    )


def _sample_live_slot_metric(
    config: ControlCenterConfig,
    *,
    base_url: str,
    label: str,
    source: str,
    snapshot_key: str,
) -> dict[str, Any] | None:
    normalized_base_url = str(base_url or "").strip()
    if not normalized_base_url:
        return None

    try:
        with urlopen(f"{normalized_base_url}/slots", timeout=BENCHMARK_SLOTS_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return None

    if not isinstance(payload, list):
        return None

    current_slots: dict[str, int] = {}
    for item in payload:
        if not isinstance(item, dict) or not item.get("is_processing"):
            continue
        slot_id = str(item.get("id", ""))
        task_id = str(item.get("id_task", ""))
        next_tokens = item.get("next_token")
        if not isinstance(next_tokens, list) or not next_tokens:
            continue
        first_token = next_tokens[0]
        if not isinstance(first_token, dict):
            continue
        try:
            decoded = int(first_token.get("n_decoded", 0) or 0)
        except (TypeError, ValueError):
            continue
        current_slots[f"{slot_id}:{task_id}"] = decoded

    measured_at = datetime.now(timezone.utc)
    snapshot = {"measuredAt": measured_at.isoformat(), "slots": current_slots}
    with _LIVE_SIGNAL_LOCK:
        previous_snapshot = _load_live_slot_snapshot(config, snapshot_key)
        _save_live_slot_snapshot(config, snapshot_key, snapshot)

    if not current_slots:
        return None

    previous_slots = previous_snapshot.get("slots")
    previous_measured_at = _parse_iso_timestamp(previous_snapshot.get("measuredAt"))
    if not isinstance(previous_slots, dict) or previous_measured_at is None:
        return None

    elapsed_seconds = (measured_at - previous_measured_at).total_seconds()
    if elapsed_seconds <= 0:
        return None

    delta_tokens = 0
    for slot_key, decoded in current_slots.items():
        previous_decoded = previous_slots.get(slot_key)
        if not isinstance(previous_decoded, int):
            continue
        if decoded > previous_decoded:
            delta_tokens += decoded - previous_decoded

    if delta_tokens <= 0:
        return None

    throughput = round(delta_tokens / elapsed_seconds, 2)
    return {
        "measuredAt": snapshot["measuredAt"],
        "label": label,
        "source": source,
        "activeRoutes": len(current_slots),
        "promptTokens": 0,
        "completionTokens": delta_tokens,
        "totalTokens": delta_tokens,
        "promptMs": 0.0,
        "completionMs": round(elapsed_seconds * 1000, 2),
        "totalMs": round(elapsed_seconds * 1000, 2),
        "promptTokensPerSecond": None,
        "completionTokensPerSecond": throughput,
        "totalTokensPerSecond": throughput,
        "signature": f"{label}:{snapshot_key}:{snapshot['measuredAt']}:{delta_tokens}",
    }


def _load_live_slot_snapshot(config: ControlCenterConfig, snapshot_key: str) -> dict[str, Any]:
    payload = read_json_object(config.benchmark_live_slots_snapshot_path)
    entries = payload.get("entries")
    if isinstance(entries, dict):
        entry = entries.get(snapshot_key)
        return dict(entry) if isinstance(entry, dict) else {}
    if snapshot_key == "active-runtime" and isinstance(payload.get("slots"), dict):
        return {
            "measuredAt": str(payload.get("measuredAt", "") or ""),
            "slots": dict(payload.get("slots", {})),
        }
    return {}


def _save_live_slot_snapshot(
    config: ControlCenterConfig,
    snapshot_key: str,
    snapshot: dict[str, Any],
) -> None:
    payload = read_json_object(config.benchmark_live_slots_snapshot_path)
    entries = payload.get("entries")
    normalized_entries = dict(entries) if isinstance(entries, dict) else {}
    normalized_entries[snapshot_key] = dict(snapshot)
    atomic_write_json(
        config.benchmark_live_slots_snapshot_path,
        {"entries": normalized_entries},
    )


def _select_recent_live_current(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    for item in reversed(history):
        measured_at = _parse_iso_timestamp(item.get("measuredAt"))
        if measured_at is None:
            continue
        if (now - measured_at).total_seconds() > BENCHMARK_LIVE_SIGNAL_FRESHNESS_SECONDS:
            continue
        return item
    return None


def _run_selected_worker(config: ControlCenterConfig, run_id: str, scenario: dict[str, Any]) -> None:
    run_state = _load_run_state(config)
    if run_state.get("runId") != run_id:
        return
    run_state["status"] = "running"
    run_state["percent"] = 5
    run_state["scenarioStatuses"][0]["status"] = "running"
    run_state["scenarioStatuses"][0]["summary"] = "Scenario se izvrsava."
    _save_run_state(config, run_state)

    result = _execute_benchmark_prompt(config, str(scenario.get("prompt", "")), label=f"benchmark-{scenario.get('id', 'scenario')}")
    final_status = "done" if result["status"] == "ok" else "failed"
    metric = result.get("metric")
    if isinstance(metric, dict):
        history = _load_history(config)
        history.append(metric)
        _save_history(config, history[-500:])

    run_state = _load_run_state(config)
    if run_state.get("runId") != run_id:
        return
    run_state["status"] = final_status
    run_state["percent"] = 100
    run_state["finishedAt"] = _now_iso()
    run_state["message"] = str(result.get("summary", "Benchmark je završen."))
    run_state["scenarioStatuses"][0]["status"] = final_status
    run_state["scenarioStatuses"][0]["summary"] = run_state["message"]
    _save_run_state(config, run_state)

    _append_saved_run(
        config,
        {
            "runId": run_id,
            "mode": "selected",
            "batteryName": run_state.get("batteryName", ""),
            "scenarioName": run_state.get("scenarioName", ""),
            **_saved_run_metadata(config),
            "status": final_status,
            "startedAt": run_state.get("startedAt", ""),
            "finishedAt": run_state.get("finishedAt", ""),
            "currentMetric": _attach_environment(metric, _current_environment(config)) if isinstance(metric, dict) else None,
        },
    )


def _run_battery_worker(
    config: ControlCenterConfig,
    run_id: str,
    battery: dict[str, Any],
    scenarios: list[dict[str, Any]],
) -> None:
    run_state = _load_run_state(config)
    if run_state.get("runId") != run_id:
        return
    run_state["status"] = "running"
    _save_run_state(config, run_state)
    scenario_results: list[dict[str, Any]] = []

    for index, scenario in enumerate(scenarios, start=1):
        run_state = _load_run_state(config)
        if run_state.get("runId") != run_id:
            return
        run_state["currentIndex"] = index
        run_state["currentScenarioId"] = str(scenario.get("id", ""))
        run_state["currentScenarioName"] = str(scenario.get("name", ""))
        run_state["percent"] = round(((index - 1) / max(len(scenarios), 1)) * 100)
        run_state["message"] = f"Pokrećem scenario {index}/{len(scenarios)}: {scenario.get('name', '')}"
        run_state["scenarioStatuses"][index - 1]["status"] = "running"
        run_state["scenarioStatuses"][index - 1]["summary"] = "Scenario se izvrsava."
        _save_run_state(config, run_state)

        result = _execute_benchmark_prompt(config, str(scenario.get("prompt", "")), label=f"benchmark-{scenario.get('id', 'scenario')}")
        final_status = "done" if result["status"] == "ok" else "failed"
        metric = result.get("metric")
        if isinstance(metric, dict):
            history = _load_history(config)
            history.append(metric)
            _save_history(config, history[-500:])
        scenario_results.append(
            {
                "scenarioId": str(scenario.get("id", "")),
                "scenarioName": str(scenario.get("name", "")),
                "status": final_status,
                "summary": str(result.get("summary", "")),
                "metric": metric if isinstance(metric, dict) else None,
            }
        )

        run_state = _load_run_state(config)
        if run_state.get("runId") != run_id:
            return
        run_state["scenarioStatuses"][index - 1]["status"] = final_status
        run_state["scenarioStatuses"][index - 1]["summary"] = str(result.get("summary", ""))
        run_state["percent"] = round((index / max(len(scenarios), 1)) * 100)
        _save_run_state(config, run_state)

    overall_status = "done" if all(item["status"] == "done" for item in scenario_results) else "failed"
    run_state = _load_run_state(config)
    if run_state.get("runId") != run_id:
        return
    run_state["status"] = overall_status
    run_state["finishedAt"] = _now_iso()
    run_state["message"] = (
        "Benchmark battery je završen."
        if overall_status == "done"
        else "Benchmark battery je završen sa greškama."
    )
    _save_run_state(config, run_state)

    environment = _current_environment(config)
    _append_saved_run(
        config,
        {
            "runId": run_id,
            "mode": "battery",
            "batteryName": str(battery.get("name", "")),
            "repeatCount": _int_or_zero(run_state.get("repeatCount")) or 1,
            "scenarioName": "",
            **_saved_run_metadata(config),
            "status": overall_status,
            "startedAt": run_state.get("startedAt", ""),
            "finishedAt": run_state.get("finishedAt", ""),
            "scenarioResults": [
                {
                    **item,
                    "metric": _attach_environment(item.get("metric"), environment)
                    if isinstance(item.get("metric"), dict)
                    else item.get("metric"),
                }
                for item in scenario_results
            ],
        },
    )


def _execute_benchmark_prompt(
    config: ControlCenterConfig,
    prompt: str,
    *,
    label: str,
) -> dict[str, Any]:
    runtime_state = load_runtime_state(config)
    base_url = str(runtime_state.get("base_url", "") or "").strip()
    model_name = str(runtime_state.get("active_model", "") or "local-model")
    request_payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 160,
        "stream": False,
    }
    request = Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started_at = datetime.now(timezone.utc)
    started_perf = time.monotonic()
    try:
        with urlopen(request, timeout=BENCHMARK_REQUEST_TIMEOUT_SECONDS) as response:
            response_payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        return {
            "status": "error",
            "summary": f"Benchmark prompt nije uspeo: HTTP {exc.code}. {message}".strip(),
        }
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "status": "error",
            "summary": f"Benchmark prompt nije uspeo: {exc}",
        }

    total_ms = max((time.monotonic() - started_perf) * 1000.0, 1.0)
    metric = _build_metric_from_completion_response(
        response_payload,
        measured_at=started_at.isoformat(),
        label=label,
        total_ms=total_ms,
    )
    return {
        "status": "ok",
        "summary": "Benchmark scenario je završen.",
        "metric": metric,
    }


def _build_metric_from_completion_response(
    response_payload: dict[str, Any],
    *,
    measured_at: str,
    label: str,
    total_ms: float,
) -> dict[str, Any]:
    usage = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
    timings = response_payload.get("timings") if isinstance(response_payload.get("timings"), dict) else {}

    prompt_tokens = _int_or_zero(usage.get("prompt_tokens"))
    completion_tokens = _int_or_zero(usage.get("completion_tokens"))
    total_tokens = _int_or_zero(usage.get("total_tokens"))
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens

    prompt_ms = _float_or_none(timings.get("prompt_ms"))
    completion_ms = _float_or_none(timings.get("predicted_ms"))
    if prompt_ms is None and prompt_tokens > 0:
        prompt_ms = total_ms
    if completion_ms is None and completion_tokens > 0:
        completion_ms = total_ms

    prompt_tps = _tokens_per_second(prompt_tokens, prompt_ms)
    completion_tps = _tokens_per_second(completion_tokens, completion_ms)
    total_tps = _tokens_per_second(total_tokens, total_ms)

    return {
        "measuredAt": measured_at,
        "label": label,
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "totalTokens": total_tokens,
        "promptMs": round(prompt_ms or 0.0, 2),
        "completionMs": round(completion_ms or total_ms, 2),
        "totalMs": round(total_ms, 2),
        "promptTokensPerSecond": prompt_tps,
        "completionTokensPerSecond": completion_tps,
        "totalTokensPerSecond": total_tps,
    }


def _build_benchmark_environment(
    runtime_state: dict[str, Any],
    settings_state: dict[str, Any],
) -> dict[str, Any]:
    return {
        "modelId": str(runtime_state.get("active_model_id", "unknown") or "unknown"),
        "modelLabel": str(runtime_state.get("active_model", "unknown") or "unknown"),
        "runtime": str(runtime_state.get("active_runtime", "unknown") or "unknown"),
        "runtimeLabel": _runtime_label(str(runtime_state.get("active_runtime", "unknown") or "unknown")),
        "profile": str(settings_state.get("profile", runtime_state.get("profile", "balanced")) or "balanced"),
        "context": int(settings_state.get("context", 0) or 0),
        "outputTokens": int(settings_state.get("outputTokens", 0) or 0),
        "thinkingMode": str(settings_state.get("thinkingMode", "mid") or "mid"),
        "runtimeLiveStatus": str(runtime_state.get("runtime_live_status", "unknown") or "unknown"),
        "runtimeLiveReason": str(runtime_state.get("runtime_live_reason", "") or ""),
    }


def _current_environment(config: ControlCenterConfig) -> dict[str, Any]:
    runtime_state = load_runtime_state(config)
    settings_state = load_effective_settings_state(config)
    return _build_benchmark_environment(runtime_state, settings_state)


def _saved_run_metadata(config: ControlCenterConfig) -> dict[str, Any]:
    environment = _current_environment(config)
    return {
        "modelId": environment["modelId"],
        "modelLabel": environment["modelLabel"],
        "runtime": environment["runtime"],
        "runtimeLabel": environment["runtimeLabel"],
        "profile": environment["profile"],
        "context": environment["context"],
        "outputTokens": environment["outputTokens"],
        "thinkingMode": environment["thinkingMode"],
    }


def _attach_environment(item: dict[str, Any] | None, environment: dict[str, Any]) -> dict[str, Any] | None:
    if item is None:
        return None
    payload = dict(item)
    payload["environment"] = dict(environment)
    return payload


def _normalize_saved_runs(
    runs: list[dict[str, Any]],
    environment: dict[str, Any],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in runs:
        payload = dict(item)
        payload.setdefault("modelId", environment["modelId"])
        payload.setdefault("modelLabel", environment["modelLabel"])
        payload.setdefault("runtime", environment["runtime"])
        payload.setdefault("runtimeLabel", environment["runtimeLabel"])
        payload.setdefault("profile", environment["profile"])
        payload.setdefault("context", environment["context"])
        payload.setdefault("outputTokens", environment["outputTokens"])
        payload.setdefault("thinkingMode", environment["thinkingMode"])
        if isinstance(payload.get("currentMetric"), dict):
            payload["currentMetric"] = _attach_environment(payload["currentMetric"], environment)
        if isinstance(payload.get("scenarioResults"), list):
            payload["scenarioResults"] = [
                {
                    **scenario,
                    "metric": _attach_environment(scenario.get("metric"), environment)
                    if isinstance(scenario, dict) and isinstance(scenario.get("metric"), dict)
                    else (scenario.get("metric") if isinstance(scenario, dict) else None),
                }
                if isinstance(scenario, dict)
                else scenario
                for scenario in payload["scenarioResults"]
            ]
        normalized.append(payload)
    return normalized


def _select_export_runs(
    config: ControlCenterConfig,
    run_ids: list[str] | None,
) -> list[dict[str, Any]]:
    environment = _current_environment(config)
    runs = _normalize_saved_runs(_load_saved_runs(config), environment)
    if not run_ids:
        return runs
    normalized_ids = [str(item or "").strip() for item in run_ids if str(item or "").strip()]
    indexed_runs = {
        str(item.get("runId", "") or ""): item
        for item in runs
        if isinstance(item, dict) and str(item.get("runId", "") or "").strip()
    }
    selected_runs: list[dict[str, Any]] = []
    for run_id in normalized_ids:
        match = indexed_runs.get(run_id)
        if match is None:
            raise ValueError(f"Benchmark run nije pronađen: {run_id}")
        selected_runs.append(match)
    return selected_runs


def _build_compare_row(run: dict[str, Any]) -> dict[str, Any]:
    scenario_results = run.get("scenarioResults")
    scenario_metrics = [
        item.get("metric")
        for item in scenario_results
        if isinstance(item, dict) and isinstance(item.get("metric"), dict)
    ] if isinstance(scenario_results, list) else []
    primary_metric = run.get("currentMetric") if isinstance(run.get("currentMetric"), dict) else None
    metric = primary_metric or _aggregate_metrics(scenario_metrics)
    return {
        "runId": str(run.get("runId", "") or ""),
        "label": _run_display_label(run),
        "mode": str(run.get("mode", "") or ""),
        "batteryName": str(run.get("batteryName", "") or ""),
        "scenarioName": str(run.get("scenarioName", "") or ""),
        "modelId": str(run.get("modelId", "") or ""),
        "modelLabel": str(run.get("modelLabel", "") or ""),
        "runtime": str(run.get("runtime", "") or ""),
        "runtimeLabel": str(run.get("runtimeLabel", "") or ""),
        "profile": str(run.get("profile", "") or ""),
        "context": int(run.get("context", 0) or 0),
        "outputTokens": int(run.get("outputTokens", 0) or 0),
        "thinkingMode": str(run.get("thinkingMode", "") or ""),
        "status": str(run.get("status", "") or ""),
        "startedAt": str(run.get("startedAt", "") or ""),
        "finishedAt": str(run.get("finishedAt", "") or ""),
        "scenarioCount": len(scenario_results) if isinstance(scenario_results, list) else (1 if primary_metric else 0),
        "metricSource": "current" if primary_metric else ("scenario-average" if scenario_metrics else "none"),
        "promptTokensPerSecond": _metric_value(metric, "promptTokensPerSecond"),
        "completionTokensPerSecond": _metric_value(metric, "completionTokensPerSecond"),
        "totalTokensPerSecond": _metric_value(metric, "totalTokensPerSecond"),
        "totalMs": _metric_value(metric, "totalMs"),
    }


def _build_compare_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "promptTokensPerSecond": _metric_summary(rows, "promptTokensPerSecond", higher_is_better=True),
        "completionTokensPerSecond": _metric_summary(rows, "completionTokensPerSecond", higher_is_better=True),
        "totalTokensPerSecond": _metric_summary(rows, "totalTokensPerSecond", higher_is_better=True),
        "totalMs": _metric_summary(rows, "totalMs", higher_is_better=False),
    }


def _metric_summary(
    rows: list[dict[str, Any]],
    key: str,
    *,
    higher_is_better: bool,
) -> dict[str, Any]:
    values = [
        (str(row.get("runId", "") or ""), _metric_value(row, key))
        for row in rows
    ]
    present = [(run_id, value) for run_id, value in values if value is not None]
    if not present:
        return {"bestRunId": None, "bestValue": None, "average": None}
    best_run_id, best_value = (
        max(present, key=lambda item: item[1])
        if higher_is_better
        else min(present, key=lambda item: item[1])
    )
    average = round(sum(value for _, value in present) / len(present), 2)
    return {
        "bestRunId": best_run_id,
        "bestValue": round(best_value, 2),
        "average": average,
    }


def _aggregate_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not metrics:
        return None
    return {
        "promptTokensPerSecond": _average(metrics, "promptTokensPerSecond"),
        "completionTokensPerSecond": _average(metrics, "completionTokensPerSecond"),
        "totalTokensPerSecond": _average(metrics, "totalTokensPerSecond"),
        "totalMs": _average(metrics, "totalMs"),
    }


def _flatten_export_rows(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for run in runs:
        current_metric = run.get("currentMetric") if isinstance(run.get("currentMetric"), dict) else None
        if current_metric is not None:
            flattened.append(_build_export_row(run, current_metric, metric_scope="current"))
        scenario_results = run.get("scenarioResults")
        if isinstance(scenario_results, list):
            for scenario in scenario_results:
                if not isinstance(scenario, dict):
                    continue
                metric = scenario.get("metric") if isinstance(scenario.get("metric"), dict) else None
                flattened.append(
                    _build_export_row(
                        run,
                        metric,
                        metric_scope="scenario",
                        scenario_id=str(scenario.get("scenarioId", "") or ""),
                        scenario_name=str(scenario.get("scenarioName", "") or ""),
                        scenario_status=str(scenario.get("status", "") or ""),
                    )
                )
        if current_metric is None and not isinstance(scenario_results, list):
            flattened.append(_build_export_row(run, None, metric_scope="run"))
    return flattened


def _build_export_row(
    run: dict[str, Any],
    metric: dict[str, Any] | None,
    *,
    metric_scope: str,
    scenario_id: str = "",
    scenario_name: str = "",
    scenario_status: str = "",
) -> dict[str, Any]:
    return {
        "runId": str(run.get("runId", "") or ""),
        "mode": str(run.get("mode", "") or ""),
        "batteryName": str(run.get("batteryName", "") or ""),
        "scenarioName": scenario_name or str(run.get("scenarioName", "") or ""),
        "modelId": str(run.get("modelId", "") or ""),
        "modelLabel": str(run.get("modelLabel", "") or ""),
        "runtime": str(run.get("runtime", "") or ""),
        "runtimeLabel": str(run.get("runtimeLabel", "") or ""),
        "profile": str(run.get("profile", "") or ""),
        "context": int(run.get("context", 0) or 0),
        "outputTokens": int(run.get("outputTokens", 0) or 0),
        "thinkingMode": str(run.get("thinkingMode", "") or ""),
        "status": str(run.get("status", "") or ""),
        "startedAt": str(run.get("startedAt", "") or ""),
        "finishedAt": str(run.get("finishedAt", "") or ""),
        "metricScope": metric_scope,
        "metricLabel": str(metric.get("label", "") or "") if isinstance(metric, dict) else "",
        "scenarioId": scenario_id,
        "scenarioMetricStatus": scenario_status,
        "promptTokensPerSecond": _metric_value(metric, "promptTokensPerSecond"),
        "completionTokensPerSecond": _metric_value(metric, "completionTokensPerSecond"),
        "totalTokensPerSecond": _metric_value(metric, "totalTokensPerSecond"),
        "totalMs": _metric_value(metric, "totalMs"),
    }


def _run_display_label(run: dict[str, Any]) -> str:
    if str(run.get("mode", "") or "") == "battery":
        return str(run.get("batteryName", "") or run.get("runId", "") or "battery-run")
    return str(run.get("scenarioName", "") or run.get("runId", "") or "selected-run")


def _metric_value(payload: dict[str, Any] | None, key: str) -> float | None:
    if not isinstance(payload, dict):
        return None
    raw_value = payload.get(key)
    if raw_value is None:
        return None
    try:
        return round(float(raw_value), 2)
    except (TypeError, ValueError):
        return None


def _build_live_state(
    *,
    active_run: dict[str, Any],
    live_current: dict[str, Any] | None,
    recent_benchmark_fallback: dict[str, Any] | None,
) -> dict[str, Any]:
    if live_current is not None:
        return {
            "status": "active",
            "hasLiveSignal": True,
            "reason": "Live throughput signal dolazi iz aktivnog llama.cpp-kompatibilnog /slots uzorka.",
        }
    if str(active_run.get("status", "") or "") in {"queued", "running"}:
        return {
            "status": "warming",
            "hasLiveSignal": False,
            "reason": "Benchmark je pokrenut, ali runtime još nije prijavio live throughput signal.",
        }
    if recent_benchmark_fallback is not None:
        return {
            "status": "recent-benchmark",
            "hasLiveSignal": False,
            "reason": "Runtime trenutno nema aktivan live throughput signal. Prikazujem poslednji benchmark throughput kao referencu dok nema novog live saobraćaja.",
        }
    return {
        "status": "idle",
        "hasLiveSignal": False,
        "reason": "Runtime trenutno nema aktivan throughput signal. Pokreni benchmark ili OpenCode zahtev da bi se live tok/s pojavio.",
    }


def _build_telemetry_summary(
    *,
    history: list[dict[str, Any]],
    live_history: list[dict[str, Any]],
    live_current: dict[str, Any] | None,
    latest_history_metric: dict[str, Any] | None,
    recent_benchmark_fallback: dict[str, Any] | None,
    environment: dict[str, Any],
    live_state: dict[str, Any],
    active_run: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    recent_history = []
    for item in history:
        measured_at = _parse_iso_timestamp(item.get("measuredAt"))
        if measured_at is None:
            continue
        if (now - measured_at).total_seconds() > BENCHMARK_TELEMETRY_WINDOW_HOURS * 3600:
            continue
        recent_history.append(item)

    recent_live_tail = _collect_unfinalized_live_telemetry_tail(
        live_history=live_history,
        latest_history_metric=latest_history_metric,
        now=now,
    )

    input_24h_tokens = sum(_int_or_zero(item.get("promptTokens")) for item in recent_history) + sum(
        _int_or_zero(item.get("promptTokens")) for item in recent_live_tail
    )
    output_24h_tokens = sum(_int_or_zero(item.get("completionTokens")) for item in recent_history) + sum(
        _int_or_zero(item.get("completionTokens")) for item in recent_live_tail
    )
    total_24h_tokens = sum(_int_or_zero(item.get("totalTokens")) for item in recent_history) + sum(
        _int_or_zero(item.get("totalTokens")) for item in recent_live_tail
    )
    if total_24h_tokens <= 0:
        total_24h_tokens = input_24h_tokens + output_24h_tokens

    input_share_percent = round((input_24h_tokens / total_24h_tokens) * 100, 1) if total_24h_tokens > 0 else 0.0
    output_share_percent = round((output_24h_tokens / total_24h_tokens) * 100, 1) if total_24h_tokens > 0 else 0.0
    visible_live_metric = live_current
    last_signal_metric = live_current or recent_benchmark_fallback
    last_update_metric = last_signal_metric or latest_history_metric

    return {
        "windowHours": BENCHMARK_TELEMETRY_WINDOW_HOURS,
        "input24hTokens": input_24h_tokens,
        "output24hTokens": output_24h_tokens,
        "total24hTokens": total_24h_tokens,
        "estimatedCost24hUsd": round(
            (total_24h_tokens / 1_000_000.0) * BENCHMARK_PROXY_COST_PER_MILLION_TOKENS_USD,
            4,
        ),
        "activeRoutes": _int_or_zero((live_current or {}).get("activeRoutes")),
        "activeRoutesLabel": _active_routes_label(
            _int_or_zero((live_current or {}).get("activeRoutes")),
            environment,
            live_current,
        ),
        "liveNowTokensPerSecond": _metric_value(visible_live_metric, "totalTokensPerSecond")
        if visible_live_metric
        else None,
        "lastSignalTokensPerSecond": _metric_value(last_signal_metric, "totalTokensPerSecond")
        if last_signal_metric
        else None,
        "lastSignalLabel": str((last_signal_metric or {}).get("label", "") or ""),
        "lastSignalStateLabel": _last_signal_state_label(
            live_current=live_current,
            recent_benchmark_fallback=recent_benchmark_fallback,
        ),
        "lastSignalAt": str((last_signal_metric or {}).get("measuredAt", "") or ""),
        "flowState": _telemetry_flow_state(live_state)[0],
        "flowStateLabel": _telemetry_flow_state(live_state)[1],
        "flowStateReason": str(live_state.get("reason", "") or ""),
        "lastUpdate": str((last_update_metric or {}).get("measuredAt", "") or ""),
        "inputSharePercent": input_share_percent,
        "outputSharePercent": output_share_percent,
        "launchQueueSignal": _build_launch_queue_signal(active_run),
    }


def _collect_unfinalized_live_telemetry_tail(
    *,
    live_history: list[dict[str, Any]],
    latest_history_metric: dict[str, Any] | None,
    now: datetime,
) -> list[dict[str, Any]]:
    latest_history_measured_at = _parse_iso_timestamp((latest_history_metric or {}).get("measuredAt"))
    recent_live_tail: list[dict[str, Any]] = []
    for item in live_history:
        measured_at = _parse_iso_timestamp(item.get("measuredAt"))
        if measured_at is None:
            continue
        if (now - measured_at).total_seconds() > BENCHMARK_TELEMETRY_WINDOW_HOURS * 3600:
            continue
        if latest_history_measured_at is not None and measured_at <= latest_history_measured_at:
            continue
        recent_live_tail.append(item)
    return recent_live_tail


def _telemetry_flow_state(live_state: dict[str, Any]) -> tuple[str, str]:
    status = str(live_state.get("status", "") or "idle")
    if status == "active":
        return "active-generation", "active generation"
    if status == "warming":
        return "syncing", "syncing"
    if status == "recent-benchmark":
        return "recent-benchmark", "skorašnji benchmark"
    return "quiet", "quiet"


def _last_signal_state_label(
    *,
    live_current: dict[str, Any] | None,
    recent_benchmark_fallback: dict[str, Any] | None,
) -> str:
    if live_current is not None:
        return "aktivan live signal"
    if recent_benchmark_fallback is not None:
        return "skorašnji benchmark"
    return ""


def _recent_benchmark_fallback(
    latest_history_metric: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(latest_history_metric, dict):
        return None
    if _metric_value(latest_history_metric, "totalTokensPerSecond") is None:
        return None
    measured_at = _parse_iso_timestamp(latest_history_metric.get("measuredAt"))
    if measured_at is None:
        return None
    if (datetime.now(timezone.utc) - measured_at).total_seconds() > BENCHMARK_TELEMETRY_WINDOW_HOURS * 3600:
        return None
    return latest_history_metric


def _active_routes_label(
    active_routes: int,
    environment: dict[str, Any],
    sample: dict[str, Any] | None,
) -> str:
    if active_routes <= 0:
        return "Nema aktivnih ruta."
    route_label = str((sample or {}).get("label", "") or "live")
    return f"{environment['runtimeLabel']} / {environment['modelLabel']} / {route_label}"


def _build_launch_queue_signal(active_run: dict[str, Any]) -> dict[str, str]:
    status = str(active_run.get("status", "") or "idle")
    message = str(active_run.get("message", "") or "").strip()
    if status == "running":
        return {
            "status": "active",
            "label": "launch queue active",
            "summary": message or "Benchmark trenutno drži launch queue aktivnom.",
        }
    if status == "queued":
        return {
            "status": "waiting",
            "label": "launch queue waiting",
            "summary": message or "Benchmark čeka pokretanje i drži launch queue u redu čekanja.",
        }
    if status == "failed":
        return {
            "status": "attention",
            "label": "launch queue failed",
            "summary": message or "Poslednji benchmark launch nije uspeo.",
        }
    return {
        "status": "quiet",
        "label": "launch queue quiet",
        "summary": message or "Nema čekajućih benchmark launch zadataka.",
    }


def _runtime_label(runtime_name: str) -> str:
    return {
        "llama.cpp": "llama.cpp",
        "turboquant": "TurboQuant",
        "unknown": "unknown",
    }.get(runtime_name, runtime_name)


def _scenario_status_payload(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "scenarioId": str(item.get("id", "")),
            "scenarioName": str(item.get("name", "")),
            "status": "queued",
            "summary": "čeka pokretanje.",
        }
        for item in scenarios
    ]


def _normalize_repeat_count(value: object) -> int | None:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    if normalized < 1 or normalized > BENCHMARK_MAX_REPEAT_COUNT:
        return None
    return normalized


def _expand_battery_scenarios(
    scenarios: list[dict[str, Any]],
    repeat_count: int,
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for pass_index in range(1, repeat_count + 1):
        for scenario_index, scenario in enumerate(scenarios, start=1):
            copied = deepcopy(scenario)
            base_id = str(copied.get("id", "") or f"scenario-{scenario_index}")
            base_name = str(copied.get("name", "") or base_id)
            if repeat_count > 1:
                copied["id"] = f"{base_id}__pass_{pass_index}_of_{repeat_count}"
                copied["name"] = f"{base_name} · prolaz {pass_index}/{repeat_count}"
            copied["sourceScenarioId"] = base_id
            copied["sourceScenarioName"] = base_name
            copied["repeatIndex"] = pass_index
            copied["repeatCount"] = repeat_count
            expanded.append(copied)
    return expanded


def _build_battery_launch_message(battery_name: str, repeat_count: int) -> str:
    if repeat_count <= 1:
        return f"Pokrećem full battery: {battery_name}"
    return f"Pokrećem full battery x{repeat_count}: {battery_name}"


def _parse_iso_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _tokens_per_second(tokens: int, duration_ms: float | None) -> float | None:
    if tokens <= 0 or duration_ms is None or duration_ms <= 0:
        return None
    return round(tokens / (duration_ms / 1000.0), 2)


def _int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
