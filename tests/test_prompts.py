from local_ai_control_center_installer.prompts import (
    collect_installer_answers,
    render_confirmation_summary,
)
from local_ai_control_center_installer.session import InstallerSession


def test_collect_installer_answers_accepts_default_upgrade_and_paths():
    answers = iter(["", "", "1", "1", "2", ""])
    session = InstallerSession(existing_install_detected=True)

    updated = collect_installer_answers(session, input_fn=lambda _: next(answers))

    assert updated.install_mode == "upgrade"
    assert updated.install_root.endswith("LocalAIControlCenter")
    assert updated.starter_model == "recommended-6gb"


def test_collect_installer_answers_records_additional_model_paths():
    answers = iter(["D:\\Apps\\LACC", "3", "2", "2", "C:\\models;E:\\shared-models"])
    session = InstallerSession()

    updated = collect_installer_answers(session, input_fn=lambda _: next(answers))

    assert updated.install_mode == "fresh"
    assert updated.starter_model == "recommended-24gb"
    assert updated.additional_model_paths == ["C:\\models", "E:\\shared-models"]


def test_collect_installer_answers_retries_invalid_numbered_input():
    answers = iter(["9", "2", "", "4", "1", "3", "2", "2", ""])
    outputs = []
    session = InstallerSession(existing_install_detected=True)

    updated = collect_installer_answers(
        session,
        input_fn=lambda _: next(answers),
        output_fn=outputs.append,
    )

    assert updated.install_mode == "fresh"
    assert updated.starter_model == "recommended-6gb"
    assert any("Expected one of ['1', '2']" in line for line in outputs)
    assert any("Expected one of ['1', '2', '3']" in line for line in outputs)


def test_render_confirmation_summary_lists_future_facing_answers():
    session = InstallerSession(
        existing_install_detected=True,
        install_mode="upgrade",
        install_root="C:\\Apps\\LACC",
        starter_model="recommended-12gb",
        install_opencode=True,
        attempt_turboquant=False,
        additional_model_paths=["C:\\models", "E:\\shared-models"],
    )

    summary = render_confirmation_summary(session)

    assert "Install mode: upgrade" in summary
    assert "Install root: C:\\Apps\\LACC" in summary
    assert "Starter model: recommended-12gb" in summary
    assert "Install OpenCode: yes" in summary
    assert "Attempt TurboQuant: no" in summary
    assert "Additional model paths: C:\\models; E:\\shared-models" in summary


def test_collect_installer_answers_emits_summary_after_collecting_answers():
    answers = iter(["D:\\Apps\\LACC", "2", "1", "1", "C:\\models"])
    outputs = []
    session = InstallerSession()

    updated = collect_installer_answers(
        session,
        input_fn=lambda _: next(answers),
        output_fn=outputs.append,
    )

    assert outputs[-1] == render_confirmation_summary(updated)
    assert "Install root: D:\\Apps\\LACC" in outputs[-1]
    assert "Starter model: recommended-12gb" in outputs[-1]
    assert "Install OpenCode: yes" in outputs[-1]
    assert "Attempt TurboQuant: yes" in outputs[-1]
    assert "Additional model paths: C:\\models" in outputs[-1]
