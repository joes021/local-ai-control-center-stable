import pytest

from local_ai_control_center_installer.windows_release import (
    build_versioned_setup_name,
    run_windows_installer_entry,
)


def test_build_versioned_setup_name_embeds_version_number():
    assert build_versioned_setup_name("0.1.2") == "LocalAIControlCenterSetup-v0.1.2.exe"


def test_build_versioned_setup_name_normalizes_existing_v_prefix():
    assert build_versioned_setup_name(" v0.1.2 ") == "LocalAIControlCenterSetup-v0.1.2.exe"


def test_build_versioned_setup_name_rejects_blank_version():
    with pytest.raises(ValueError, match="version is required"):
        build_versioned_setup_name("  ")


def test_run_windows_installer_entry_waits_for_confirmation_in_frozen_mode():
    prompts: list[str] = []

    exit_code = run_windows_installer_entry(
        main_fn=lambda: 1,
        pause_fn=lambda prompt: prompts.append(prompt) or "",
        frozen=True,
    )

    assert exit_code == 1
    assert prompts == ["Press Enter to close the installer window..."]


def test_run_windows_installer_entry_does_not_pause_when_not_frozen():
    prompts: list[str] = []

    exit_code = run_windows_installer_entry(
        main_fn=lambda: 0,
        pause_fn=lambda prompt: prompts.append(prompt) or "",
        frozen=False,
    )

    assert exit_code == 0
    assert prompts == []


def test_run_windows_installer_entry_waits_for_confirmation_when_main_fn_raises():
    prompts: list[str] = []

    def crash() -> int:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_windows_installer_entry(
            main_fn=crash,
            pause_fn=lambda prompt: prompts.append(prompt) or "",
            frozen=True,
        )

    assert prompts == ["Press Enter to close the installer window..."]


def test_run_windows_installer_entry_dispatches_panel_mode_without_pause():
    calls: list[str] = []
    prompts: list[str] = []

    exit_code = run_windows_installer_entry(
        main_fn=lambda: calls.append("installer") or 1,
        panel_main_fn=lambda argv=None: calls.append("panel") or 0,
        argv=["LocalAIControlCenterPanel.exe", "--panel", "--install-root", "C:\\AI"],
        pause_fn=lambda prompt: prompts.append(prompt) or "",
        frozen=True,
    )

    assert exit_code == 0
    assert calls == ["panel"]
    assert prompts == []
