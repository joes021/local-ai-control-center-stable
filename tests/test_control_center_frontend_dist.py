import re
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def test_packaged_frontend_dist_contains_built_assets():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )

    assert (dist_root / "index.html").is_file()
    assert any(path.is_file() for path in (dist_root / "assets").glob("*"))


def test_control_center_serves_built_frontend_asset():
    client = TestClient(app)
    index_response = client.get("/")

    assert index_response.status_code == 200
    match = re.search(r'"/assets/[^"]+"', index_response.text)
    assert match is not None

    asset_path = match.group(0).strip('"')
    asset_response = client.get(asset_path)

    assert asset_response.status_code == 200


def test_packaged_settings_ui_uses_numeric_preset_dropdowns_with_custom_inputs():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Context" in bundled_text
    assert "Output tokens" in bundled_text
    assert "Izaberi context veličinu" in bundled_text
    assert "Izaberi output token limit" in bundled_text
    assert "Unesi context veličinu" in bundled_text
    assert "Unesi output token limit" in bundled_text
    assert "Standardni korak:" not in bundled_text


def test_settings_page_source_shows_custom_numeric_fields_conditionally():
    source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")

    assert "const contextChoice = resolveTokenChoice(settings.context);" in source
    assert 'contextChoice === "custom" ? (' in source
    assert "const outputTokensChoice = resolveTokenChoice(settings.outputTokens);" in source
    assert 'outputTokensChoice === "custom" ? (' in source


def test_theme_source_and_packaged_frontend_include_named_themes():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Dark Chocolate" in settings_source
    assert "Light" in settings_source
    assert "Dark" in settings_source
    assert "Neon Green" in settings_source
    assert "Marine Blue" in settings_source
    assert "data-theme" in layout_source
    assert '[data-theme="dark-chocolate"]' in styles_source
    assert '[data-theme="light"]' in styles_source
    assert '[data-theme="dark"]' in styles_source
    assert '[data-theme="neon-green"]' in styles_source
    assert '[data-theme="marine-blue"]' in styles_source


def test_workflow_preset_source_mentions_core_presets():
    workflow_source = Path("frontend/src/lib/workflowPresets.ts").read_text(encoding="utf-8")
    search_source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")

    assert "Research" in workflow_source
    assert "Code" in workflow_source
    assert "Low VRAM" in workflow_source
    assert "Long context" in workflow_source
    assert "Docs + web" in workflow_source
    assert "Benchmark battery" in workflow_source
    assert "Preset radnog toka" in search_source
    assert "Preset radnog toka" in knowledge_source
    assert "Preset radnog toka" in benchmark_source


def test_home_source_formats_runtime_binary_as_name_and_compact_location():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "describeRuntimeBinaryPath" in home_source
    assert "Lokacija binara" in home_source
    assert "runtime-binary-card" in home_source
    assert "runtime-binary-file" in styles_source
    assert "runtime-binary-location" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Lokacija binara" in bundled_js
    assert "describeRuntimeBinaryPath" not in bundled_js
    assert "runtime-binary-file" in bundled_css
    assert "runtime-binary-location" in bundled_css


def test_observability_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    observability_source = Path("frontend/src/pages/ObservabilityPage.tsx").read_text(encoding="utf-8")

    assert "Observability" in app_source
    assert "GPU uživo" in observability_source
    assert "Runtime signal" in observability_source
    assert "Skorašnji log signali" in observability_source


def test_layout_and_benchmark_source_show_persistent_resource_strip_and_mode_labels():
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")

    assert "LiveResourceStrip" in layout_source
    assert "CPU uživo" in benchmark_source
    assert "RAM uživo" in benchmark_source
    assert "VRAM uživo" in benchmark_source
    assert "Režim izvršavanja" in benchmark_source
    assert "GPU VRAM dominantno" in benchmark_source
    assert "Hibrid VRAM + RAM" in benchmark_source
    assert "CPU + RAM" in benchmark_source


def test_live_resource_strip_source_and_packaged_frontend_use_compact_clickable_two_line_metrics_without_horizontal_scroll():
    strip_source = Path("frontend/src/components/LiveResourceStrip.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "live-resource-inline-row" in strip_source
    assert "live-resource-inline-item" in strip_source
    assert "estimateHybridRuntimeUsage" in strip_source
    assert "estimateContextFitFromKvBuffer" in strip_source
    assert "simplifyGpuName" in strip_source
    assert "formatUsedTotalGiBCompact" in strip_source
    assert "aria-pressed" in strip_source
    assert "resource-chip-detail-panel" in strip_source
    assert "Otvori VRAM tuning" in strip_source
    assert ".live-resource-inline-row" in styles_source
    assert ".live-resource-inline-item" in styles_source
    assert "grid-template-columns: minmax(0, 0.66fr) minmax(0, 1.08fr) minmax(0, 1.08fr) minmax(0, 1.22fr) minmax(0, 1.48fr) minmax(0, 0.9fr) minmax(0, 1.58fr);" in styles_source
    assert "grid-template-rows: auto auto;" in styles_source
    assert "overflow-x: auto;" not in styles_source
    assert ".live-resource-inline-button" in styles_source
    assert ".resource-chip-detail-panel" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Živi resursi" in bundled_js
    assert "Model proces" in bundled_js
    assert "Klikni stavku za pun detalj" in bundled_js
    assert "Hibrid" in bundled_js
    assert "Puni GPU fit" in bundled_js
    assert "Otvori VRAM tuning" in bundled_js
    assert "RTX 3060" in bundled_js
    assert ".live-resource-inline-row" in bundled_css
    assert ".live-resource-inline-item" in bundled_css
    assert ".live-resource-inline-button" in bundled_css
    assert ".resource-chip-detail-panel" in bundled_css
    assert "grid-template-columns:minmax(0,.66fr) minmax(0,1.08fr) minmax(0,1.08fr) minmax(0,1.22fr) minmax(0,1.48fr) minmax(0,.9fr) minmax(0,1.58fr)" in bundled_css


def test_runtime_resource_panel_source_explains_hybrid_ram_spill_and_full_gpu_fit():
    panel_source = Path("frontend/src/components/RuntimeResourcePanel.tsx").read_text(encoding="utf-8")

    assert "Procena RAM preliva" in panel_source
    assert "Još VRAM-a za puni GPU fit" in panel_source
    assert "Ovo je procena na osnovu odnosa GPU slojeva" in panel_source


def test_settings_source_mentions_vram_fit_tuning_and_manual_gpu_layers_override():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    runtime_helper_source = Path("frontend/src/lib/runtimeDiagnostics.ts").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert "VRAM fit tuning" in settings_source
    assert "GPU layers override" in settings_source
    assert "Procenjeni context za puni GPU fit" in settings_source
    assert "Try to fit in VRAM" in settings_source
    assert "estimateContextFitFromKvBuffer" in runtime_helper_source
    assert "Samo spuštanje context-a verovatno nije dovoljno" in settings_source
    assert "Auto trenutno cilja" in settings_source
    assert "Više GPU slojeva = više VRAM" in settings_source
    assert "Sačuvaj i primeni na runtime" in settings_source
    assert "Runtime se tada još ne restartuje" in settings_source
    assert "Poslednji VRAM fit predlog" in settings_source
    assert "Ovo još nije sačuvano ni aktivno u runtime-u." in settings_source
    assert "Poslednja primena runtime-a" in settings_source
    assert "Ako je runtime već aktivan, portal ga restartuje" in settings_source
    assert "TurboQuant smernice za čistiji VRAM fit" in settings_source
    assert js_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "VRAM fit tuning" in bundled_js
    assert "GPU layers override" in bundled_js
    assert "Try to fit in VRAM" in bundled_js
    assert "VRAM fit" in bundled_js
    assert "GPU layers" in bundled_js
    assert "TurboQuant smernice" in bundled_js
    assert "Poslednji VRAM fit predlog" in bundled_js
    assert "Poslednja primena runtime-a" in bundled_js


def test_fleet_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    fleet_source = Path("frontend/src/pages/FleetPage.tsx").read_text(encoding="utf-8")

    assert "Fleet" in app_source
    assert "Udaljene mašine" in fleet_source
    assert "Osveži sve" in fleet_source
    assert "Dodaj mašinu" in fleet_source


def test_jobs_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    jobs_source = Path("frontend/src/pages/JobsPage.tsx").read_text(encoding="utf-8")

    assert "Jobs" in app_source
    assert "Zakazani poslovi" in jobs_source
    assert "Pokreni sada" in jobs_source
    assert "Sačuvaj posao" in jobs_source


def test_app_source_and_packaged_frontend_use_primary_tabs_plus_more_menu():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Više" in app_source
    assert "Početna" in app_source
    assert "Server" in app_source
    assert "Modeli" in app_source
    assert "OpenCode" in app_source
    assert "Pretraga" in app_source
    assert "Podešavanja" in app_source
    assert "nav-more-button" in app_source
    assert "nav-menu-panel" in app_source
    assert "nav-menu-section-label" in app_source
    assert ".top-nav-primary" in styles_source
    assert ".nav-more-shell" in styles_source
    assert ".nav-more-button" in styles_source
    assert ".nav-menu-panel" in styles_source
    assert ".nav-menu-section-label" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Više" in bundled_js
    assert "Početna" in bundled_js
    assert "Modeli" in bundled_js
    assert "Podešavanja" in bundled_js
    assert "nav-more-button" in bundled_js
    assert "nav-menu-panel" in bundled_js
    assert "nav-menu-section-label" in bundled_js
    assert ".top-nav-primary" in bundled_css
    assert ".nav-more-shell" in bundled_css
    assert ".nav-more-button" in bundled_css
    assert ".nav-menu-panel" in bundled_css
    assert ".nav-menu-section-label" in bundled_css


def test_workflows_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    workflows_source = Path("frontend/src/pages/WorkflowsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Workflows" in app_source
    assert "Radni prostor za radne tokove" in workflows_source
    assert "Aktiviraj preset" in workflows_source
    assert "Otvori pretragu" in workflows_source
    assert "workflow-preset-grid" in workflows_source
    assert ".workflow-preset-grid" in styles_source
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in styles_source


def test_workflows_source_supports_user_editable_presets_with_editor_state_and_clone():
    workflows_source = Path("frontend/src/pages/WorkflowsPage.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert "Poništi izmene u editoru" in workflows_source
    assert "Kloniraj preset" in workflows_source
    assert "Nesačuvane izmene" in workflows_source
    assert "ugrađeni preset" in workflows_source
    assert "korisnički preset" in workflows_source
    assert "Sačuvaj kao novi preset" in workflows_source
    assert "Sačuvaj izmene preseta" in workflows_source
    assert "Obriši korisnički preset" in workflows_source
    assert "Učitaj u editor" in workflows_source
    assert "saveWorkflowPreset" in api_source
    assert "deleteWorkflowPreset" in api_source


def test_tuning_lab_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    page_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Tuning Lab" in app_source
    assert "queueTuningLabExperiment" in api_source
    assert "queueTuningLabBatch" in api_source
    assert "applyTuningLabWinner" in api_source
    assert "exportTuningLabRun" in api_source
    assert "importTuningSnippet" in api_source
    assert "bootstrapOpenCode" in api_source
    assert "Tuning Lab" in page_source
    assert "Game Batch 01" in page_source
    assert "Pokreni ceo batch" in page_source
    assert "Učitaj easy" in page_source
    assert "Učitaj medium" in page_source
    assert "Učitaj hard" in page_source
    assert "Pokreni task" in page_source
    assert "Otvori rezultat" in page_source
    assert "Šta ovaj batch meri" in page_source
    assert "Jedan klik =" in page_source
    assert "Trenutno u editoru" in page_source
    assert "Brzi tok za ovaj task" in page_source
    assert "1. Učitaj task" in page_source
    assert "2. Pokreni task" in page_source
    assert "3. Otvori rezultat" in page_source
    assert "Koristi trenutni radni direktorijum" in page_source
    assert "Sve osnovne akcije za ovaj task ostaju u istoj kartici." in page_source
    assert "Otvori napredna podešavanja" in page_source
    assert "Koristi trenutne slot postavke" in page_source
    assert "Dodaj u queue" in page_source
    assert "Primeni pobednički set" in page_source
    assert "Export / share" in page_source
    assert "Uvezi forum / Reddit snippet" in page_source


def test_server_and_tuning_lab_sources_show_runtime_gpu_diagnostics():
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    tuning_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "GPU offload dijagnostika" in server_source
    assert "Planirano kroz launch komandu" in server_source
    assert "Potvrđeno kroz runtime log" in server_source
    assert "GPU offload dijagnostika" in tuning_source
    assert "Launch plan" in tuning_source
    assert "Potvrda loga" in tuning_source
    assert "Prompt ingest" in tuning_source
    assert "Runtime generacija" in tuning_source
    assert "Živa generacija" in tuning_source
    assert "Šta OpenCode upravo radi" in tuning_source
    assert "OpenCode ne otvara zaseban GUI prozor" in tuning_source
    assert "Tuning Lab trenutno nije spreman za pokretanje" in tuning_source
    assert "runBlockers" in tuning_source
    assert "Instaliraj ili popravi OpenCode" in tuning_source
    assert "OpenCode nedostaje za Tuning Lab" in tuning_source
    assert "Aktivni run cockpit" in tuning_source
    assert "tuning-lab-slot-grid" in tuning_source
    assert "tuning-lab-results-table" in tuning_source
    assert "tuning-lab-history-card" in tuning_source
    assert "Zašto je ovaj slot pobedio" in tuning_source
    assert "Aktivni korak" in tuning_source
    assert "Poslednji log signal" in tuning_source
    assert "OpenCode u Tuning Lab-u radi u pozadini" in tuning_source
    assert "Queue radi sekvencijalno" in tuning_source
    assert "OpenCode PID" in tuning_source
    assert "Živa sesija i signal" in tuning_source
    assert "Workspace, logovi i komande" in tuning_source
    assert "Živi workspace i preview" in tuning_source
    assert "Poslednje menjani fajlovi" in tuning_source
    assert "Preview:" in tuning_source
    assert "OpenCode signal uživo" in tuning_source
    assert "Napredni debug trag" in tuning_source
    assert "Aktivna OpenCode poruka" in tuning_source
    assert "Alat " in tuning_source
    assert "Živi output" in tuning_source
    assert "tuning-lab-cockpit-metric-grid" in tuning_source
    assert "Kopiraj workspace putanju" in tuning_source
    assert "Kopiraj log putanju" in tuning_source
    assert "Kopiraj output putanju" in tuning_source
    assert "Token telemetry nije prijavljen" in tuning_source
    assert "Filtriraj istoriju" in tuning_source
    assert "Spremno za otvaranje" in tuning_source
    assert "Poslednji playable" in tuning_source
    assert "Playable rezultat još nije dostupan" in tuning_source
    assert "Sačuvan playable izlaz" in tuning_source
    assert "Kopiraj parametre" in tuning_source
    assert "Kopiraj runtime komandu" in tuning_source
    assert "Kopiraj OpenCode komandu" in tuning_source
    assert "Izmenjeni fajlovi" in tuning_source
    assert "Otvori diff" in tuning_source
    assert "Collapse all" in tuning_source
    assert "Expand all" in tuning_source
    assert ".tuning-lab-slot-grid" in styles_source
    assert ".tuning-lab-results-table" in styles_source
    assert ".tuning-lab-history-card" in styles_source
    assert ".tuning-lab-history-toolbar" in styles_source
    assert ".tuning-lab-progress-grid" in styles_source
    assert ".tuning-lab-filter-grid" in styles_source
    assert ".tuning-lab-diff-browser" in styles_source


def test_tuning_lab_source_mentions_visible_live_opencode_session():
    page_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "OpenCode sesija uživo" in page_source
    assert "Spremno za snimanje ekrana" in page_source
    assert "Ovaj prikaz možeš direktno da snimaš" in page_source
    assert ".tuning-lab-live-console" in styles_source
    assert ".tuning-lab-copy-row" in styles_source
    assert ".tuning-lab-batch-overview" in styles_source
    assert ".tuning-lab-batch-focus-list" in styles_source
    assert ".tuning-lab-batch-task-badges" in styles_source
    assert ".tuning-lab-batch-run-hint" in styles_source
    assert ".tuning-lab-batch-quick-run" in styles_source
    assert ".tuning-lab-batch-action-rail" in styles_source
    assert ".tuning-lab-batch-task-actions" in styles_source
    assert ".tuning-lab-batch-task-state" in styles_source
    assert ".tuning-lab-batch-playable-meta" in styles_source
    assert ".tuning-lab-cockpit" in styles_source
    assert ".tuning-lab-cockpit-grid" in styles_source
    assert ".tuning-lab-cockpit-strip" in styles_source
    assert ".tuning-lab-path-card" in styles_source
    assert ".tuning-lab-workspace-card" in styles_source
    assert ".tuning-lab-workspace-columns" in styles_source
    assert ".tuning-lab-workspace-preview-panel" in styles_source
    assert ".tuning-lab-cockpit-main" in styles_source
    assert ".tuning-lab-cockpit-metric-grid" in styles_source
    assert ".tuning-lab-cockpit-metric" in styles_source
    assert ".tuning-lab-resource-list" in styles_source
    assert ".tuning-lab-resource-value" in styles_source
    assert ".tuning-lab-log-lines" in styles_source
    assert ".tuning-lab-log-line" in styles_source
    assert ".tuning-lab-log-raw" in styles_source


def test_tuning_lab_source_mentions_history_selection_and_delete_actions():
    page_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Obriši selektovane" in page_source
    assert "Obriši sve" in page_source
    assert "Obriši sve failed" in page_source
    assert "Obriši i vezane fajlove na disku" in page_source
    assert "Selektovano:" in page_source
    assert "Očisti selekciju" in page_source
    assert "deleteTuningLabHistory" in api_source
    assert ".tuning-lab-history-selection-bar" in styles_source
    assert ".tuning-lab-history-select-cell" in styles_source
    assert ".tuning-lab-history-select-toggle" in styles_source


def test_benchmark_source_explanation_is_present():
    page_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Izvori llama.cpp signala" in page_source
    assert "Graf sada prati sav llama.cpp-kompatibilni /slots throughput" in page_source
    assert "Aktivni runtime" in page_source
    assert "Tuning Lab" in page_source
    assert "Drugi llama.cpp tok" in page_source
    assert ".benchmark-source-summary" in styles_source
    assert ".benchmark-source-chip-row" in styles_source


def test_server_and_opencode_source_include_equivalent_launch_command_panels():
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "Ekvivalentne CLI komande" in server_source
    assert "Kopiraj PowerShell" in server_source
    assert "Kopiraj cmd.exe" in server_source
    assert "sampling parametri" in server_source
    assert "PowerShell` koristi prefiks `&`" in server_source
    assert "Ako ručno lepiš komandu u Command Prompt" in server_source
    assert "Ekvivalentna OpenCode komanda" in opencode_source
    assert "Launcher .cmd" in opencode_source
    assert "PowerShell prikaz" in opencode_source
    assert "Managed config ulazi" in opencode_source
    assert "Env promenljive" in opencode_source
    assert "Provider" in opencode_source
    assert "Base URL" in opencode_source
    assert "command-preview-grid" in opencode_source
    assert "opencode-config-grid" in opencode_source
    assert "opencode-env-grid" in opencode_source
    assert "Efektivna local-lacc inference podrazumevana podešavanja" in opencode_source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Ekvivalentne CLI komande" in bundled_text
    assert "Kopiraj cmd.exe" in bundled_text
    assert "sampling parametri" in bundled_text
    assert "Ako ručno lepiš komandu u Command Prompt" in bundled_text
    assert "Ekvivalentna OpenCode komanda" in bundled_text
    assert "Launcher .cmd" in bundled_text
    assert "Managed config ulazi" in bundled_text
    assert "Env promenljive" in bundled_text
    assert "Base URL" in bundled_text
    assert "command-preview-grid" in bundled_text
    assert "opencode-config-grid" in bundled_text
    assert "opencode-env-grid" in bundled_text
    assert "Efektivna local-lacc inference podrazumevana podešavanja" in bundled_text

    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    assert ".command-preview-grid" in styles_source
    assert ".opencode-config-grid" in styles_source
    assert ".opencode-env-grid" in styles_source


def test_settings_source_uses_stable_option_grids_and_balanced_core_layout():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "settings-option-grid" in settings_source
    assert ".settings-option-grid" in styles_source
    assert "settings-cluster-grid-profiles" in styles_source
    assert "grid-template-columns: 1fr;" in styles_source
    assert "settings-cluster-grid-core" in styles_source
    assert "repeat(2, minmax(260px, 1fr))" in styles_source


def test_settings_source_clearly_separates_general_search_and_turboquant_sections():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert "Kako da koristiš ovu stranu" in settings_source
    assert "Opšta podešavanja" in settings_source
    assert "Pretraga i izvori" in settings_source
    assert "TurboQuant podešavanja" in settings_source
    assert "Sačuvaj opšta podešavanja" in settings_source
    assert "Sačuvaj TurboQuant podešavanja" in settings_source
    assert js_assets

    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Kako da koristiš ovu stranu" in bundled_text
    assert "Opšta podešavanja" in bundled_text
    assert "Pretraga i izvori" in bundled_text
    assert "TurboQuant podešavanja" in bundled_text
    assert "Sačuvaj opšta podešavanja" in bundled_text
    assert "Sačuvaj TurboQuant podešavanja" in bundled_text


def test_packaged_settings_action_and_browse_buttons_use_panel_button_theme():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert css_assets
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert ".settings-action-row button" in bundled_css
    assert ".settings-path-row button" in bundled_css


def test_packaged_frontend_buttons_include_hover_and_active_feedback_states():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert css_assets
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert ":hover:not(:disabled)" in bundled_css
    assert ":active:not(:disabled)" in bundled_css
    assert ":focus-visible" in bundled_css
    assert "translateY(-1px)" in bundled_css
    assert "translateY(1px)" in bundled_css


def test_browser_page_source_groups_quant_filters_and_supports_quant_sort():
    source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")

    assert "normalizeQuantFilterKey" in source
    assert "quant-asc" in source
    assert "quant-desc" in source
    assert "const browserQuery = useMemo<BrowserCatalogQuery>(" in source
    assert "quant: quantFilter" in source
    assert "sort: sortKey" in source
    assert "const payload = await fetchBrowserCatalog(query);" in source


def test_browser_page_source_uses_compact_badges_for_mtp_and_fit_columns():
    source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")

    assert "compactMtpLabel" in source
    assert "compactFitLabel" in source
    assert "Fit: {item.fitLabel}" not in source


def test_models_and_browser_source_explain_that_mtp_models_use_draft_mtp_runtime_path():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")

    assert "draft-mtp" in models_source
    assert "TurboQuant" in models_source
    assert "download-only" not in models_source
    assert "draft-mtp" in browser_source
    assert "TurboQuant" in browser_source


def test_models_page_source_uses_backend_lifecycle_truth_for_actions_and_badges():
    source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")

    assert "lifecycleTone(item.lifecycleStatus)" in source
    assert 'item.lifecycleLabel ?? "Status"' in source
    assert "item.lifecycleSummary" in source
    assert "item.downloadActive" in source
    assert "item.canDownload" in source
    assert "downloadActionLabel(item)" in source


def test_models_page_source_requires_explicit_confirmation_before_forced_risky_activation():
    source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert "Ovaj model verovatno neće moći da radi ili će raditi loše na ovoj mašini." in source
    assert "Da li želiš ipak da pokušaš aktivaciju?" in source
    assert "Ipak pokušaj aktivaciju" in source
    assert "activateModel(item.id, { force: true })" in source
    assert "force?: boolean" in api_source
    assert js_assets

    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Ovaj model verovatno neće moći da radi ili će raditi loše na ovoj mašini." in bundled_text
    assert "Da li želiš ipak da pokušaš aktivaciju?" in bundled_text
    assert "Ipak pokušaj aktivaciju" in bundled_text


def test_packaged_browser_ui_contains_quant_sort_labels():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Quant smallest first" in bundled_text
    assert "Quant largest first" in bundled_text


def test_api_source_disables_cache_for_download_progress_polling():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert 'fetch("/api/models/download-progress", { cache: "no-store" })' in source


def test_api_source_keeps_long_model_downloads_pending_instead_of_false_timeout_error():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert 'initial.action === "download-model"' in source
    assert "const progressPayload = await fetchDownloadProgress();" in source
    assert 'progressPayload.status === "starting" || progressPayload.status === "downloading"' in source
    assert "Download je i dalje u toku. Prati Download status karticu dok se ne završi." in source


def test_api_source_supports_browser_catalog_query_params():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert "export type BrowserCatalogQuery" in source
    assert "new URLSearchParams()" in source
    assert "params.toString()" in source
    assert 'cache: "no-store"' in source


def test_download_progress_card_source_explains_retry_without_resume():
    source = Path("frontend/src/components/ModelDownloadProgressCard.tsx").read_text(encoding="utf-8")

    assert "Resume nije podržan" in source
    assert "ponovo kliknuti Download" in source


def test_download_progress_card_source_supports_indeterminate_progress_when_percent_is_unknown():
    source = Path("frontend/src/components/ModelDownloadProgressCard.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "download-progress-fill-indeterminate" in source
    assert "Ukupna veličina još nije prijavljena" in source
    assert ".download-progress-fill-indeterminate" in styles_source
    assert "@keyframes download-progress-pulse" in styles_source


def test_app_source_and_packaged_frontend_include_updates_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'updates: "Ažuriranja"' in source
    assert "UpdatesPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Ažuriranja" in bundled_text
    assert "Proveri ažuriranja" in bundled_text


def test_api_source_disables_cache_for_update_progress_polling():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert 'fetch("/api/updates/progress", { cache: "no-store" })' in source


def test_app_source_and_packaged_frontend_include_benchmark_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'benchmark: "Benchmark"' in source
    assert "BenchmarkPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Benchmark" in bundled_text
    assert "Telemetrija" in bundled_text
    assert "Puls tokena" in bundled_text


def test_app_source_and_packaged_frontend_include_search_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'search: "Pretraga"' in source
    assert "SearchPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Radni prostor za pretragu" in bundled_text
    assert "Pronađi veb izvore" in bundled_text
    assert "Pretraži i odgovori lokalno" in bundled_text
    assert "Compare providers" in bundled_text
    assert "DuckDuckGo" in bundled_text
    assert "Konačan odgovor lokalnog modela" in bundled_text
    assert "Setup managed SearxNG (Windows + WSL)" in bundled_text
    assert "SearxNG nije podešen" in bundled_text
    assert "Managed local SearxNG (Windows + WSL)" in bundled_text
    assert "Ovo su izvori, ne konačan odgovor." in bundled_text
    assert "Otvori izvor" in bundled_text
    assert "Kad pokreneš upit, ovde će se pojaviti normalizovani veb rezultati." in bundled_text
    assert "Ako provider status kaže `SearxNG nije podešen`" in bundled_text


def test_app_source_and_packaged_frontend_include_knowledge_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")

    assert 'knowledge: "Znanje"' in source
    assert "KnowledgePage" in source
    assert "pickWorkingDirectory" in knowledge_source
    assert "Pregledaj" in knowledge_source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Radni prostor znanja" in bundled_text
    assert "Dokumenti + veb" in bundled_text
    assert "Pregledaj" in bundled_text
    assert "Kolekcije" in knowledge_source
    assert "Oznake" in knowledge_source
    assert "Citati" in knowledge_source
    assert "Izvezi JSON" in knowledge_source
    assert "Izvezi Markdown" in knowledge_source
    assert "Kad pokreneš upit nad znanjem, ovde će se pojaviti lokalni pogoci iz dokumenata." in knowledge_source
    assert "ovde ćeš videti koji dokumenti su korišćeni" in knowledge_source
    assert "i njihove citate." in knowledge_source


def test_updates_page_source_uses_serbian_diacritics_in_progress_guidance():
    source = Path("frontend/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")

    assert "Pročitaj poruku iznad." in source
    assert "Sačekaj da download stigne do 100%. Installer će se zatim pokrenuti automatski." in source
    assert "Ako pokreneš instalaciju ažuriranja, ovde ćeš videti ceo tok preuzimanja i pokretanja installera." in source


def test_settings_and_opencode_source_include_web_search_controls_and_guidance():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "Web search mode" in settings_source
    assert "Provider pretrage" in settings_source
    assert "DuckDuckGo (public web, no key)" in settings_source
    assert "Manual SearxNG base URL (optional, no WSL)" in settings_source
    assert "Setup managed SearxNG (Windows + WSL)" in settings_source
    assert "Managed local SearxNG (Windows + WSL)" in settings_source
    assert "Search results limit" in settings_source
    assert "On-demand prefix" in settings_source
    assert "local-lacc" in settings_source
    assert "local-lacc" in opencode_source
    assert "shared search sloj" in opencode_source


def test_search_page_source_makes_web_results_clickable_and_guides_toward_answer():
    source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")

    assert "Compare providers" in source
    assert "DuckDuckGo" in source
    assert "Provider pretrage" in source
    assert "Pronađi veb izvore" in source
    assert "Pretraži i odgovori lokalno" in source
    assert "Konačan odgovor lokalnog modela" in source
    assert "Ovo su izvori, ne konačan odgovor." in source
    assert 'target="_blank"' in source
    assert "Otvori izvor" in source


def test_home_page_source_uses_single_system_overview_card():
    source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")

    assert "GENERAL_REFRESH_MS = 5000" in source
    assert "BENCHMARK_REALTIME_REFRESH_MS = 1000" in source
    assert "async function loadBenchmarkOnly()" in source
    assert "void loadBenchmarkOnly();" in source
    assert "Pregled sistema" in source
    assert "TelemetryPanel" in source
    assert "Puls tokena" in telemetry_source
    assert "Ulaz 24h" in telemetry_source
    assert "Izlaz 24h" in telemetry_source
    assert "Aktivne rute" in telemetry_source
    assert "Uživo sada" in telemetry_source
    assert "Poslednji throughput signal" in telemetry_source
    assert "Stanje Control Center-a" in source
    assert "Aktivan runtime" in source
    assert "Status runtime servera" in source
    assert "Aktivni model" in source
    assert "Profil" in source
    assert "Dostupni runtime-i" in source


def test_telemetry_source_and_styles_keep_live_now_layout_stable_when_signal_drops():
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "const hasLiveNowSignal = telemetry?.liveNowTokensPerSecond != null;" in telemetry_source
    assert 'const liveNowDisplay = hasLiveNowSignal ? liveNow : "\\u00A0";' in telemetry_source
    assert "telemetry-live-shell" in telemetry_source
    assert "telemetry-live-value-active" in telemetry_source
    assert "telemetry-live-value-idle" in telemetry_source
    assert "telemetry-last-signal telemetry-last-signal-persistent" in telemetry_source
    assert ".telemetry-live-shell" in styles_source
    assert ".telemetry-live-value-idle" in styles_source
    assert ".telemetry-last-signal-persistent" in styles_source


def test_benchmark_page_source_includes_compare_export_and_idle_truth():
    source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")

    assert "const REALTIME_REFRESH_MS = 1000;" in source
    assert "TelemetryPanel" in source
    assert "Telemetrija" in telemetry_source
    assert "Uživo: tok tokena, sinhronizacija i signal reda pokretanja" in telemetry_source
    assert "Puls tokena" in telemetry_source
    assert "Trošak 24h" in telemetry_source
    assert "Odnos ulaza i izlaza" in telemetry_source
    assert "fetchBenchmarkCompare" in source
    assert "exportBenchmarkRuns" in source
    assert "Uporedi izabrana pokretanja" in source
    assert "Izvezi JSON" in source
    assert "Izvezi CSV" in source
    assert "BX2" in source
    assert "BX5" in source
    assert "BX10" in source
    assert "Prikaz na grafikonu" in source
    assert "Input tokeni" in source
    assert "Output tokeni" in source
    assert "Ukupno tokeni" in source
    assert "await runBatteryBenchmark(selectedBattery.id, repeatCount);" in source
    assert "telemetry?.flowStateReason" in telemetry_source
    assert "telemetry?.lastSignalTokensPerSecond" in telemetry_source
    assert "Izaberi najmanje dva saved run-a da bi compare prikaz bio aktivan." in source
    assert "Model:" in source
    assert "Runtime:" in source

    assert "const SAVED_RUNS_PER_PAGE = 10;" in source
    assert "Prikazani rezultati" in source
    assert "Prethodna strana" in source
    assert "Sledeća strana" in source
    assert "setSavedRunsPage(1);" in source

    telemetry_index = source.index("TelemetryPanel")
    chart_index = source.index("Grafikon benchmarka")
    history_index = source.index("Benchmark istorija")
    assert telemetry_index < chart_index < history_index


def test_api_source_supports_benchmark_compare_and_export():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert "fetchBenchmarkCompare" in source
    assert "/api/benchmark/compare" in source
    assert "exportBenchmarkRuns" in source
    assert "/api/benchmark/export" in source
    assert "runBatteryBenchmark(batteryId: string, repeatCount = 1)" in source
    assert "repeatCount" in source


def test_packaged_frontend_contains_benchmark_compare_export_copy():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Uporedi izabrana pokretanja" in bundled_text
    assert "Izvezi JSON" in bundled_text
    assert "Izvezi CSV" in bundled_text
    assert "Kontekst benchmarka" in bundled_text
    assert "Puls tokena" in bundled_text
    assert "Ulaz 24h" in bundled_text
    assert "Izlaz 24h" in bundled_text
    assert "Aktivne rute" in bundled_text
    assert "Trošak 24h" in bundled_text
    assert "Uživo sada" in bundled_text
    assert "Poslednji throughput signal" in bundled_text
    assert "Odnos ulaza i izlaza" in bundled_text
    assert "Prikazani rezultati" in bundled_text
    assert "Prethodna strana" in bundled_text
    assert "Sledeća strana" in bundled_text
    assert "BX2" in bundled_text
    assert "BX5" in bundled_text
    assert "BX10" in bundled_text
    assert "Prikaz na grafikonu" in bundled_text
    assert "Input tokeni" in bundled_text
    assert "Output tokeni" in bundled_text
    assert "Ukupno tokeni" in bundled_text
    assert "telemetry-live-shell" in bundled_text


def test_theme_sensitive_controls_and_browser_surfaces_use_theme_variables():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert ".settings-field-label" in styles_source
    assert "::placeholder" in styles_source
    assert ".custom-select-trigger" in styles_source
    assert ".custom-select-menu" in styles_source
    assert ".compat-badge {" in styles_source
    assert ".browser-table th {" in styles_source
    assert ".browser-sort-button-active {" in styles_source
    assert ".browser-badge," in styles_source
    assert ".browser-source-huggingface {" in styles_source
    assert "color: var(--app-text-soft);" in styles_source
    assert "border: 1px solid var(--app-field-border);" in styles_source
    assert "background: var(--app-field-bg-alt);" in styles_source
    assert "color: var(--app-accent-strong);" in styles_source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert css_assets
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert ".custom-select-trigger" in bundled_css
    assert ".compat-badge{" in bundled_css
    assert ".browser-table th{" in bundled_css
    assert ".browser-sort-button-active{" in bundled_css
    assert "var(--app-field-border)" in bundled_css
    assert "var(--app-field-bg-alt)" in bundled_css
    assert "var(--app-accent-strong)" in bundled_css


def test_compatibility_modal_source_and_packaged_frontend_include_runtime_breakdown_copy():
    source = Path("frontend/src/components/CompatibilityCalculatorPanel.tsx").read_text(encoding="utf-8")

    assert "Najbolji runtime" in source
    assert "Pregled po runtime-u" in source
    assert "Opterećenje izlaza" in source
    assert "Rezerva memorije" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Najbolji runtime" in bundled_text
    assert "Pregled po runtime-u" in bundled_text
    assert "Opterećenje izlaza" in bundled_text


def test_app_source_and_packaged_frontend_include_compatibility_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'compatibility: "Kompatibilnost"' in source
    assert "CompatibilityPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Kompatibilnost" in bundled_text
    assert "Snimak sistema" in bundled_text
    assert "Udaljeni katalog" in bundled_text


def test_compatibility_page_source_uses_local_and_remote_model_inputs():
    source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(encoding="utf-8")

    assert "fetchModels" in source
    assert "fetchBrowserCatalog" in source
    assert "Aktivni model" in source
    assert "Lokalni katalog" in source
    assert "Udaljeni katalog" in source
    assert "Provera kompatibilnosti" in source


def test_models_and_browser_source_offer_compatibility_tab_handoff():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")

    assert "Compatibility tab" in models_source
    assert "Compatibility tab" in browser_source


def test_compatibility_handoff_includes_installed_size_and_resolved_path_for_local_models():
    source = Path("frontend/src/lib/compatibility.ts").read_text(encoding="utf-8")

    assert "installedSizeGiB: item.installedSizeGiB ?? item.approxSizeGiB ?? null" in source
    assert "absolute_path: item.resolvedPath ?? null" in source


def test_models_source_guides_local_gguf_import_into_local_group():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")

    assert "Model je dodat u `Lokalni modeli`" in models_source
    assert "Ipak pokušaj aktivaciju" in models_source
    assert "scrollIntoView" in models_source


def test_server_page_source_uses_runtime_generic_actions_and_labels():
    source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")

    assert "Start runtime server" in source
    assert "Stop runtime server" in source
    assert "Otvori runtime veb" in source
    assert "serverStatus?.canStart === false" in source
    assert "serverStatus?.canOpenWeb === false" in source
    assert "Start llama.cpp server" not in source


def test_home_and_opencode_source_use_backend_open_action_contract():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "opencode?.openActionLabel" in home_source
    assert "opencode?.canOpen === false" in home_source
    assert "opencode.openActionLabel" in opencode_source
    assert "opencode.canOpen === false" in opencode_source
    assert "bootstrapActionLabel" in opencode_source
    assert "Instaliraj ili popravi OpenCode" in opencode_source


def test_settings_and_workflows_source_include_generation_sampling_controls():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    workflows_source = Path("frontend/src/pages/WorkflowsPage.tsx").read_text(
        encoding="utf-8"
    )
    workflow_presets_source = Path("frontend/src/lib/workflowPresets.ts").read_text(
        encoding="utf-8"
    )
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert "Generacija i sampling" in settings_source
    assert "Temperature" in settings_source
    assert "Top-k" in settings_source
    assert "Top-p" in settings_source
    assert "Min-p" in settings_source
    assert "Repeat penalty" in settings_source
    assert "Repeat last N" in settings_source
    assert "Presence penalty" in settings_source
    assert "Frequency penalty" in settings_source
    assert "Seed" in settings_source
    assert "Inference i sampling" in workflows_source
    assert "temperature: 0.2" in workflow_presets_source
    assert "topK: 20" in workflow_presets_source
    assert js_assets

    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Generacija i sampling" in bundled_text
    assert "Inference i sampling" in bundled_text
    assert "Repeat penalty" in bundled_text
    assert "Frequency penalty" in bundled_text


def test_settings_and_workflows_source_make_inference_settings_visible_without_deep_editor_drilldown():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    workflows_source = Path("frontend/src/pages/WorkflowsPage.tsx").read_text(
        encoding="utf-8"
    )
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert "Aktivna inference podešavanja" in settings_source
    assert "Temp" in settings_source
    assert "Top-k" in settings_source
    assert "Top-p" in settings_source
    assert "Seed" in settings_source
    assert "Inference sažetak" in workflows_source
    assert "temp" in workflows_source
    assert "top-k" in workflows_source
    assert "top-p" in workflows_source
    assert "seed" in workflows_source
    assert js_assets

    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Aktivna inference podešavanja" in bundled_text
    assert "Inference sažetak" in bundled_text


def test_settings_source_explains_inference_parameters_and_uses_compact_summary_layout():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Šta radi i kada da ga menjaš" in settings_source
    assert "Za kodiranje:" in settings_source
    assert "Za kreativniji chat:" in settings_source
    assert "Za stabilne benchmarke:" in settings_source
    assert "Brzi orijentiri" in settings_source
    assert "Niže = mirnije" in settings_source
    assert "Fiksan broj = ponovljivije" in settings_source
    assert "inference-parameter-grid" in settings_source
    assert "inference-spotlight-shell" in styles_source
    assert "inference-parameter-note" in styles_source
    assert "inference-summary-chip-note" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Šta radi i kada da ga menjaš" in bundled_js
    assert "Za kodiranje:" in bundled_js
    assert "Za kreativniji chat:" in bundled_js
    assert "Za stabilne benchmarke:" in bundled_js
    assert "Brzi orijentiri" in bundled_js
    assert "Niže = mirnije" in bundled_js
    assert "Fiksan broj = ponovljivije" in bundled_js
    assert "inference-parameter-grid" in bundled_js
    assert "inference-spotlight-shell" in bundled_css
    assert "inference-parameter-note" in bundled_css
    assert "inference-summary-chip-note" in bundled_css


def test_shared_ux_components_and_guided_flow_copy_are_present_in_core_pages():
    flow_component = Path("frontend/src/components/PageFlowCard.tsx").read_text(encoding="utf-8")
    state_component = Path("frontend/src/components/PageDataStateCard.tsx").read_text(encoding="utf-8")
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")
    search_source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    tuning_lab_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    logs_source = Path("frontend/src/pages/LogsPage.tsx").read_text(encoding="utf-8")
    repair_source = Path("frontend/src/pages/RepairPage.tsx").read_text(encoding="utf-8")
    updates_source = Path("frontend/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Prirodan tok rada" in flow_component
    assert "page-flow-card" in flow_component
    assert "page-flow-step" in flow_component
    assert "Pokušaj ponovo" in state_component
    assert "page-data-state-card" in state_component

    assert "Najbrži sledeći korak" in home_source
    assert "Proveri runtime i model" in home_source
    assert "Otvori OpenCode ili Tuning Lab" in home_source
    assert "PageFlowCard" in home_source
    assert "Otvori Tuning Lab" in home_source

    assert "Server tok" in server_source
    assert "Start ili stop runtime server" in server_source
    assert "Ručna CLI komanda" in server_source
    assert "PageFlowCard" in server_source

    assert "Model tok" in models_source
    assert "Dodaj ili preuzmi model" in models_source
    assert "Aktiviraj model" in models_source
    assert "PageFlowCard" in models_source
    assert "PageDataStateCard" in models_source

    assert "Browser tok" in browser_source
    assert "Refresh katalog" in browser_source
    assert "Dodaj lokalno ili proveri fit" in browser_source
    assert "PageFlowCard" in browser_source
    assert "PageDataStateCard" in browser_source

    assert "Search tok" in search_source
    assert "Izaberi provider" in search_source
    assert "Pokreni search, answer ili compare" in search_source
    assert "PageFlowCard" in search_source
    assert "PageDataStateCard" in search_source

    assert "OpenCode tok" in opencode_source
    assert "Proveri runtime vezu" in opencode_source
    assert "Otvori novu sesiju" in opencode_source
    assert "PageFlowCard" in opencode_source
    assert "PageDataStateCard" in opencode_source

    assert "Benchmark tok" in benchmark_source
    assert "Izaberi test ili bateriju" in benchmark_source
    assert "Gledaj telemetriju i istoriju" in benchmark_source
    assert "PageFlowCard" in benchmark_source
    assert "PageDataStateCard" in benchmark_source

    assert "Settings tok" in settings_source
    assert "Izaberi scope i preset" in settings_source
    assert "Sačuvaj opšta podešavanja" in settings_source
    assert "PageFlowCard" in settings_source
    assert "PageDataStateCard" in settings_source

    assert "Tuning Lab tok" in tuning_lab_source
    assert "Učitaj task ili batch" in tuning_lab_source
    assert "Pokreni task i prati cockpit" in tuning_lab_source
    assert "OpenCode živi output" in tuning_lab_source
    assert "Runtime prompt" in tuning_lab_source
    assert "Runtime generacija" in tuning_lab_source
    assert "PageFlowCard" in tuning_lab_source
    assert "PageDataStateCard" in tuning_lab_source

    assert "Log tok" in logs_source
    assert "Osveži logove" in logs_source
    assert "PageFlowCard" in logs_source
    assert "PageDataStateCard" in logs_source

    assert "Repair tok" in repair_source
    assert "Popravka runtime-a" in repair_source
    assert "PageFlowCard" in repair_source

    assert "Updates tok" in updates_source
    assert "Osveži status" in updates_source
    assert "PageFlowCard" in updates_source
    assert "PageDataStateCard" in updates_source

    assert ".page-flow-card" in styles_source
    assert ".page-flow-grid" in styles_source
    assert ".page-flow-step" in styles_source
    assert ".page-data-state-card" in styles_source
