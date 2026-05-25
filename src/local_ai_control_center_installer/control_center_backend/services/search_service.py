from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote_plus, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.search_provider_service import (
    resolve_search_provider_target,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    ensure_runtime_ready,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    LEGACY_DEFAULT_WEB_SEARCH_BASE_URL,
    load_effective_settings_state,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    atomic_write_json,
    read_json_object,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_runtime_state,
)


SEARCH_HISTORY_LIMIT = 20
SEARCH_REQUEST_TIMEOUT_FALLBACK_SECONDS = 20
LOCAL_MODEL_ANSWER_TIMEOUT_SECONDS = 180.0
MAX_SNIPPET_LENGTH = 480


def load_web_search_settings(
    config: ControlCenterConfig | None = None,
) -> dict[str, object]:
    config = config or get_config()
    settings = load_effective_settings_state(config)
    return {
        "mode": str(settings.get("webSearchMode", "off") or "off"),
        "provider": str(settings.get("webSearchProvider", "searxng") or "searxng"),
        "baseUrl": str(settings.get("webSearchBaseUrl", "") or ""),
        "maxResults": int(settings.get("webSearchMaxResults", 5) or 5),
        "timeoutSeconds": int(settings.get("webSearchTimeoutSeconds", SEARCH_REQUEST_TIMEOUT_FALLBACK_SECONDS) or SEARCH_REQUEST_TIMEOUT_FALLBACK_SECONDS),
        "promptPrefix": str(settings.get("webSearchPromptPrefix", "/web") or "/web"),
    }


def perform_search_query(
    query: str,
    *,
    config: ControlCenterConfig | None = None,
    opener: Callable[..., Any] = urlopen,
    mode_label: str = "manual",
    record_history: bool = False,
) -> dict[str, Any]:
    config = config or get_config()
    settings = load_web_search_settings(config)
    target = resolve_search_provider_target(config)
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return _search_error_payload(
            query="",
            summary="Search query je prazan.",
            settings=settings,
        )
    if not target["effectiveBaseUrl"]:
        return _search_error_payload(
            query=normalized_query,
            summary="SearxNG nije podesen. Pokreni Setup local SearxNG ili unesi pravi base URL.",
            settings=settings,
        )

    request_url = _build_searxng_request_url(str(target["effectiveBaseUrl"]), normalized_query)
    request = Request(
        request_url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with opener(request, timeout=float(settings["timeoutSeconds"])) as response:
            raw_payload = _decode_searxng_payload(
                response.read().decode("utf-8", errors="replace"),
                request_url=request_url,
            )
    except HTTPError as exc:
        return _search_error_payload(
            query=normalized_query,
            summary=f"SearxNG je vratio HTTP {exc.code}.",
            settings=settings,
        )
    except ValueError as exc:
        return _search_error_payload(
            query=normalized_query,
            summary=str(exc),
            settings=settings,
        )
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        if target["source"] == "legacy-default" and str(target["effectiveBaseUrl"]).rstrip("/") == LEGACY_DEFAULT_WEB_SEARCH_BASE_URL.rstrip("/"):
            return _search_error_payload(
                query=normalized_query,
                summary="Legacy 127.0.0.1:8080 vise se ne smatra podrazumevanim SearxNG endpointom. Pokreni Setup local SearxNG ili unesi pravi base URL.",
                settings=settings,
            )
        return _search_error_payload(
            query=normalized_query,
            summary=f"SearxNG query nije uspeo: {exc}",
            settings=settings,
        )

    results = _normalize_searxng_results(raw_payload, limit=int(settings["maxResults"]))
    payload = {
        "status": "ok",
        "provider": str(settings["provider"]),
        "mode": mode_label,
        "query": normalized_query,
        "resultCount": len(results),
        "summary": f"Pronadjeno je {len(results)} web rezultata preko SearxNG.",
        "results": results,
        "history": [],
    }
    if record_history:
        _append_search_history(
            config,
            query=normalized_query,
            mode=mode_label,
            result_count=len(results),
        )
        payload["history"] = load_search_history(config)
    return payload


def load_search_history(
    config: ControlCenterConfig | None = None,
) -> list[dict[str, object]]:
    config = config or get_config()
    payload = read_json_object(config.search_history_path)
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    history: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        history.append(
            {
                "query": str(item.get("query", "") or ""),
                "mode": str(item.get("mode", "") or ""),
                "resultCount": int(item.get("resultCount", 0) or 0),
                "askedAt": str(item.get("askedAt", "") or ""),
            }
        )
    return history[:SEARCH_HISTORY_LIMIT]


def prepare_proxy_chat_completion_body(
    payload: dict[str, Any],
    *,
    config: ControlCenterConfig | None = None,
    search_func: Callable[[str], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = config or get_config()
    settings = load_web_search_settings(config)
    mode = str(settings["mode"])
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload, _proxy_meta(False, mode=mode)

    trigger = _extract_search_trigger(
        messages,
        mode=mode,
        prompt_prefix=str(settings["promptPrefix"]),
    )
    if not trigger["shouldSearch"]:
        return payload, _proxy_meta(False, mode=mode)

    search_callable = search_func or (
        lambda query: perform_search_query(
            query,
            config=config,
            mode_label=mode,
            record_history=False,
        )
    )
    search_payload = search_callable(str(trigger["query"]))
    if str(search_payload.get("status", "")) != "ok":
        return payload, _proxy_meta(
            False,
            mode=mode,
            query=str(trigger["query"]),
            search_summary=str(search_payload.get("summary", "") or ""),
        )

    augmented_messages = _inject_search_context(
        trigger["messages"],
        search_payload,
    )
    next_payload = dict(payload)
    next_payload["messages"] = augmented_messages
    return next_payload, _proxy_meta(
        True,
        mode=mode,
        query=str(trigger["query"]),
        search_summary=str(search_payload.get("summary", "") or ""),
    )


def answer_with_local_model(
    query: str,
    *,
    config: ControlCenterConfig | None = None,
    search_func: Callable[[str], dict[str, Any]] | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    config = config or get_config()
    runtime_ready = ensure_runtime_ready(config)
    if runtime_ready.get("status") != "ok":
        return {
            "status": "error",
            "provider": "searxng",
            "mode": "manual",
            "query": str(query or "").strip(),
            "resultCount": 0,
            "summary": str(runtime_ready.get("summary", "") or "Runtime nije spreman za search answer."),
            "results": [],
            "history": load_search_history(config),
            "answer": "",
            "answerModel": "",
            "answerRuntime": "",
            "usage": {
                "promptTokens": None,
                "completionTokens": None,
                "totalTokens": None,
            },
        }

    search_callable = search_func or (
        lambda next_query: perform_search_query(
            next_query,
            config=config,
            mode_label="manual",
            record_history=True,
        )
    )
    search_payload = search_callable(str(query or "").strip())
    if str(search_payload.get("status", "")) != "ok":
        return {
            **search_payload,
            "answer": "",
            "answerModel": "",
            "answerRuntime": "",
            "usage": {
                "promptTokens": None,
                "completionTokens": None,
                "totalTokens": None,
            },
        }

    runtime_state = load_runtime_state(config)
    model_name = str(runtime_state.get("active_model", "") or "local-model")
    runtime_name = str(runtime_state.get("active_runtime", "") or "llama.cpp")
    settings = load_effective_settings_state(config)
    request_payload = {
        "model": model_name,
        "messages": _inject_search_context(
            [{"role": "user", "content": str(query or "").strip()}],
            search_payload,
        ),
        "temperature": 0,
        "max_tokens": int(settings.get("outputTokens", 8192) or 8192),
        "stream": False,
    }
    request = Request(
        f"{str(runtime_state.get('base_url', '')).rstrip('/')}/v1/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=LOCAL_MODEL_ANSWER_TIMEOUT_SECONDS) as response:
            response_payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        return {
            **search_payload,
            "status": "error",
            "summary": f"Local model odgovor nije uspeo: HTTP {exc.code}.",
            "answer": "",
            "answerModel": model_name,
            "answerRuntime": runtime_name,
            "usage": {
                "promptTokens": None,
                "completionTokens": None,
                "totalTokens": None,
            },
        }
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            **search_payload,
            "status": "error",
            "summary": f"Local model odgovor nije uspeo: {exc}",
            "answer": "",
            "answerModel": model_name,
            "answerRuntime": runtime_name,
            "usage": {
                "promptTokens": None,
                "completionTokens": None,
                "totalTokens": None,
            },
        }

    usage = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
    return {
        **search_payload,
        "status": "ok",
        "answer": _extract_completion_answer(response_payload),
        "answerModel": model_name,
        "answerRuntime": runtime_name,
        "usage": {
            "promptTokens": _int_or_none(usage.get("prompt_tokens")),
            "completionTokens": _int_or_none(usage.get("completion_tokens")),
            "totalTokens": _int_or_none(usage.get("total_tokens")),
        },
    }


def _normalize_searxng_results(
    payload: object,
    *,
    limit: int,
) -> list[dict[str, object]]:
    raw_results = []
    if isinstance(payload, dict):
        candidate = payload.get("results")
        if isinstance(candidate, list):
            raw_results = candidate

    normalized: list[dict[str, object]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or "").strip()
        url = str(item.get("url", "") or "").strip()
        snippet = str(item.get("content", "") or item.get("snippet", "") or "").strip()
        engine = str(item.get("engine", "") or item.get("source", "") or "").strip() or "unknown"
        if not title or not url:
            continue
        normalized.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet[:MAX_SNIPPET_LENGTH],
                "engine": engine,
            }
        )
        if len(normalized) >= max(limit, 1):
            break
    return normalized


def _build_searxng_request_url(base_url: str, query: str) -> str:
    normalized_base = str(base_url or "").strip()
    split = urlsplit(normalized_base)
    scheme = split.scheme or "http"
    netloc = split.netloc or split.path
    path = split.path if split.netloc else ""
    normalized_path = (path or "").rstrip("/")
    if normalized_path.endswith("/search"):
        search_path = normalized_path or "/search"
    else:
        search_path = f"{normalized_path}/search" if normalized_path else "/search"

    query_pairs = [(key, value) for key, value in parse_qsl(split.query, keep_blank_values=True) if key not in {"q", "format"}]
    query_pairs.extend([("q", query), ("format", "json")])
    encoded_query = "&".join(f"{quote_plus(key)}={quote_plus(value)}" for key, value in query_pairs)
    return urlunsplit((scheme, netloc, search_path, encoded_query, ""))


def _decode_searxng_payload(raw_text: str, *, request_url: str) -> object:
    normalized_text = raw_text.lstrip("\ufeff").strip()
    if not normalized_text:
        raise ValueError(
            f"SearxNG nije vratio JSON odgovor. Proveri da li base URL pokazuje na SearxNG instancu ili /search endpoint: {request_url}"
        )
    try:
        return json.loads(normalized_text)
    except json.JSONDecodeError:
        snippet = normalized_text[:120].replace("\r", " ").replace("\n", " ")
        raise ValueError(
            "SearxNG nije vratio JSON odgovor. "
            f"Proveri da li base URL pokazuje na SearxNG instancu ili /search endpoint. "
            f"Primer odgovora: {snippet}"
        ) from None


def _extract_search_trigger(
    messages: list[object],
    *,
    mode: str,
    prompt_prefix: str,
) -> dict[str, object]:
    if mode == "off":
        return {"shouldSearch": False, "messages": messages, "query": ""}

    last_index = -1
    last_text = ""
    for index in range(len(messages) - 1, -1, -1):
        item = messages[index]
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "") or "").strip().lower() != "user":
            continue
        last_index = index
        last_text = _message_content_as_text(item.get("content"))
        if last_text:
            break

    if last_index < 0 or not last_text.strip():
        return {"shouldSearch": False, "messages": messages, "query": ""}

    if mode == "always":
        return {
            "shouldSearch": True,
            "messages": messages,
            "query": last_text.strip(),
        }

    normalized_prefix = prompt_prefix.strip()
    if not normalized_prefix:
        normalized_prefix = "/web"
    if not last_text.strip().lower().startswith(normalized_prefix.lower()):
        return {"shouldSearch": False, "messages": messages, "query": ""}

    stripped_text = last_text.strip()[len(normalized_prefix) :].strip()
    next_messages = list(messages)
    next_messages[last_index] = _replace_message_content(next_messages[last_index], stripped_text)
    return {
        "shouldSearch": bool(stripped_text),
        "messages": next_messages,
        "query": stripped_text,
    }


def _replace_message_content(message: object, next_text: str) -> dict[str, object]:
    if not isinstance(message, dict):
        return {"role": "user", "content": next_text}
    next_message = dict(message)
    content = next_message.get("content")
    if isinstance(content, list):
        replaced = False
        next_content: list[object] = []
        for item in content:
            if isinstance(item, dict) and str(item.get("type", "") or "") == "text" and not replaced:
                next_item = dict(item)
                next_item["text"] = next_text
                next_content.append(next_item)
                replaced = True
                continue
            next_content.append(item)
        if not replaced:
            next_content.insert(0, {"type": "text", "text": next_text})
        next_message["content"] = next_content
        return next_message
    next_message["content"] = next_text
    return next_message


def _message_content_as_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and str(item.get("type", "") or "") == "text":
                parts.append(str(item.get("text", "") or ""))
        return "\n".join(part for part in parts if part)
    return ""


def _inject_search_context(
    messages: list[object],
    search_payload: dict[str, Any],
) -> list[dict[str, object]]:
    normalized_messages = [
        item for item in messages if isinstance(item, dict)
    ]
    system_message = {
        "role": "system",
        "content": _build_search_system_prompt(search_payload),
    }
    return [system_message, *normalized_messages]


def _build_search_system_prompt(search_payload: dict[str, Any]) -> str:
    lines = [
        "Koristi sledece web rezultate kao dodatni kontekst.",
        "Ako odgovor nije jasno podrzan rezultatima, reci to otvoreno.",
        "Kada se pozivas na web rezultat, navedi naslov i URL iz izvora.",
        "",
        f"Search query: {search_payload.get('query', '')}",
        "",
    ]
    for index, item in enumerate(search_payload.get("results", []), start=1):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"[{index}] {item.get('title', '')}",
                f"URL: {item.get('url', '')}",
                f"Snippet: {item.get('snippet', '')}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _search_error_payload(
    *,
    query: str,
    summary: str,
    settings: dict[str, object],
) -> dict[str, Any]:
    return {
        "status": "error",
        "provider": str(settings["provider"]),
        "mode": "manual",
        "query": query,
        "resultCount": 0,
        "summary": summary,
        "results": [],
        "history": [],
    }


def _append_search_history(
    config: ControlCenterConfig,
    *,
    query: str,
    mode: str,
    result_count: int,
) -> None:
    items = load_search_history(config)
    next_items = [
        {
            "query": query,
            "mode": mode,
            "resultCount": result_count,
            "askedAt": datetime.now(timezone.utc).isoformat(),
        },
        *items,
    ][:SEARCH_HISTORY_LIMIT]
    atomic_write_json(config.search_history_path, {"items": next_items})


def _proxy_meta(
    used_search: bool,
    *,
    mode: str,
    query: str = "",
    search_summary: str = "",
) -> dict[str, object]:
    return {
        "usedSearch": used_search,
        "mode": mode,
        "query": query,
        "searchSummary": search_summary,
    }


def _extract_completion_answer(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
    return ""


def _int_or_none(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
