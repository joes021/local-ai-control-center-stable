from pathlib import Path


def test_advanced_page_uses_full_width_intro_and_embeds_real_actions_in_zone_cards():
    advanced_source = Path("frontend/src/pages/AdvancedPage.tsx").read_text(
        encoding="utf-8"
    )
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "SupportPageDeck" in advanced_source
    assert "<SupportPageDeck" in advanced_source
    assert 'eyebrow="Sekundarni hub"' in advanced_source
    assert 'title="Napredno bez dupliranih komandi"' in advanced_source
    assert "resultHint={" in advanced_source
    assert "SecondaryActionRail" not in advanced_source
    assert "runtimepilot-secondary-hub-fullwidth" in advanced_source
    assert "runtimepilot-advanced-summary-actions" in advanced_source
    assert "runtimepilot-advanced-summary-routes" not in advanced_source
    assert "deck-control-button-primary" not in advanced_source
    assert "Otvori Benchmark" in advanced_source
    assert "Otvori Tuning Lab" in advanced_source
    assert "Otvori kompatibilnost" in advanced_source
    assert "Otvori telemetriju" in advanced_source
    assert "Otvori Browser katalog" in advanced_source
    assert "Otvori Znanje" in advanced_source
    assert "Otvori Pretragu" in advanced_source
    assert "Otvori Radne tokove" in advanced_source
    assert "Otvori Project Memory" in advanced_source
    assert "Otvori Podešavanja" in advanced_source
    assert "Otvori Logove" in advanced_source
    assert "Otvori Pomoć" in advanced_source
    assert "Otvori Popravku" in advanced_source
    assert "Otvori Ažuriranja" in advanced_source
    assert "Otvori Flotu" in advanced_source
    assert "Otvori Poslove" in advanced_source

    assert ".runtimepilot-secondary-hub-fullwidth" in styles_source
    assert ".runtimepilot-advanced-summary-actions" in styles_source
    assert ".runtimepilot-advanced-summary-actions > button" in styles_source
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in styles_source
    assert (
        ".runtimepilot-support-page-deck-layout-with-side {\n"
        "  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);\n"
        "  align-items: stretch;\n"
        "}"
    ) in styles_source
    assert (
        ".runtimepilot-support-page-deck-main {\n"
        "  min-width: 0;\n"
        "  height: 100%;\n"
        "}"
    ) in styles_source
    assert (
        ".runtimepilot-support-page-deck-side {\n"
        "  display: grid;\n"
        "  gap: 8px;\n"
        "  align-content: start;\n"
        "  height: 100%;\n"
    ) in styles_source
