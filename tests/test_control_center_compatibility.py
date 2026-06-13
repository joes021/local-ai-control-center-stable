import importlib

from fastapi.testclient import TestClient
from types import SimpleNamespace
from unittest.mock import patch

from local_ai_control_center_installer.control_center_backend.config import get_config
from local_ai_control_center_installer.control_center_backend.main import app
from local_ai_control_center_installer.control_center_backend.services import (
    compatibility_service,
)
from local_ai_control_center_installer.control_center_backend.services.compatibility_service import (
    calculate_compatibility,
)


def test_compatibility_check_route_passes_catalog_model_id():
    expected = {"status": "radi", "checkedAt": "2026-05-23T12:00:00Z", "summary": "staje"}
    from unittest.mock import patch

    with patch(
        "local_ai_control_center_installer.control_center_backend.routes.compatibility.run_compatibility_check",
        return_value=expected,
    ) as service:
        client = TestClient(app)
        response = client.post("/api/compatibility/check", json={"catalogModelId": "unsloth/demo/demo.gguf"})

    assert response.status_code == 200
    assert response.json() == expected
    service.assert_called_once_with(catalog_model_id="unsloth/demo/demo.gguf", model=None, overrides=None)


def test_compatibility_apply_route_returns_result_and_updated_payload():
    expected = {
        "result": {"status": "ok", "summary": "primenjeno"},
        "compatibility": {"status": "granicno", "fitLabel": "Granicno", "summary": "ponovo provereno"},
    }
    from unittest.mock import patch

    with patch(
        "local_ai_control_center_installer.control_center_backend.routes.compatibility.apply_compatibility_action",
        return_value=expected,
    ) as service:
        client = TestClient(app)
        response = client.post(
            "/api/compatibility/apply",
            json={
                "catalogModelId": "unsloth/demo/demo.gguf",
                "action": {"kind": "set-runtime-preference", "value": "turboquant"},
            },
        )

    assert response.status_code == 200
    assert response.json() == expected
    service.assert_called_once()


def test_calculate_compatibility_returns_runtime_breakdown_and_best_runtime():
    payload = calculate_compatibility(
        {
            "id": "unsloth/demo.gguf",
            "label": "Demo Q4",
            "quantization": "Q4_K_M",
            "approxSizeGiB": 5.6,
            "minimumVramGiB": 4.8,
            "recommendedVramGiB": 6.2,
            "minimumRamGiB": 10.0,
            "contextWindow": 131072,
            "defaultOutputTokens": 4096,
        },
        system_info={
            "ramGiB": 32.0,
            "vramGiB": 12.0,
            "turboQuantAvailable": True,
            "context": 131072,
            "outputTokens": 4096,
            "turboQuantConfig": {
                "ctk": "turbo4",
                "ctv": "turbo3",
                "ncmoe": 20,
                "runtimePreference": "turboquant",
            },
        },
    )

    assert payload["bestRuntime"] in {"llama.cpp", "turboquant"}
    assert payload["bestRuntimeLabel"] in {"llama.cpp", "TurboQuant"}
    assert payload["overallFitStatus"] in {"radi", "granicno", "ne radi"}
    assert payload["overallFitLabel"]
    runtime_breakdown = payload["runtimeBreakdown"]
    assert set(runtime_breakdown) == {"llama.cpp", "turboquant"}
    assert runtime_breakdown["llama.cpp"]["fitStatus"] in {"radi", "granicno", "ne radi"}
    assert runtime_breakdown["turboquant"]["fitStatus"] in {"radi", "granicno", "ne radi"}
    assert "outputPressure" in payload["memoryBudget"]
    assert "headroomGiB" in payload["memoryBudget"]["vram"]


def test_calculate_compatibility_marks_mtp_as_not_working_for_turboquant():
    payload = calculate_compatibility(
        {
            "id": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF/Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "label": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "quantization": "IQ2_XXS",
            "approxSizeGiB": 10.0,
            "minimumVramGiB": 8.0,
            "recommendedVramGiB": 10.0,
            "minimumRamGiB": 18.0,
            "contextWindow": 262144,
            "defaultOutputTokens": 4096,
        },
        system_info={
            "ramGiB": 64.0,
            "vramGiB": 24.0,
            "turboQuantAvailable": True,
            "context": 131072,
            "outputTokens": 4096,
            "turboQuantConfig": {
                "ctk": "turbo4",
                "ctv": "turbo3",
                "ncmoe": 30,
                "runtimePreference": "turboquant",
            },
        },
    )

    assert payload["runtimeBreakdown"]["turboquant"]["fitStatus"] == "ne radi"
    assert "MTP" in payload["runtimeBreakdown"]["turboquant"]["summary"]


def test_calculate_compatibility_raises_pressure_for_large_context_and_output():
    payload = calculate_compatibility(
        {
            "id": "unsloth/demo-large.gguf",
            "label": "Demo Large Q4",
            "quantization": "Q4_K_M",
            "approxSizeGiB": 11.0,
            "minimumVramGiB": 8.0,
            "recommendedVramGiB": 12.0,
            "minimumRamGiB": 20.0,
            "contextWindow": 262144,
            "defaultOutputTokens": 4096,
        },
        system_info={
            "ramGiB": 32.0,
            "vramGiB": 12.0,
            "turboQuantAvailable": True,
            "context": 262144,
            "outputTokens": 8192,
            "turboQuantConfig": {
                "ctk": "turbo4",
                "ctv": "turbo3",
                "ncmoe": 20,
                "runtimePreference": "turboquant",
            },
        },
    )

    assert payload["memoryBudget"]["contextPressure"]["level"] in {"medium", "high"}
    assert payload["memoryBudget"]["outputPressure"]["level"] in {"medium", "high"}
    assert payload["runtimeBreakdown"]["llama.cpp"]["fitStatus"] in {"granicno", "ne radi"}


def test_calculate_compatibility_marks_turboquant_unavailable_when_installation_lacks_it():
    payload = calculate_compatibility(
        {
            "id": "unsloth/demo.gguf",
            "label": "Demo Q4",
            "quantization": "Q4_K_M",
            "approxSizeGiB": 5.6,
            "minimumVramGiB": 4.8,
            "recommendedVramGiB": 6.2,
            "minimumRamGiB": 10.0,
            "contextWindow": 131072,
            "defaultOutputTokens": 4096,
        },
        system_info={
            "ramGiB": 32.0,
            "vramGiB": 12.0,
            "turboQuantAvailable": False,
            "context": 131072,
            "outputTokens": 4096,
            "turboQuantConfig": {
                "ctk": "turbo4",
                "ctv": "turbo3",
                "ncmoe": 20,
                "runtimePreference": "turboquant",
            },
        },
    )

    assert payload["runtimeBreakdown"]["turboquant"]["fitStatus"] == "ne radi"
    assert "nije dostupan" in payload["runtimeBreakdown"]["turboquant"]["summary"].lower()


def test_calculate_compatibility_uses_installed_size_when_approx_size_is_missing():
    payload = calculate_compatibility(
        {
            "id": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF/Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "label": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "installedSizeGiB": 10.02,
            "contextWindow": 262144,
            "defaultOutputTokens": 4096,
        },
        system_info={
            "ramGiB": 15.88,
            "vramGiB": 6.0,
            "turboQuantAvailable": True,
            "context": 262144,
            "outputTokens": 8192,
            "turboQuantConfig": {
                "ctk": "turbo4",
                "ctv": "turbo3",
                "ncmoe": 20,
                "runtimePreference": "turboquant",
            },
        },
    )

    assert payload["overallFitStatus"] == "ne radi"
    assert payload["bestRuntime"] == "llama.cpp"
    assert payload["memoryBudget"]["vram"]["requiredGiB"] > 6.0


def test_calculate_compatibility_treats_ud_iq_quant_as_turboquant_ready_for_non_mtp_models():
    payload = calculate_compatibility(
        {
            "id": "unsloth-unsloth-qwen3-6-35b-a3b-gguf-qwen3-6-35b-a3b-ud-iq2-xxs",
            "label": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "filename": "Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf",
            "family": "Qwen",
            "installedSizeGiB": 10.02,
            "repo": "unsloth/Qwen3.6-35B-A3B-GGUF",
        },
        system_info={
            "ramGiB": 31.77,
            "vramGiB": 12.0,
            "turboQuantAvailable": True,
            "context": 262144,
            "outputTokens": 8192,
            "turboQuantConfig": {
                "ctk": "turbo4",
                "ctv": "turbo3",
                "ncmoe": 30,
                "runtimePreference": "llama.cpp",
            },
        },
    )

    assert payload["overallFitStatus"] == "granicno"
    assert payload["bestRuntime"] == "turboquant"
    assert payload["runtimeBreakdown"]["turboquant"]["fitStatus"] == "granicno"
    assert payload["runtimeBreakdown"]["turboquant"]["estimated"]["requiredVramGiB"] < 12.0


def test_calculate_compatibility_uses_absolute_path_size_for_local_model_when_size_fields_are_missing():
    fake_size_gib = 16.08
    fake_size_bytes = int(fake_size_gib * (1024**3))
    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.stat", return_value=SimpleNamespace(st_size=fake_size_bytes)),
    ):
        payload = calculate_compatibility(
            {
                "id": "local-qwen3-6-28b-reap20-a3b-q4-k-m",
                "label": "Qwen3.6-28B-REAP20-A3B-Q4_K_M",
                "filename": "Qwen3.6-28B-REAP20-A3B-Q4_K_M.gguf",
                "family": "Custom",
                "absolute_path": "C:/models/Qwen3.6-28B-REAP20-A3B-Q4_K_M.gguf",
            },
            system_info={
                "ramGiB": 31.77,
                "vramGiB": 12.0,
                "turboQuantAvailable": True,
                "context": 32768,
                "outputTokens": 2048,
                "turboQuantConfig": {
                    "ctk": "turbo4",
                    "ctv": "turbo3",
                    "ncmoe": 20,
                    "runtimePreference": "turboquant",
                },
            },
        )

    assert payload["memoryBudget"]["vram"]["requiredGiB"] > 10.0
    assert payload["memoryBudget"]["ram"]["requiredGiB"] > 20.0
    assert payload["overallFitStatus"] in {"granicno", "ne radi"}


def test_detect_local_system_info_reuses_recent_hardware_snapshot(monkeypatch, tmp_path):
    module = importlib.import_module(
        "local_ai_control_center_installer.control_center_backend.services.compatibility_service"
    )
    module = importlib.reload(module)

    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    config = get_config()

    calls = {
        "settings": 0,
        "turbo": 0,
        "ram": 0,
        "vram": 0,
        "availability": 0,
    }

    def fake_settings(config=None, include_search_provider_status=False):
        calls["settings"] += 1
        return {"context": 262144, "outputTokens": 8192}

    def fake_turbo_config(config=None):
        calls["turbo"] += 1
        return {"ctk": "turbo4", "ctv": "turbo3"}

    def fake_ram():
        calls["ram"] += 1
        return 32.0

    def fake_vram():
        calls["vram"] += 1
        return 12.0

    def fake_packaged(config):
        calls["availability"] += 1
        return True

    monkeypatch.setattr(module, "load_settings_payload", fake_settings)
    monkeypatch.setattr(module, "load_turboquant_config", fake_turbo_config)
    monkeypatch.setattr(module, "detect_ram_gib", fake_ram)
    monkeypatch.setattr(module, "detect_vram_gib", fake_vram)
    monkeypatch.setattr(module, "_detect_packaged_turboquant_available", fake_packaged)

    first = module.detect_local_system_info(config=config)
    second = module.detect_local_system_info(config=config)

    assert first == second
    assert calls == {
        "settings": 1,
        "turbo": 1,
        "ram": 1,
        "vram": 1,
        "availability": 1,
    }


def test_detect_ram_gib_reuses_recent_windows_probe(monkeypatch):
    module = importlib.reload(compatibility_service)
    calls: list[dict[str, object]] = []

    class FakeCompletedProcess:
        returncode = 0
        stdout = "31.77"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return FakeCompletedProcess()

    monkeypatch.setattr(module.os, "name", "nt", raising=False)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    first = module.detect_ram_gib()
    second = module.detect_ram_gib()

    assert first == 31.77
    assert second == first
    assert len(calls) == 1
    assert calls[0]["creationflags"] == getattr(module.subprocess, "CREATE_NO_WINDOW", 0)


def test_detect_vram_gib_reuses_recent_probe(monkeypatch):
    module = importlib.reload(compatibility_service)
    calls: list[dict[str, object]] = []

    class FakeCompletedProcess:
        returncode = 0
        stdout = "12288"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return FakeCompletedProcess()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    first = module.detect_vram_gib()
    second = module.detect_vram_gib()

    assert first == 12.0
    assert second == first
    assert len(calls) == 1
    assert calls[0]["creationflags"] == getattr(module.subprocess, "CREATE_NO_WINDOW", 0)
