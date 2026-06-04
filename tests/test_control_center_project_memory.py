import importlib
import pytest


def _load_project_memory_service():
    try:
        return importlib.import_module(
            "local_ai_control_center_installer.control_center_backend.services.project_memory_service"
        )
    except ModuleNotFoundError:
        pytest.fail("project_memory_service modul još ne postoji")


def test_project_memory_service_returns_default_memory_when_store_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    project_memory_service = _load_project_memory_service()

    payload = project_memory_service.get_project_memory()

    assert payload["status"] == "idle"
    assert payload["goal"]["text"] == ""
    assert payload["rules"] == []
    assert payload["decisions"] == []
    assert payload["progress"] == []
    assert payload["nextSteps"] == []


def test_project_memory_service_updates_goal_rules_and_next_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    project_memory_service = _load_project_memory_service()

    project_memory_service.save_project_memory(
        {
            "goal": {"text": "Napraviti playable HTML igru", "locked": True},
            "rules": [{"id": "one-file", "text": "Jedan HTML fajl", "locked": True}],
            "decisions": [{"id": "canvas", "text": "Koristi canvas"}],
            "progress": [{"id": "loop", "text": "Postavljena game loop logika"}],
            "nextSteps": [{"id": "collision", "text": "Dovršiti collision"}],
        }
    )

    payload = project_memory_service.get_project_memory()

    assert payload["goal"]["text"] == "Napraviti playable HTML igru"
    assert payload["goal"]["locked"] is True
    assert payload["rules"][0]["text"] == "Jedan HTML fajl"
    assert payload["nextSteps"][0]["text"] == "Dovršiti collision"


def test_project_memory_seed_from_task_extracts_goal_rules_and_next_step():
    project_memory_service = _load_project_memory_service()

    seeded = project_memory_service.seed_project_memory_from_task(
        goal="Napraviti HTML igru",
        task_prompt="""Napravi playable HTML igru u jednom fajlu.
Mora imati score i restart.
Prvo dovrši collision i game over flow.""",
    )

    assert seeded["goal"]["text"] == "Napraviti HTML igru"
    assert any("jednom fajlu" in item["text"].lower() for item in seeded["rules"])
    assert any("score" in item["text"].lower() for item in seeded["rules"])
    assert any("collision" in item["text"].lower() for item in seeded["nextSteps"])
