from copy import deepcopy
from pathlib import Path

from .platform_paths import default_install_root_for_platform
from .runtime_manifest import (
    list_prompt_starter_models,
    load_runtime_manifest,
    resolve_requested_starter_model,
)

UTF8_BOM_MOJIBAKE = "\u00ef\u00bb\u00bf"


class PromptCancelledError(Exception):
    pass


class StarterModelCatalogError(Exception):
    pass


def normalize_prompt_input(raw_value: str) -> str:
    return (
        raw_value.replace("\ufeff", "")
        .replace(UTF8_BOM_MOJIBAKE, "")
        .strip()
    )


def choose_number(raw_value: str, default: str, allowed: set[str]) -> str:
    value = normalize_prompt_input(raw_value) or default
    if value not in allowed:
        raise ValueError(friendly_number_error(sorted(allowed)))
    return value


def parse_model_paths(raw_value: str) -> list[str]:
    return [
        normalized
        for item in raw_value.split(";")
        if (normalized := normalize_prompt_input(item))
    ]


def friendly_number_error(allowed: list[str]) -> str:
    if len(allowed) == 1:
        return f"Please enter {allowed[0]}."
    if len(allowed) == 2:
        return f"Please enter {allowed[0]} or {allowed[1]}."
    prefix = ", ".join(allowed[:-1])
    return f"Please enter {prefix}, or {allowed[-1]}."


def count_questionnaire_steps(existing_install_detected: bool) -> int:
    return 7 if existing_install_detected else 6


def path_looks_like_existing_install(install_root: str | None) -> bool:
    normalized = normalize_prompt_input(install_root or "")
    if not normalized:
        return False
    return Path(normalized).expanduser().exists()


def build_step_title(step_index: int, total_steps: int, title: str) -> str:
    return f"[{step_index}/{total_steps}] {title}"


def build_numbered_prompt(
    title: str,
    options: list[tuple[str, str]],
    default: str,
    *,
    step_index: int | None = None,
    total_steps: int | None = None,
) -> str:
    resolved_title = title
    if step_index is not None and total_steps is not None:
        resolved_title = build_step_title(step_index, total_steps, title)
    lines = [resolved_title]
    for number, label in options:
        lines.append(f"{number}) {label}")
    lines.append(f"Select a number (default: {default}): ")
    return "\n".join(lines)


def build_text_prompt(
    title: str,
    *,
    step_index: int,
    total_steps: int,
) -> str:
    return f"{build_step_title(step_index, total_steps, title)}: "


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
    starter_model_label = _render_selected_starter_model_label(session.starter_model)
    return "\n".join(
        [
            "Installer configuration summary:",
            f"Install mode: {session.install_mode}",
            f"Install root: {session.install_root}",
            f"Starter model: {starter_model_label}",
            f"Install OpenCode: {opencode}",
            f"Attempt TurboQuant: {turboquant}",
            f"Additional model paths: {additional_paths}",
        ]
    )


def _render_selected_starter_model_label(starter_model_id: str | None) -> str:
    normalized = (starter_model_id or "").strip()
    if not normalized:
        return "(none)"

    try:
        manifest = load_runtime_manifest()
        entry = resolve_requested_starter_model(manifest, normalized)
    except (OSError, ValueError):
        return normalized

    prompt_label = entry.get("prompt_label")
    if not isinstance(prompt_label, str) or not prompt_label.strip():
        return normalized
    return prompt_label.strip()


def collect_installer_answers(session, input_fn=input, output_fn=print):
    draft_session = deepcopy(session)
    total_steps = count_questionnaire_steps(draft_session.existing_install_detected)
    step_index = 1

    if draft_session.existing_install_detected:
        install_mode = prompt_for_number(
            build_numbered_prompt(
                "Install mode",
                [("1", "Upgrade"), ("2", "Fresh install")],
                "1",
                step_index=step_index,
                total_steps=total_steps,
            ),
            "1",
            {"1", "2"},
            input_fn=input_fn,
            output_fn=output_fn,
        )
        draft_session.install_mode = "upgrade" if install_mode == "1" else "fresh"
        step_index += 1
    else:
        draft_session.install_mode = "fresh"

    default_install_root = draft_session.install_root or str(
        default_install_root_for_platform(platform=draft_session.platform).expanduser()
    )
    draft_session.install_root = (
        normalize_prompt_input(
            input_fn(
                build_text_prompt(
                    f"Install root (default: {default_install_root})",
                    step_index=step_index,
                    total_steps=total_steps,
                )
            )
        )
        or default_install_root
    )
    step_index += 1

    selected_root_has_existing_install = path_looks_like_existing_install(
        draft_session.install_root
    )
    draft_session.existing_install_detected = selected_root_has_existing_install

    if not session.existing_install_detected and selected_root_has_existing_install:
        total_steps = count_questionnaire_steps(True)
        install_mode = prompt_for_number(
            build_numbered_prompt(
                "Install mode",
                [("1", "Upgrade"), ("2", "Fresh install")],
                "1",
                step_index=step_index,
                total_steps=total_steps,
            ),
            "1",
            {"1", "2"},
            input_fn=input_fn,
            output_fn=output_fn,
        )
        draft_session.install_mode = "upgrade" if install_mode == "1" else "fresh"
        step_index += 1

    starter_model_options, starter_model_choices, starter_model_default = (
        build_starter_model_prompt_options()
    )
    model_choice = prompt_for_number(
        build_numbered_prompt(
            "Starter model",
            starter_model_options,
            starter_model_default,
            step_index=step_index,
            total_steps=total_steps,
        ),
        starter_model_default,
        set(starter_model_choices),
        input_fn=input_fn,
        output_fn=output_fn,
    )
    draft_session.starter_model = starter_model_choices[model_choice]
    step_index += 1
    draft_session.install_opencode = (
        prompt_for_number(
            build_numbered_prompt(
                "Install OpenCode (required for a successful installation)",
                [("1", "Yes"), ("2", "No")],
                "1",
                step_index=step_index,
                total_steps=total_steps,
            ),
            "1",
            {"1", "2"},
            input_fn=input_fn,
            output_fn=output_fn,
        )
        == "1"
    )
    step_index += 1
    draft_session.attempt_turboquant = (
        prompt_for_number(
            build_numbered_prompt(
                "Attempt TurboQuant",
                [("1", "Yes"), ("2", "No")],
                "1",
                step_index=step_index,
                total_steps=total_steps,
            ),
            "1",
            {"1", "2"},
            input_fn=input_fn,
            output_fn=output_fn,
        )
        == "1"
    )
    step_index += 1
    draft_session.additional_model_paths = parse_model_paths(
        input_fn(
            build_text_prompt(
                "Additional model paths (semicolon-separated, optional)",
                step_index=step_index,
                total_steps=total_steps,
            )
        )
    )
    step_index += 1

    output_fn(render_confirmation_summary(draft_session))
    confirmation = prompt_for_number(
        build_numbered_prompt(
            "Confirm choices",
            [("1", "Confirm"), ("2", "Cancel")],
            "1",
            step_index=step_index,
            total_steps=total_steps,
        ),
        "1",
        {"1", "2"},
        input_fn=input_fn,
        output_fn=output_fn,
    )
    if confirmation == "2":
        raise PromptCancelledError("Installer questionnaire cancelled.")

    return draft_session
