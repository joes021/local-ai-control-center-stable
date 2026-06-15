from pathlib import Path


def test_opencode_actions_use_full_height_vertical_command_rail():
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(
        encoding="utf-8"
    )
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert (
        'className="runtimepilot-primary-tab-rack-command-grid '
        'runtimepilot-primary-tab-rack-command-grid-vertical"'
        in opencode_source
    )
    assert ".runtimepilot-primary-tab-rack-command-grid-vertical" in styles_source
    assert "grid-template-columns: 1fr;" in styles_source


def test_opencode_source_uses_clean_serbian_copy_without_mojibake():
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(
        encoding="utf-8"
    )

    assert "Sesija još nije otvorena" in opencode_source
    assert "Managed config sažetak" in opencode_source
    assert (
        "Posle klika prvo ovde čitaš da li je otvaranje uspelo i šta je sledeći korak."
        in opencode_source
    )
    assert "joÅ¡" not in opencode_source
    assert "saÅ¾etak" not in opencode_source
    assert "ÄitaÅ¡" not in opencode_source
    assert "Ãƒâ€šÃ‚Â·" not in opencode_source
    assert "Ã‚Â·" not in opencode_source


def test_opencode_safe_selects_anchor_to_trigger_and_use_solid_menu_fill():
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(
        encoding="utf-8"
    )
    custom_select_source = Path("frontend/src/components/CustomSelect.tsx").read_text(
        encoding="utf-8"
    )
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Bezbednosni kanal" in opencode_source
    assert "Sloboda i ograničenja OpenCode agenta" in opencode_source
    assert "Bezbednosni režim" in opencode_source
    assert "Autonomija" in opencode_source
    assert "createPortal(" in custom_select_source
    assert "custom-select-menu custom-select-menu-portal" in custom_select_source
    assert (
        ".runtimepilot-opencode-settings-row {\n"
        "  display: grid;\n"
        "  grid-template-columns: repeat(2, minmax(0, 1fr));\n"
        "  gap: 12px;\n"
        "  min-width: 0;\n"
        "  align-items: start;\n"
        "}"
    ) in styles_source
    assert (
        ".runtimepilot-opencode-compact-field {\n"
        "  display: grid;\n"
        "  gap: 8px;\n"
        "  min-width: 0;\n"
        "  font-size: 0.92rem;\n"
        "  color: var(--app-text-soft);\n"
        "  align-content: start;\n"
        "}"
    ) in styles_source
    assert (
        ".custom-select-menu {\n"
        "  position: absolute;\n"
        "  top: 0;\n"
        "  left: 0;\n"
        "  width: 100%;\n"
        "  min-width: 0;\n"
        "  max-width: min(420px, calc(100vw - 24px));\n"
        "  max-height: min(360px, calc(100vh - 24px));\n"
        "  box-sizing: border-box;\n"
        "  z-index: 120;\n"
        "  display: grid;\n"
        "  grid-template-columns: minmax(0, 1fr);\n"
        "  justify-items: stretch;\n"
        "  gap: 6px;\n"
        "  padding: 8px;\n"
        "  overflow-x: hidden;\n"
        "  overflow-y: auto;\n"
        "  overscroll-behavior: contain;\n"
        "  scrollbar-gutter: stable;\n"
        "  border-radius: 16px;\n"
        "  border: 1px solid var(--app-field-border);\n"
        "  background: color-mix(in srgb, var(--app-card-soft-bg) 94%, var(--app-overlay-solid-fill) 6%);\n"
    ) in styles_source
    assert (
        ".custom-select-menu-portal {\n"
        "  position: fixed;\n"
        "  isolation: isolate;\n"
        "}"
    ) in styles_source
    assert (
        ".custom-select-option {\n"
        "  width: 100%;\n"
        "  max-width: 100%;\n"
        "  box-sizing: border-box;\n"
        "  display: block;\n"
        "  border: 1px solid transparent;\n"
        "  background: color-mix(in srgb, var(--app-card-soft-bg) 90%, var(--app-overlay-solid-fill) 10%);\n"
    ) in styles_source
    assert (
        ".custom-select-option-label {\n"
        "  display: block;\n"
        "  min-width: 0;\n"
        "  overflow: hidden;\n"
        "  text-overflow: ellipsis;\n"
        "  white-space: normal;\n"
    ) in styles_source


def test_opencode_action_clusters_fill_their_cards_and_use_cleaner_serbian_copy():
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(
        encoding="utf-8"
    )
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    normalized_source = " ".join(opencode_source.split())

    assert (
        "Preset menja samo OpenCode korake. Bezbednosni režim, autonomija i radni "
        "direktorijum ostaju odvojena podešavanja."
    ) in normalized_source
    assert "OpenCode sesije" in opencode_source
    assert "Kontrolni kanal" in opencode_source

    assert ".runtimepilot-opencode-preset-actions," in styles_source
    assert (
        ".runtimepilot-opencode-preset-actions {\n"
        "  width: 100%;\n"
        "  grid-template-columns: repeat(2, minmax(0, 1fr));\n"
        "}"
    ) in styles_source
    assert (
        ".runtimepilot-opencode-form-actions,\n"
        ".runtimepilot-opencode-settings-actions {\n"
        "  grid-template-columns: repeat(2, minmax(0, 1fr));\n"
        "  width: 100%;\n"
        "}"
    ) in styles_source
    assert (
        ".runtimepilot-opencode-preset-actions > button,\n"
        ".runtimepilot-opencode-form-actions > button,\n"
        ".runtimepilot-opencode-settings-actions > button {\n"
        "  width: 100%;\n"
        "  min-width: 0;\n"
        "  justify-self: stretch;\n"
        "}"
    ) in styles_source
    assert (
        ".runtimepilot-opencode-preset-actions > button:only-child,\n"
        ".runtimepilot-opencode-settings-actions > button:only-child {\n"
        "  grid-column: 1 / -1;\n"
        "}"
    ) in styles_source
