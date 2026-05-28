from __future__ import annotations

import json
import inspect
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from local_ai_control_center_installer.control_center_backend.services.search_service import (
    perform_search_query,
    prepare_proxy_chat_completion_body,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    load_effective_settings_state,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_runtime_state,
)


router = APIRouter()


@router.api_route(
    "/api/runtime-proxy/v1/{upstream_path:path}",
    methods=["GET", "POST"],
)
async def runtime_proxy(upstream_path: str, request: Request):
    raw_body = await request.body()
    body: dict[str, object] | bytes | None = None
    content_type = request.headers.get("content-type", "")
    if raw_body:
        if "application/json" in content_type.lower():
            try:
                parsed = json.loads(raw_body.decode("utf-8"))
                body = parsed if isinstance(parsed, dict) else raw_body
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = raw_body
        else:
            body = raw_body

    path = f"/v1/{upstream_path}"
    if request.url.query:
        path = f"{path}?{request.url.query}"
    headers = _forwardable_headers(request.headers)
    if request.method.upper() == "POST" and path == "/v1/chat/completions" and isinstance(body, dict):
        body, _ = prepare_proxy_chat_completion_body(
            body,
            search_func=perform_search_query,
        )
        body = _apply_generation_defaults(body)
    elif request.method.upper() == "POST" and path == "/v1/completions" and isinstance(body, dict):
        body = _apply_generation_defaults(body)

    stream_requested = isinstance(body, dict) and bool(body.get("stream"))
    proxied = _invoke_forward_runtime_request(
        method=request.method.upper(),
        path=path,
        body=body,
        headers=headers,
        stream=stream_requested,
    )
    if proxied.get("streaming"):
        return StreamingResponse(
            proxied["iterator"],
            status_code=int(proxied["status_code"]),
            headers=dict(proxied.get("headers", {})),
        )
    return Response(
        content=proxied.get("body", b""),
        status_code=int(proxied["status_code"]),
        headers=dict(proxied.get("headers", {})),
    )


def forward_runtime_request(
    *,
    method: str,
    path: str,
    body: dict[str, object] | bytes | None,
    headers: dict[str, str],
    stream: bool = False,
) -> dict[str, object]:
    runtime_state = load_runtime_state()
    upstream_base_url = str(runtime_state.get("base_url", "") or "").rstrip("/")
    upstream_url = f"{upstream_base_url}{path}"
    data: bytes | None
    next_headers = dict(headers)
    if isinstance(body, dict):
        data = json.dumps(body).encode("utf-8")
        next_headers.setdefault("Content-Type", "application/json")
    elif isinstance(body, bytes):
        data = body
    else:
        data = None

    request = UrlRequest(
        upstream_url,
        data=data,
        headers=next_headers,
        method=method,
    )
    try:
        response = urlopen(request, timeout=180.0)
    except HTTPError as exc:
        return {
            "status_code": exc.code,
            "headers": _response_headers(exc.headers),
            "body": exc.read(),
        }
    except (OSError, URLError, TimeoutError) as exc:
        return {
            "status_code": 502,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "error": {
                        "message": f"Runtime proxy nije uspeo da kontaktira upstream: {exc}",
                        "type": "runtime_proxy_error",
                    }
                }
            ).encode("utf-8"),
        }

    if stream:
        response_headers = _response_headers(response.headers)
        return {
            "status_code": response.status,
            "headers": response_headers,
            "streaming": True,
            "iterator": _stream_response_iterator(response),
        }

    with response:
        return {
            "status_code": response.status,
            "headers": _response_headers(response.headers),
            "body": response.read(),
        }


def _stream_response_iterator(response):
    try:
        while True:
            chunk = response.read(8192)
            if not chunk:
                break
            yield chunk
    finally:
        response.close()


def _forwardable_headers(headers: Any) -> dict[str, str]:
    allowed = {"accept", "content-type", "authorization"}
    return {
        key: value
        for key, value in headers.items()
        if key.lower() in allowed
    }


def _response_headers(headers: Any) -> dict[str, str]:
    next_headers: dict[str, str] = {}
    for key, value in getattr(headers, "items", lambda: [])():
        if key.lower() in {"content-length", "transfer-encoding", "connection"}:
            continue
        next_headers[str(key)] = str(value)
    if "Content-Type" not in next_headers:
        next_headers["Content-Type"] = "application/json"
    return next_headers


def _invoke_forward_runtime_request(
    *,
    method: str,
    path: str,
    body: dict[str, object] | bytes | None,
    headers: dict[str, str],
    stream: bool,
) -> dict[str, object]:
    parameters = inspect.signature(forward_runtime_request).parameters.values()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return forward_runtime_request(
            method=method,
            path=path,
            body=body,
            headers=headers,
            stream=stream,
        )
    if "stream" in inspect.signature(forward_runtime_request).parameters:
        return forward_runtime_request(
            method=method,
            path=path,
            body=body,
            headers=headers,
            stream=stream,
        )
    return forward_runtime_request(
        method=method,
        path=path,
        body=body,
        headers=headers,
    )


def _apply_generation_defaults(payload: dict[str, object]) -> dict[str, object]:
    settings = load_effective_settings_state()
    next_payload = dict(payload)
    defaults = {
        "temperature": float(settings.get("temperature", 0.8)),
        "top_p": float(settings.get("topP", 0.95)),
        "top_k": int(settings.get("topK", 40)),
        "min_p": float(settings.get("minP", 0.05)),
        "repeat_penalty": float(settings.get("repeatPenalty", 1.0)),
        "repeat_last_n": int(settings.get("repeatLastN", 64)),
        "presence_penalty": float(settings.get("presencePenalty", 0.0)),
        "frequency_penalty": float(settings.get("frequencyPenalty", 0.0)),
        "seed": int(settings.get("seed", -1)),
        "max_tokens": int(settings.get("outputTokens", 8192)),
    }
    for key, value in defaults.items():
        if key not in next_payload or next_payload.get(key) is None:
            next_payload[key] = value
    return next_payload
