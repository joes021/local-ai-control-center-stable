from __future__ import annotations

import json
import inspect
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

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
from local_ai_control_center_installer.control_center_backend.services.tuning_lab_service import (
    resolve_tuning_runtime_profile,
)


router = APIRouter()


@router.api_route(
    "/api/runtime-proxy/v1/{upstream_path:path}",
    methods=["GET", "POST"],
)
async def runtime_proxy(upstream_path: str, request: Request):
    return await _proxy_runtime_request(
        upstream_path=upstream_path,
        request=request,
        generation_override=None,
    )


@router.api_route(
    "/api/runtime-proxy/tuning/{profile_token}/v1/{upstream_path:path}",
    methods=["GET", "POST"],
)
async def tuning_runtime_proxy(profile_token: str, upstream_path: str, request: Request):
    runtime_profile = resolve_tuning_runtime_profile(profile_token)
    if runtime_profile is None:
        return Response(
            content=json.dumps(
                {
                    "error": {
                        "message": "Traženi tuning runtime profil nije pronađen.",
                        "type": "tuning_runtime_profile_missing",
                    }
                }
            ).encode("utf-8"),
            status_code=404,
            headers={"Content-Type": "application/json"},
        )
    generation_override = runtime_profile.get("settingsPatch")
    return await _proxy_runtime_request(
        upstream_path=upstream_path,
        request=request,
        generation_override=dict(generation_override) if isinstance(generation_override, dict) else None,
        upstream_base_url=str(runtime_profile.get("upstreamBaseUrl", "") or "").strip() or None,
    )


async def _proxy_runtime_request(
    *,
    upstream_path: str,
    request: Request,
    generation_override: dict[str, object] | None,
    upstream_base_url: str | None = None,
):
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
        body = _apply_generation_defaults(body, override_settings=generation_override)
    elif request.method.upper() == "POST" and path == "/v1/completions" and isinstance(body, dict):
        body = _apply_generation_defaults(body, override_settings=generation_override)

    stream_requested = isinstance(body, dict) and bool(body.get("stream"))
    proxied = await run_in_threadpool(
        _invoke_forward_runtime_request,
        method=request.method.upper(),
        path=path,
        body=body,
        headers=headers,
        stream=stream_requested,
        upstream_base_url=upstream_base_url,
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
    upstream_base_url: str | None = None,
) -> dict[str, object]:
    if upstream_base_url:
        resolved_upstream_base_url = str(upstream_base_url or "").rstrip("/")
    else:
        runtime_state = load_runtime_state()
        resolved_upstream_base_url = str(runtime_state.get("base_url", "") or "").rstrip("/")
    upstream_url = f"{resolved_upstream_base_url}{path}"
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
    upstream_base_url: str | None = None,
) -> dict[str, object]:
    signature = inspect.signature(forward_runtime_request)
    parameters = signature.parameters
    parameter_values = parameters.values()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameter_values):
        return forward_runtime_request(
            method=method,
            path=path,
            body=body,
            headers=headers,
            stream=stream,
            upstream_base_url=upstream_base_url,
        )
    if "stream" in parameters and "upstream_base_url" in parameters:
        return forward_runtime_request(
            method=method,
            path=path,
            body=body,
            headers=headers,
            stream=stream,
            upstream_base_url=upstream_base_url,
        )
    if "stream" in parameters:
        return forward_runtime_request(
            method=method,
            path=path,
            body=body,
            headers=headers,
            stream=stream,
        )
    if "upstream_base_url" in parameters:
        return forward_runtime_request(
            method=method,
            path=path,
            body=body,
            headers=headers,
            upstream_base_url=upstream_base_url,
        )
    return forward_runtime_request(
        method=method,
        path=path,
        body=body,
        headers=headers,
    )


def _apply_generation_defaults(
    payload: dict[str, object],
    *,
    override_settings: dict[str, object] | None = None,
) -> dict[str, object]:
    settings = load_effective_settings_state()
    merged_settings = dict(settings)
    if override_settings:
        merged_settings.update(override_settings)
    next_payload = dict(payload)
    defaults = {
        "temperature": float(merged_settings.get("temperature", 0.8)),
        "top_p": float(merged_settings.get("topP", 0.95)),
        "top_k": int(merged_settings.get("topK", 40)),
        "min_p": float(merged_settings.get("minP", 0.05)),
        "repeat_penalty": float(merged_settings.get("repeatPenalty", 1.0)),
        "repeat_last_n": int(merged_settings.get("repeatLastN", 64)),
        "presence_penalty": float(merged_settings.get("presencePenalty", 0.0)),
        "frequency_penalty": float(merged_settings.get("frequencyPenalty", 0.0)),
        "seed": int(merged_settings.get("seed", -1)),
        "max_tokens": int(merged_settings.get("outputTokens", 8192)),
    }
    for key, value in defaults.items():
        if key not in next_payload or next_payload.get(key) is None:
            next_payload[key] = value
    return next_payload
