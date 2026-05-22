from copy import deepcopy
from pathlib import Path

from .runtime_manifest import list_prompt_starter_models, load_runtime_manifest

DEFAULT_INSTALL_ROOT = str(Path.home() / "LocalAIControlCenter")


class PromptCancelledError(Exception):
    pass


class StarterModelCatalogError(Exception):
    pass


def choose_number(raw_value: str, default: str, allowed: set[str]) -> str:
    value = raw_value.strip() or default
    if value not in allowed:
        raise ValueError(friendly_number_error(sorted(allowed)))
    return value


def parse_model_paths(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(";") if item.strip()]


def friendly_number_error(allowed: list[str]) -> str:
    if len(allowed) == 1:
        return f"Please enter {allowed[0]}."
    if len(allowed) == 2:
        return f"Please enter {allowed[0]} or {allowed[1]}."
    prefix = ", ".join(allowed[:-1])
    return f"Please enter {prefix}, or {allowed[-1]}."


def build_numbered_prompt(title: str, options: list[tuple[str, str]], default: str) -> str:
    lines = [title]
    for number, label in options:
        lines.append(f"{number}) {label}")
    lines.append(f"Select a number (default: {default}): ")
    return "\n".join(lines)


def build_starter_model_prompt_options() -> tuple[list[tuple[str, str]], dict[str, str], str]:
    try:
        options = list_prompt_starter_models(load_runtime_manifest())
    except (OSError, ValueError) as exc:
        raise StarterModelCatalogError(
            f"Starter model catalog is unavailable: {exc}"
        ) from exc
    numbered_options = [
        (str(index), option.prompt_label) for index, option in enumerate(options, start=1)
    ]
    number_to_model_id = {
        str(index): option.model_id for index, option in enumerate(options, start=1)
    }
    default_choice = determine_default_prompt_choice(options)
    return numbered_options, number_to_model_id, default_choice


def determine_default_prompt_choice(options) -> str:
    for index, option in enumerate(options, start=1):
        if option.recommended_default:
            return str(index)
    raise ValueError("Starter model catalog is missing a recommended default.")


def prompt_for_number(
    prompt_text: str,
    default: str,
    allowed: set[str],
    input_fn=input,
    output_fn=print,
) -> str:
    while True:
        try:
            return choose_number(input_fn(prompt_text), default, allowed)
        except ValueError as error:
            output_fn(str(error))


def render_confirmation_summary(session) -> str:
    additional_paths = "; ".join(session.additional_model_paths) or "(none)"
    opencode = "yes" if session.install_opencode else "no"
    turboquant = "yes" if session.attempt_turboquant else "no"
    return "\n".join(
        [
            "Installer configuration summary:",
            f"Install mode: {session.install_mode}",
            f"Install root: {session.install_root}",
            f"Starter model: {session.starter_model}",
            f"Install OpenCode: {opencode}",
            f"Attempt TurboQuant: {turboquant}",
            f"Additional model paths: {additional_paths}",
        ]
    )


def collect_installer_answers(session, input_fn=input, output_fn=print):
    draft_session = deepcopy(session)

    if draft_session.existing_install_detected:
        install_mode = prompt_for_number(
            build_numbered_prompt(
                "Install mode",
                [("1", "Upgrade"), ("2", "Fresh install")],
                "1",
            ),
            "1",
            {"1", "2"},
            input_fn=input_fn,
            output_fn=output_fn,
        )
        draft_session.install_mode = "upgrade" if install_mode == "1" else "fresh"
    else:
        draft_session.install_mode = "fresh"

    default_install_root = draft_session.install_root or DEFAULT_INSTALL_ROOT
    draft_session.install_root = (
        input_fn(f"Install root (default: {default_install_root}): ").strip()
        or default_install_root
    )

    starter_model_options, starter_model_choices, starter_model_default = (
        build_starter_model_prompt_options()
    )
    model_choice = prompt_for_number(
        build_numbered_prompt(
            "Starter model",
            starter_model_options,
            starter_model_default,
        ),
        starter_model_default,
        set(starter_model_choices),
        input_fn=input_fn,
        output_fn=output_fn,
    )
    draft_session.starter_model = starter_model_choices[model_choice]
    draft_session.install_opencode = (
        prompt_for_number(
            build_numbered_prompt(
                "Install OpenCode (required for a successful installation)",
                [("1", "Yes"), ("2", "No")],
                "1",
            ),
            "1",
            {"1", "2"},
            input_fn=input_fn,
            output_fn=output_fn,
        )
        == "1"
    )
    draft_session.attempt_turboquant = (
        prompt_for_number(
            build_numbered_prompt(
                "Attempt TurboQuant",
                [("1", "Yes"), ("2", "No")],
                "2",
            ),
            "2",
            {"1", "2"},
            input_fn=input_fn,
            output_fn=output_fn,
        )
        == "1"
    )
    draft_session.additional_model_paths = parse_model_paths(
        input_fn("Additional model paths (semicolon-separated, optional): ")
    )

    output_fn(render_confirmation_summary(draft_session))
    confirmation = prompt_for_number(
        build_numbered_prompt(
            "Confirm choices",
            [("1", "Confirm"), ("2", "Cancel")],
            "1",
        ),
        "1",
        {"1", "2"},
        input_fn=input_fn,
        output_fn=output_fn,
    )
    if confirmation == "2":
        raise PromptCancelledError("Installer questionnaire cancelled.")

    return draft_session
