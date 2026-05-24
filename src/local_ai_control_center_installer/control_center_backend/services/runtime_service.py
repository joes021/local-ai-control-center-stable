from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    start_server,
    stop_server,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    RUNTIME_SELECTION_FILE,
    find_runtime_pid,
    load_runtime_state,
)


def select_runtime(
    runtime_name: str,
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    normalized = str(runtime_name or "").strip().lower()
    if normalized not in {"llama.cpp", "turboquant"}:
        return _result("error", "select-runtime", f"Nepoznat runtime: {runtime_name}")

    runtime_state = load_runtime_state(config)
    if normalized == "turboquant" and not runtime_state["turbo_available"]:
        reason = str(runtime_state.get("turbo_reason", "") or "").strip()
        if runtime_state.get("turbo_installed"):
            summary = (
                "TurboQuant ne moze da se aktivira jer runtime ne moze uspesno da se pokrene."
            )
            if reason:
                summary = f"{summary} {reason}"
            return _result("error", "select-runtime", summary)
        return _result(
            "error",
            "select-runtime",
            "TurboQuant ne moze da se aktivira jer runtime nije instaliran.",
        )
    if normalized == "llama.cpp" and not runtime_state["llama_available"]:
        return _result(
            "error",
            "select-runtime",
            "llama.cpp ne moze da se aktivira jer runtime nije instaliran.",
        )

    selection_path = config.control_center_config_root / RUNTIME_SELECTION_FILE
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    previous_selection = _snapshot_selection_file(selection_path)
    selection_path.write_text(
        json.dumps({"runtime": normalized}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if find_runtime_pid(int(runtime_state["port"])) is not None:
        stop_result = stop_server(config)
        if stop_result.get("status") != "ok":
            _restore_selection_file(selection_path, previous_selection)
            return stop_result
        start_result = start_server(config)
        if start_result.get("status") != "ok":
            _restore_selection_file(selection_path, previous_selection)
            restore_result = start_server(config)
            if restore_result.get("status") == "ok":
                return _result(
                    "error",
                    "select-runtime",
                    f"{start_result.get('summary', 'Novi runtime nije uspeo da se pokrene.')} Aktivni runtime izbor je vracen i prethodni runtime je ponovo pokrenut.",
                )
            return _result(
                "error",
                "select-runtime",
                f"{start_result.get('summary', 'Novi runtime nije uspeo da se pokrene.')} Aktivni runtime izbor je vracen, ali prethodni runtime nije mogao automatski da se vrati.",
            )

    chosen_label = "TurboQuant" if normalized == "turboquant" else "llama.cpp"
    return _result("ok", "select-runtime", f"Aktiviran runtime: {chosen_label}")


def _snapshot_selection_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _restore_selection_file(path: Path, snapshot: dict[str, Any] | None) -> None:
    if snapshot is None:
        try:
            path.unlink()
        except OSError:
            pass
        return
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def _result(status: str, action: str, summary: str) -> dict[str, object]:
    return {
        "status": status,
        "action": action,
        "summary": summary,
        "details": {
            "returncode": 0 if status == "ok" else 1,
            "stdout": summary if status == "ok" else "",
            "stderr": "" if status == "ok" else summary,
        },
    }
