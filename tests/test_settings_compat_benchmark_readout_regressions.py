from pathlib import Path


def test_shared_hifi_readout_styles_exist():
    styles = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert ".runtimepilot-readout-card {" in styles
    assert ".runtimepilot-state-chip {" in styles


def test_settings_page_uses_shared_hifi_readout_cards_and_state_chips():
    source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")

    assert "settings-action-route-card runtimepilot-readout-card" in source
    assert "apply-state-chip runtimepilot-state-chip" in source


def test_compatibility_flow_uses_shared_hifi_readout_cards_and_state_chips():
    page_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(
        encoding="utf-8"
    )
    panel_source = Path(
        "frontend/src/components/CompatibilityCalculatorPanel.tsx"
    ).read_text(encoding="utf-8")

    assert "compatibility-snapshot-card runtimepilot-readout-card" in page_source
    assert "compatibility-choice-card runtimepilot-readout-card" in page_source
    assert "compatibility-action-route-card runtimepilot-readout-card" in panel_source
    assert "compatibility-live-setting-card runtimepilot-readout-card" in panel_source
    assert "apply-state-chip runtimepilot-state-chip" in panel_source


def test_benchmark_page_uses_shared_hifi_readout_cards_for_chart_and_history():
    source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")

    assert "benchmark-setup-readout runtimepilot-readout-card" in source
    assert "benchmark-chart-readout runtimepilot-readout-card" in source
    assert "benchmark-history-compare-readout runtimepilot-readout-card" in source
    assert "benchmark-history-empty runtimepilot-readout-card" in source
    assert "benchmark-saved-run-readout runtimepilot-readout-card" in source
    assert "benchmark-saved-run-metric runtimepilot-readout-card" in source
