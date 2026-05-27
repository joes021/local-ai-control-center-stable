from __future__ import annotations

import html
import json
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote_plus, unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - dependency should be present in packaged builds
    certifi = None

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.search_provider_service import (
    resolve_search_provider,
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

SEARCH_PROVIDER_LABELS = {
    "searxng": "SearxNG",
    "duckduckgo": "DuckDuckGo",
}


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
    provider_override: str | None = None,
    opener: Callable[..., Any] = urlopen,
    mode_label: str = "manual",
    record_history: bool = False,
) -> dict[str, Any]:
    config = config or get_config()
    settings = load_web_search_settings(config)
    provider = resolve_search_provider(config, provider_override=provider_override)
    settings = {
        **settings,
        "provider": provider,
    }
    target = resolve_search_provider_target(config, provider_override=provider)
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return _search_error_payload(
            query="",
            summary="Search query je prazan.",
            settings=settings,
        )
    try:
        results = _perform_provider_query(
            provider,
            query=normalized_query,
            target=target,
            opener=opener,
            timeout_seconds=float(settings["timeoutSeconds"]),
            limit=int(settings["maxResults"]),
            settings=settings,
        )
    except _SearchProviderError as exc:
        return _search_error_payload(
            query=normalized_query,
            summary=str(exc),
            settings=settings,
        )
    payload = {
        "status": "ok",
        "provider": provider,
        "providerLabel": _provider_label(provider),
        "mode": mode_label,
        "query": normalized_query,
        "resultCount": len(results),
        "summary": f"Pronađeno je {len(results)} veb rezultata preko {_provider_label(provider)}.",
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
    provider_override: str | None = None,
    search_func: Callable[[str], dict[str, Any]] | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    config = config or get_config()
    provider = resolve_search_provider(config, provider_override=provider_override)
    runtime_ready = ensure_runtime_ready(config)
    if runtime_ready.get("status") != "ok":
        return {
            "status": "error",
            "provider": provider,
            "providerLabel": _provider_label(provider),
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
            provider_override=provider,
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


class _SearchProviderError(RuntimeError):
    pass


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self, *, limit: int):
        super().__init__(convert_charrefs=True)
        self.limit = max(limit, 1)
        self.results: list[dict[str, object]] = []
        self._capture_kind = ""
        self._chunks: list[str] = []
        self._current_href = ""
        self._snippet_target_index: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if len(self.results) >= self.limit:
            return
        attributes = {key: value or "" for key, value in attrs}
        class_names = set(attributes.get("class", "").split())
        if tag == "a" and "result__a" in class_names:
            self._capture_kind = "title"
            self._chunks = []
            self._current_href = attributes.get("href", "")
            self._snippet_target_index = None
            return
        if (
            tag in {"a", "div", "span"}
            and "result__snippet" in class_names
            and self.results
            and not self.results[-1]["snippet"]
        ):
            self._capture_kind = "snippet"
            self._chunks = []
            self._snippet_target_index = len(self.results) - 1
            return
        if tag == "br" and self._capture_kind:
            self._chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._capture_kind == "title" and tag == "a":
            title = _clean_html_text("".join(self._chunks))
            url = _normalize_duckduckgo_result_url(self._current_href)
            if title and url:
                self.results.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": "",
                        "engine": "duckduckgo",
                    }
                )
            self._capture_kind = ""
            self._chunks = []
            self._current_href = ""
            return
        if self._capture_kind == "snippet" and tag in {"a", "div", "span"}:
            snippet = _clean_html_text("".join(self._chunks))[:MAX_SNIPPET_LENGTH]
            if (
                snippet
                and self._snippet_target_index is not None
                and self._snippet_target_index < len(self.results)
            ):
                self.results[self._snippet_target_index]["snippet"] = snippet
            self._capture_kind = ""
            self._chunks = []
            self._snippet_target_index = None

    def handle_data(self, data: str) -> None:
        if self._capture_kind:
            self._chunks.append(data)


def _perform_provider_query(
    provider: str,
    *,
    query: str,
    target: dict[str, str],
    opener: Callable[..., Any],
    timeout_seconds: float,
    limit: int,
    settings: dict[str, object],
) -> list[dict[str, object]]:
    if provider == "duckduckgo":
        ssl_context = _build_outbound_ssl_context()
        request_url = _build_duckduckgo_request_url(query)
        request = Request(
            request_url,
            headers={
                "Accept": "text/html",
                "User-Agent": "LocalAIControlCenter/1.0 (+DuckDuckGo HTML search)",
            },
            method="GET",
        )
        try:
            raw_text = _read_text_response(
                opener,
                request,
                timeout=timeout_seconds,
                ssl_context=ssl_context,
            )
        except HTTPError as exc:
            raise _SearchProviderError(f"DuckDuckGo je vratio HTTP {exc.code}.") from None
        except (OSError, URLError, TimeoutError) as exc:
            if _is_tls_verification_error(exc):
                try:
                    raw_text = _read_text_response(
                        opener,
                        request,
                        timeout=timeout_seconds,
                        ssl_context=_build_relaxed_ssl_context(),
                    )
                except HTTPError as retry_exc:
                    raise _SearchProviderError(f"DuckDuckGo je vratio HTTP {retry_exc.code}.") from None
                except (OSError, URLError, TimeoutError) as retry_exc:
                    raise _SearchProviderError(f"DuckDuckGo query nije uspeo: {retry_exc}") from None
            else:
                raise _SearchProviderError(f"DuckDuckGo query nije uspeo: {exc}") from None
        return _normalize_duckduckgo_results(raw_text, limit=limit)

    if not target["effectiveBaseUrl"]:
        raise _SearchProviderError(
            "SearxNG nije podešen. Pokreni Setup local SearxNG ili unesi pravi base URL."
        )

    request_url = _build_searxng_request_url(str(target["effectiveBaseUrl"]), query)
    request = Request(
        request_url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            raw_payload = _decode_searxng_payload(
                response.read().decode("utf-8", errors="replace"),
                request_url=request_url,
            )
    except HTTPError as exc:
        raise _SearchProviderError(f"SearxNG je vratio HTTP {exc.code}.") from None
    except ValueError as exc:
        raise _SearchProviderError(str(exc)) from None
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        if (
            target["source"] == "legacy-default"
            and str(target["effectiveBaseUrl"]).rstrip("/")
            == LEGACY_DEFAULT_WEB_SEARCH_BASE_URL.rstrip("/")
        ):
            raise _SearchProviderError(
                "Legacy 127.0.0.1:8080 više se ne smatra podrazumevanim SearxNG endpointom. Pokreni Setup local SearxNG ili unesi pravi base URL."
            ) from None
        raise _SearchProviderError(f"SearxNG query nije uspeo: {exc}") from None
    return _normalize_searxng_results(raw_payload, limit=limit)


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


def _build_duckduckgo_request_url(query: str) -> str:
    encoded_query = quote_plus(str(query or "").strip())
    return f"https://html.duckduckgo.com/html/?q={encoded_query}"


def _normalize_duckduckgo_results(raw_text: str, *, limit: int) -> list[dict[str, object]]:
    parser = _DuckDuckGoResultParser(limit=limit)
    parser.feed(raw_text)
    parser.close()
    return parser.results[: max(limit, 1)]


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
        "Koristi sledeće veb rezultate kao dodatni kontekst.",
        "Ako odgovor nije jasno podržan rezultatima, reci to otvoreno.",
        "Kada se pozivaš na veb rezultat, navedi naslov i URL iz izvora.",
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
        "providerLabel": _provider_label(str(settings["provider"])),
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


def _normalize_duckduckgo_result_url(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    if candidate.startswith("//"):
        candidate = f"https:{candidate}"
    elif candidate.startswith("/"):
        candidate = f"https://duckduckgo.com{candidate}"
    split = urlsplit(candidate)
    if split.netloc.endswith("duckduckgo.com") and split.path.startswith("/l/"):
        params = dict(parse_qsl(split.query, keep_blank_values=True))
        redirected = params.get("uddg", "")
        if redirected:
            return unquote(redirected)
    return candidate


def _clean_html_text(value: str) -> str:
    normalized = html.unescape(str(value or ""))
    return " ".join(normalized.split()).strip()


def _provider_label(provider: str) -> str:
    return SEARCH_PROVIDER_LABELS.get(str(provider or "").strip().lower(), provider)


def _build_outbound_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _open_request(
    opener: Callable[..., Any],
    request: Request,
    *,
    timeout: float,
    ssl_context: ssl.SSLContext | None = None,
):
    if ssl_context is None:
        return opener(request, timeout=timeout)
    try:
        return opener(request, timeout=timeout, context=ssl_context)
    except TypeError:
        return opener(request, timeout=timeout)


def _read_text_response(
    opener: Callable[..., Any],
    request: Request,
    *,
    timeout: float,
    ssl_context: ssl.SSLContext | None = None,
) -> str:
    with _open_request(
        opener,
        request,
        timeout=timeout,
        ssl_context=ssl_context,
    ) as response:
        return response.read().decode("utf-8", errors="replace")


def _build_relaxed_ssl_context() -> ssl.SSLContext:
    return ssl._create_unverified_context()


def _is_tls_verification_error(exc: BaseException) -> bool:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    if isinstance(exc, URLError):
        reason = exc.reason
        return isinstance(reason, ssl.SSLCertVerificationError)
    return False
