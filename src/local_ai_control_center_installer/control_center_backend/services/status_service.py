from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.network_service import (
    detect_tailscale_ip,
)
from local_ai_control_center_installer.runtime_bootstrap import (
    DEFAULT_MANAGED_RUNTIME_PORT,
    build_runtime_endpoint_base_url,
    load_runtime_endpoint_config,
)
from local_ai_control_center_installer.runtime_binary_health import (
    detect_missing_sidecar_imports,
)
from local_ai_control_center_installer.runtime_manifest import load_runtime_manifest
from local_ai_control_center_installer.turboquant import load_turboquant_manifest
from local_ai_control_center_installer.control_center_uninstall import (
    UNINSTALL_REGISTRY_KEY,
)


RUNTIME_SELECTION_FILE = "runtime-selection.json"
SUPPORTED_RUNTIMES = {"llama.cpp", "turboquant"}
LAUNCH_PROBE_SKIP_ENV = "LACC_SKIP_RUNTIME_LAUNCH_PROBE"
LAUNCH_PROBE_TIMEOUT_SECONDS = 5.0


def load_status_payload(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    runtime_state = load_runtime_state(config)
    turboquant_display = _build_turboquant_display(runtime_state)
    tailscale_ip = detect_tailscale_ip()
    tailscale_url = ""
    if config.access_mode == "tailscale" and tailscale_ip:
        tailscale_url = f"http://{tailscale_ip}:{config.ui_port}/"

    host_platform = platform.system().strip().lower() or "unknown"
    host_platform_label = {
        "windows": "Windows",
        "linux": "Linux",
        "darwin": "macOS",
    }.get(host_platform, host_platform.title())

    return {
        "hostPlatform": host_platform,
        "hostPlatformLabel": host_platform_label,
        "hostShellLabel": "PowerShell" if host_platform == "windows" else "Shell",
        "version": _detect_version(config),
        "health": "ok" if runtime_state["active_model"] != "unknown" else "unknown",
        "activeModel": runtime_state["active_model"],
        "profile": runtime_state["profile"],
        "uiPort": config.ui_port,
        "uiUrl": config.ui_url,
        "localUrl": config.ui_url,
        "tailscaleUrl": tailscale_url,
        "accessMode": config.access_mode,
        "bindHost": config.ui_host,
        "runtimeStatus": runtime_state["active_runtime"],
        "runtimeSummary": _build_runtime_summary(runtime_state),
        "activeRuntimeLabel": _runtime_label(runtime_state["active_runtime"]),
        "requestedRuntimeLabel": _runtime_label(runtime_state["requested_runtime"]),
        "runtimeSelectionSummary": runtime_state["runtime_selection_summary"],
        "runtimeSelectionSource": runtime_state["active_binary_source"],
        "availableRuntimes": _build_available_runtimes(runtime_state),
        "llamaRuntimeAvailable": runtime_state["llama_available"],
        "turboQuantRuntimeAvailable": runtime_state["turbo_available"],
        "llamaCppStatus": _build_runtime_install_status(
            available=bool(runtime_state["llama_available"]),
            installed=bool(runtime_state["llama_installed"]),
        ),
        "turboQuantStatus": _build_runtime_install_status(
            available=bool(runtime_state["turbo_available"]),
            installed=bool(runtime_state["turbo_installed"]),
        ),
        "turboQuantReason": runtime_state["turbo_reason"],
        "turboQuantDisplayState": turboquant_display["state"],
        "turboQuantSummary": turboquant_display["summary"],
        "turboQuantGuidance": turboquant_display["guidance"],
        "activeRuntimeBinary": runtime_state["active_binary"],
        "activeRuntimeBinarySource": runtime_state["active_binary_source"],
        "runtimeLiveStatus": runtime_state["runtime_live_status"],
        "runtimeLiveReason": runtime_state["runtime_live_reason"],
    }


def load_runtime_state(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    install_root = config.install_root

    active_model_payload = _read_json_file(install_root / "config" / "active-model.json")
    active_model_path = Path(str(active_model_payload.get("model_path", "") or "")).expanduser()
    active_model_id = str(active_model_payload.get("model_id", "unknown") or "unknown")
    active_model_label = active_model_path.name if active_model_path.name else str(
        active_model_id
    )

    endpoint_path = install_root / "config" / "runtime-endpoint.json"
    try:
        endpoint = load_runtime_endpoint_config(endpoint_path)
        port = endpoint.port
        base_url = endpoint.base_url
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        port = DEFAULT_MANAGED_RUNTIME_PORT
        base_url = build_runtime_endpoint_base_url(port)

    runtime_manifest = load_runtime_manifest()
    llama_relative = runtime_manifest["runtime_artifact"]["install_subdir"]
    llama_binary = install_root / llama_relative / "llama-server.exe"

    turbo_manifest = load_turboquant_manifest()
    turbo_artifact = turbo_manifest["turboquant_artifact"]
    turbo_launch = turbo_artifact["launch"]["executable_relative_path"]
    turbo_binary = install_root / turbo_artifact["install_subdir"] / turbo_launch

    llama_installed = llama_binary.is_file()
    turbo_installed = turbo_binary.is_file()
    llama_available, llama_reason = probe_runtime_binary_launchable(llama_binary)
    turbo_available, turbo_reason = probe_runtime_binary_launchable(turbo_binary)
    selection_state = _resolve_selected_runtime(
        config,
        llama_available=llama_available,
        turbo_available=turbo_available,
        active_model_id=active_model_id,
        active_model_path=active_model_path,
        llama_binary=llama_binary,
        turbo_binary=turbo_binary,
    )
    requested_runtime = selection_state["requested_runtime"]
    selection_source = selection_state["selection_source"]
    active_runtime = selection_state["active_runtime"]
    runtime_selection_summary = selection_state["selection_summary"]

    active_binary = ""
    if active_runtime == "llama.cpp" and llama_available:
        active_binary = str(llama_binary)
    elif active_runtime == "turboquant" and turbo_available:
        active_binary = str(turbo_binary)

    active_binary_path = (
        Path(active_binary)
        if active_binary
        else (llama_binary if active_runtime == "llama.cpp" else turbo_binary)
    )
    active_model_supported, active_model_reason = classify_runtime_model_support(
        model_id=active_model_id,
        model_path=active_model_path,
        runtime_name=active_runtime,
        runtime_binary_path=active_binary_path,
    )

    health_status = probe_server_health(base_url)
    runtime_pid = find_runtime_pid(port)
    runtime_live_status, runtime_live_reason = _build_runtime_live_signal(
        health_status,
        runtime_pid,
    )
    if not active_model_supported and runtime_pid is None:
        runtime_live_status = "stopped"
        runtime_live_reason = active_model_reason

    return {
        "install_root": install_root,
        "profile": _load_profile(config),
        "active_model": active_model_label or "unknown",
        "active_model_id": active_model_id,
        "active_model_path": str(active_model_path) if active_model_path else "",
        "active_model_supported": active_model_supported,
        "active_model_reason": active_model_reason,
        "port": port,
        "base_url": base_url,
        "llama_binary": str(llama_binary),
        "turbo_binary": str(turbo_binary),
        "llama_installed": llama_installed,
        "turbo_installed": turbo_installed,
        "llama_available": llama_available,
        "turbo_available": turbo_available,
        "requested_runtime": requested_runtime,
        "active_runtime": active_runtime,
        "runtime_selection_summary": runtime_selection_summary,
        "active_binary": active_binary,
        "active_binary_source": selection_source,
        "runtime_live_status": runtime_live_status,
        "runtime_live_reason": runtime_live_reason,
        "llama_reason": llama_reason,
        "turbo_reason": turbo_reason,
    }


def classify_runtime_model_support(
    *,
    model_id: str,
    model_path: Path | str,
    runtime_name: str = "llama.cpp",
    runtime_binary_path: Path | str | None = None,
) -> tuple[bool, str]:
    resolved_path = model_path if isinstance(model_path, Path) else Path(str(model_path or ""))
    normalized_runtime = str(runtime_name or "").strip().lower() or "llama.cpp"
    if _is_mtp_model(model_id=model_id, model_path=resolved_path):
        if normalized_runtime == "turboquant":
            return (
                False,
                "TurboQuant runtime trenutno ne podržava MTP GGUF aktivaciju. Koristi llama.cpp draft-mtp put.",
            )
        runtime_binary = (
            runtime_binary_path if isinstance(runtime_binary_path, Path) else Path(str(runtime_binary_path or ""))
        )
        if not runtime_binary.is_file():
            return (
                False,
                "llama.cpp runtime binar za MTP put nije pronađen.",
            )
        if not runtime_supports_draft_mtp(runtime_binary):
            return (
                False,
                "Aktivni llama.cpp runtime trenutno nema draft-mtp podršku za MTP GGUF model.",
            )
        return True, "MTP model je spreman za llama.cpp draft-mtp runtime put."
    return True, ""


def runtime_supports_draft_mtp(binary_path: Path | str) -> bool:
    resolved = binary_path if isinstance(binary_path, Path) else Path(str(binary_path or ""))
    if not resolved.is_file():
        return False
    try:
        stat = resolved.stat()
    except OSError:
        return False
    return _runtime_supports_draft_mtp_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=16)
def _runtime_supports_draft_mtp_cached(
    binary_path: str,
    file_size: int,
    file_mtime_ns: int,
) -> bool:
    del file_size
    del file_mtime_ns
    resolved = Path(binary_path)
    if detect_missing_sidecar_imports(resolved):
        return False
    completed = subprocess.run(
        [str(resolved), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        return False
    output = f"{completed.stdout}\n{completed.stderr}".lower()
    return "--spec-type" in output and "draft-mtp" in output


def probe_server_health(base_url: str) -> str:
    try:
        with urlopen(f"{base_url}/health", timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 503:
            return "loading"
        return "offline"
    except (URLError, TimeoutError, OSError):
        return "offline"
    except (ValueError, json.JSONDecodeError):
        return "offline"

    if payload.get("status") == "ok":
        return "ready"
    return "offline"


def find_runtime_pid(port: int) -> int | None:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None

    expected_local_address = f"127.0.0.1:{port}".lower()
    for raw_line in result.stdout.splitlines():
        columns = raw_line.split()
        if len(columns) < 5 or columns[0].upper() != "TCP":
            continue
        local_address = columns[1].lower()
        state = columns[3].upper()
        pid_raw = columns[4]
        if local_address != expected_local_address or state != "LISTENING":
            continue
        try:
            return int(pid_raw)
        except ValueError:
            return None
    return None


def probe_runtime_binary_launchable(binary_path: Path) -> tuple[bool, str]:
    runtime_label = _runtime_label_from_path(binary_path)
    if not binary_path.is_file():
        return False, f"{runtime_label} runtime nije instaliran."
    if os.environ.get(LAUNCH_PROBE_SKIP_ENV) == "1":
        return True, f"{runtime_label} launch probe je preskocen."

    missing_sidecars = detect_missing_sidecar_imports(binary_path)
    if missing_sidecars:
        missing_labels = ", ".join(missing_sidecars)
        return (
            False,
            f"{runtime_label} launch probe failed: missing sidecar DLLs: {missing_labels}.",
        )

    try:
        completed = subprocess.run(
            [str(binary_path), "--version"],
            cwd=str(binary_path.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=LAUNCH_PROBE_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"{runtime_label} launch probe failed: timeout."
    except OSError as exc:
        return False, f"{runtime_label} launch probe failed: {exc}."

    if completed.returncode == 0:
        return True, f"{runtime_label} runtime je instaliran i spreman."

    detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
    return False, f"{runtime_label} launch probe failed: {detail}."


def is_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _resolve_selected_runtime(
    config: ControlCenterConfig,
    *,
    llama_available: bool,
    turbo_available: bool,
    active_model_id: str,
    active_model_path: Path,
    llama_binary: Path,
    turbo_binary: Path,
) -> dict[str, str]:
    selection_payload = _read_json_file(
        config.control_center_config_root / RUNTIME_SELECTION_FILE
    )
    requested = str(selection_payload.get("runtime", "") or "").strip().lower()
    defaulted = requested not in SUPPORTED_RUNTIMES
    if requested not in SUPPORTED_RUNTIMES:
        requested = "llama.cpp"
        source = "default"
    else:
        source = "selection"

    active_runtime = requested
    selection_summary = f"Koristi se izabrani runtime: {_runtime_label(requested)}."

    requested_available = turbo_available if requested == "turboquant" else llama_available
    requested_binary = turbo_binary if requested == "turboquant" else llama_binary
    requested_supports, requested_reason = _runtime_candidate_supports_model(
        runtime_name=requested,
        available=requested_available,
        binary_path=requested_binary,
        model_id=active_model_id,
        model_path=active_model_path,
    )
    alternate = "llama.cpp" if requested == "turboquant" else "turboquant"
    alternate_available = llama_available if alternate == "llama.cpp" else turbo_available
    alternate_binary = llama_binary if alternate == "llama.cpp" else turbo_binary
    alternate_supports, alternate_reason = _runtime_candidate_supports_model(
        runtime_name=alternate,
        available=alternate_available,
        binary_path=alternate_binary,
        model_id=active_model_id,
        model_path=active_model_path,
    )

    if requested_supports:
        return {
            "requested_runtime": requested,
            "active_runtime": active_runtime,
            "selection_source": source,
            "selection_summary": selection_summary,
        }

    if alternate_supports:
        active_runtime = alternate
        source = "fallback"
        if _is_mtp_model(model_id=active_model_id, model_path=active_model_path):
            selection_summary = (
                f"Izabrani runtime {_runtime_label(requested)} ne podržava MTP GGUF aktivaciju, "
                f"pa se koristi {_runtime_label(alternate)} draft-mtp put."
            )
        elif requested == "turboquant":
            selection_summary = "Izabrani runtime TurboQuant trenutno nije dostupan, pa se koristi llama.cpp."
        elif defaulted:
            selection_summary = "Runtime nije bio eksplicitno izabran; llama.cpp nije dostupan, pa se koristi TurboQuant."
        else:
            selection_summary = "Izabrani runtime llama.cpp trenutno nije dostupan, pa se koristi TurboQuant."
    else:
        selection_summary = requested_reason or alternate_reason or selection_summary

    return {
        "requested_runtime": requested,
        "active_runtime": active_runtime,
        "selection_source": source,
        "selection_summary": selection_summary,
    }


def _runtime_candidate_supports_model(
    *,
    runtime_name: str,
    available: bool,
    binary_path: Path,
    model_id: str,
    model_path: Path,
) -> tuple[bool, str]:
    if not available:
        return False, f"{_runtime_label(runtime_name)} trenutno nije dostupan."
    return classify_runtime_model_support(
        model_id=model_id,
        model_path=model_path,
        runtime_name=runtime_name,
        runtime_binary_path=binary_path,
    )


def _is_mtp_model(*, model_id: str, model_path: Path | str) -> bool:
    resolved_path = model_path if isinstance(model_path, Path) else Path(str(model_path or ""))
    joined = " ".join(
        part
        for part in [
            str(model_id or ""),
            resolved_path.name,
            str(resolved_path.parent.name or ""),
        ]
        if part
    ).lower()
    return "mtp" in joined


def _build_runtime_live_signal(
    health_status: str,
    runtime_pid: int | None,
) -> tuple[str, str]:
    if health_status == "ready":
        return "started", "Runtime health endpoint odgovara."
    if health_status == "loading":
        return "warming", "Runtime odgovara, ali model se još učitava."
    if runtime_pid is not None:
        return "degraded", "Runtime proces postoji, ali health endpoint ne odgovara."
    return "stopped", "Runtime trenutno nije pokrenut."


def _build_runtime_summary(runtime_state: dict[str, object]) -> str:
    parts = [f"Aktivan runtime: {_runtime_label(str(runtime_state['active_runtime']))}"]
    requested_runtime = str(runtime_state.get("requested_runtime", "") or "")
    if requested_runtime and requested_runtime != runtime_state["active_runtime"]:
        parts.append(f"Izabrani runtime: {_runtime_label(requested_runtime)}")
    elif str(runtime_state.get("active_binary_source", "") or "") == "selection":
        parts.append(f"Izabrani runtime: {_runtime_label(requested_runtime or str(runtime_state['active_runtime']))}")
    if runtime_state["llama_available"]:
        parts.append("llama.cpp dostupan")
    if runtime_state["turbo_available"]:
        parts.append("TurboQuant dostupan")
    if not runtime_state["llama_available"] and not runtime_state["turbo_available"]:
        parts.append("nema potvrde o dostupnom runtime-u")
    selection_summary = str(runtime_state.get("runtime_selection_summary", "") or "").strip()
    if selection_summary and str(runtime_state.get("active_binary_source", "") or "") in {"fallback", "default"}:
        parts.append(selection_summary)
    return " | ".join(parts)


def _build_available_runtimes(runtime_state: dict[str, object]) -> list[str]:
    runtimes: list[str] = []
    if runtime_state["llama_available"]:
        runtimes.append("llama.cpp")
    if runtime_state["turbo_available"]:
        runtimes.append("TurboQuant")
    return runtimes


def _runtime_label(runtime_name: str) -> str:
    return {
        "llama.cpp": "llama.cpp",
        "turboquant": "TurboQuant",
        "unknown": "unknown",
    }.get(runtime_name, runtime_name)


def _runtime_label_from_path(binary_path: Path) -> str:
    normalized = str(binary_path).lower()
    if "turboquant" in normalized:
        return "TurboQuant"
    return "llama.cpp"


def _build_runtime_install_status(*, available: bool, installed: bool) -> str:
    if available:
        return "ready"
    if installed:
        return "failed"
    return "missing"


def _build_turboquant_display(runtime_state: dict[str, object]) -> dict[str, str]:
    turbo_available = bool(runtime_state.get("turbo_available"))
    turbo_installed = bool(runtime_state.get("turbo_installed"))
    turbo_reason = str(runtime_state.get("turbo_reason", "") or "").strip()

    if turbo_available:
        return {
            "state": "available",
            "summary": "TurboQuant je dostupan za aktivaciju.",
            "guidance": "Možeš ga aktivirati kada želiš manji memorijski pritisak ili TurboQuant-specifične presete.",
        }

    if turbo_installed:
        guidance = "Panel koristi llama.cpp dok TurboQuant ne dobije ispravne runtime zavisnosti."
        if "missing sidecar dlls" in turbo_reason.lower():
            guidance = (
                "Panel koristi llama.cpp dok TurboQuant ne dobije nedostajuće DLL fajlove."
            )
        return {
            "state": "disabled",
            "summary": "TurboQuant trenutno nije dostupan na ovoj instalaciji.",
            "guidance": guidance,
        }

    return {
        "state": "missing",
        "summary": "TurboQuant nije instaliran u ovom okruženju.",
        "guidance": "Panel koristi llama.cpp dok TurboQuant ne bude dodat kroz installer ili repair tok.",
    }


def _load_profile(config: ControlCenterConfig) -> str:
    payload = _read_json_file(
        config.control_center_config_root / "settings.json"
    )
    return str(payload.get("profile", "balanced") or "balanced")


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _detect_version(config: ControlCenterConfig | None = None) -> str:
    report_version = _read_version_from_install_report((config or get_config()).install_root)
    if report_version:
        return report_version

    installed_version = _query_windows_display_version()
    if installed_version:
        return installed_version

    try:
        return package_version("local-ai-control-center-installer")
    except PackageNotFoundError:
        pass

    return "unknown"


def _query_windows_display_version() -> str | None:
    completed = subprocess.run(
        [
            "reg",
            "query",
            UNINSTALL_REGISTRY_KEY,
            "/v",
            "DisplayVersion",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        return None

    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line or "DisplayVersion" not in line:
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "DisplayVersion":
            return parts[-1].strip()
    return None


def _read_version_from_install_report(install_root: Path) -> str | None:
    payload = _read_json_file(install_root / "logs" / "install-report.json")
    for key in ("product_version", "version", "display_version"):
        value = str(payload.get(key, "") or "").strip()
        if value:
            return value
    return None
