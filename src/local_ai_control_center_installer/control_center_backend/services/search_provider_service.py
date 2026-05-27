from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote_plus, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    LEGACY_DEFAULT_WEB_SEARCH_BASE_URL,
    ALLOWED_WEB_SEARCH_PROVIDERS,
    load_effective_settings_state,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    action_result,
    atomic_write_json,
    read_json_object,
)
from local_ai_control_center_installer.platform_paths import is_windows_platform


MANAGED_SEARXNG_PORT = 18083
MANAGED_SEARXNG_BASE_URL = f"http://127.0.0.1:{MANAGED_SEARXNG_PORT}/search"
SEARCH_PROVIDER_HEALTH_TIMEOUT_SECONDS = 3.0
WSL_BOOTSTRAP_PROBE_TIMEOUT_SECONDS = 5
BOOTSTRAP_CAPABILITY_CACHE_TTL_SECONDS = 60.0
_BOOTSTRAP_CAPABILITY_CACHE: dict[str, Any] = {}


def load_search_provider_state(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    payload = read_json_object(config.search_provider_state_path)
    managed = payload.get("managed")
    if not isinstance(managed, dict):
        managed = {}
    return {
        "managed": {
            "enabled": bool(managed.get("enabled", False)),
            "baseUrl": str(managed.get("baseUrl", "") or ""),
            "distro": str(managed.get("distro", "") or ""),
            "port": int(managed.get("port", MANAGED_SEARXNG_PORT) or MANAGED_SEARXNG_PORT),
            "repoPath": str(managed.get("repoPath", "") or ""),
            "venvPath": str(managed.get("venvPath", "") or ""),
            "settingsPath": str(managed.get("settingsPath", "") or ""),
            "logPath": str(managed.get("logPath", "") or ""),
            "pidPath": str(managed.get("pidPath", "") or ""),
            "lastBootstrapAt": str(managed.get("lastBootstrapAt", "") or ""),
            "lastBootstrapStatus": str(managed.get("lastBootstrapStatus", "") or ""),
            "lastBootstrapMessage": str(managed.get("lastBootstrapMessage", "") or ""),
        }
    }


def resolve_search_provider_target(
    config: ControlCenterConfig | None = None,
    *,
    provider_override: str | None = None,
) -> dict[str, str]:
    config = config or get_config()
    settings = load_effective_settings_state(config)
    provider = resolve_search_provider(config, provider_override=provider_override)
    state = load_search_provider_state(config)
    managed = state["managed"]
    manual_url = str(settings.get("webSearchBaseUrl", "") or "").strip()
    managed_url = str(managed.get("baseUrl", "") or "").strip() if managed.get("enabled") else ""

    if provider == "duckduckgo":
        return {
            "provider": provider,
            "source": "public-web",
            "configuredBaseUrl": "",
            "effectiveBaseUrl": "",
        }

    if manual_url and not _is_legacy_default_url(manual_url):
        return {
            "provider": provider,
            "source": "manual",
            "configuredBaseUrl": manual_url,
            "effectiveBaseUrl": manual_url,
        }
    if managed_url:
        return {
            "provider": provider,
            "source": "managed",
            "configuredBaseUrl": manual_url,
            "effectiveBaseUrl": managed_url,
        }
    if manual_url:
        return {
            "provider": provider,
            "source": "legacy-default" if _is_legacy_default_url(manual_url) else "manual",
            "configuredBaseUrl": manual_url,
            "effectiveBaseUrl": manual_url,
        }
    return {
        "provider": provider,
        "source": "none",
        "configuredBaseUrl": "",
        "effectiveBaseUrl": "",
    }


def resolve_search_provider(
    config: ControlCenterConfig | None = None,
    *,
    provider_override: str | None = None,
) -> str:
    config = config or get_config()
    settings = load_effective_settings_state(config)
    candidate = str(
        provider_override
        or settings.get("webSearchProvider", "searxng")
        or "searxng"
    ).strip().lower()
    if candidate not in ALLOWED_WEB_SEARCH_PROVIDERS:
        return "searxng"
    return candidate


def load_search_provider_status(
    config: ControlCenterConfig | None = None,
    *,
    provider_override: str | None = None,
    opener: Callable[..., Any] = urlopen,
    command_runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    config = config or get_config()
    state = load_search_provider_state(config)
    provider = resolve_search_provider(config, provider_override=provider_override)
    target = resolve_search_provider_target(config, provider_override=provider)

    if provider == "duckduckgo":
        return _build_status_payload(
            status="healthy",
            label="DuckDuckGo spreman",
            summary="DuckDuckGo public web search je spreman bez API ključa. Rezultati koriste best-effort HTML integraciju.",
            provider=provider,
            provider_label="DuckDuckGo",
            source="public-web",
            configured_base_url="",
            effective_base_url="https://html.duckduckgo.com/html/",
            service_label="DuckDuckGo HTML",
            can_query=True,
            can_bootstrap=False,
            state=state,
            bootstrap={"reason": "Managed bootstrap nije potreban za DuckDuckGo."},
        )

    bootstrap = _describe_bootstrap_capability(command_runner)

    if not target["effectiveBaseUrl"]:
        last_bootstrap_status = str(state["managed"].get("lastBootstrapStatus", "") or "")
        if last_bootstrap_status == "bootstrap-blocked":
            return _build_status_payload(
                status="bootstrap-blocked",
                label=_status_label("bootstrap-blocked", provider),
                summary=f"SearxNG nije podešen. Managed bootstrap je blokiran: {state['managed'].get('lastBootstrapMessage', '')}",
                provider=provider,
                provider_label="SearxNG",
                source=target["source"],
                configured_base_url=target["configuredBaseUrl"],
                effective_base_url="",
                service_label="",
                can_query=False,
                can_bootstrap=False,
                state=state,
                bootstrap=bootstrap,
            )
        if not bootstrap["available"]:
            return _build_status_payload(
                status="not-configured",
                label=_status_label("not-configured", provider),
                summary=f"SearxNG nije podešen. Managed bootstrap trenutno nije dostupan: {bootstrap['reason']}",
                provider=provider,
                provider_label="SearxNG",
                source=target["source"],
                configured_base_url=target["configuredBaseUrl"],
                effective_base_url="",
                service_label="",
                can_query=False,
                can_bootstrap=False,
                state=state,
                bootstrap=bootstrap,
            )
        return _build_status_payload(
            status="not-configured",
            label=_status_label("not-configured", provider),
            summary="SearxNG nije podešen. Pokreni Setup local SearxNG ili unesi ručni base URL.",
            provider=provider,
            provider_label="SearxNG",
            source=target["source"],
            configured_base_url=target["configuredBaseUrl"],
            effective_base_url="",
            service_label="",
            can_query=False,
            can_bootstrap=bootstrap["available"],
            state=state,
            bootstrap=bootstrap,
        )

    probe = _probe_search_endpoint(target["effectiveBaseUrl"], opener=opener)
    if target["source"] == "legacy-default" and probe["status"] == "unreachable":
        return _build_status_payload(
            status="not-configured",
            label=_status_label("not-configured", provider),
            summary="Legacy 127.0.0.1:8080 više se ne smatra podrazumevanim SearxNG endpointom. Pokreni Setup local SearxNG ili unesi pravi base URL.",
            provider=provider,
            provider_label="SearxNG",
            source=target["source"],
            configured_base_url=target["configuredBaseUrl"],
            effective_base_url=target["effectiveBaseUrl"],
            service_label="",
            can_query=False,
            can_bootstrap=bootstrap["available"],
            state=state,
            bootstrap=bootstrap,
        )

    return _build_status_payload(
        status=str(probe["status"]),
        label=_status_label(str(probe["status"]), provider),
        summary=str(probe["summary"]),
        provider=provider,
        provider_label="SearxNG",
        source=target["source"],
        configured_base_url=target["configuredBaseUrl"],
        effective_base_url=target["effectiveBaseUrl"],
        service_label=str(probe.get("serviceLabel", "") or ""),
        can_query=str(probe["status"]) == "healthy",
        can_bootstrap=bootstrap["available"],
        state=state,
        bootstrap=bootstrap,
    )


def bootstrap_search_provider(
    config: ControlCenterConfig | None = None,
    *,
    provider_override: str | None = None,
    command_runner: Callable[..., Any] = subprocess.run,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    config = config or get_config()
    provider = resolve_search_provider(config, provider_override=provider_override)
    if provider != "searxng":
        return {
            "result": action_result(
                "error",
                "bootstrap-search-provider",
                "Managed bootstrap je trenutno podržan samo za SearxNG provider.",
                stderr="Managed bootstrap je trenutno podržan samo za SearxNG provider.",
            ),
            "providerStatus": load_search_provider_status(
                config,
                provider_override=provider,
                opener=opener,
                command_runner=command_runner,
            ),
        }
    state = load_search_provider_state(config)
    bootstrap = _describe_bootstrap_capability(command_runner, refresh=True)
    if not bootstrap["available"]:
        _write_search_provider_state(
            config,
            {
                "managed": {
                    **state["managed"],
                    "enabled": False,
                    "lastBootstrapAt": _now_iso(),
                    "lastBootstrapStatus": "bootstrap-blocked",
                    "lastBootstrapMessage": str(bootstrap["reason"]),
                }
            },
        )
        return {
            "result": action_result(
                "error",
                "bootstrap-search-provider",
                f"Managed SearxNG bootstrap je blokiran: {bootstrap['reason']}",
                stderr=str(bootstrap["reason"]),
            ),
            "providerStatus": load_search_provider_status(
                config,
                provider_override=provider,
                opener=opener,
                command_runner=command_runner,
            ),
        }

    managed_metadata = _managed_metadata(bootstrap["distro"])
    script_path = _write_bootstrap_script(managed_metadata)
    wsl_script_path = _windows_path_to_wsl_path(script_path)
    try:
        completed = command_runner(
            ["wsl", "-d", managed_metadata["distro"], "bash", wsl_script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            check=False,
        )
    except FileNotFoundError as exc:
        completed = None
        failure_message = str(exc)
    else:
        failure_message = ""
    finally:
        try:
            script_path.unlink()
        except OSError:
            pass

    if completed is None or completed.returncode != 0:
        stderr = _condense_bootstrap_output(
            failure_message or getattr(completed, "stderr", "") or getattr(completed, "stdout", "")
        )
        _write_search_provider_state(
            config,
            {
                "managed": {
                    **state["managed"],
                    **managed_metadata,
                    "enabled": False,
                    "lastBootstrapAt": _now_iso(),
                    "lastBootstrapStatus": "error",
                    "lastBootstrapMessage": stderr,
                }
            },
        )
        return {
            "result": action_result(
                "error",
                "bootstrap-search-provider",
                f"Managed SearxNG bootstrap nije uspeo: {stderr}",
                stderr=stderr,
            ),
            "providerStatus": load_search_provider_status(
                config,
                provider_override=provider,
                opener=opener,
                command_runner=command_runner,
            ),
        }

    _write_search_provider_state(
        config,
        {
            "managed": {
                **state["managed"],
                **managed_metadata,
                "enabled": True,
                "lastBootstrapAt": _now_iso(),
                "lastBootstrapStatus": "ok",
                "lastBootstrapMessage": "Managed SearxNG bootstrap je završen.",
            }
        },
    )
    provider_status = load_search_provider_status(
        config,
        provider_override=provider,
        opener=opener,
        command_runner=command_runner,
    )
    if provider_status["status"] != "healthy":
        _write_search_provider_state(
            config,
            {
                "managed": {
                    **load_search_provider_state(config)["managed"],
                    "enabled": False,
                    "lastBootstrapAt": _now_iso(),
                    "lastBootstrapStatus": "error",
                    "lastBootstrapMessage": str(provider_status["summary"]),
                }
            },
        )
        provider_status = load_search_provider_status(
            config,
            provider_override=provider,
            opener=opener,
            command_runner=command_runner,
        )
        return {
            "result": action_result(
                "error",
                "bootstrap-search-provider",
                f"Managed SearxNG bootstrap nije dao zdrav JSON endpoint: {provider_status['summary']}",
                stderr=str(provider_status["summary"]),
            ),
            "providerStatus": provider_status,
        }

    return {
        "result": action_result(
            "ok",
            "bootstrap-search-provider",
            "Managed SearxNG je podignut i provereno vraća JSON pretragu.",
            stdout="Managed SearxNG je podignut i provereno vraća JSON pretragu.",
        ),
        "providerStatus": provider_status,
    }


def _probe_search_endpoint(
    base_url: str,
    *,
    opener: Callable[..., Any],
) -> dict[str, str]:
    request_url = _build_probe_request_url(base_url)
    request = Request(request_url, headers={"Accept": "application/json"}, method="GET")
    try:
        with opener(request, timeout=SEARCH_PROVIDER_HEALTH_TIMEOUT_SECONDS) as response:
            raw_text = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        service_label = _detect_service_label(body)
        if service_label:
            return {
                "status": "wrong-service",
                "summary": f"Na adresi radi drugi servis: {service_label}.",
                "serviceLabel": service_label,
            }
        return {
            "status": "error",
            "summary": f"SearxNG endpoint je vratio HTTP {exc.code}.",
            "serviceLabel": "",
        }
    except (OSError, URLError, TimeoutError) as exc:
        return {
            "status": "unreachable",
            "summary": f"SearxNG endpoint nije dostupan: {exc}",
            "serviceLabel": "",
        }

    normalized_text = raw_text.lstrip("\ufeff").strip()
    if not normalized_text:
        return {
            "status": "error",
            "summary": "SearxNG endpoint je odgovorio praznim telom umesto JSON-a.",
            "serviceLabel": "",
        }
    try:
        payload = json.loads(normalized_text)
    except json.JSONDecodeError:
        service_label = _detect_service_label(normalized_text)
        if service_label:
            return {
                "status": "wrong-service",
                "summary": f"Na adresi radi drugi servis: {service_label}.",
                "serviceLabel": service_label,
            }
        snippet = normalized_text[:120].replace("\r", " ").replace("\n", " ")
        return {
            "status": "error",
            "summary": f"SearxNG endpoint nije vratio JSON odgovor. Primer: {snippet}",
            "serviceLabel": "",
        }

    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return {
            "status": "healthy",
            "summary": "SearxNG vraća validan JSON odgovor i spreman je za upit.",
            "serviceLabel": "SearxNG",
        }
    return {
        "status": "error",
        "summary": "SearxNG endpoint je odgovorio JSON-om, ali ne u ocekivanom search formatu.",
        "serviceLabel": "",
    }


def _describe_bootstrap_capability(
    command_runner: Callable[..., Any],
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    if not refresh:
        cached = _load_cached_bootstrap_capability()
        if cached is not None:
            return cached

    if not is_windows_platform():
        result = {
            "available": False,
            "reason": "Managed bootstrap je trenutno podržan samo na Windows + WSL putu.",
            "distro": "",
        }
        _store_cached_bootstrap_capability(result)
        return result
    try:
        completed = command_runner(
            ["wsl", "-l", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=WSL_BOOTSTRAP_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        result = {
            "available": False,
            "reason": "WSL nije instaliran ili wsl.exe nije dostupan.",
            "distro": "",
        }
        _store_cached_bootstrap_capability(result)
        return result
    except subprocess.TimeoutExpired:
        result = {
            "available": False,
            "reason": "WSL trenutno ne odgovara na proveru distro liste.",
            "distro": "",
        }
        _store_cached_bootstrap_capability(result)
        return result
    if getattr(completed, "returncode", 1) != 0:
        stderr = _condense_bootstrap_output(
            getattr(completed, "stderr", "") or getattr(completed, "stdout", "")
        )
        result = {
            "available": False,
            "reason": f"WSL nije spreman: {stderr}",
            "distro": "",
        }
        _store_cached_bootstrap_capability(result)
        return result
    distros = [
        _sanitize_wsl_text(line).lstrip("*").strip()
        for line in str(getattr(completed, "stdout", "") or "").splitlines()
        if _sanitize_wsl_text(line).strip()
    ]
    if not distros:
        result = {
            "available": False,
            "reason": "Nije pronađen nijedan WSL distro za managed SearxNG bootstrap.",
            "distro": "",
        }
        _store_cached_bootstrap_capability(result)
        return result
    chosen = next((item for item in distros if item.lower() == "ubuntu"), distros[0])
    result = {
        "available": True,
        "reason": f"WSL distro {chosen} je dostupan za managed bootstrap.",
        "distro": chosen,
    }
    _store_cached_bootstrap_capability(result)
    return result


def _load_cached_bootstrap_capability() -> dict[str, Any] | None:
    expires_at = float(_BOOTSTRAP_CAPABILITY_CACHE.get("expiresAt", 0.0) or 0.0)
    value = _BOOTSTRAP_CAPABILITY_CACHE.get("value")
    if not isinstance(value, dict):
        return None
    if time.monotonic() >= expires_at:
        _BOOTSTRAP_CAPABILITY_CACHE.clear()
        return None
    return dict(value)


def _store_cached_bootstrap_capability(value: dict[str, Any]) -> None:
    _BOOTSTRAP_CAPABILITY_CACHE.clear()
    _BOOTSTRAP_CAPABILITY_CACHE.update(
        {
            "expiresAt": time.monotonic() + BOOTSTRAP_CAPABILITY_CACHE_TTL_SECONDS,
            "value": dict(value),
        }
    )


def _build_status_payload(
    *,
    status: str,
    label: str,
    summary: str,
    provider: str,
    provider_label: str,
    source: str,
    configured_base_url: str,
    effective_base_url: str,
    service_label: str,
    can_query: bool,
    can_bootstrap: bool,
    state: dict[str, Any],
    bootstrap: dict[str, Any],
) -> dict[str, Any]:
    return {
        "provider": provider,
        "providerLabel": provider_label,
        "status": status,
        "label": label,
        "summary": summary,
        "source": source,
        "configuredBaseUrl": configured_base_url,
        "effectiveBaseUrl": effective_base_url,
        "serviceLabel": service_label,
        "canQuery": can_query,
        "canBootstrap": can_bootstrap,
        "bootstrapSummary": str(bootstrap.get("reason", "") or ""),
        "managed": dict(state.get("managed", {})),
    }


def _status_label(value: str, provider: str) -> str:
    if provider == "duckduckgo":
        return {
            "healthy": "DuckDuckGo spreman",
            "error": "DuckDuckGo greška",
        }.get(value, value)
    return {
        "not-configured": "SearxNG nije podešen",
        "healthy": "SearxNG spreman",
        "unreachable": "SearxNG nije dostupan",
        "wrong-service": "Drugi servis na adresi",
        "error": "SearxNG greška",
        "bootstrap-blocked": "Managed bootstrap blokiran",
    }.get(value, value)


def _write_search_provider_state(
    config: ControlCenterConfig,
    payload: dict[str, Any],
) -> None:
    atomic_write_json(config.search_provider_state_path, payload)


def _build_probe_request_url(base_url: str) -> str:
    split = urlsplit(str(base_url or "").strip())
    scheme = split.scheme or "http"
    netloc = split.netloc or split.path
    path = split.path if split.netloc else ""
    normalized_path = (path or "").rstrip("/")
    if normalized_path.endswith("/search"):
        search_path = normalized_path or "/search"
    else:
        search_path = f"{normalized_path}/search" if normalized_path else "/search"
    query_pairs = [(key, value) for key, value in parse_qsl(split.query, keep_blank_values=True) if key not in {"q", "format"}]
    query_pairs.extend([("q", "health"), ("format", "json")])
    encoded_query = "&".join(f"{quote_plus(key)}={quote_plus(value)}" for key, value in query_pairs)
    return urlunsplit((scheme, netloc, search_path, encoded_query, ""))


def _detect_service_label(raw_text: str) -> str:
    normalized = str(raw_text or "").strip()
    if not normalized:
        return ""
    title_match = re.search(r"(?is)<title>\s*(.*?)\s*</title>", normalized)
    if title_match:
        return title_match.group(1).strip()
    lowered = normalized.lower()
    if "open webui" in lowered:
        return "Open WebUI"
    if "<html" in lowered or "<!doctype html" in lowered:
        return "HTML servis"
    return ""


def _is_legacy_default_url(value: str) -> bool:
    normalized = str(value or "").strip().rstrip("/")
    return normalized == LEGACY_DEFAULT_WEB_SEARCH_BASE_URL.rstrip("/")


def _managed_metadata(distro: str) -> dict[str, Any]:
    base_dir = "$HOME/.local-ai-control-center/searxng"
    return {
        "distro": distro,
        "port": MANAGED_SEARXNG_PORT,
        "baseUrl": MANAGED_SEARXNG_BASE_URL,
        "repoPath": f"{base_dir}/repo",
        "venvPath": f"{base_dir}/.venv",
        "settingsPath": f"{base_dir}/settings.yml",
        "logPath": f"{base_dir}/searxng.log",
        "pidPath": f"{base_dir}/searxng.pid",
    }


def _write_bootstrap_script(metadata: dict[str, Any]) -> Path:
    script_path = Path(tempfile.gettempdir()) / "lacc-managed-searxng-bootstrap.sh"
    script_path.write_text(
        _render_bootstrap_script(metadata),
        encoding="ascii",
        newline="\n",
    )
    return script_path


def _render_bootstrap_script(metadata: dict[str, Any]) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f'BASE_DIR="{metadata["repoPath"][:-5]}"',
            f'REPO_DIR="{metadata["repoPath"]}"',
            f'VENV_DIR="{metadata["venvPath"]}"',
            f'SETTINGS_PATH="{metadata["settingsPath"]}"',
            f'LOG_PATH="{metadata["logPath"]}"',
            f'PID_PATH="{metadata["pidPath"]}"',
            f'PORT="{metadata["port"]}"',
            'export BASE_DIR REPO_DIR VENV_DIR SETTINGS_PATH LOG_PATH PID_PATH PORT',
            'mkdir -p "$BASE_DIR"',
            'command -v python3 >/dev/null 2>&1 || { echo "python3 nije dostupan u WSL."; exit 41; }',
            'command -v git >/dev/null 2>&1 || { echo "git nije dostupan u WSL."; exit 42; }',
            'command -v openssl >/dev/null 2>&1 || { echo "openssl nije dostupan u WSL."; exit 43; }',
            'python3 -m pip --version >/dev/null 2>&1 || { echo "python3 -m pip nije dostupan u WSL."; exit 44; }',
            'python3 -m pip install --user --disable-pip-version-check --quiet virtualenv',
            'if [ -d "$REPO_DIR" ] && [ ! -d "$REPO_DIR/.git" ]; then',
            '  rm -rf "$REPO_DIR"',
            'fi',
            'if [ ! -d "$REPO_DIR/.git" ]; then',
            '  git clone --depth 1 https://github.com/searxng/searxng.git "$REPO_DIR"',
            'else',
            '  git -C "$REPO_DIR" pull --ff-only',
            'fi',
            'if [ ! -x "$VENV_DIR/bin/python" ]; then',
            '  python3 -m virtualenv "$VENV_DIR"',
            'fi',
            '"$VENV_DIR/bin/pip" install --disable-pip-version-check -r "$REPO_DIR/requirements.txt"',
            '"$VENV_DIR/bin/python" - <<\'PY\'',
            "import os, re, secrets, sys",
            "from pathlib import Path",
            'repo_dir = Path(os.environ["REPO_DIR"])',
            'settings_path = Path(os.environ["SETTINGS_PATH"])',
            'port = os.environ["PORT"]',
            'venv_dir = Path(os.environ["VENV_DIR"])',
            'text = (repo_dir / "searx" / "settings.yml").read_text(encoding="utf-8")',
            'text = re.sub(r\'(?m)^(\\s*instance_name:\\s*).*$\', lambda m: f\'{m.group(1)}"Local AI Control Center"\', text, count=1)',
            'text = re.sub(r\'(?ms)^  formats:\\n(?:    - .*\\n)+\', "  formats:\\n    - html\\n    - json\\n", text, count=1)',
            'text = re.sub(r\'(?m)^(\\s*port:\\s*).*$\', lambda m: f"{m.group(1)}{port}", text, count=1)',
            'text = re.sub(r\'(?m)^(\\s*bind_address:\\s*).*$\', lambda m: f\'{m.group(1)}"127.0.0.1"\', text, count=1)',
            'text = re.sub(r\'(?m)^(\\s*secret_key:\\s*).*$\', lambda m: f\'{m.group(1)}"{secrets.token_hex(32)}"\', text, count=1)',
            'settings_path.write_text(text, encoding="utf-8")',
            'if sys.version_info < (3, 11):',
            '    subprocess_result = __import__("subprocess").run([str(venv_dir / "bin" / "pip"), "install", "--disable-pip-version-check", "tomli"], check=True)',
            '    (repo_dir / "tomllib.py").write_text("from tomli import *\\n", encoding="utf-8")',
            'else:',
            '    shim_path = repo_dir / "tomllib.py"',
            '    if shim_path.exists():',
            '        shim_path.unlink()',
            "PY",
            'export REPO_DIR VENV_DIR SETTINGS_PATH LOG_PATH PID_PATH PORT',
            'if [ -f "$PID_PATH" ]; then',
            '  EXISTING_PID="$(cat "$PID_PATH" || true)"',
            '  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then',
            '    if "$VENV_DIR/bin/python" - <<\'PY\' >/dev/null 2>&1',
            "import json, os, urllib.request",
            'port = os.environ["PORT"]',
            'url = f"http://127.0.0.1:{port}/search?q=health&format=json"',
            'with urllib.request.urlopen(url, timeout=3) as response:',
            '    payload = json.loads(response.read().decode("utf-8", errors="replace"))',
            'assert isinstance(payload.get("results"), list)',
            "PY",
            '    then',
            '      exit 0',
            '    fi',
            '    kill "$EXISTING_PID" || true',
            '    sleep 1',
            '  fi',
            'fi',
            'nohup env SEARXNG_SETTINGS_PATH="$SETTINGS_PATH" PYTHONPATH="$REPO_DIR" "$VENV_DIR/bin/python" -m searx.webapp >"$LOG_PATH" 2>&1 &',
            'echo $! > "$PID_PATH"',
            'sleep 4',
            '"$VENV_DIR/bin/python" - <<\'PY\'',
            "import json, os, urllib.request",
            'port = os.environ["PORT"]',
            'url = f"http://127.0.0.1:{port}/search?q=health&format=json"',
            'with urllib.request.urlopen(url, timeout=5) as response:',
            '    payload = json.loads(response.read().decode("utf-8", errors="replace"))',
            'assert isinstance(payload.get("results"), list)',
            "PY",
            "",
        ]
    )


def _windows_path_to_wsl_path(path: Path) -> str:
    resolved = str(path.resolve())
    if len(resolved) >= 3 and resolved[1] == ":":
        drive = resolved[0].lower()
        tail = resolved[2:].replace("\\", "/")
        return f"/mnt/{drive}{tail}"
    return resolved.replace("\\", "/")


def _condense_bootstrap_output(value: str) -> str:
    normalized = re.sub(r"\s+", " ", _sanitize_wsl_text(str(value or "")).strip())
    return normalized[:300] if normalized else "Nepoznat bootstrap problem."


def _sanitize_wsl_text(value: str) -> str:
    return str(value or "").replace("\x00", "")


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
