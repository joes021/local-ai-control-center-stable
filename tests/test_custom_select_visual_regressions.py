from pathlib import Path


def test_custom_select_portal_uses_opaque_field_surface():
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    portal_block = styles.split(".custom-select-menu-portal {", 1)[1].split("}", 1)[0]

    assert "background: var(--app-field-bg-alt);" in portal_block


def test_custom_select_options_keep_solid_surface_inside_portal_menu():
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    option_block = styles.split(".custom-select-option {", 1)[1].split("}", 1)[0]

    assert "background: var(--app-field-bg);" in option_block


def test_custom_select_hover_uses_hifi_button_surface_instead_of_flat_warning_fill():
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    hover_block = styles.split(".custom-select-option:hover,", 1)[1].split("}", 1)[0]

    assert "background: var(--app-button-hover-bg);" in hover_block
    assert "border-color: var(--app-button-hover-border);" in hover_block
    assert "background: var(--app-warning-bg);" not in hover_block
