from pathlib import Path


def test_logs_page_uses_shell_decks_and_explicit_result_anchor():
    logs_source = Path("frontend/src/pages/LogsPage.tsx").read_text(encoding="utf-8")

    assert "RuntimePilotStatusDeck" in logs_source
    assert "RuntimePilotActionDeck" in logs_source
    assert "runtimepilot-inline-heading" in logs_source
    assert 'id="logs-action-result"' in logs_source
    assert "Osveži snapshot" in logs_source
    assert "Skok na rezultat" in logs_source


def test_repair_page_uses_shell_decks_and_result_anchor():
    repair_source = Path("frontend/src/pages/RepairPage.tsx").read_text(encoding="utf-8")

    assert "RuntimePilotStatusDeck" in repair_source
    assert "RuntimePilotActionDeck" in repair_source
    assert "runtimepilot-inline-heading" in repair_source
    assert 'id="repair-action-result"' in repair_source
    assert "Bezbedan servisni tok" in repair_source
    assert "Popravka instalacije" in repair_source
    assert "Popravka runtime-a" in repair_source


def test_updates_page_uses_shell_decks_and_progress_anchor():
    updates_source = Path("frontend/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")

    assert "RuntimePilotStatusDeck" in updates_source
    assert "RuntimePilotActionDeck" in updates_source
    assert "runtimepilot-inline-heading" in updates_source
    assert 'id="updates-progress-panel"' in updates_source
    assert 'id="updates-action-result"' in updates_source
    assert 'className="wide-card runtimepilot-service-anchor"' in updates_source
    assert "Proveri ažuriranja" in updates_source
    assert "Instaliraj ažuriranje" in updates_source


def test_jobs_page_uses_shell_decks_with_form_list_and_result_anchors():
    jobs_source = Path("frontend/src/pages/JobsPage.tsx").read_text(encoding="utf-8")

    assert "RuntimePilotStatusDeck" in jobs_source
    assert "RuntimePilotActionDeck" in jobs_source
    assert "runtimepilot-inline-heading" in jobs_source
    assert 'id="jobs-create-form"' in jobs_source
    assert 'id="jobs-list"' in jobs_source
    assert 'id="jobs-action-result"' in jobs_source
    assert "Skok na formu" in jobs_source
    assert "Skok na listu" in jobs_source
    assert "Sačuvaj posao" in jobs_source
