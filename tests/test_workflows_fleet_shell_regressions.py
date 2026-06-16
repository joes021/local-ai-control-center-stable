from pathlib import Path


def test_workflows_page_uses_status_and_action_decks_with_clear_jump_targets():
    workflows_source = Path("frontend/src/pages/WorkflowsPage.tsx").read_text(
        encoding="utf-8"
    )

    assert "RuntimePilotStatusDeck" in workflows_source
    assert "RuntimePilotActionDeck" in workflows_source
    assert 'id="workflow-preset-catalog"' in workflows_source
    assert 'id="workflow-preset-editor"' in workflows_source
    assert "Skok na katalog" in workflows_source
    assert "Skok na editor" in workflows_source
    assert "Otvori pretragu" in workflows_source
    assert "Otvori znanje" in workflows_source
    assert "Otvori benchmark" in workflows_source


def test_fleet_page_uses_status_and_action_decks_with_form_and_catalog_routes():
    fleet_source = Path("frontend/src/pages/FleetPage.tsx").read_text(
        encoding="utf-8"
    )

    assert "RuntimePilotStatusDeck" in fleet_source
    assert "RuntimePilotActionDeck" in fleet_source
    assert 'id="fleet-machine-form"' in fleet_source
    assert 'id="fleet-machine-catalog"' in fleet_source
    assert 'id="fleet-action-result"' in fleet_source
    assert "Skok na formu" in fleet_source
    assert "Skok na katalog" in fleet_source
    assert "Osveži sve" in fleet_source
    assert "Dodaj mašinu" in fleet_source
