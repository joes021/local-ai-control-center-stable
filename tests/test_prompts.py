import pytest

from local_ai_control_center_installer.prompts import (
    PromptCancelledError,
    StarterModelCatalogError,
    collect_installer_answers,
    render_confirmation_summary,
)
from local_ai_control_center_installer.runtime_manifest import StarterModelOption
from local_ai_control_center_installer.session import InstallerSession


def make_capturing_input(answers, prompts):
    iterator = iter(answers)

    def input_fn(prompt):
        prompts.append(prompt)
        return next(iterator)

    return input_fn


def test_collect_installer_answers_accepts_default_upgrade_and_paths():
    prompts = []
    answers = iter(["", "", "1", "1", "2", "", "1"])
    session = InstallerSession(existing_install_detected=True)

    updated = collect_installer_answers(
        session,
        input_fn=lambda prompt: prompts.append(prompt) or next(answers),
    )

    assert updated.install_mode == "upgrade"
    assert updated.install_root.endswith("LocalAIControlCenter")
    assert updated.starter_model == "recommended-6gb"
    assert updated.install_opencode is True
    assert updated.attempt_turboquant is False


def test_collect_installer_answers_records_additional_model_paths():
    answers = iter(["D:\\Apps\\LACC", "3", "2", "2", "C:\\models;E:\\shared-models", "1"])
    session = InstallerSession()

    updated = collect_installer_answers(session, input_fn=lambda _: next(answers))

    assert updated.install_mode == "fresh"
    assert updated.starter_model == "recommended-24gb"
    assert updated.install_opencode is False
    assert updated.attempt_turboquant is False
    assert updated.additional_model_paths == ["C:\\models", "E:\\shared-models"]


def test_collect_installer_answers_retries_invalid_numbered_input():
    answers = iter(["9", "2", "", "4", "1", "3", "2", "2", "", "7", "1"])
    outputs = []
    session = InstallerSession(existing_install_detected=True)

    updated = collect_installer_answers(
        session,
        input_fn=lambda _: next(answers),
        output_fn=outputs.append,
    )

    assert updated.install_mode == "fresh"
    assert updated.starter_model == "recommended-6gb"
    assert any("Please enter 1 or 2." in line for line in outputs)
    assert any("Please enter 1, 2, or 3." in line for line in outputs)


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
    assert (
        "Starter model: Qwen2.5 Coder 14B Instruct Q4_K_M (recommended-12gb)"
        in summary
    )
    assert "Install OpenCode: yes" in summary
    assert "Attempt TurboQuant: no" in summary
    assert "Additional model paths: C:\\models; E:\\shared-models" in summary


def test_collect_installer_answers_emits_summary_before_confirmation_prompt():
    prompts = []
    outputs = []
    session = InstallerSession()
    input_fn = make_capturing_input(
        ["D:\\Apps\\LACC", "2", "1", "1", "C:\\models", "1"],
        prompts,
    )

    updated = collect_installer_answers(
        session,
        input_fn=input_fn,
        output_fn=outputs.append,
    )

    assert outputs[-1] == render_confirmation_summary(updated)
    assert "Install root: D:\\Apps\\LACC" in outputs[-1]
    assert (
        "Starter model: Qwen2.5 Coder 14B Instruct Q4_K_M (recommended-12gb)"
        in outputs[-1]
    )
    assert "Install OpenCode: yes" in outputs[-1]
    assert "Attempt TurboQuant: yes" in outputs[-1]
    assert "Additional model paths: C:\\models" in outputs[-1]
    assert prompts[-1].startswith("Confirm choices")


def test_collect_installer_answers_raises_prompt_cancelled_error_on_cancel():
    answers = iter(["", "1", "1", "2", "", "2"])

    with pytest.raises(PromptCancelledError):
        collect_installer_answers(InstallerSession(), input_fn=lambda _: next(answers))


def test_collect_installer_answers_cancel_leaves_original_session_unchanged():
    original = InstallerSession(
        existing_install_detected=True,
        install_mode="upgrade",
        install_root="C:\\Existing",
        starter_model="recommended-6gb",
        install_opencode=False,
        attempt_turboquant=False,
        additional_model_paths=["D:\\models"],
    )
    answers = iter(["2", "D:\\Apps\\LACC", "3", "1", "1", "C:\\models", "2"])

    with pytest.raises(PromptCancelledError):
        collect_installer_answers(original, input_fn=lambda _: next(answers))

    assert original.install_mode == "upgrade"
    assert original.install_root == "C:\\Existing"
    assert original.starter_model == "recommended-6gb"
    assert original.install_opencode is False
    assert original.attempt_turboquant is False
    assert original.additional_model_paths == ["D:\\models"]


def test_collect_installer_answers_shows_numbered_options_and_defaults():
    prompts = []
    input_fn = make_capturing_input(["", "", "1", "2", "", "", "1"], prompts)

    collect_installer_answers(
        InstallerSession(existing_install_detected=True),
        input_fn=input_fn,
    )

    assert "Install mode" in prompts[0]
    assert "1) Upgrade" in prompts[0]
    assert "2) Fresh install" in prompts[0]
    assert "default: 1" in prompts[0]
    assert "Install root" in prompts[1]
    assert "Starter model" in prompts[2]
    assert "1) Qwen2.5 Coder 7B Instruct Q4_K_M (recommended-6gb)" in prompts[2]
    assert "2) Qwen2.5 Coder 14B Instruct Q4_K_M (recommended-12gb)" in prompts[2]
    assert "3) Qwen2.5 Coder 32B Instruct Q4_K_M (recommended-24gb)" in prompts[2]
    assert "default: 1" in prompts[2]
    assert "Install OpenCode" in prompts[3]
    assert "1) Yes" in prompts[3]
    assert "2) No" in prompts[3]
    assert "required for a successful installation" in prompts[3]
    assert "default: 1" in prompts[3]
    assert "Attempt TurboQuant" in prompts[4]
    assert "1) Yes" in prompts[4]
    assert "2) No" in prompts[4]
    assert "default: 2" in prompts[4]
    assert "Additional model paths" in prompts[5]
    assert "Confirm choices" in prompts[6]
    assert "1) Confirm" in prompts[6]
    assert "2) Cancel" in prompts[6]
    assert "default: 1" in prompts[6]


def test_collect_installer_answers_retries_invalid_confirmation_then_confirms():
    answers = iter(["", "1", "2", "", "", "0", "1"])
    outputs = []

    updated = collect_installer_answers(
        InstallerSession(),
        input_fn=lambda _: next(answers),
        output_fn=outputs.append,
    )

    assert updated.starter_model == "recommended-6gb"
    assert any("Please enter 1 or 2." in line for line in outputs)


def test_collect_installer_answers_uses_manifest_default_prompt_choice(monkeypatch):
    answers = iter(["", "", "1", "2", "", "1"])

    monkeypatch.setattr(
        "local_ai_control_center_installer.prompts.load_runtime_manifest",
        lambda: {"starter_models": {}},
    )
    monkeypatch.setattr(
        "local_ai_control_center_installer.prompts.list_prompt_starter_models",
        lambda manifest: [
            StarterModelOption(
                model_id="recommended-6gb",
                prompt_label="Qwen2.5 Coder 7B Instruct Q4_K_M (recommended-6gb)",
                prompt_order=1,
                recommended_default=False,
            ),
            StarterModelOption(
                model_id="recommended-12gb",
                prompt_label="Qwen2.5 Coder 14B Instruct Q4_K_M (recommended-12gb)",
                prompt_order=2,
                recommended_default=True,
            ),
            StarterModelOption(
                model_id="recommended-24gb",
                prompt_label="Qwen2.5 Coder 32B Instruct Q4_K_M (recommended-24gb)",
                prompt_order=3,
                recommended_default=False,
            ),
        ],
    )

    updated = collect_installer_answers(
        InstallerSession(),
        input_fn=lambda _: next(answers),
    )

    assert updated.starter_model == "recommended-12gb"


@pytest.mark.parametrize(
    ("side_effect", "expected_message"),
    [
        (FileNotFoundError("missing runtime manifest"), "missing runtime manifest"),
        (ValueError("malformed runtime manifest"), "malformed runtime manifest"),
        (
            ValueError("Duplicate starter model prompt_order: 1"),
            "Duplicate starter model prompt_order: 1",
        ),
    ],
)
def test_collect_installer_answers_wraps_starter_model_catalog_failures(
    monkeypatch,
    side_effect,
    expected_message,
):
    def raise_catalog_error():
        raise side_effect

    monkeypatch.setattr(
        "local_ai_control_center_installer.prompts.load_runtime_manifest",
        raise_catalog_error,
    )

    with pytest.raises(StarterModelCatalogError, match=expected_message):
        collect_installer_answers(InstallerSession(), input_fn=lambda _: "")
