import json
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def _write_settings(install_root: Path, payload: dict[str, object]) -> None:
    settings_path = install_root / "config" / "control-center" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_tuning_profiles(install_root: Path, payload: dict[str, object]) -> None:
    profiles_path = install_root / "config" / "control-center" / "tuning-lab-runtime-profiles.json"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_runtime_proxy_injects_generation_defaults_when_search_is_off(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "off",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 5,
            "webSearchTimeoutSeconds": 20,
            "webSearchPromptPrefix": "/web",
            "temperature": 0.2,
            "topK": 20,
            "topP": 0.9,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 96,
            "presencePenalty": 0.3,
            "frequencyPenalty": 0.1,
            "seed": 42,
            "outputTokens": 2048,
        },
    )

    captured: dict[str, object] = {}

    def fake_forward(*, method, path, body, headers):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        captured["headers"] = headers
        return {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": True, "echo": body}).encode("utf-8"),
        }

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.runtime_proxy.forward_runtime_request",
        fake_forward,
    )

    client = TestClient(app)
    request_payload = {
        "model": "local-lacc/demo.gguf",
        "messages": [{"role": "user", "content": "zdravo"}],
        "stream": False,
    }
    response = client.post("/api/runtime-proxy/v1/chat/completions", json=request_payload)

    assert response.status_code == 200
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/chat/completions"
    assert captured["body"] == {
        **request_payload,
        "temperature": 0.2,
        "top_k": 20,
        "top_p": 0.9,
        "min_p": 0.0,
        "repeat_penalty": 1.0,
        "repeat_last_n": 96,
        "presence_penalty": 0.3,
        "frequency_penalty": 0.1,
        "seed": 42,
        "max_tokens": 2048,
    }
    assert response.json()["echo"] == captured["body"]


def test_runtime_proxy_augments_chat_request_when_on_demand_prefix_is_present(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "on-demand",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 5,
            "webSearchTimeoutSeconds": 20,
            "webSearchPromptPrefix": "/web",
        },
    )

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.runtime_proxy.perform_search_query",
        lambda query: {
            "status": "ok",
            "provider": "searxng",
            "query": query,
            "resultCount": 1,
            "results": [
                {
                    "title": "AI search result",
                    "url": "https://example.invalid/search",
                    "snippet": "Search snippet",
                    "engine": "demo",
                }
            ],
            "summary": "Pronađen je 1 rezultat.",
        },
    )

    captured: dict[str, object] = {}

    def fake_forward(*, method, path, body, headers):
        captured["body"] = body
        return {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": True}).encode("utf-8"),
        }

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.runtime_proxy.forward_runtime_request",
        fake_forward,
    )

    client = TestClient(app)
    response = client.post(
        "/api/runtime-proxy/v1/chat/completions",
        json={
            "model": "local-lacc/demo.gguf",
            "messages": [{"role": "user", "content": "/web najnovije ai vesti"}],
            "stream": False,
        },
    )

    assert response.status_code == 200
    proxied_messages = captured["body"]["messages"]
    assert proxied_messages[0]["role"] == "system"
    assert "AI search result" in str(proxied_messages[0]["content"])
    assert proxied_messages[-1]["content"] == "najnovije ai vesti"
    assert captured["body"]["temperature"] == 0.8
    assert captured["body"]["top_p"] == 0.95
    assert captured["body"]["top_k"] == 40
    assert captured["body"]["max_tokens"] == 8192


def test_runtime_proxy_keeps_explicit_generation_values_from_client(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "off",
            "webSearchProvider": "searxng",
            "temperature": 0.2,
            "topK": 20,
            "topP": 0.9,
            "minP": 0.0,
            "repeatPenalty": 1.0,
            "repeatLastN": 96,
            "presencePenalty": 0.3,
            "frequencyPenalty": 0.1,
            "seed": 42,
            "outputTokens": 2048,
        },
    )

    captured: dict[str, object] = {}

    def fake_forward(*, method, path, body, headers):
        captured["body"] = body
        return {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": True, "echo": body}).encode("utf-8"),
        }

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.runtime_proxy.forward_runtime_request",
        fake_forward,
    )

    client = TestClient(app)
    response = client.post(
        "/api/runtime-proxy/v1/chat/completions",
        json={
            "model": "local-lacc/demo.gguf",
            "messages": [{"role": "user", "content": "zdravo"}],
            "stream": False,
            "temperature": 0.6,
            "top_k": 5,
            "top_p": 0.7,
            "min_p": 0.01,
            "repeat_penalty": 1.2,
            "repeat_last_n": 32,
            "presence_penalty": 0.0,
            "frequency_penalty": -0.2,
            "seed": 777,
            "max_tokens": 512,
        },
    )

    assert response.status_code == 200
    assert captured["body"]["temperature"] == 0.6
    assert captured["body"]["top_k"] == 5
    assert captured["body"]["top_p"] == 0.7
    assert captured["body"]["min_p"] == 0.01
    assert captured["body"]["repeat_penalty"] == 1.2
    assert captured["body"]["repeat_last_n"] == 32
    assert captured["body"]["presence_penalty"] == 0.0
    assert captured["body"]["frequency_penalty"] == -0.2
    assert captured["body"]["seed"] == 777
    assert captured["body"]["max_tokens"] == 512


def test_tuning_runtime_proxy_injects_slot_specific_generation_defaults(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "off",
            "temperature": 0.8,
            "topK": 40,
            "topP": 0.95,
            "minP": 0.05,
            "repeatPenalty": 1.0,
            "repeatLastN": 64,
            "presencePenalty": 0.0,
            "frequencyPenalty": 0.0,
            "seed": -1,
            "outputTokens": 8192,
        },
    )
    _write_tuning_profiles(
        install_root,
        {
            "profiles": [
                {
                    "token": "slot-a",
                    "experimentId": "exp-1",
                    "slotId": "recommended",
                    "settingsPatch": {
                        "temperature": 0.25,
                        "topK": 12,
                        "topP": 0.72,
                        "minP": 0.01,
                        "repeatPenalty": 1.15,
                        "repeatLastN": 24,
                        "presencePenalty": 0.2,
                        "frequencyPenalty": -0.1,
                        "seed": 123,
                        "outputTokens": 640,
                    },
                },
                {
                    "token": "slot-b",
                    "experimentId": "exp-1",
                    "slotId": "custom",
                    "settingsPatch": {
                        "temperature": 1.1,
                        "topK": 80,
                        "topP": 0.99,
                        "minP": 0.09,
                        "repeatPenalty": 1.0,
                        "repeatLastN": 96,
                        "presencePenalty": 0.0,
                        "frequencyPenalty": 0.5,
                        "seed": 999,
                        "outputTokens": 1200,
                    },
                },
            ]
        },
    )

    captured_bodies: list[dict[str, object]] = []

    def fake_forward(*, method, path, body, headers):
        assert method == "POST"
        assert path == "/v1/chat/completions"
        assert isinstance(body, dict)
        captured_bodies.append(body)
        return {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"ok": True, "echo": body}).encode("utf-8"),
        }

    monkeypatch.setattr(
        "local_ai_control_center_installer.control_center_backend.routes.runtime_proxy.forward_runtime_request",
        fake_forward,
    )

    client = TestClient(app)
    request_payload = {
        "model": "local-lacc/demo.gguf",
        "messages": [{"role": "user", "content": "test"}],
        "stream": False,
    }

    slot_a_response = client.post("/api/runtime-proxy/tuning/slot-a/v1/chat/completions", json=request_payload)
    slot_b_response = client.post("/api/runtime-proxy/tuning/slot-b/v1/chat/completions", json=request_payload)

    assert slot_a_response.status_code == 200
    assert slot_b_response.status_code == 200
    assert captured_bodies[0]["temperature"] == 0.25
    assert captured_bodies[0]["top_k"] == 12
    assert captured_bodies[0]["top_p"] == 0.72
    assert captured_bodies[0]["min_p"] == 0.01
    assert captured_bodies[0]["repeat_penalty"] == 1.15
    assert captured_bodies[0]["repeat_last_n"] == 24
    assert captured_bodies[0]["presence_penalty"] == 0.2
    assert captured_bodies[0]["frequency_penalty"] == -0.1
    assert captured_bodies[0]["seed"] == 123
    assert captured_bodies[0]["max_tokens"] == 640
    assert captured_bodies[1]["temperature"] == 1.1
    assert captured_bodies[1]["top_k"] == 80
    assert captured_bodies[1]["top_p"] == 0.99
    assert captured_bodies[1]["min_p"] == 0.09
    assert captured_bodies[1]["frequency_penalty"] == 0.5
    assert captured_bodies[1]["seed"] == 999
    assert captured_bodies[1]["max_tokens"] == 1200


def test_tuning_runtime_proxy_returns_404_for_unknown_profile_token(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(install_root, {"webSearchMode": "off"})

    client = TestClient(app)
    response = client.post(
        "/api/runtime-proxy/tuning/missing-token/v1/chat/completions",
        json={"model": "local-lacc/demo.gguf", "messages": [{"role": "user", "content": "x"}]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "tuning_runtime_profile_missing"
