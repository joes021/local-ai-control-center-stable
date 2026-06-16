from pathlib import Path


def test_action_result_panel_uses_horizontal_full_width_header_layout():
    source = Path("frontend/src/components/ActionResultPanel.tsx").read_text(
        encoding="utf-8"
    )
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "runtimepilot-action-copy-inline" in source
    assert ".runtimepilot-action-copy-inline {" in styles
    assert "flex: 1 1 100%;" in styles
    assert "justify-content: space-between;" in styles


def test_updates_progress_card_uses_shared_horizontal_heading_layout():
    source = Path("frontend/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "runtimepilot-inline-heading" in source
    assert ".runtimepilot-inline-heading {" in styles
    assert ".runtimepilot-inline-heading .status-value {" in styles
