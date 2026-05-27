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
    assert "Izaberi context velicinu" in bundled_text
    assert "Izaberi output token limit" in bundled_text
    assert "Unesi context velicinu" in bundled_text
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
    assert "Workflow preset" in search_source
    assert "Workflow preset" in knowledge_source
    assert "Workflow preset" in benchmark_source


def test_observability_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    observability_source = Path("frontend/src/pages/ObservabilityPage.tsx").read_text(encoding="utf-8")

    assert "Observability" in app_source
    assert "Live GPU" in observability_source
    assert "Runtime signal" in observability_source
    assert "Recent log signals" in observability_source


def test_fleet_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    fleet_source = Path("frontend/src/pages/FleetPage.tsx").read_text(encoding="utf-8")

    assert "Fleet" in app_source
    assert "Remote machines" in fleet_source
    assert "Refresh all" in fleet_source
    assert "Add machine" in fleet_source


def test_jobs_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    jobs_source = Path("frontend/src/pages/JobsPage.tsx").read_text(encoding="utf-8")

    assert "Jobs" in app_source
    assert "Scheduled jobs" in jobs_source
    assert "Run now" in jobs_source
    assert "Save job" in jobs_source


def test_workflows_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    workflows_source = Path("frontend/src/pages/WorkflowsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Workflows" in app_source
    assert "Workflow workspace" in workflows_source
    assert "Activate preset" in workflows_source
    assert "Open Search" in workflows_source
    assert "workflow-preset-grid" in workflows_source
    assert ".workflow-preset-grid" in styles_source
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in styles_source


def test_settings_source_uses_stable_option_grids_and_balanced_core_layout():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "settings-option-grid" in settings_source
    assert ".settings-option-grid" in styles_source
    assert "settings-cluster-grid-profiles" in styles_source
    assert "grid-template-columns: 1fr;" in styles_source
    assert "settings-cluster-grid-core" in styles_source
    assert "repeat(2, minmax(260px, 1fr))" in styles_source


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
    assert "item.lifecycleLabel ?? \"Status\"" in source
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

    assert "Ovaj model verovatno nece moci da radi ili ce raditi lose na ovoj masini." in source
    assert "Da li zelis ipak da pokusas aktivaciju?" in source
    assert "Ipak pokusaj aktivaciju" in source
    assert "activateModel(item.id, { force: true })" in source
    assert "force?: boolean" in api_source
    assert js_assets

    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Ovaj model verovatno nece moci da radi ili ce raditi lose na ovoj masini." in bundled_text
    assert "Da li zelis ipak da pokusas aktivaciju?" in bundled_text
    assert "Ipak pokusaj aktivaciju" in bundled_text


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


def test_api_source_supports_browser_catalog_query_params():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert "export type BrowserCatalogQuery" in source
    assert "new URLSearchParams()" in source
    assert "params.toString()" in source
    assert 'cache: "no-store"' in source


def test_download_progress_card_source_explains_retry_without_resume():
    source = Path("frontend/src/components/ModelDownloadProgressCard.tsx").read_text(encoding="utf-8")

    assert "Resume nije podrzan" in source
    assert "ponovo kliknuti Download" in source


def test_app_source_and_packaged_frontend_include_updates_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'updates: "Updates"' in source
    assert "UpdatesPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Updates" in bundled_text
    assert "Check updates" in bundled_text


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
    assert "Telemetry" in bundled_text
    assert "Token Pulse" in bundled_text


def test_app_source_and_packaged_frontend_include_search_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'search: "Search"' in source
    assert "SearchPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Search workspace" in bundled_text
    assert "Find web sources" in bundled_text
    assert "Search + answer locally" in bundled_text
    assert "Compare providers" in bundled_text
    assert "DuckDuckGo" in bundled_text
    assert "Final answer from local model" in bundled_text
    assert "Setup managed SearxNG (Windows + WSL)" in bundled_text
    assert "SearxNG nije podesen" in bundled_text
    assert "Managed local SearxNG (Windows + WSL)" in bundled_text
    assert "Ovo su izvori, ne finalan odgovor." in bundled_text
    assert "Open source" in bundled_text


def test_app_source_and_packaged_frontend_include_knowledge_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")

    assert 'knowledge: "Knowledge"' in source
    assert "KnowledgePage" in source
    assert "pickWorkingDirectory" in knowledge_source
    assert "Browse" in knowledge_source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Knowledge workspace" in bundled_text
    assert "Documents + web" in bundled_text
    assert "Browse" in bundled_text
    assert "Collections" in knowledge_source
    assert "Tags" in knowledge_source
    assert "Citations" in knowledge_source
    assert "Export JSON" in knowledge_source
    assert "Export Markdown" in knowledge_source


def test_settings_and_opencode_source_include_web_search_controls_and_guidance():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "Web search mode" in settings_source
    assert "Search provider" in settings_source
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
    assert "Search provider" in source
    assert "Find web sources" in source
    assert "Search + answer locally" in source
    assert "Final answer from local model" in source
    assert "Ovo su izvori, ne finalan odgovor." in source
    assert 'target="_blank"' in source
    assert "Open source" in source


def test_home_page_source_uses_single_system_overview_card():
    source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")

    assert "System overview" in source
    assert "TelemetryPanel" in source
    assert "Token Pulse" in telemetry_source
    assert "Input 24h" in telemetry_source
    assert "Output 24h" in telemetry_source
    assert "Active routes" in telemetry_source
    assert "Live now" in telemetry_source
    assert "Control Center health" in source
    assert "Aktivan runtime" in source
    assert "Status runtime servera" in source
    assert "Aktivni model" in source
    assert "Profil" in source
    assert "Dostupni runtime-i" in source


def test_benchmark_page_source_includes_compare_export_and_idle_truth():
    source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")

    assert "TelemetryPanel" in source
    assert "Telemetry" in telemetry_source
    assert "Live token flow, sync i launch queue signal" in telemetry_source
    assert "Token Pulse" in telemetry_source
    assert "Cost 24h" in telemetry_source
    assert "Input / output split" in telemetry_source
    assert "fetchBenchmarkCompare" in source
    assert "exportBenchmarkRuns" in source
    assert "Compare selected runs" in source
    assert "Export JSON" in source
    assert "Export CSV" in source
    assert "telemetry?.flowStateReason" in telemetry_source
    assert "Izaberi najmanje dva saved run-a da bi compare prikaz bio aktivan." in source
    assert "Model:" in source
    assert "Runtime:" in source


def test_api_source_supports_benchmark_compare_and_export():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert "fetchBenchmarkCompare" in source
    assert "/api/benchmark/compare" in source
    assert "exportBenchmarkRuns" in source
    assert "/api/benchmark/export" in source


def test_packaged_frontend_contains_benchmark_compare_export_copy():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Compare selected runs" in bundled_text
    assert "Export JSON" in bundled_text
    assert "Export CSV" in bundled_text
    assert "Benchmark context" in bundled_text
    assert "Token Pulse" in bundled_text
    assert "Input 24h" in bundled_text
    assert "Output 24h" in bundled_text
    assert "Active routes" in bundled_text
    assert "Cost 24h" in bundled_text
    assert "Live now" in bundled_text
    assert "Input / output split" in bundled_text


def test_compatibility_modal_source_and_packaged_frontend_include_runtime_breakdown_copy():
    source = Path("frontend/src/components/CompatibilityCalculatorPanel.tsx").read_text(encoding="utf-8")

    assert "Best runtime" in source
    assert "Runtime breakdown" in source
    assert "Output pressure" in source
    assert "Memory headroom" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Best runtime" in bundled_text
    assert "Runtime breakdown" in bundled_text
    assert "Output pressure" in bundled_text


def test_app_source_and_packaged_frontend_include_compatibility_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'compatibility: "Compatibility"' in source
    assert "CompatibilityPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("index-*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Compatibility" in bundled_text
    assert "System snapshot" in bundled_text
    assert "Remote catalog" in bundled_text


def test_compatibility_page_source_uses_local_and_remote_model_inputs():
    source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(encoding="utf-8")

    assert "fetchModels" in source
    assert "fetchBrowserCatalog" in source
    assert "Active model" in source
    assert "Local catalog" in source
    assert "Remote catalog" in source
    assert "Check compatibility" in source


def test_models_and_browser_source_offer_compatibility_tab_handoff():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")

    assert "Compatibility tab" in models_source
    assert "Compatibility tab" in browser_source


def test_server_page_source_uses_runtime_generic_actions_and_labels():
    source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")

    assert "Start runtime server" in source
    assert "Stop runtime server" in source
    assert "Open runtime web" in source
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
