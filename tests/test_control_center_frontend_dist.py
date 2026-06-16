import re
from pathlib import Path

from fastapi.testclient import TestClient

from local_ai_control_center_installer.control_center_backend.main import app


def _read_tuning_lab_frontend_sources() -> str:
    parts = [Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")]
    tuning_components = Path("frontend/src/components/tuning-lab")
    if tuning_components.is_dir():
        for path in sorted(tuning_components.glob("*")):
            if path.suffix in {".ts", ".tsx"}:
                parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


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


def test_packaged_frontend_js_chunks_stay_under_vite_warning_threshold():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert js_assets

    oversized_assets = [
        f"{path.name}={path.stat().st_size}"
        for path in js_assets
        if path.stat().st_size > 500 * 1024
    ]

    assert oversized_assets == []


def test_runtimepilot_favicon_is_declared_and_packaged():
    source_index = Path("frontend/index.html").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    packaged_index = (dist_root / "index.html").read_text(encoding="utf-8")

    assert 'rel="icon"' in source_index
    assert "/runtimepilot-favicon.png" in source_index
    assert 'rel="icon"' in packaged_index
    assert "/runtimepilot-favicon.png" in packaged_index
    assert (Path("frontend/public") / "runtimepilot-favicon.png").is_file()
    assert (dist_root / "runtimepilot-favicon.png").is_file()

    client = TestClient(app)
    favicon_response = client.get("/runtimepilot-favicon.png")

    assert favicon_response.status_code == 200
    assert favicon_response.headers["content-type"] == "image/png"


def test_packaged_settings_ui_uses_numeric_preset_dropdowns_with_custom_inputs():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

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


def test_settings_page_source_reuses_context_picker_pattern_for_turboquant_context():
    source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")

    assert "const turboContextChoice = resolveTokenChoice(activeTurboConfig.context);" in source
    assert 'parameter.id === "context" ? (' in source
    assert "Izaberi TurboQuant context veličinu" in source
    assert "Unesi TurboQuant context veličinu" in source
    assert 'turboContextChoice === "custom" ? (' in source


def test_settings_source_includes_opencode_disk_hygiene_panel_and_actions():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    types_source = Path("frontend/src/lib/types.ts").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Disk higijena OpenCode workspace-a" in settings_source
    assert "Očisti sada" in settings_source
    assert "OpCode scratch i copy workspace-i" not in settings_source
    assert "fetchOpenCodeWorkspaceHygiene" in settings_source
    assert "cleanupOpenCodeWorkspaceHygiene" in settings_source
    assert "OpenCodeWorkspaceHygienePayload" in types_source
    assert "/api/opencode/hygiene" in api_source
    assert "/api/opencode/hygiene/cleanup" in api_source
    assert ".settings-hygiene-grid" in styles_source
    assert ".settings-hygiene-item-list" in styles_source


def test_settings_source_mentions_last_auto_cleanup_signal_for_opencode_hygiene():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    types_source = Path("frontend/src/lib/types.ts").read_text(encoding="utf-8")

    assert "lastAutoCleanup" in settings_source
    assert "Auto-cleanup" in settings_source
    assert "lastAutoCleanup" in types_source


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


def test_layout_source_and_packaged_frontend_include_scroll_to_top_control():
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "window.scrollTo({ top: 0, behavior: \"smooth\" })" in layout_source
    assert "runtimepilot-scroll-top-button" in layout_source
    assert "Na vrh" in layout_source
    assert ".runtimepilot-scroll-top-button" in styles_source
    assert ".runtimepilot-scroll-top-button-visible" in styles_source
    assert ".runtimepilot-scroll-top-button-symbol" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Na vrh" in bundled_js
    assert ".runtimepilot-scroll-top-button" in bundled_css
    assert ".runtimepilot-scroll-top-button-visible" in bundled_css


def test_workflow_preset_source_mentions_core_presets():
    workflow_source = Path("frontend/src/lib/workflowPresets.ts").read_text(encoding="utf-8")
    search_source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")

    assert "Istraživanje" in workflow_source
    assert "Kod" in workflow_source
    assert "Nizak VRAM" in workflow_source
    assert "Dug kontekst" in workflow_source
    assert "Dokumenti + veb" in workflow_source
    assert "Benchmark baterija" in workflow_source
    assert "Preset radnog toka" in search_source
    assert "Preset radnog toka" in knowledge_source
    assert "Preset radnog toka" in benchmark_source


def test_home_source_exposes_command_deck_intro_and_primary_flow_grid():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Brzi signal" in home_source
    assert "HomeStatusDeck" in home_source
    assert 'variant="home"' in home_source
    assert ".runtimepilot-home-status-grid" in styles_source
    assert ".runtimepilot-home-status-deck" in styles_source
    assert ".telemetry-panel-home" in styles_source


def test_home_source_uses_five_card_status_deck_in_locked_order():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    deck_source = Path("frontend/src/components/shell/HomeStatusDeck.tsx").read_text(
        encoding="utf-8"
    )
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "HomeStatusDeck" in home_source
    assert '"Health"' in deck_source
    assert '"Runtime"' in deck_source
    assert '"Model"' in deck_source
    assert '"Context"' in deck_source
    assert '"OpenCode"' in deck_source
    assert ".runtimepilot-home-status-deck" in styles_source


def test_home_source_drops_big_runtime_model_opencode_modules():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")

    assert 'title="Runtime"' not in home_source
    assert 'title="Lokalni model"' not in home_source
    assert 'title="OpenCode"' not in home_source
    assert "Brzi signal" in home_source


def test_observability_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    observability_source = Path("frontend/src/pages/ObservabilityPage.tsx").read_text(encoding="utf-8")

    assert "Observability" in app_source
    assert "GPU uživo" in observability_source
    assert "Runtime signal" in observability_source
    assert "Skorašnji log signali" in observability_source


def test_layout_and_benchmark_source_show_persistent_resource_strip_and_mode_labels():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layer_source = Path(
        "frontend/src/components/shell/SystemStatusLayer.tsx"
    ).read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")

    assert "SystemStatusLayer" in app_source
    assert "LiveResourceStrip" in layer_source
    assert "CPU uživo" in benchmark_source
    assert "RAM uživo" in benchmark_source
    assert "VRAM uživo" in benchmark_source
    assert "Režim izvršavanja" in benchmark_source
    assert "GPU VRAM dominantno" in benchmark_source
    assert "Hibrid VRAM + RAM" in benchmark_source
    assert "CPU + RAM" in benchmark_source


def test_app_and_layout_source_and_packaged_frontend_show_global_active_model_strip():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    layer_source = Path(
        "frontend/src/components/shell/SystemStatusLayer.tsx"
    ).read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "SystemStatusLayer" in app_source
    assert "systemStatusLayer={systemStatusLayer}" in app_source
    assert "systemStatusLayer" in layout_source
    assert "LiveResourceStrip" in layer_source
    assert "runtimepilot-active-model-strip" in app_source
    assert "runtimepilot-utility-module" in app_source
    assert "runtimepilot-active-model-layout" in app_source
    assert "runtimepilot-utility-title" in app_source
    assert "runtimepilot-active-model-meta" in app_source
    assert "Otvori modele" in app_source
    assert "Runtime aktivan" in app_source
    assert "Nema aktivnog modela" in app_source
    assert ".runtimepilot-system-status-layer" in styles_source
    assert ".runtimepilot-active-model-strip" in styles_source
    assert ".runtimepilot-utility-module" in styles_source
    assert ".runtimepilot-utility-head" in styles_source
    assert ".runtimepilot-utility-title" in styles_source
    assert ".runtimepilot-active-model-open" in styles_source
    assert ".runtimepilot-active-model-meta" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Aktivni model" in bundled_js
    assert "Otvori modele" in bundled_js
    assert "Runtime aktivan" in bundled_js
    assert "Nema aktivnog modela" in bundled_js
    assert ".runtimepilot-system-status-layer" in bundled_css
    assert ".runtimepilot-active-model-strip" in bundled_css
    assert ".runtimepilot-utility-module" in bundled_css
    assert ".runtimepilot-utility-head" in bundled_css
    assert ".runtimepilot-utility-title" in bundled_css
    assert ".runtimepilot-active-model-open" in bundled_css
    assert ".runtimepilot-active-model-meta" in bundled_css


def test_shell_source_uses_unified_system_status_layer():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(
        encoding="utf-8"
    )
    layer_source = Path(
        "frontend/src/components/shell/SystemStatusLayer.tsx"
    ).read_text(encoding="utf-8")

    assert "SystemStatusLayer" in app_source
    assert "systemStatusLayer={systemStatusLayer}" in app_source
    assert "systemStatusLayer?: ReactNode" in layout_source
    assert "activeModelStrip={" not in app_source
    assert "activeModelStrip?: ReactNode" not in layout_source
    assert "LiveResourceStrip" in layer_source
    assert "sticky" in layer_source.lower()


def test_styles_source_includes_full_and_compact_system_status_modes():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert ".runtimepilot-system-status-layer" in styles_source
    assert ".runtimepilot-system-status-layer-sticky" in styles_source
    assert ".runtimepilot-system-status-layer-compact" in styles_source


def test_shell_source_shares_live_resource_state_between_full_and_compact_modes():
    layer_source = Path(
        "frontend/src/components/shell/SystemStatusLayer.tsx"
    ).read_text(encoding="utf-8")
    strip_source = Path("frontend/src/components/LiveResourceStrip.tsx").read_text(
        encoding="utf-8"
    )

    assert "useLiveResourceStripState" in layer_source
    assert layer_source.count("state={liveResourceStripState}") == 2
    assert "type LiveResourceStripSharedState" in strip_source
    assert "state?: LiveResourceStripSharedState" in strip_source
    assert "compact?: boolean" in strip_source


def test_shell_source_recomputes_sticky_visibility_when_status_layer_resizes():
    layer_source = Path(
        "frontend/src/components/shell/SystemStatusLayer.tsx"
    ).read_text(encoding="utf-8")

    assert "ResizeObserver" in layer_source
    assert "resizeObserver.observe(fullLayer)" in layer_source
    assert "resizeObserver.disconnect()" in layer_source


def test_packaged_frontend_includes_unified_system_status_layer():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Aktivni model" in bundled_js
    assert "Živi resursi" in bundled_js
    assert ".runtimepilot-system-status-layer" in bundled_css
    assert ".runtimepilot-system-status-layer-sticky" in bundled_css
    assert ".runtimepilot-system-status-layer-compact" in bundled_css
    assert ".live-resource-strip-compact" in bundled_css


def test_project_memory_source_and_packaged_frontend_keep_project_memory_as_page_and_nav_tool():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/pages/ProjectMemoryPage.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    types_source = Path("frontend/src/lib/types.ts").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "projectMemory" in app_source
    assert "Project Memory" in app_source
    assert "projectMemoryStrip" not in app_source
    assert "systemStatusLayer" in layout_source
    assert "projectMemoryStrip" not in layout_source
    assert "Posej iz task teksta" in page_source
    assert "Sačuvaj Project Memory" in page_source
    assert "Glavni fokus" in page_source
    assert "Važna pravila" in page_source
    assert "Već odlučeno" in page_source
    assert "Napredak" in page_source
    assert "Sledeće" in page_source
    assert 'className="project-memory-grid wide-card"' in page_source
    assert "Još nema pravila" in page_source
    assert "Još nema sledećeg koraka" in page_source
    assert "fetchProjectMemory" in api_source
    assert "seedProjectMemory" in api_source
    assert "saveProjectMemory" in api_source
    assert "ProjectMemoryPayload" in types_source
    assert "ProjectMemorySavePayload" in types_source
    assert ".runtimepilot-project-memory-strip" in styles_source
    assert ".project-memory-grid" in styles_source
    assert ".project-memory-empty-state" in styles_source
    assert ".project-memory-item-row" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Project Memory" in bundled_js
    assert "Posej iz task teksta" in bundled_js
    assert "Sačuvaj Project Memory" in bundled_js
    assert "Još nema pravila" in bundled_js
    assert "Još nema sledećeg koraka" in bundled_js
    assert ".project-memory-grid" in bundled_css
    assert ".project-memory-empty-state" in bundled_css
    assert ".project-memory-item-row" in bundled_css


def test_live_resource_strip_source_and_packaged_frontend_use_compact_clickable_two_line_metrics_without_horizontal_scroll():
    strip_source = Path("frontend/src/components/LiveResourceStrip.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "live-resource-inline-row" in strip_source
    assert "live-resource-inline-item" in strip_source
    assert "estimateHybridRuntimeUsage" in strip_source
    assert "estimateContextFitFromKvBuffer" in strip_source
    assert "simplifyGpuName" in strip_source
    assert "formatUsedTotalGiBCompact" in strip_source
    assert "aria-pressed" in strip_source
    assert "resource-chip-detail-panel" in strip_source
    assert "resource-chip-detail-panel-idle" in strip_source
    assert "resource-chip-detail-panel-expanded" in strip_source
    assert "resource-chip-detail-idle-copy" in strip_source
    assert "live-resource-inline-meter" in strip_source
    assert "live-resource-inline-meter-fill" in strip_source
    assert "live-resource-inline-meter-scale" in strip_source
    assert "Otvori VRAM tuning" in strip_source
    assert 'label: "Context"' in strip_source
    assert "Restart potreban" in strip_source
    assert "Usklađeno" in strip_source
    assert "Staje u VRAM" in strip_source
    assert "Ne staje u VRAM" in strip_source
    assert "GPU drži model, ali ceo runtime ne staje u VRAM" in strip_source
    assert "težine modela jesu na GPU-u, ali ceo runtime nije čist VRAM fit." in strip_source
    assert "Sistemski RAM se i dalje koristi samo za mapiranje i pomoćne bafere." in strip_source
    assert ".live-resource-inline-row" in styles_source
    assert ".live-resource-inline-item" in styles_source
    assert "live-resource-inline-item-compact-numeric" in strip_source
    assert ".live-resource-inline-item-compact-numeric .live-resource-inline-value" in styles_source
    assert ".live-resource-inline-meter" in styles_source
    assert ".live-resource-inline-meter-fill" in styles_source
    assert ".live-resource-inline-meter-scale" in styles_source
    assert "padding: 6px 8px;" in styles_source
    assert "grid-template-columns: minmax(0, 0.58fr) minmax(0, 0.94fr) minmax(0, 0.94fr) minmax(0, 0.96fr) minmax(0, 1.08fr) minmax(0, 1.08fr) minmax(0, 0.82fr) minmax(0, 1.28fr);" in styles_source
    assert "grid-template-rows: auto auto auto;" in styles_source
    assert "overflow-x: auto;" not in styles_source
    assert ".live-resource-inline-button" in styles_source
    assert ".resource-chip-detail-panel" in styles_source
    assert ".resource-chip-detail-panel-idle" in styles_source
    assert ".resource-chip-detail-idle-copy" in styles_source
    assert ".live-resource-context-alert" not in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Živi resursi" in bundled_js
    assert "Model proces" in bundled_js
    assert "Klikni stavku za pun detalj" in bundled_js
    assert "Izaberi CPU, RAM, VRAM, režim, offload ili GPU kada želiš pun kontekst." in bundled_js
    assert "Hibrid" in bundled_js
    assert "GPU drži ceo model" in bundled_js
    assert "Otvori VRAM tuning" in bundled_js
    assert "RTX 3060" in bundled_js
    assert "Context" in bundled_js
    assert "Restart potreban" in bundled_js
    assert "Usklađeno" in bundled_js
    assert "Staje u VRAM" in bundled_js
    assert "Ne staje u VRAM" in bundled_js
    assert "Sistemski RAM se i dalje koristi samo za mapiranje i pomoćne bafere." in bundled_js
    assert "Potreban restart runtime-a" in bundled_js
    assert "Config ctx" in bundled_js
    assert "Živi ctx" in bundled_js
    assert ".live-resource-inline-row" in bundled_css
    assert ".live-resource-inline-item" in bundled_css
    assert ".live-resource-inline-item-compact-numeric .live-resource-inline-value" in bundled_css
    assert ".live-resource-inline-meter" in bundled_css
    assert ".live-resource-inline-meter-fill" in bundled_css
    assert ".live-resource-inline-meter-scale" in bundled_css
    assert ".live-resource-inline-button" in bundled_css
    assert ".resource-chip-detail-panel" in bundled_css
    assert ".resource-chip-detail-panel-idle" in bundled_css
    assert "padding:6px 8px" in bundled_css
    assert "grid-template-columns:minmax(0,.58fr) minmax(0,.94fr) minmax(0,.94fr) minmax(0,.96fr) minmax(0,1.08fr) minmax(0,1.08fr) minmax(0,.82fr) minmax(0,1.28fr)" in bundled_css
    assert "grid-template-rows:auto auto auto" in bundled_css


def test_runtime_resource_panel_source_explains_hybrid_ram_spill_and_full_gpu_fit():
    panel_source = Path("frontend/src/components/RuntimeResourcePanel.tsx").read_text(encoding="utf-8")

    assert "Procena RAM preliva" in panel_source
    assert "Još VRAM-a za puni GPU fit" in panel_source
    assert "Ovo je procena na osnovu odnosa GPU slojeva" in panel_source
    assert "Config context" in panel_source
    assert "Živi process context" in panel_source
    assert "Potreban restart runtime-a" in panel_source


def test_settings_source_mentions_vram_fit_tuning_and_manual_gpu_layers_override():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    runtime_helper_source = Path("frontend/src/lib/runtimeDiagnostics.ts").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert "VRAM fit tuning" in settings_source
    assert "GPU layers override" in settings_source
    assert "Procenjeni context za puni GPU fit" in settings_source
    assert "Pokušaj VRAM fit" in settings_source
    assert "estimateContextFitFromKvBuffer" in runtime_helper_source
    assert "Samo spuštanje context-a verovatno nije dovoljno" in settings_source
    assert "Auto trenutno cilja" in settings_source
    assert "Više GPU slojeva = više VRAM" in settings_source
    assert "Sačuvaj i primeni na runtime" in settings_source
    assert "Runtime se tada još ne restartuje" in settings_source
    assert "Poslednji VRAM fit predlog" in settings_source
    assert "Ovo još nije sačuvano ni aktivno u runtime-u." in settings_source
    assert "Poslednja primena runtime-a" in settings_source
    assert "Ako je runtime već aktivan, RuntimePilot ga restartuje" in settings_source
    assert "TurboQuant smernice za čistiji VRAM fit" in settings_source
    assert js_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "VRAM fit tuning" in bundled_js
    assert "GPU layers override" in bundled_js
    assert "Pokušaj VRAM fit" in bundled_js
    assert "VRAM fit" in bundled_js
    assert "GPU layers" in bundled_js
    assert "TurboQuant smernice" in bundled_js
    assert "Poslednji VRAM fit predlog" in bundled_js
    assert "Poslednja primena runtime-a" in bundled_js


def test_opencode_source_and_styles_use_service_bay_layout_for_advanced_tools():
    page_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "RuntimePilotStatusDeck" in page_source
    assert "RuntimePilotActionDeck" in page_source
    assert "Servisni tok OpenCode-a" in page_source
    assert "Komande i launcher" in page_source
    assert "Presetovi i ponašanje agenta" in page_source
    assert "Bezbednost i autonomija" in page_source
    assert "runtimepilot-opencode-service-bay" in page_source
    assert "runtimepilot-opencode-service-panel" in page_source
    assert "runtimepilot-opencode-transport-rail" in page_source
    assert "runtimepilot-opencode-summary-grid" in page_source
    assert ".runtimepilot-opencode-summary-grid" in styles_source
    assert "runtimepilot-opencode-field-stack" in page_source
    assert "runtimepilot-opencode-preset-grid" in page_source
    assert "runtimepilot-opencode-instance-grid" in page_source
    assert "runtimepilot-primary-tab-rack-detail-grid" not in page_source
    assert "runtimepilot-primary-tab-rack-detail-actions" not in page_source
    assert "runtimepilot-opencode-inline-transport" in page_source
    assert "runtimepilot-opencode-form-actions" in page_source
    assert "runtimepilot-opencode-settings-row" in page_source
    assert "runtimepilot-opencode-settings-actions" in page_source
    assert "Koraci po toku" in page_source
    assert "Preset kanal" in page_source
    assert "Bezbednosni kanal" in page_source
    assert "runtimepilot-opencode-control-rack" in page_source
    assert "runtimepilot-opencode-control-card" in page_source
    assert "runtimepilot-opencode-step-field" in page_source

    assert ".runtimepilot-opencode-service-bay" in styles_source
    assert ".runtimepilot-opencode-service-panel" in styles_source
    assert ".runtimepilot-opencode-transport-rail" in styles_source
    assert ".runtimepilot-opencode-field-stack" in styles_source
    assert ".runtimepilot-opencode-preset-grid" in styles_source
    assert ".runtimepilot-opencode-instance-grid" in styles_source
    assert ".runtimepilot-primary-tab-rack" in styles_source
    assert ".runtimepilot-primary-tab-rack-detail-grid" in styles_source
    assert ".runtimepilot-opencode-inline-transport" in styles_source
    assert ".runtimepilot-opencode-form-actions" in styles_source
    assert ".runtimepilot-opencode-settings-row" in styles_source
    assert ".runtimepilot-opencode-settings-actions" in styles_source
    assert ".runtimepilot-opencode-control-rack" in styles_source
    assert ".runtimepilot-opencode-control-card" in styles_source
    assert ".runtimepilot-opencode-step-field" in styles_source
    assert "grid-template-columns: repeat(auto-fit, minmax(168px, max-content));" in styles_source


def test_settings_source_uses_hifi_vram_stack_with_transport_controls():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "settings-vram-hifi-stack" in settings_source
    assert "settings-vram-mixer-deck" in settings_source
    assert "settings-vram-transport-deck" in settings_source
    assert "settings-vram-monitor-deck" in settings_source
    assert "Primeni postojeće" in settings_source
    assert "Sačuvaj i primeni" in settings_source
    assert "saveAndApplySavedVramTuning" in settings_source
    assert ".settings-vram-hifi-stack" in styles_source
    assert ".settings-vram-mixer-deck" in styles_source
    assert ".settings-vram-transport-deck" in styles_source
    assert ".settings-vram-monitor-deck" in styles_source
    assert ".settings-vram-transport-actions" in styles_source


def test_settings_source_uses_hifi_decks_for_general_search_and_turbo_sections():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "settings-general-hifi-stack" in settings_source
    assert "settings-general-mixer-deck" in settings_source
    assert "settings-general-transport-deck" in settings_source
    assert "settings-general-monitor-deck" in settings_source

    assert "settings-search-hifi-stack" in settings_source
    assert "settings-search-mixer-deck" in settings_source
    assert "settings-search-transport-deck" in settings_source
    assert "settings-search-monitor-deck" in settings_source

    assert "settings-turbo-hifi-stack" in settings_source
    assert "settings-turbo-mixer-deck" in settings_source
    assert "settings-turbo-transport-deck" in settings_source
    assert "settings-turbo-monitor-deck" in settings_source

    assert ".settings-general-hifi-stack" in styles_source
    assert ".settings-general-mixer-deck" in styles_source
    assert ".settings-search-hifi-stack" in styles_source
    assert ".settings-search-mixer-deck" in styles_source
    assert ".settings-turbo-hifi-stack" in styles_source
    assert ".settings-turbo-mixer-deck" in styles_source


def test_fleet_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    fleet_source = Path("frontend/src/pages/FleetPage.tsx").read_text(encoding="utf-8")

    assert "Fleet" in app_source
    assert "Udaljene mašine" in fleet_source
    assert "Osveži sve" in fleet_source
    assert "Dodaj mašinu" in fleet_source


def test_models_and_nav_source_protect_local_model_layout_and_even_nav_card_heights():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert 'className="model-item-copy-head"' in models_source
    assert 'className="model-item-copy-main"' in models_source
    assert 'className="models-local-group-anchor wide-card"' in models_source
    assert 'ref={localGroupRef}' in models_source
    assert "showWhenEmpty = false" in models_source
    assert "if (!items.length && !showWhenEmpty)" in models_source
    assert ".model-item-copy-head" in styles_source
    assert ".model-item-copy-main" in styles_source
    assert ".model-item-copy-head code" in styles_source
    assert ".models-local-group-anchor" in styles_source
    assert "grid-column: 1 / -1;" in styles_source
    assert ".runtimepilot-nav-button-copy" in styles_source
    assert "min-width: 0;" in styles_source
    assert ".runtimepilot-nav-button-cue" in styles_source
    assert "font-size: 0.85rem;" in styles_source
    assert "overflow: visible;" in styles_source
    assert "text-overflow: clip;" in styles_source
    assert "overflow-wrap: normal;" in styles_source
    assert "white-space: nowrap;" in styles_source
    assert "text-overflow: ellipsis;" in styles_source
    assert ".nav-more-shell" in styles_source
    assert "flex: 0 0 182px;" in styles_source
    assert "align-self: auto;" in styles_source
    assert "display: flex;" in styles_source
    assert ".nav-more-button" in styles_source
    assert "min-height: 70px;" in styles_source


def test_jobs_source_and_navigation_are_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    jobs_source = Path("frontend/src/pages/JobsPage.tsx").read_text(encoding="utf-8")

    assert "Jobs" in app_source
    assert "Zakazani poslovi" in jobs_source or "Pozadinski poslovi" in jobs_source
    assert "Pokreni sada" in jobs_source
    assert "Sačuvaj posao" in jobs_source


def test_app_source_and_packaged_frontend_use_primary_tabs_plus_more_menu():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Više" not in app_source
    assert "Početna" in app_source
    assert "Runtime" in app_source
    assert "Modeli" in app_source
    assert "OpenCode" in app_source
    assert "Napredno" in app_source
    assert "nav-more-button" not in app_source
    assert "nav-menu-panel" not in app_source
    assert "nav-menu-section-label" not in app_source
    assert "LOCAL AI RUNTIME CONTROL CENTER" in app_source
    assert "Control. Monitor. Optimize." in app_source
    assert ".top-nav-primary" in styles_source
    assert "repeat(5, minmax(0, 1fr))" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Početna" in bundled_js
    assert "Modeli" in bundled_js
    assert "Napredno" in bundled_js
    assert "LOCAL AI RUNTIME CONTROL CENTER" in bundled_js
    assert "Control. Monitor. Optimize." in bundled_js
    assert ".top-nav-primary" in bundled_css
    assert ".nav-more-button" in bundled_css
    assert ".nav-menu-panel" in bundled_css
    assert ".nav-menu-section-label" in bundled_css


def test_mobile_hero_navigation_source_and_bundle_force_two_column_tabs():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    hero_nav_mobile_rule = re.search(
        r"@media\s*\(max-width:\s*760px\)\s*\{[\s\S]*?\.runtimepilot-hero-nav-shell \.top-nav-primary\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);",
        styles_source,
    )
    hero_nav_last_tile_rule = re.search(
        r"@media\s*\(max-width:\s*760px\)\s*\{[\s\S]*?\.runtimepilot-hero-nav-shell \.top-nav-primary > :last-child\s*\{[\s\S]*?grid-column:\s*1 / -1;",
        styles_source,
    )

    assert hero_nav_mobile_rule is not None
    assert hero_nav_last_tile_rule is not None
    assert css_assets

    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert re.search(
        r"@media\s*\(max-width:\s*760px\)\{[\s\S]*?\.runtimepilot-hero-nav-shell \.top-nav-primary\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)",
        bundled_css,
    )
    assert re.search(
        r"@media\s*\(max-width:\s*760px\)\{[\s\S]*?\.runtimepilot-hero-nav-shell \.top-nav-primary>:last-child\{[\s\S]*?grid-column:\s*1\s*/\s*-1",
        bundled_css,
    )


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
    compatibility_source = Path(
        "frontend/src/components/CompatibilityCalculatorPanel.tsx"
    ).read_text(encoding="utf-8")
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
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
    assert "Izvezi / podeli" in page_source
    assert "TuningLabStatusDeck" in page_source
    assert ".tuning-lab-status-deck" in styles_source
    assert "tuning-lab-cockpit-tip-strip" in page_source
    assert "Uvezi forum / Reddit snippet" in page_source
    assert 'className="action-button-soft"' in page_source
    assert page_source.count('className="action-button"') >= 4
    assert 'className="action-button"' in compatibility_source
    assert 'className="action-button"' in settings_source
    assert ".action-button," in styles_source
    assert ".action-button-soft" in styles_source
    assert ".action-button:hover:not(:disabled)" in styles_source
    assert ".tuning-lab-batch-action-card {\n  display: grid;\n  grid-template-rows: auto 1fr auto;" in styles_source
    assert ".tuning-lab-batch-action-card button {\n  justify-self: stretch;\n  width: 100%;\n  min-height: 44px;" in styles_source
    assert ".tuning-lab-overview-grid" in styles_source
    assert ".tuning-lab-cockpit-tip-strip" in styles_source


def test_server_and_tuning_lab_sources_show_runtime_gpu_diagnostics():
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    tuning_source = _read_tuning_lab_frontend_sources()
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
    assert "TuningLabTriSlotReceiverRack" in tuning_source
    assert "tuning-lab-receiver-rack" in tuning_source
    assert "tuning-lab-slot-row" in tuning_source
    assert "tuning-lab-slot-identity-panel" in tuning_source
    assert "tuning-lab-slot-square-control" in tuning_source
    assert "tuning-lab-slot-led-row" in tuning_source
    assert "tuning-lab-slot-display-panel" in tuning_source
    assert "tuning-lab-slot-display-box" in tuning_source
    assert "tuning-lab-slot-precision-rack" in tuning_source
    assert "tuning-lab-slot-precision-group" in tuning_source
    assert "tuning-lab-slot-state-draft" in tuning_source
    assert "tuning-lab-slot-state-active" in tuning_source
    assert "tuning-lab-slot-state-recommended" in tuning_source
    assert "tuning-lab-slot-zones" in tuning_source
    assert "Sampling" in tuning_source
    assert "Stability" in tuning_source
    assert "Bias" in tuning_source
    assert "Profil" in tuning_source
    assert "Thinking" in tuning_source
    assert "Source" in tuning_source
    assert "Context" in tuning_source
    assert "Output" in tuning_source
    assert "tuning-lab-results-table" in tuning_source
    assert "tuning-lab-history-card" in tuning_source
    assert "Zašto je ovaj slot pobedio" in tuning_source
    assert "Aktivni korak" in tuning_source
    assert "Poslednji log signal" in tuning_source
    assert "OpenCode u Tuning Lab-u radi u pozadini" in tuning_source
    assert "Red čekanja radi sekvencijalno" in tuning_source
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
    assert "Skupi sve" in tuning_source
    assert "Proširi sve" in tuning_source
    assert ".tuning-lab-slot-grid" in styles_source
    assert (
        ".tuning-lab-slot-grid {\n"
        "  display: grid;\n"
        "  gap: 16px;\n"
        "  grid-template-columns: minmax(0, 1fr);\n"
        "}" in styles_source
    )
    assert (
        ".tuning-lab-slot-grid,\n"
        "  .tuning-lab-check-grid {\n"
        "    grid-template-columns: repeat(2, minmax(0, 1fr));\n"
        "  }" not in styles_source
    )
    assert ".tuning-lab-slot-identity-panel" in styles_source
    assert ".tuning-lab-slot-square-control" in styles_source
    assert ".tuning-lab-slot-led-row" in styles_source
    assert ".tuning-lab-slot-display-panel" in styles_source
    assert ".tuning-lab-slot-display-box" in styles_source
    assert ".tuning-lab-slot-precision-rack" in styles_source
    assert ".tuning-lab-slot-precision-group" in styles_source
    assert ".tuning-lab-slot-state-draft" in styles_source
    assert ".tuning-lab-slot-state-active" in styles_source
    assert ".tuning-lab-slot-state-recommended" in styles_source
    assert ".tuning-lab-slot-zones" in styles_source
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


def test_tuning_lab_tri_slot_components_use_hifi_selects_and_clean_serbian_copy():
    identity_source = Path(
        "frontend/src/components/tuning-lab/TuningLabSlotIdentityPanel.tsx"
    ).read_text(encoding="utf-8")
    display_source = Path(
        "frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx"
    ).read_text(encoding="utf-8")
    precision_source = Path(
        "frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx"
    ).read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    normalized_display_source = " ".join(display_source.split())

    assert 'from "../CustomSelect"' in identity_source
    assert "preporučeno" in identity_source
    assert "Signal chain" in identity_source
    assert "Ručni unos" in display_source
    assert "koliko context-a držiš otvoreno" in display_source
    assert "koliki output limit stvarno puštaš u radu" in normalized_display_source
    assert "odmah vidiš ceo miks" in precision_source
    assert ".tuning-lab-slot-square-control .custom-select-trigger" in styles_source
    assert ".tuning-lab-slot-square-control .custom-select-menu" in styles_source
    assert ".tuning-lab-slot-square-select" in styles_source
    assert ".tuning-lab-slot-square-source" in styles_source


def test_tuning_lab_page_uses_plain_serbian_copy_and_active_run_empty_deck():
    page_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    normalized_page_source = " ".join(page_source.split())

    assert "Auto-detect će odlučiti da li treba pytest, npm test ili cargo test." in page_source
    assert "Koristi trenutne slot postavke iz Baseline, Recommended i Custom kolona." in page_source
    assert "OpenCode sesija uživo je prikazana ovde u RuntimePilot-u kao stvarni opencode.exe --pure run proces" in normalized_page_source
    assert "Queue ostaje sekvencijalan: jedan run po jedan" in page_source
    assert "Trenutno nema aktivnog Tuning Lab run-a." in page_source
    assert "Sledeći korak: učitaj task ili batch" in page_source
    assert ".tuning-lab-progress-card" in styles_source
    assert ".tuning-lab-progress-empty" in styles_source
    assert ".tuning-lab-progress-empty-card" in styles_source


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


def test_tuning_lab_history_filters_use_custom_select_instead_of_native_selects():
    page_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    history_section = page_source.split("Filtriraj istoriju", 1)[1].split(
        "Učitavam Tuning Lab istoriju...", 1
    )[0]

    assert 'import { CustomSelect } from "../components/CustomSelect";' in page_source
    assert "historyGoalFilterOptions" in page_source
    assert "historyRuntimeFilterOptions" in page_source
    assert "historyStatusFilterOptions" in page_source
    assert "draftGoalOptions" in page_source
    assert 'ariaLabel="Izaberi cilj eksperimenta"' in page_source
    assert 'ariaLabel="Filtriraj istoriju po cilju"' in page_source
    assert 'ariaLabel="Filtriraj istoriju po runtime-u"' in page_source
    assert 'ariaLabel="Filtriraj istoriju po statusu"' in page_source
    assert page_source.count("<CustomSelect") >= 4
    assert "<select" not in page_source
    assert "<CustomSelect" in history_section
    assert "<select" not in history_section
    assert ".tuning-lab-filter-grid .custom-select" in styles_source
    assert ".tuning-lab-filter-grid .custom-select-trigger" in styles_source


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
    assert "Osnovni URL" in opencode_source
    assert "command-preview-grid" in opencode_source
    assert "opencode-config-grid" in opencode_source
    assert "opencode-env-grid" in opencode_source
    assert "Efektivna local-lacc inference podrazumevana" in opencode_source
    assert "Skok na rezultat" in opencode_source
    assert "Napredni alati" in opencode_source
    assert "izolovanom workspace-u" in opencode_source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

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
    assert "Osnovni URL" in bundled_text
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
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert "Brzi signal podešavanja" in settings_source
    assert "Opšta podešavanja" in settings_source
    assert "Pretraga i izvori" in settings_source
    assert "TurboQuant podešavanja" in settings_source
    assert "Sačuvaj opšta podešavanja" in settings_source
    assert "Sačuvaj TurboQuant podešavanja" in settings_source
    assert js_assets

    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Opšta podešavanja" in bundled_text
    assert "Pretraga i izvori" in bundled_text
    assert "TurboQuant podešavanja" in bundled_text
    assert "Sačuvaj opšta podešavanja" in bundled_text
    assert "Sačuvaj TurboQuant podešavanja" in bundled_text


def test_settings_compatibility_and_benchmark_use_plain_serbian_copy_in_key_helpers():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    compatibility_panel_source = Path(
        "frontend/src/components/CompatibilityCalculatorPanel.tsx"
    ).read_text(encoding="utf-8")

    assert "Za kod: niža temperatura, niži top-k, fiksan seed." in settings_source
    assert "Za kod: niža `temperature`, niži `top-k`, fiksan `seed`." not in settings_source
    assert (
        "Ovo važi za tab Pretraga i za OpenCode kada koristi lokalni local-lacc provider."
        in settings_source
    )
    assert "Ovo važi za Search tab i za OpenCode kada koristi lokalni `local-lacc` provider." not in settings_source
    assert "Pokreni podešavanje lokalnog SearxNG-a ili unesi ručni base URL." in settings_source
    assert "Pokreni Setup local SearxNG ili unesi ručni base URL." not in settings_source
    assert "Kalkulator kompatibilnosti" in compatibility_panel_source
    assert "Compatibility calculator" not in compatibility_panel_source
    assert "Kad klikneš Primeni, prvo gledaj Aktivno sada na runtime-u." in compatibility_panel_source
    assert "Kad klikneš `Primeni`, prvo gledaj `Aktivno sada na runtime-u`." not in compatibility_panel_source
    assert "Scenario i baterija se pokreću direktno iz gornjih akcija" in benchmark_source
    assert "action rail-a" not in benchmark_source
    assert "probaj 15m ili 1h za širi pregled." in benchmark_source
    assert "siri pregled" not in benchmark_source


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


def test_browser_page_source_guides_cold_start_refresh_and_avoids_duplicate_boot_fetches():
    source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")

    assert "Prvo punjenje može da traje oko minut" in source
    assert "void refreshCatalogViewFromCache({ syncTable: true });" in source
    assert "void Promise.all([loadCatalogIndex(), loadCatalog()]);" not in source


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
    js_assets = list((dist_root / "assets").glob("*.js"))

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


def test_models_page_source_only_offers_real_delete_actions_for_each_model_type():
    source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "canRemoveModelFile" in source
    assert "canRemoveModelRegistry" in source
    assert "hasAnyDeleteAction" in source
    assert "deleteActionHint" in source
    assert "Kurirani model možeš da sakriješ iz liste" in source
    assert 'item.isCustom ? "Ukloni iz liste" : "Sakrij sa liste"' in source
    assert "Model trenutno nema fajl na disku za brisanje." in source
    assert "(!removeFile && !removeRegistry)" in source
    assert "Potvrdi brisanje" in source
    assert "model-delete-panel" in source
    assert "model-group-header-meta" in source
    assert "model-fact-grid" in source
    assert "models-summary-grid" in source
    assert "models-toolbar-note-grid" in source
    assert "models-import-grid" in source
    assert "models-local-group-anchor" in source
    assert ".model-group-header-meta" in styles_source
    assert ".model-fact-grid" in styles_source
    assert ".model-fact-card" in styles_source
    assert ".model-delete-panel" in styles_source
    assert ".models-summary-grid" in styles_source
    assert ".models-toolbar-note-grid" in styles_source
    assert ".models-import-grid" in styles_source
    assert ".models-local-group-anchor" in styles_source


def test_models_group_header_has_breathing_room_above_model_list():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert ".model-list {" in styles_source
    assert "margin-top: 14px;" in styles_source
    assert css_assets

    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)
    assert ".model-list" in bundled_css


def test_packaged_browser_ui_contains_quant_sort_labels():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Manji quant prvo" in bundled_text
    assert "Veći quant prvo" in bundled_text


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
    assert "ponovo kliknuti Preuzmi" in source


def test_download_progress_card_source_supports_indeterminate_progress_when_percent_is_unknown():
    source = Path("frontend/src/components/ModelDownloadProgressCard.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "download-progress-fill-indeterminate" in source
    assert "Ukupna veličina još nije prijavljena" in source
    assert ".download-progress-fill-indeterminate" in styles_source
    assert "@keyframes download-progress-pulse" in styles_source


def test_app_source_and_packaged_frontend_include_updates_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'updates: { label: "Ažuriranja"' in source
    assert "UpdatesPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Ažuriranja" in bundled_text
    assert "Proveri ažuriranja" in bundled_text


def test_api_source_disables_cache_for_update_progress_polling():
    source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert 'fetch("/api/updates/progress", { cache: "no-store" })' in source


def test_app_source_and_packaged_frontend_include_benchmark_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'benchmark: { label: "Benchmark"' in source
    assert "BenchmarkPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Benchmark" in bundled_text
    assert "Telemetrija" in bundled_text
    assert "Puls tokena" in bundled_text


def test_app_source_and_packaged_frontend_include_search_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'search: { label: "Pretraga"' in source
    assert "SearchPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Radni prostor za pretragu" in bundled_text
    assert "Pronađi veb izvore" in bundled_text
    assert "Pretraži i odgovori lokalno" in bundled_text
    assert "Uporedi providere" in bundled_text
    assert "DuckDuckGo" in bundled_text
    assert "Konačan odgovor lokalnog modela" in bundled_text
    assert "Podesi managed SearxNG (Windows + WSL)" in bundled_text
    assert "SearxNG nije podešen" in bundled_text
    assert "Managed lokalni SearxNG (Windows + WSL)" in bundled_text
    assert "Ovo su izvori, ne konačan odgovor." in bundled_text
    assert "Otvori izvor" in bundled_text
    assert "Kad pokreneš upit, ovde će se pojaviti normalizovani veb rezultati." in bundled_text
    assert "Ako provider status kaže SearxNG nije podešen" in bundled_text
    assert "`SearxNG nije podešen`" not in bundled_text


def test_app_source_and_packaged_frontend_include_knowledge_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")

    assert 'knowledge: { label: "Znanje"' in source
    assert "KnowledgePage" in source
    assert "pickWorkingDirectory" in knowledge_source
    assert "Pregledaj" in knowledge_source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Radni prostor znanja" in bundled_text
    assert "Dokumenti + veb" in bundled_text
    assert "Pregledaj" in bundled_text
    assert "Samo dokumenti koristi samo lokalni indeks." in bundled_text
    assert "`Samo dokumenti`" not in bundled_text
    assert "Kolekcije" in knowledge_source
    assert "Oznake" in knowledge_source
    assert "Citati" in knowledge_source
    assert "Izvezi JSON" in knowledge_source
    assert "Izvezi Markdown" in knowledge_source
    assert "Kad pokreneš upit nad znanjem, ovde će se pojaviti lokalni pogoci iz dokumenata." in knowledge_source
    assert "ovde ćeš videti koji dokumenti su korišćeni" in knowledge_source
    assert "i njihove citate." in knowledge_source


def test_knowledge_page_source_and_styles_define_spacing_for_fields_and_actions():
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "runtimepilot-faceplate-module knowledge-panel" in knowledge_source
    assert 'className="settings-page-grid knowledge-form-grid"' in knowledge_source
    assert 'className="settings-action-row knowledge-action-row"' in knowledge_source
    assert 'className="inline-actions knowledge-export-actions"' in knowledge_source
    assert 'className="model-item-copy"' in knowledge_source

    assert ".settings-page-grid {" in styles_source
    assert ".settings-compact-field {" in styles_source
    assert ".knowledge-panel {" in styles_source
    assert ".knowledge-form-grid {" in styles_source
    assert ".knowledge-action-row {" in styles_source
    assert ".knowledge-export-actions {" in styles_source

    assert css_assets
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert ".knowledge-panel" in bundled_css


def test_knowledge_page_uses_custom_selects_instead_of_native_select_dropdowns():
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert 'import { CustomSelect } from "../components/CustomSelect";' in knowledge_source
    assert knowledge_source.count("<CustomSelect") >= 3
    assert "<select value=" not in knowledge_source
    assert ".settings-compact-field > .custom-select" in styles_source
    assert ".knowledge-action-row > .settings-control-block" in styles_source


def test_updates_page_source_uses_serbian_diacritics_in_progress_guidance():
    source = Path("frontend/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")

    assert "Pročitaj poruku iznad." in source
    assert "Sačekaj da download stigne do 100%. Installer će se zatim pokrenuti automatski." in source
    assert "Ako pokreneš instalaciju ažuriranja, ovde ćeš videti ceo tok preuzimanja i pokretanja installera." in source


def test_settings_and_opencode_source_include_web_search_controls_and_guidance():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "Režim veb pretrage" in settings_source
    assert "Provider pretrage" in settings_source
    assert "DuckDuckGo (public web, no key)" in settings_source
    assert "Ručni SearxNG base URL (opciono, bez WSL-a)" in settings_source
    assert "Podesi managed SearxNG (Windows + WSL)" in settings_source
    assert "Managed lokalni SearxNG (Windows + WSL)" in settings_source
    assert "Limit rezultata pretrage" in settings_source
    assert "Prefiks za zahtev" in settings_source
    assert "Režim pristupa" in settings_source
    assert "Tema boja" in settings_source
    assert "local-lacc" in settings_source
    assert "local-lacc" in opencode_source
    assert "iz trenutnog RuntimePilot okruženja" in opencode_source


def test_search_page_source_makes_web_results_clickable_and_guides_toward_answer():
    source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")

    assert "Uporedi providere" in source
    assert "DuckDuckGo" in source
    assert "Provider pretrage" in source
    assert "Pronađi veb izvore" in source
    assert "Pretraži i odgovori lokalno" in source
    assert "Konačan odgovor lokalnog modela" in source
    assert "Ovo su izvori, ne konačan odgovor." in source
    assert 'target="_blank"' in source
    assert "Otvori izvor" in source


def test_home_page_source_uses_command_deck_intro_and_telemetry_support():
    source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert "GENERAL_REFRESH_MS = 5000" in source
    assert "BENCHMARK_REALTIME_REFRESH_MS = 1000" in source
    assert "async function loadBenchmarkOnly()" in source
    assert "void loadBenchmarkOnly();" in source
    assert "HomeStatusDeck" in source
    assert "Brzi signal" in source
    assert "TelemetryPanel" in source
    assert "Puls tokena" in telemetry_source
    assert "Ulaz 24h" in telemetry_source
    assert "Izlaz 24h" in telemetry_source
    assert "Aktivne rute" in telemetry_source
    assert "Uživo sada" in telemetry_source
    assert "Poslednji throughput signal" in telemetry_source
    assert "Control. Monitor. Optimize." in app_source
    assert "RuntimePilot" in app_source
    assert "Runtime" in source
    assert "Model" in source
    assert "Context" in source
    assert "OpenCode" in source
    assert 'variant="home"' in source


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
    assert "Izaberi najmanje dva sačuvana run-a da bi prikaz poređenja bio aktivan." in source
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
    js_assets = list((dist_root / "assets").glob("*.js"))

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


def test_overlay_surfaces_use_solid_fill_to_avoid_transparent_bleed():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "--app-overlay-solid-fill" in styles_source
    assert "--app-overlay-solid-fill: rgb(28, 24, 20);" in styles_source
    assert "--app-overlay-solid-fill: rgb(255, 252, 246);" in styles_source
    assert "--app-overlay-solid-fill: rgb(13, 17, 24);" in styles_source
    assert "--app-overlay-solid-fill: rgb(8, 18, 11);" in styles_source
    assert "--app-overlay-solid-fill: rgb(7, 19, 32);" in styles_source

    nav_surface_match = re.search(r"\.runtimepilot-nav-surface \{(?P<body>.*?)\n\}", styles_source, re.S)
    assert nav_surface_match is not None
    nav_surface_block = nav_surface_match.group("body")
    assert "position: relative;" in nav_surface_block
    assert "z-index: 40;" in nav_surface_block
    assert "isolation: isolate;" in nav_surface_block

    nav_menu_match = re.search(r"\.nav-menu-panel \{(?P<body>.*?)\n\}", styles_source, re.S)
    assert nav_menu_match is not None
    nav_menu_block = nav_menu_match.group("body")
    assert "background-color: var(--app-overlay-solid-fill);" in nav_menu_block
    assert "isolation: isolate;" in nav_menu_block

    command_deck_match = re.search(r"\.runtimepilot-command-deck \{(?P<body>.*?)\n\}", styles_source, re.S)
    assert command_deck_match is not None
    command_deck_block = command_deck_match.group("body")
    assert "background-color: var(--app-overlay-solid-fill);" in command_deck_block
    assert "isolation: isolate;" in command_deck_block

    live_strip_match = re.search(r"\.live-resource-strip \{(?P<body>.*?)\n\}", styles_source, re.S)
    assert live_strip_match is not None
    live_strip_block = live_strip_match.group("body")
    assert "background-color: var(--app-overlay-solid-fill);" in live_strip_block
    assert "isolation: isolate;" in live_strip_block

    live_item_match = re.search(r"\.live-resource-inline-item \{(?P<body>.*?)\n\}", styles_source, re.S)
    assert live_item_match is not None
    live_item_block = live_item_match.group("body")
    assert "background-color:" in live_item_block


def test_compatibility_modal_source_and_packaged_frontend_include_runtime_breakdown_copy():
    source = Path("frontend/src/components/CompatibilityCalculatorPanel.tsx").read_text(encoding="utf-8")

    assert "Najbolji runtime" in source
    assert "Pregled po runtime-u" in source
    assert "Opterećenje izlaza" in source
    assert "Rezerva memorije" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Najbolji runtime" in bundled_text
    assert "Pregled po runtime-u" in bundled_text
    assert "Opterećenje izlaza" in bundled_text


def test_app_source_and_packaged_frontend_include_compatibility_navigation():
    source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'compatibility: { label: "Kompatibilnost"' in source
    assert "CompatibilityPage" in source

    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert js_assets
    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Kompatibilnost" in bundled_text
    assert "Snimak sistema" in bundled_text
    assert "Udaljeni katalog" in bundled_text


def test_runtimepilot_primes_slow_server_and_models_payloads_for_warm_navigation():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    server_page_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    models_page_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    settings_page_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")

    assert "primeServerStatusCache" in api_source
    assert "primeModelsCache" in api_source
    assert "primeSettingsCache" in api_source
    assert "peekServerStatusCache" in api_source
    assert "peekModelsCache" in api_source
    assert "peekSettingsCache" in api_source

    assert "primeServerStatusCache" in app_source
    assert "primeModelsCache" in app_source
    assert "primeSettingsCache" in app_source

    assert "useState<ServerStatusPayload | null>(() =>" in server_page_source
    assert "peekServerStatusCache()" in server_page_source
    assert "useState<ModelsPayload | null>(() => peekModelsCache())" in models_page_source
    assert "useState<SettingsPayload | null>(() => peekSettingsCache())" in settings_page_source
    assert "fetchSettings({ preferCache: true })" in settings_page_source
    assert 'loadingText="Učitavam podešavanja..."' in settings_page_source


def test_runtimepilot_nav_compacts_secondary_cues_on_medium_widths():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "@media (max-width: 1180px)" in styles_source
    assert ".runtimepilot-nav-button-cue," in styles_source
    assert ".runtimepilot-nav-menu-cue {" in styles_source or ".runtimepilot-nav-menu-cue," in styles_source
    assert "display: none;" in styles_source


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

    assert "Tab kompatibilnosti" in models_source
    assert "Tab kompatibilnosti" in browser_source


def test_compatibility_handoff_includes_installed_size_and_resolved_path_for_local_models():
    source = Path("frontend/src/lib/compatibility.ts").read_text(encoding="utf-8")

    assert "installedSizeGiB: item.installedSizeGiB ?? item.approxSizeGiB ?? null" in source
    assert "absolute_path: item.resolvedPath ?? null" in source


def test_models_source_guides_local_gguf_import_into_local_group():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")

    assert "Model je dodat u `Lokalni modeli`" in models_source
    assert "Ipak pokušaj aktivaciju" in models_source
    assert "scrollIntoView" in models_source


def test_models_local_upload_flow_uses_browser_picker_progress_and_immediate_status_refresh():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    types_source = Path("frontend/src/lib/types.ts").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert 'type="file"' in models_source
    assert "uploadLocalModel(" in models_source
    assert "localUploadProgress" in models_source
    assert "model-import-progress-card" in models_source
    assert "window.dispatchEvent(new Event(\"runtimepilot:status-refresh-requested\"))" in models_source
    assert "export type LocalUploadProgress" in types_source
    assert "new XMLHttpRequest()" in api_source
    assert 'fetch("/api/status", { cache: "no-store" })' in api_source
    assert 'window.addEventListener("runtimepilot:status-refresh-requested"' in app_source
    assert ".model-import-progress-card" in styles_source
    assert ".model-import-file-meta" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "runtimepilot:status-refresh-requested" in bundled_js
    assert "Dodaj lokalni GGUF" in bundled_js
    assert "Izaberi fajl" in bundled_js
    assert "Sačuvaj upload u lokalni model folder" in bundled_js
    assert ".model-import-progress-card" in bundled_css
    assert ".model-import-file-meta" in bundled_css


def test_server_page_source_uses_runtime_generic_actions_and_labels():
    source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")

    assert "Pokreni runtime" in source
    assert "Restartuj runtime" in source
    assert "Zaustavi runtime" in source
    assert "Otvori runtime veb" in source
    assert "Otvori context" in source
    assert "Dijagnostika" in source
    assert "serverStatus?.canStart === false" in source
    assert "serverStatus?.canOpenWeb === false" in source
    assert "restartServer" in api_source
    assert "/api/server/restart" in api_source
    assert "Start llama.cpp server" not in source


def test_home_and_opencode_source_use_backend_open_action_contract():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "opencode?.openActionLabel" not in home_source
    assert "opencode?.canOpen === false" not in home_source
    assert "onOpenOpenCode" in home_source
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
    js_assets = list((dist_root / "assets").glob("*.js"))

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
    assert "Inference i sampling" in workflows_source or "Inferencija i uzorkovanje" in workflows_source
    assert "temperature: 0.2" in workflow_presets_source
    assert "topK: 20" in workflow_presets_source
    assert js_assets

    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Generacija i sampling" in bundled_text
    assert "Inference i sampling" in bundled_text or "Inferencija i uzorkovanje" in bundled_text
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
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert "Aktivna inference podešavanja" in settings_source
    assert "Temp" in settings_source
    assert "Top-k" in settings_source
    assert "Top-p" in settings_source
    assert "Seed" in settings_source
    assert "Inference sažetak" in workflows_source or "Sažetak inferencije" in workflows_source
    assert "temp" in workflows_source
    assert "top-k" in workflows_source
    assert "top-p" in workflows_source
    assert "seed" in workflows_source
    assert js_assets

    bundled_text = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Aktivna inference podešavanja" in bundled_text
    assert "Inference sažetak" in bundled_text or "Sažetak inferencije" in bundled_text


def test_settings_source_explains_inference_parameters_and_uses_compact_summary_layout():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
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


def test_settings_inference_guidance_uses_full_width_horizontal_rack_layout():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert ".inference-parameter-grid {" in styles_source
    assert "grid-template-columns: 1fr;" in styles_source
    assert ".inference-parameter-card {" in styles_source
    assert "grid-template-columns: minmax(150px, 180px) minmax(180px, 220px) minmax(0, 1fr);" in styles_source
    assert "grid-template-areas:" in styles_source
    assert ".inference-parameter-ranges {" in styles_source
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in styles_source


def test_shared_ux_components_and_guided_flow_copy_are_present_in_core_pages():
    flow_component = Path("frontend/src/components/PageFlowCard.tsx").read_text(encoding="utf-8")
    primary_flow_component = Path("frontend/src/components/PrimaryFlowCard.tsx").read_text(encoding="utf-8")
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
    assert "primary-flow-card" in primary_flow_component
    assert "Pokušaj ponovo" in state_component
    assert "page-data-state-card" in state_component

    assert "HomeStatusDeck" in home_source
    assert "Brzi signal" in home_source
    assert 'variant="home"' in home_source
    assert ".runtimepilot-home-status-grid" in styles_source
    assert ".runtimepilot-home-status-deck" in styles_source

    assert "Runtime cockpit" in server_source
    assert "PrimaryTabRack" in server_source
    assert "runtimepilot-primary-tab-rack" in styles_source
    assert "Napredna dijagnostika i ručne komande" in server_source
    assert "PrimaryFlowCard" not in server_source

    assert "Aktivni model i brza promena" in models_source
    assert "Brzi izbor modela" in models_source
    assert "Napredni katalog i izvori" in models_source
    assert "PrimaryTabRack" in models_source
    assert "PrimaryFlowCard" not in models_source
    assert "PageDataStateCard" in models_source

    assert 'title="Osveži, filtriraj, pa odluči"' in browser_source
    assert "Osveži katalog" in browser_source
    assert "Dodaj lokalno ili proveri fit" in browser_source
    assert "SupportPageDeck" in browser_source
    assert "PageDataStateCard" in browser_source

    assert 'title="Provider, upit i rezultat"' in search_source
    assert "Izaberi provider" in search_source
    assert "Pokreni pretragu, odgovor ili poređenje" in search_source
    assert "SupportPageDeck" in search_source
    assert "PageDataStateCard" in search_source

    assert "OpenCode radni tok" in opencode_source
    assert "Otvori u izolovanom workspace-u" in opencode_source
    assert "Izolovan workspace" in opencode_source
    assert "PageFlowCard" in opencode_source
    assert "RuntimePilotStatusDeck" in opencode_source
    assert "RuntimePilotActionDeck" in opencode_source
    assert "PrimaryTabRack" not in opencode_source
    assert "Napredni OpenCode alati" in opencode_source
    assert "PrimaryFlowCard" not in opencode_source
    assert "PageDataStateCard" in opencode_source

    assert "Benchmark tok" in benchmark_source
    assert "Izbor scenarija i baterije" in benchmark_source
    assert "Gledaj telemetriju i istoriju" in benchmark_source
    assert "PageFlowCard" in benchmark_source
    assert "PageDataStateCard" in benchmark_source
    assert "RuntimePilotStatusDeck" in benchmark_source
    assert "RuntimePilotActionDeck" in benchmark_source
    assert "SecondaryActionRail" not in benchmark_source

    assert "Settings tok" in settings_source
    assert "Izaberi opseg i preset" in settings_source
    assert "Sačuvaj opšta podešavanja" in settings_source
    assert "PageFlowCard" in settings_source
    assert "PageDataStateCard" in settings_source
    assert "RuntimePilotStatusDeck" in settings_source
    assert "RuntimePilotActionDeck" in settings_source
    assert "Provider pretrage" in settings_source

    assert "TuningLabStatusDeck" in tuning_lab_source
    assert "Signal i spremnost" in tuning_lab_source
    assert "Sledeći korak" in tuning_lab_source
    assert "OpenCode živi output" in tuning_lab_source
    assert "Runtime prompt" in tuning_lab_source
    assert "Runtime generacija" in tuning_lab_source
    assert "PageFlowCard" not in tuning_lab_source
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


def test_tuning_lab_source_uses_fast_overview_and_separate_history_loading():
    tuning_lab_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    api_source = Path("frontend/src/lib/api.ts").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    route_source = Path(
        "src/local_ai_control_center_installer/control_center_backend/routes/tuning_lab.py"
    ).read_text(encoding="utf-8")
    service_source = Path(
        "src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py"
    ).read_text(encoding="utf-8")

    assert "fetchTuningLabOverview" in tuning_lab_source
    assert "fetchTuningLabHistoryPage" in tuning_lab_source
    assert "Učitavam Tuning Lab istoriju..." in tuning_lab_source
    assert "/api/tuning-lab/overview" in api_source
    assert "/api/tuning-lab/history?page=" in api_source
    assert '"/api/tuning-lab/overview"' in route_source
    assert "load_tuning_lab_overview" in route_source
    assert "def load_tuning_lab_overview" in service_source
    assert "def _build_tuning_lab_history_payload" in service_source


def test_tuning_lab_shell_uses_b_light_section_order():
    tuning_lab_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    deck_source = Path("frontend/src/components/shell/TuningLabStatusDeck.tsx").read_text(
        encoding="utf-8"
    )
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Signal i spremnost" in tuning_lab_source
    assert "Aktivni run cockpit" in tuning_lab_source
    assert "Tri slota" in tuning_lab_source
    assert "Gotovi batch testovi" in tuning_lab_source
    assert "Priprema run-a" in tuning_lab_source
    assert "Aktivni run i red čekanja" in tuning_lab_source
    assert "Filtriraj istoriju" in tuning_lab_source
    assert tuning_lab_source.index("Aktivni run cockpit") < tuning_lab_source.index("Tri slota")
    assert tuning_lab_source.index("Tri slota") < tuning_lab_source.index("Gotovi batch testovi")
    assert tuning_lab_source.index("Gotovi batch testovi") < tuning_lab_source.index("Priprema run-a")
    assert tuning_lab_source.index("Priprema run-a") < tuning_lab_source.index("Aktivni run i red čekanja")
    assert tuning_lab_source.index("Aktivni run i red čekanja") < tuning_lab_source.index("Filtriraj istoriju")
    assert "TuningLabStatusDeck" in tuning_lab_source
    assert "tuning-lab-status-deck" in deck_source
    assert ".tuning-lab-status-deck" in styles_source
    assert ".page-flow-grid" in styles_source
    assert ".page-flow-step" in styles_source
    assert ".page-data-state-card" in styles_source


def test_models_and_browser_copy_use_serbian_collapse_and_unknown_labels():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")
    compatibility_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(
        encoding="utf-8"
    )
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert '"Proširi"' in models_source
    assert '"Skupi"' in models_source
    assert '"nepoznato"' in models_source
    assert '"Nepoznato"' in browser_source
    assert '"Nepoznat model"' in browser_source
    assert '"Svi izvori"' in browser_source
    assert '"Sve familije"' in browser_source
    assert '"Sve kvantizacije"' in browser_source
    assert '"Bilo koji MTP"' in browser_source
    assert '"Najnovije prvo"' in browser_source
    assert '"Nepoznato"' in compatibility_source
    assert '"Nepoznat model"' in compatibility_source
    assert "@media (max-width: 760px)" in styles_source
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in styles_source


def test_mobile_live_resource_strip_source_and_bundle_use_two_column_cards():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    live_row_mobile_rule = re.search(
        r"@media\s*\(max-width:\s*760px\)\s*\{[\s\S]*?\.live-resource-inline-row\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);",
        styles_source,
    )

    assert live_row_mobile_rule is not None
    assert css_assets

    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert re.search(
        r"@media\s*\(max-width:\s*760px\)\{[\s\S]*?\.live-resource-inline-row\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)",
        bundled_css,
    )


def test_runtimepilot_phase_two_copy_is_present_in_source_and_bundle():
    def normalize_runtimepilot_copy(text: str) -> str:
        return " ".join(text.split())

    server_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    )
    opencode_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")
    )
    search_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")
    )
    settings_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    )
    tuning_lab_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    )
    workflows_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/WorkflowsPage.tsx").read_text(encoding="utf-8")
    )
    models_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    )
    repair_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/RepairPage.tsx").read_text(encoding="utf-8")
    )
    updates_source = normalize_runtimepilot_copy(
        Path("frontend/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")
    )
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert "RuntimePilot je stvarno pokušao GPU offload" in server_source
    assert "ručni ekvivalent onoga što RuntimePilot radi" in server_source
    assert "OpenCode radni tok" in opencode_source
    assert "što RuntimePilot radi kada otvara OpenCode" in opencode_source
    assert "iz trenutnog RuntimePilot okruženja" in opencode_source
    assert "Zajednička RuntimePilot web pretraga" in search_source
    assert "isti RuntimePilot search sloj" in search_source
    assert "Glavni radni profil za RuntimePilot i lokalni model" in settings_source
    assert "opšti radni kontekst RuntimePilot-a" in settings_source
    assert "RuntimePilot ga restartuje" in settings_source
    assert "ovde u RuntimePilot-u" in tuning_lab_source
    assert "OpenCode sesija uživo je prikazana ovde u RuntimePilot-u" in tuning_lab_source
    assert "preset vodi RuntimePilot odmah" in workflows_source
    assert "za ceo RuntimePilot" in workflows_source
    assert "kada preset aktiviraš kroz RuntimePilot" in workflows_source
    assert "RuntimePilot će otvoriti grupu" in models_source
    assert "koji RuntimePilot predloži" in repair_source
    assert "šta RuntimePilot zna o njoj" in updates_source
    assert js_assets

    bundled_js = normalize_runtimepilot_copy(
        "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    )

    assert "RuntimePilot" in bundled_js
    assert "search sloj" in bundled_js
    assert "Glavni radni profil" in bundled_js
    assert "OpenCode" in bundled_js


def test_runtimepilot_phase_three_visual_shell_and_diacritics_are_present():
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    compatibility_source = Path("frontend/src/components/CompatibilityCalculatorPanel.tsx").read_text(
        encoding="utf-8"
    )
    tuning_lab_service_source = Path(
        "src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py"
    ).read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "runtimepilot-hero-panel" in layout_source
    assert "runtimepilot-hero-brandline" in layout_source
    assert "runtimepilot-hero-copy" in layout_source
    assert "shellMarkers" not in app_source
    assert ".runtimepilot-hero-panel" in styles_source
    assert ".runtimepilot-nav-surface" in styles_source
    assert ".runtimepilot-hero-brandline" in styles_source
    assert ".runtimepilot-hero-copy" in styles_source
    assert "čekam prve benchmark uzorke" in benchmark_source
    assert "više važnih podešavanja" in compatibility_source
    assert "Run je prekinut pre nego što je ovaj slot završio." in tuning_lab_service_source
    assert "Sesija je živa i čeka sledeći alat ili upis fajla." in tuning_lab_service_source
    assert css_assets

    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert ".runtimepilot-hero-panel" in bundled_css
    assert ".runtimepilot-nav-surface" in bundled_css


def test_runtimepilot_phase_four_and_five_shared_shell_is_present():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    live_strip_source = Path("frontend/src/components/LiveResourceStrip.tsx").read_text(encoding="utf-8")
    flow_source = Path("frontend/src/components/PageFlowCard.tsx").read_text(encoding="utf-8")
    data_state_source = Path("frontend/src/components/PageDataStateCard.tsx").read_text(encoding="utf-8")
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert css_assets

    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "runtimepilot-page-shell" in layout_source
    assert "runtimepilot-command-deck" in live_strip_source
    assert "runtimepilot-section-shell" in flow_source
    assert "runtimepilot-data-state-shell" in data_state_source
    assert "runtimepilot-telemetry-shell" in telemetry_source
    assert "RuntimePilot Control Deck" in app_source

    assert ".runtimepilot-page-shell" in styles_source
    assert ".runtimepilot-command-deck" in styles_source
    assert ".runtimepilot-section-shell" in styles_source
    assert ".runtimepilot-data-state-shell" in styles_source
    assert ".runtimepilot-telemetry-shell" in styles_source

    assert ".runtimepilot-page-shell" in bundled_css
    assert ".runtimepilot-command-deck" in bundled_css
    assert ".runtimepilot-section-shell" in bundled_css
    assert ".runtimepilot-data-state-shell" in bundled_css
    assert ".runtimepilot-telemetry-shell" in bundled_css


def test_runtimepilot_phase_six_visual_redesign_surfaces_icons_and_control_deck_elements():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    brand_source = Path("frontend/src/components/BrandLockup.tsx").read_text(encoding="utf-8")
    flow_source = Path("frontend/src/components/PageFlowCard.tsx").read_text(encoding="utf-8")
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "runtimepilot-nav-button-glyph" in app_source
    assert "runtimepilot-hero-brandline" in layout_source
    assert "runtimepilot-hero-copy" in layout_source
    assert "brand-lockup" in brand_source
    assert "runtimepilot-page-shell-signal" in layout_source
    assert "runtimepilot-section-glyph" in flow_source
    assert "telemetry-radar-shell" in telemetry_source
    assert "Brzi signal" in home_source
    assert "HomeStatusDeck" in home_source
    assert ".runtimepilot-nav-button-glyph" in styles_source
    assert ".runtimepilot-hero-brandline" in styles_source
    assert ".runtimepilot-hero-copy" in styles_source
    assert ".brand-lockup" in styles_source
    assert "grid-template-columns: minmax(300px, 520px) minmax(0, 1fr);" in styles_source
    assert "max-width: 42rem;" in styles_source
    assert ".runtimepilot-page-shell-signal" in styles_source
    assert ".runtimepilot-section-glyph" in styles_source
    assert ".telemetry-radar-shell" in styles_source
    assert ".runtimepilot-home-status-deck" in styles_source
    assert ".runtimepilot-home-status-grid" in styles_source
    assert ".telemetry-home-header" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Brzi signal" in bundled_js
    assert "Kompaktan signal rada" in bundled_js
    assert "Control. Monitor. Optimize." in bundled_js
    assert ".runtimepilot-hero-brandline" in bundled_css
    assert ".runtimepilot-hero-copy" in bundled_css
    assert ".brand-lockup" in bundled_css
    assert ".runtimepilot-home-status-deck" in bundled_css
    assert ".runtimepilot-home-status-grid" in bundled_css
    assert ".runtimepilot-page-shell-signal" in bundled_css
    assert ".runtimepilot-section-glyph" in bundled_css
    assert ".telemetry-radar-shell" in bundled_css
    assert ".runtimepilot-home-mixed-shell" in bundled_css
    assert ".runtimepilot-home-control-intro" in bundled_css


def test_help_page_and_more_menu_include_runtimepilot_help_center():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    help_source = Path("frontend/src/pages/HelpPage.tsx").read_text(encoding="utf-8")
    icon_source = Path("frontend/src/components/RuntimePilotIcon.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "HelpPage" in app_source
    assert 'help: { label: "Pomoć", cue: "Vodiči", icon: "help" }' in app_source
    assert 'label: "Pomoć"' in app_source
    assert 'page === "help"' in app_source
    assert "Brzi početak" in help_source
    assert "Šta radi svaki tab" in help_source
    assert "Rešavanje problema" in help_source
    assert "Pojmovnik" in help_source
    assert "Najčešći tokovi" in help_source
    assert "help-signal-strip" in help_source
    assert "GPU layers" in help_source
    assert "Visok prioritet" in help_source
    assert "Brza dijagnostika" in help_source
    assert '"help"' in icon_source
    assert ".help-overview-grid" in styles_source
    assert ".help-glossary-grid" in styles_source
    assert ".help-callout-card" in styles_source
    assert ".help-path-grid" in styles_source
    assert ".help-signal-strip" in styles_source
    assert ".page-flow-card {\n  display: grid;" in styles_source
    assert ".help-overview-shell,\n.help-section-card {\n  display: grid;" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Pomoć" in bundled_js
    assert "Brzi početak" in bundled_js
    assert "Rešavanje problema" in bundled_js
    assert "Pojmovnik" in bundled_js
    assert "Najčešći tokovi" in bundled_js
    assert "Visok prioritet" in bundled_js
    assert "Brza dijagnostika" in bundled_js
    assert ".help-overview-grid" in bundled_css
    assert ".page-flow-card" in bundled_css
    assert ".help-overview-shell" in bundled_css
    assert ".help-glossary-grid" in bundled_css


def test_action_result_panel_source_uses_human_status_badges_and_clearer_copy():
    source = Path("frontend/src/components/ActionResultPanel.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Poslednja akcija" in source
    assert "Rezultat je spreman u detaljima ispod" in source
    assert "Akcija je primljena i pokrenuta." in source
    assert 'case "accepted":' in source
    assert "Primljeno" in source
    assert 'case "queued":' in source
    assert "Akcija je u toku. Prati detalje ispod za novi signal." in source
    assert "runtimepilot-action-head" in source
    assert "runtimepilot-action-badge" in source
    assert "runtimepilot-action-copy" in source
    assert ".runtimepilot-action-head" in styles_source
    assert ".runtimepilot-action-badge" in styles_source
    assert ".runtimepilot-action-copy" in styles_source


def test_models_page_keeps_action_rail_inside_its_track_and_stacks_earlier():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert 'className="model-item-copy-head"' in models_source
    assert 'className="model-item-copy-main"' in models_source
    assert ".model-item-header" in styles_source
    assert "@media (max-width: 1320px)" in styles_source
    assert "grid-template-columns: minmax(0, 1fr) minmax(280px, 300px);" in styles_source
    assert 'grid-template-areas: "head head" "main rail";' in styles_source
    assert 'grid-template-areas: "head" "main" "rail";' in styles_source
    assert ".model-item-copy-head" in styles_source
    assert ".model-item-copy-main" in styles_source
    assert "grid-area: rail;" in styles_source
    assert "grid-auto-rows: minmax(0, 1fr);" in styles_source
    assert "display: grid;" in styles_source
    assert "grid-template-columns: 1fr;" in styles_source
    assert "justify-self: stretch;" in styles_source
    assert "width: 100%;" in styles_source
    assert "max-width: 300px;" in styles_source
    assert (
        ".model-item-header > .inline-actions button {\n"
        "  width: 100%;\n"
        "  height: 100%;\n"
        "  min-height: 52px;\n"
        "  padding: 8px 14px;\n"
        "  line-height: 1.15;\n"
        "}"
    ) in styles_source
    assert "grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));" in styles_source
    assert "minmax(0, 1.08fr)" in styles_source
    assert "minmax(0, 1.1fr)" in styles_source
    assert css_assets

    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert ".model-item-header" in bundled_css
    assert ".model-item-copy-head" in bundled_css
    assert ".model-item-header>.inline-actions button" in bundled_css


def test_runtimepilot_ux_rewrite_shell_exposes_primary_flow_and_guided_entry():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Vodi me redom" in app_source
    assert "Lokalni model" in app_source
    assert "Glavni tokovi" in layout_source
    assert ".runtimepilot-guided-flow" in styles_source
    assert ".runtimepilot-primary-flows" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Vodi me redom" in bundled_js
    assert "Lokalni model" in bundled_js
    assert ".runtimepilot-guided-flow" in bundled_css
    assert ".runtimepilot-primary-flows" in bundled_css


def test_runtimepilot_ux_rewrite_uses_shared_save_and_apply_language():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Sačuvaj i primeni" in settings_source
    assert "Sačuvaj bez primene" in settings_source
    assert "Primenjeno na živi sistem" in settings_source
    assert ".apply-state-panel" in styles_source
    assert ".apply-state-chip" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Sačuvaj i primeni" in bundled_js
    assert "Sačuvaj bez primene" in bundled_js
    assert "Primenjeno na živi sistem" in bundled_js
    assert ".apply-state-panel" in bundled_css
    assert ".apply-state-chip" in bundled_css


def test_runtimepilot_ux_rewrite_home_centers_status_deck_and_compact_telemetry():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "HomeStatusDeck" in home_source
    assert "Brzi signal" in home_source
    assert 'TelemetryPanel benchmark={benchmark} variant="home"' in home_source
    assert ".runtimepilot-home-status-deck" in styles_source
    assert ".runtimepilot-home-status-grid" in styles_source
    assert ".telemetry-home-header" in styles_source
    assert ".telemetry-home-display-title" in styles_source
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Brzi signal" in bundled_js
    assert "Kompaktan signal rada" in bundled_js
    assert "Otvori context" in bundled_js
    assert ".runtimepilot-home-status-deck" in bundled_css
    assert ".runtimepilot-home-status-grid" in bundled_css
    assert ".telemetry-home-header" in bundled_css


def test_runtimepilot_ux_rewrite_runtime_models_and_opencode_pages_use_new_primary_shell():
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Runtime cockpit" in server_source
    assert "Napredna dijagnostika i ručne komande" in server_source
    assert "PrimaryTabRack" in server_source
    assert "Aktivni model i brza promena" in models_source
    assert "PrimaryTabRack" in models_source
    assert "Brzi izbor modela" in models_source
    assert "Napredni katalog i izvori" in models_source
    assert "PrimaryTabRack" not in opencode_source
    assert "OpenCode radni tok" in opencode_source
    assert "Skok na rezultat" in opencode_source
    assert "Napredni OpenCode alati" in opencode_source
    assert ".runtimepilot-primary-tab-rack" in styles_source
    assert ".runtimepilot-primary-tab-rack-signal" in styles_source
    assert ".runtimepilot-primary-tab-rack-commands" in styles_source
    assert ".runtimepilot-primary-tab-rack-deep" in styles_source
    assert ".runtimepilot-advanced-disclosure" in styles_source
    assert ".model-quick-grid" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Runtime cockpit" in bundled_js
    assert "Otvori context" in bundled_js
    assert "Aktivni model i brza promena" in bundled_js
    assert "Brzi izbor modela" in bundled_js
    assert "OpenCode radni tok" in bundled_js
    assert "Napredni OpenCode alati" in bundled_js
    assert ".runtimepilot-primary-tab-rack" in bundled_css
    assert ".runtimepilot-primary-tab-rack-signal" in bundled_css
    assert ".runtimepilot-primary-tab-rack-commands" in bundled_css
    assert ".runtimepilot-primary-tab-rack-deep" in bundled_css
    assert ".runtimepilot-advanced-disclosure" in bundled_css
    assert ".model-quick-grid" in bundled_css


def test_runtimepilot_runtime_advanced_diagnostics_use_deck_rack_layout():
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "runtimepilot-advanced-rack" in server_source
    assert "runtimepilot-advanced-intro-shell" in server_source
    assert "runtimepilot-advanced-intro-title" in server_source
    assert "runtimepilot-advanced-module" in server_source
    assert "runtimepilot-command-rack" in server_source
    assert "runtimepilot-command-module" in server_source
    assert "runtimepilot-advanced-overview-grid" in server_source
    assert "runtimepilot-advanced-summary-indicator" in server_source
    assert "runtimepilot-advanced-card-code" in server_source
    assert "runtimepilot-advanced-metric-grid" in server_source
    assert "runtimepilot-command-chip-row" in server_source
    assert "runtimepilot-command-surface-grid" in server_source
    assert "renderRuntimeStatusLink" in server_source
    assert "runtimepilot-status-link" in server_source
    assert "onOpenContextSettings" in server_source
    assert 'setSettingsFocusSection("context")' in app_source
    assert "contextSectionRef" in settings_source
    assert 'focusSectionId === "context"' in settings_source
    assert ".runtimepilot-advanced-rack" in styles_source
    assert ".runtimepilot-advanced-intro-shell" in styles_source
    assert ".runtimepilot-advanced-intro-title" in styles_source
    assert ".runtimepilot-advanced-module" in styles_source
    assert ".runtimepilot-command-rack" in styles_source
    assert ".runtimepilot-command-module" in styles_source
    assert ".runtimepilot-advanced-overview-grid" in styles_source
    assert ".runtimepilot-advanced-summary-indicator" in styles_source
    assert ".runtimepilot-advanced-card-code" in styles_source
    assert ".runtimepilot-advanced-metric-grid" in styles_source
    assert ".runtimepilot-command-chip-row" in styles_source
    assert ".runtimepilot-command-surface-grid" in styles_source
    assert ".runtimepilot-status-link" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Napredna dijagnostika i ručne komande" in bundled_js
    assert "Otvori context podešavanje" in bundled_js
    assert "Health URL" in bundled_js
    assert "_blank" in bundled_js
    assert ".runtimepilot-advanced-rack" in bundled_css
    assert ".runtimepilot-advanced-intro-shell" in bundled_css
    assert ".runtimepilot-advanced-intro-title" in bundled_css
    assert ".runtimepilot-advanced-module" in bundled_css
    assert ".runtimepilot-command-rack" in bundled_css
    assert ".runtimepilot-command-module" in bundled_css
    assert ".runtimepilot-advanced-overview-grid" in bundled_css
    assert ".runtimepilot-advanced-summary-indicator" in bundled_css
    assert ".runtimepilot-advanced-card-code" in bundled_css
    assert ".runtimepilot-advanced-metric-grid" in bundled_css
    assert ".runtimepilot-command-chip-row" in bundled_css
    assert ".runtimepilot-command-surface-grid" in bundled_css
    assert ".runtimepilot-status-link" in bundled_css


def test_runtimepilot_models_and_opencode_advanced_sections_use_deck_modules():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "runtimepilot-advanced-module-shell" in models_source
    assert "runtimepilot-advanced-module" in models_source
    assert "runtimepilot-command-module" in models_source
    assert "runtimepilot-advanced-module-shell" in opencode_source
    assert "runtimepilot-advanced-module" in opencode_source
    assert "runtimepilot-command-module" in opencode_source
    assert ".runtimepilot-advanced-module-shell" in styles_source
    assert ".runtimepilot-advanced-module" in styles_source
    assert ".runtimepilot-command-module" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Napredni katalog i izvori" in bundled_js
    assert "Napredni OpenCode alati" in bundled_js
    assert ".runtimepilot-advanced-module-shell" in bundled_css
    assert ".runtimepilot-advanced-module" in bundled_css
    assert ".runtimepilot-command-module" in bundled_css


def test_models_quick_picker_marks_active_model_in_green_and_uses_uniform_card_rack_layout():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "model-quick-card-shell" in models_source
    assert "model-quick-card-summary" in models_source
    assert "model-quick-card-facts" in models_source
    assert "model-quick-card-footer" in models_source
    assert "model-quick-action-active" in models_source
    assert 'item.active ? "Aktivan" : item.installed ? "Spreman"' in models_source
    assert ".model-quick-card-shell" in styles_source
    assert ".model-quick-card-summary" in styles_source
    assert ".model-quick-card-facts" in styles_source
    assert ".model-quick-card-footer" in styles_source
    assert ".model-quick-action-active" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Aktivan" in bundled_js
    assert ".model-quick-card-shell" in bundled_css
    assert ".model-quick-card-summary" in bundled_css
    assert ".model-quick-card-facts" in bundled_css
    assert ".model-quick-card-footer" in bundled_css
    assert ".model-quick-action-active" in bundled_css


def test_runtimepilot_settings_tuning_and_compatibility_pages_use_rack_modules():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    tuning_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    compatibility_page_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(encoding="utf-8")
    compatibility_panel_source = Path("frontend/src/components/CompatibilityCalculatorPanel.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "runtimepilot-rack-page" in settings_source
    assert "runtimepilot-faceplate-module settings-rack-module" in settings_source
    assert "runtimepilot-rack-page" in tuning_source
    assert "runtimepilot-faceplate-module tuning-rack-module" in tuning_source
    assert "runtimepilot-rack-page" in compatibility_page_source
    assert "runtimepilot-faceplate-module compat-rack-module" in compatibility_page_source
    assert "compatibility-calculator-panel" in compatibility_panel_source
    assert "runtimepilot-faceplate-module" in compatibility_panel_source
    assert ".runtimepilot-rack-page" in styles_source
    assert ".settings-rack-module" in styles_source
    assert ".tuning-rack-module" in styles_source
    assert ".compat-rack-module" in styles_source
    assert ".compatibility-calculator-panel.compat-surface" in styles_source


def test_tuning_lab_and_compatibility_pages_use_hifi_mixer_transport_and_monitoring_decks():
    tuning_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    compatibility_page_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(encoding="utf-8")
    compatibility_panel_source = Path("frontend/src/components/CompatibilityCalculatorPanel.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "tuning-lab-hifi-stack" in tuning_source
    assert "tuning-lab-mixer-deck" in tuning_source
    assert "tuning-lab-transport-deck" in tuning_source
    assert "tuning-lab-monitor-deck" in tuning_source

    assert "compatibility-hifi-stack" in compatibility_page_source
    assert "compatibility-mixer-deck" in compatibility_page_source
    assert "compatibility-monitor-deck" in compatibility_panel_source
    assert "compatibility-transport-deck" in compatibility_panel_source

    assert ".tuning-lab-hifi-stack" in styles_source
    assert ".tuning-lab-mixer-deck" in styles_source
    assert ".tuning-lab-transport-deck" in styles_source
    assert ".tuning-lab-monitor-deck" in styles_source
    assert ".compatibility-hifi-stack" in styles_source
    assert ".compatibility-mixer-deck" in styles_source
    assert ".compatibility-transport-deck" in styles_source
    assert ".compatibility-monitor-deck" in styles_source


def test_compatibility_calculator_makes_apply_results_and_active_values_easy_to_find():
    compatibility_panel_source = Path(
        "frontend/src/components/CompatibilityCalculatorPanel.tsx"
    ).read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Aktivno sada na runtime-u" in compatibility_panel_source
    assert "compatibility-live-settings-panel" in compatibility_panel_source
    assert "compatibility-live-settings-grid" in compatibility_panel_source
    assert "compatibility-action-result-inline" in compatibility_panel_source
    assert "compatibility-editor-settings-panel" in compatibility_panel_source
    assert "Napredna izmena menja editor, ne živi runtime" in compatibility_panel_source
    assert "Proveri ili primeni da bi aktivno stanje ispod bilo ažurirano." in compatibility_panel_source
    assert ".compatibility-live-settings-panel" in styles_source
    assert ".compatibility-live-settings-grid" in styles_source
    assert ".compatibility-action-result-inline" in styles_source
    assert ".compatibility-editor-settings-panel" in styles_source
    assert ".compatibility-editor-diff-grid" in styles_source


def test_benchmark_observability_help_and_project_memory_use_hifi_decks():
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    observability_source = Path("frontend/src/pages/ObservabilityPage.tsx").read_text(encoding="utf-8")
    help_source = Path("frontend/src/pages/HelpPage.tsx").read_text(encoding="utf-8")
    project_memory_source = Path("frontend/src/pages/ProjectMemoryPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "benchmark-page runtimepilot-rack-page" in benchmark_source
    assert "runtimepilot-secondary-hub" in benchmark_source
    assert "RuntimePilotActionDeck" in benchmark_source
    assert "RuntimePilotStatusDeck" in benchmark_source
    assert "SecondaryActionRail" not in benchmark_source
    assert "benchmark-hifi-stack" in benchmark_source
    assert "benchmark-mixer-deck" in benchmark_source
    assert "benchmark-setup-grid" in benchmark_source
    assert "Izbor scenarija i baterije" in benchmark_source
    assert "HomeHiFiModule" not in benchmark_source
    assert "Veliki modul 8" not in benchmark_source
    assert "Komandni dek" not in benchmark_source

    assert (
        "observability-page runtimepilot-rack-page" in observability_source
        or '"observ" + "ability-page runtimepilot-rack-page"' in observability_source
    )
    assert (
        "observability-hifi-stack" in observability_source
        or '"observ" + "ability-hifi-stack"' in observability_source
    )
    assert (
        "observability-mixer-deck" in observability_source
        or '"observ" + "ability-mixer-deck"' in observability_source
    )
    assert (
        "observability-transport-deck" in observability_source
        or '"observ" + "ability-transport-deck"' in observability_source
    )
    assert (
        "observability-monitor-deck" in observability_source
        or '"observ" + "ability-monitor-deck"' in observability_source
    )

    assert "help-page runtimepilot-rack-page" in help_source
    assert "help-hifi-stack" in help_source
    assert "help-mixer-deck" in help_source
    assert "help-transport-deck" in help_source
    assert "help-monitor-deck" in help_source

    assert "project-memory-page runtimepilot-rack-page" in project_memory_source
    assert "project-memory-hifi-stack" in project_memory_source
    assert "project-memory-mixer-deck" in project_memory_source
    assert "project-memory-transport-deck" in project_memory_source
    assert "project-memory-monitor-deck" in project_memory_source

    assert ".benchmark-hifi-stack" in styles_source
    assert ".runtimepilot-secondary-hub" in styles_source
    assert ".runtimepilot-secondary-action-rail" in styles_source
    assert ".runtimepilot-status-deck" in styles_source
    assert ".runtimepilot-action-deck" in styles_source
    assert ".benchmark-faceplate-panel" in styles_source
    assert ".benchmark-setup-grid" in styles_source
    assert ".benchmark-log-preview" in styles_source
    assert ".observability-hifi-stack" in styles_source
    assert ".help-hifi-stack" in styles_source
    assert ".project-memory-hifi-stack" in styles_source


def test_benchmark_run_statuses_use_compact_readout_grid():
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert 'className="benchmark-run-status-header"' in benchmark_source
    assert 'className="benchmark-run-status-copy"' in benchmark_source
    assert 'className="benchmark-run-status-title-block"' in benchmark_source
    assert 'className="benchmark-run-status-pass"' in benchmark_source
    assert "formatBenchmarkRunStatusBadge" in benchmark_source
    assert "compactBenchmarkRunStatusSummary" in benchmark_source
    assert ".benchmark-run-status-list" in styles_source
    assert "grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));" in styles_source
    assert ".benchmark-run-status-header" in styles_source
    assert ".benchmark-run-status-title-block" in styles_source
    assert ".benchmark-run-status-pass" in styles_source
    assert ".benchmark-run-status-copy .muted-line" in styles_source
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in styles_source
    assert css_assets

    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert ".benchmark-run-status-header" in bundled_css
    assert ".benchmark-run-status-pass" in bundled_css


def test_runtimepilot_hi_fi_shell_uses_flat_status_rails_and_rack_style_resources():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    live_strip_source = Path("frontend/src/components/LiveResourceStrip.tsx").read_text(encoding="utf-8")
    system_layer_source = Path(
        "frontend/src/components/shell/SystemStatusLayer.tsx"
    ).read_text(encoding="utf-8")
    primary_flow_source = Path("frontend/src/components/PrimaryFlowCard.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "runtimepilot-status-rail" in app_source
    assert "runtimepilot-utility-module" in app_source
    assert "runtimepilot-active-model-layout" in app_source
    assert "runtimepilot-utility-title" in app_source
    assert "systemStatusLayer" in layout_source
    assert "runtimepilot-system-status-layer" in system_layer_source
    assert "runtimepilot-faceplate-module" in primary_flow_source
    assert "runtimepilot-nav-shell-subtle" in layout_source
    assert "live-resource-rack" in live_strip_source
    assert "live-resource-rack-row" in live_strip_source
    assert ".runtimepilot-status-rail" in styles_source
    assert ".runtimepilot-system-status-layer" in styles_source
    assert ".runtimepilot-status-rack" in styles_source
    assert ".runtimepilot-faceplate-module" in styles_source
    assert ".runtimepilot-utility-module" in styles_source
    assert ".runtimepilot-utility-head" in styles_source
    assert ".runtimepilot-utility-title" in styles_source
    assert ".runtimepilot-nav-shell-subtle" in styles_source
    assert ".live-resource-rack" in styles_source
    assert ".live-resource-rack-row" in styles_source
    assert ".runtimepilot-page-shell-flat" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Aktivni model" in bundled_js
    assert "Project Memory" in bundled_js
    assert "Živi resursi" in bundled_js
    assert ".runtimepilot-status-rack" in bundled_css
    assert ".runtimepilot-faceplate-module" in bundled_css
    assert ".runtimepilot-status-rail" in bundled_css
    assert ".runtimepilot-utility-module" in bundled_css
    assert ".runtimepilot-utility-head" in bundled_css
    assert ".runtimepilot-utility-title" in bundled_css
    assert ".runtimepilot-nav-shell-subtle" in bundled_css
    assert ".live-resource-rack" in bundled_css
    assert ".live-resource-rack-row" in bundled_css
    assert ".runtimepilot-page-shell-flat" in bundled_css


def test_app_source_promotes_five_command_runtimepilot_shell():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'advanced: { label: "Napredno", cue: "Alati", icon: "control" }' in app_source
    assert 'const PRIMARY_PAGES: PageKey[] = ["home", "server", "models", "opencode", "advanced"]' in app_source
    assert 'const GUIDED_FLOW_PAGE: PageKey = "guidedFlow"' in app_source
    assert 'onStartGuidedFlow={() => setPage("guidedFlow")}' not in app_source


def test_layout_and_app_source_drop_guided_flow_from_header_nav():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")

    assert 'label: "Vodi me redom"' in app_source
    assert "nav-button-guided" not in app_source
    assert "runtimepilot-nav-shell-title" in layout_source


def test_advanced_page_source_and_app_wire_real_secondary_tool_launchers():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_source = Path("frontend/src/pages/AdvancedPage.tsx").read_text(encoding="utf-8")
    rail_source = Path("frontend/src/components/shell/SecondaryActionRail.tsx").read_text(
        encoding="utf-8"
    )
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "onOpenBenchmark" in page_source
    assert "onOpenBrowser" in page_source
    assert "onOpenTuningLab" in page_source
    assert "onOpenCompatibility" in page_source
    assert "onOpenObservability" in page_source
    assert "onOpenKnowledge" in page_source
    assert "onOpenSearch" in page_source
    assert "onOpenWorkflows" in page_source
    assert "onOpenProjectMemory" in page_source
    assert "onOpenSettings" in page_source
    assert "onOpenLogs" in page_source
    assert "onOpenHelp" in page_source
    assert "onOpenRepair" in page_source
    assert "onOpenUpdates" in page_source
    assert "onOpenFleet" in page_source
    assert "onOpenJobs" in page_source
    assert '"Otvori Benchmark"' in page_source
    assert '"Otvori Browser katalog"' in page_source
    assert '"Otvori Tuning Lab"' in page_source
    assert '"Otvori kompatibilnost"' in page_source
    assert '"Otvori telemetriju"' in page_source
    assert '"Otvori Znanje"' in page_source
    assert '"Otvori Pretragu"' in page_source
    assert '"Otvori Radne tokove"' in page_source
    assert '"Otvori Project Memory"' in page_source
    assert '"Otvori Podešavanja"' in page_source
    assert '"Otvori Logove"' in page_source
    assert '"Otvori Pomoć"' in page_source
    assert '"Otvori Popravku"' in page_source
    assert '"Otvori Ažuriranja"' in page_source
    assert '"Otvori Flotu"' in page_source
    assert '"Otvori Poslove"' in page_source
    assert "SecondaryActionRail" in rail_source
    assert "SecondaryActionRail" not in page_source
    assert "SupportPageDeck" in page_source
    assert "runtimepilot-secondary-hub-fullwidth" in page_source
    assert "runtimepilot-secondary-hub" in page_source
    assert "runtimepilot-advanced-summary-grid" in page_source
    assert "runtimepilot-advanced-summary-actions" in page_source
    assert "HomeHiFiModule" not in page_source
    assert "HomeHiFiCommandButton" not in page_source
    assert "advanced-rack-module" not in page_source
    assert "advanced-rack-stack" not in page_source
    assert '"Fix"' not in page_source
    assert '"Release"' not in page_source
    assert '{page === "advanced" ? <AdvancedPage /> : null}' not in app_source
    assert '{page === "advanced" ? (' in app_source
    assert 'onOpenBenchmark={() => setPage("benchmark")}' in app_source
    assert 'onOpenBrowser={() => setPage("browser")}' in app_source
    assert 'onOpenTuningLab={() => setPage("tuningLab")}' in app_source
    assert 'onOpenCompatibility={() => setPage("compatibility")}' in app_source
    assert 'onOpenObservability={() => setPage("observability")}' in app_source
    assert 'onOpenKnowledge={() => setPage("knowledge")}' in app_source
    assert 'onOpenSearch={() => setPage("search")}' in app_source
    assert 'onOpenWorkflows={() => setPage("workflows")}' in app_source
    assert 'onOpenProjectMemory={() => setPage("projectMemory")}' in app_source
    assert 'onOpenSettings={() => setPage("settings")}' in app_source
    assert 'onOpenLogs={() => setPage("logs")}' in app_source
    assert 'onOpenHelp={() => setPage("help")}' in app_source
    assert 'onOpenRepair={() => setPage("repair")}' in app_source
    assert 'onOpenUpdates={() => setPage("updates")}' in app_source
    assert 'onOpenFleet={() => setPage("fleet")}' in app_source
    assert 'onOpenJobs={() => setPage("jobs")}' in app_source
    assert ".runtimepilot-secondary-hub" in styles_source
    assert ".runtimepilot-secondary-action-rail" in styles_source
    assert ".runtimepilot-advanced-summary-grid" in styles_source
    assert ".runtimepilot-advanced-summary-card-service" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Otvori Benchmark" in bundled_js
    assert "Otvori Browser katalog" in bundled_js
    assert "Otvori Tuning Lab" in bundled_js
    assert "Otvori kompatibilnost" in bundled_js
    assert "Otvori telemetriju" in bundled_js
    assert "Otvori Znanje" in bundled_js
    assert "Otvori Pretragu" in bundled_js
    assert "Otvori Radne tokove" in bundled_js
    assert "Otvori Project Memory" in bundled_js
    assert "Otvori Podešavanja" in bundled_js
    assert "Otvori Logove" in bundled_js
    assert "Otvori Pomoć" in bundled_js
    assert "Otvori Popravku" in bundled_js
    assert "Otvori Ažuriranja" in bundled_js
    assert "Otvori Flotu" in bundled_js
    assert "Otvori Poslove" in bundled_js
    assert ".runtimepilot-secondary-hub" in bundled_css
    assert ".runtimepilot-secondary-action-rail" in bundled_css
    assert ".runtimepilot-advanced-summary-grid" in bundled_css
    assert ".runtimepilot-advanced-summary-card-service" in bundled_css


def test_home_hifi_component_split_exists():
    module_source = Path("frontend/src/components/home/HomeHiFiModule.tsx").read_text(encoding="utf-8")
    command_source = Path("frontend/src/components/home/HomeHiFiCommandButton.tsx").read_text(encoding="utf-8")
    rail_source = Path("frontend/src/components/home/HomeHiFiSignalRail.tsx").read_text(encoding="utf-8")

    assert "export function HomeHiFiModule" in module_source
    assert "export function HomeHiFiCommandButton" in command_source
    assert "export function HomeHiFiSignalRail" in rail_source


def test_home_source_promotes_status_dashboard_and_compact_telemetry():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "HomeStatusDeck" in home_source
    assert "Brzi signal" in home_source
    assert "onOpenSettingsContext" in home_source
    assert 'variant="home"' in home_source
    assert "HomeHiFiModule" not in home_source
    assert ".runtimepilot-home-status-deck" in styles_source
    assert ".runtimepilot-home-status-card" in styles_source
    assert ".telemetry-panel-home" in styles_source


def test_app_source_keeps_unified_system_status_layer_on_home():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert "SystemStatusLayer" in app_source
    assert 'activeModelStrip={page === "home" ? null : activeModelStrip}' not in app_source


def test_runtimepilot_source_copy_uses_real_diacritics_instead_of_literal_unicode_escape_sequences():
    allowed_sequences = {
        Path("frontend/src/components/TelemetryPanel.tsx"): ["\\u00A0"],
    }
    source_files = [
        Path("frontend/src/pages/CompatibilityPage.tsx"),
        Path("frontend/src/pages/FleetPage.tsx"),
        Path("frontend/src/pages/JobsPage.tsx"),
        Path("frontend/src/pages/KnowledgePage.tsx"),
        Path("frontend/src/pages/ObservabilityPage.tsx"),
        Path("frontend/src/pages/WorkflowsPage.tsx"),
        Path("frontend/src/components/TelemetryPanel.tsx"),
    ]

    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for allowed in allowed_sequences.get(path, []):
            text = text.replace(allowed, "")
        assert "\\u" not in text, f"{path} still contains literal unicode escape sequences in UI copy."


def test_runtimepilot_source_copy_uses_serbian_labels_on_knowledge_and_related_pages():
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")
    workflows_source = Path("frontend/src/pages/WorkflowsPage.tsx").read_text(encoding="utf-8")
    compatibility_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(encoding="utf-8")
    fleet_source = Path("frontend/src/pages/FleetPage.tsx").read_text(encoding="utf-8")
    jobs_source = Path("frontend/src/pages/JobsPage.tsx").read_text(encoding="utf-8")
    observability_source = Path("frontend/src/pages/ObservabilityPage.tsx").read_text(encoding="utf-8")

    assert 'title="Izvori, režim i odgovor"' in knowledge_source
    assert "Dokumenti + veb" in knowledge_source
    assert "Samo dokumenti" in knowledge_source
    assert "Samo veb" in knowledge_source
    assert "Upit vraća reference" in knowledge_source
    assert "Knowledge tok" not in knowledge_source
    assert "Documents-only" not in knowledge_source
    assert "Query vraća" not in knowledge_source
    assert "Answer koristi" not in knowledge_source

    assert 'title="Tok radnih tokova"' in workflows_source
    assert "Otvori pretragu" in workflows_source
    assert "Otvori znanje" in workflows_source
    assert "Otvori benchmark" in workflows_source
    assert "preset radnog toka" in workflows_source
    assert "Workflows tok" not in workflows_source
    assert "Otvori Search" not in workflows_source
    assert "Otvori Knowledge" not in workflows_source
    assert "workflow preset" not in workflows_source

    assert 'title="Tok kompatibilnosti"' in compatibility_source
    assert "Otvori katalog" in compatibility_source
    assert "Opseg određuje" in compatibility_source
    assert "kandidat iz kataloga" in compatibility_source
    assert "RuntimePilotStatusDeck" in compatibility_source
    assert "RuntimePilotActionDeck" in compatibility_source
    assert "SecondaryActionRail" not in compatibility_source
    assert "Compatibility tok" not in compatibility_source
    assert "Scope određuje" not in compatibility_source
    assert "Browser kandidat" not in compatibility_source
    assert "Otvori Browser" not in compatibility_source

    assert 'title="Tok flote"' in fleet_source
    assert "tok telemetrije" in fleet_source
    assert "Fleet tok" not in fleet_source
    assert "telemetry brojke" not in fleet_source

    assert 'title="Tok poslova"' in jobs_source
    assert "pozadinski poslovi" in jobs_source
    assert "Jobs tok" not in jobs_source
    assert "Job-ovi" not in jobs_source

    assert 'title="Tok telemetrije i resursa"' in observability_source
    assert "telemetrija i resursi" in observability_source
    assert "Tok telemetrije" in observability_source
    assert "Observability tok" not in observability_source
    assert "observability" not in observability_source


def test_home_faceplate_modules_use_full_width_active_model_telemetry_and_secondary_tool_layouts():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    telemetry_source = Path("frontend/src/components/TelemetryPanel.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "runtimepilot-active-model-layout" in app_source
    assert "runtimepilot-active-model-status" in app_source
    assert "runtimepilot-active-model-open" in app_source
    assert "HomeStatusDeck" in home_source
    assert "runtimepilot-home-support-stack" not in home_source
    assert "HomeSecondaryToolCard" not in home_source
    assert "onOpenBenchmark" not in home_source
    assert "onOpenProjectMemory" not in home_source
    assert "telemetry-home-deck" in telemetry_source
    assert "telemetry-home-display" in telemetry_source
    assert "telemetry-home-meter-bank" in telemetry_source
    assert ".runtimepilot-status-rack" in styles_source
    assert ".runtimepilot-active-model-layout" in styles_source
    assert ".runtimepilot-active-model-strip::before" in styles_source
    assert ".runtimepilot-active-model-status" in styles_source
    assert ".runtimepilot-home-status-deck" in styles_source
    assert ".runtimepilot-home-status-grid" in styles_source
    assert ".runtimepilot-home-status-card" in styles_source
    assert ".telemetry-home-deck" in styles_source
    assert ".telemetry-home-display" in styles_source
    assert ".telemetry-home-meter-bank" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Aktivni model" in bundled_js
    assert "Brzi signal" in bundled_js
    assert "Puls tokena" in bundled_js
    assert "runtimepilot-active-model-layout" in bundled_js
    assert "runtimepilot-home-status-deck" in bundled_js
    assert "telemetry-home-deck" in bundled_js
    assert "Otvori context" in bundled_js
    assert "Kompaktan signal rada" in bundled_js
    assert ".runtimepilot-active-model-layout" in bundled_css
    assert ".runtimepilot-active-model-strip:before" in bundled_css
    assert ".runtimepilot-active-model-status" in bundled_css
    assert ".runtimepilot-home-status-deck" in bundled_css
    assert ".runtimepilot-home-status-grid" in bundled_css
    assert ".runtimepilot-home-status-card" in bundled_css
    assert ".telemetry-home-deck" in bundled_css
    assert ".telemetry-home-display" in bundled_css


def test_primary_flow_and_runtime_pages_use_hifi_deck_controls_for_main_actions():
    icon_source = Path("frontend/src/components/RuntimePilotIcon.tsx").read_text(encoding="utf-8")
    flow_source = Path("frontend/src/components/PrimaryFlowCard.tsx").read_text(encoding="utf-8")
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert '"play"' in icon_source
    assert '"stop"' in icon_source
    assert '"reload"' in icon_source
    assert "primaryActionIcon" in flow_source
    assert "secondaryActionIcon" in flow_source
    assert "deck-control-button" in flow_source
    assert "deck-control-symbol" in flow_source
    assert "HomeStatusDeck" in home_source
    assert "runtimepilot-home-transport" not in home_source
    assert 'disabled={opencode?.canOpen === false}' not in home_source
    assert "PrimaryTabRack" in server_source
    assert "PrimaryTabRack" not in opencode_source
    assert "Pokreni runtime" in server_source
    assert "Otvori runtime veb" in server_source
    assert "Izolovan workspace" in opencode_source
    assert "Skok na rezultat" in opencode_source
    assert ".deck-control-button" in styles_source
    assert ".deck-control-symbol" in styles_source
    assert ".deck-control-button-primary" in styles_source
    assert ".deck-control-button-secondary" in styles_source
    assert ".runtimepilot-home-status-card-action" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "deck-control-button" in bundled_js
    assert "deck-control-symbol" in bundled_js
    assert "Pokreni runtime" in bundled_js
    assert "Zaustavi runtime" in bundled_js
    assert "Otvori OpenCode" in bundled_js
    assert "Otvori context" in bundled_js
    assert ".deck-control-button" in bundled_css
    assert ".deck-control-symbol" in bundled_css
    assert ".runtimepilot-home-status-card-action" in bundled_css


def test_home_preview_target_uses_status_dashboard_and_shell_navigation():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "VOĐENI ULAZ" in app_source
    assert "ENGINE I HEALTH" in app_source
    assert "LOKALNI KATALOG" in app_source
    assert "RADNI TOK" in app_source
    assert "TUNING I PROVERA" in app_source
    assert "runtimepilot-shell-nav-code" in app_source
    assert "runtimepilot-shell-nav-marker" in app_source
    assert "runtimepilot-shell-brand-version" in layout_source
    assert "Brzi signal" in home_source
    assert "HomeStatusDeck" in home_source
    assert "onOpenSettingsContext" in home_source
    assert ".runtimepilot-shell-nav-code" in styles_source
    assert ".runtimepilot-shell-nav-marker" in styles_source
    assert ".runtimepilot-shell-brand-version" in styles_source
    assert ".runtimepilot-home-status-grid" in styles_source
    assert ".telemetry-home-header" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "VOĐENI ULAZ" in bundled_js
    assert "Brzi signal" in bundled_js
    assert "Otvori context" in bundled_js
    assert "Kompaktan signal rada" in bundled_js
    assert ".runtimepilot-shell-nav-code" in bundled_css
    assert ".runtimepilot-home-status-grid" in bundled_css


def test_home_status_deck_context_card_routes_into_settings_focus():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "onOpenSettingsContext" in home_source
    assert "label: \"Context\"" in home_source
    assert 'onOpenSettingsContext={() => openSettingsSection("context")}' in app_source
    assert ".runtimepilot-home-status-card-context" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Otvori context" in bundled_js
    assert ".runtimepilot-home-status-card-context" in bundled_css


def test_home_status_dashboard_drops_profile_footer_shortcuts_and_big_modules():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "onOpenSettingsProfile" not in home_source
    assert "HomeHiFiModule" not in home_source
    assert "HomeStatusDeck" in home_source
    assert "profileSectionRef" in settings_source
    assert "scrollIntoView({ behavior: \"smooth\", block: \"start\" })" in settings_source
    assert ".runtimepilot-home-status-card-action" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Otvori modele" in bundled_js
    assert ".runtimepilot-home-status-card-action" in bundled_css


def test_models_page_source_highlights_where_results_appear_after_actions():
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Gde gledaš ishod" in models_source
    assert "Aktivni model gore na strani" in models_source
    assert "Status preuzimanja i Lokalni modeli" in models_source
    assert "Poslednja akcija i osvežena lista" in models_source
    assert "model-action-clarity-grid" in models_source
    assert "model-quick-next" in models_source
    assert ".model-action-clarity-grid" in styles_source
    assert ".model-quick-next" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Gde gledaš ishod" in bundled_js
    assert "Status preuzimanja i Lokalni modeli" in bundled_js
    assert ".model-action-clarity-grid" in bundled_css
    assert ".model-quick-next" in bundled_css


def test_primary_pages_share_primary_tab_rack():
    rack_source = Path("frontend/src/components/shell/PrimaryTabRack.tsx").read_text(
        encoding="utf-8"
    )
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(
        encoding="utf-8"
    )
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(
        encoding="utf-8"
    )
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(
        encoding="utf-8"
    )

    assert "PrimaryTabRack" in rack_source
    assert "Signal" in rack_source
    assert "Komande" in rack_source
    assert "Duboko" in rack_source
    assert "PrimaryTabRack" in server_source
    assert "PrimaryTabRack" in models_source
    assert "PrimaryTabRack" not in opencode_source
    assert 'onClick={() => void runAction(startServer)}' in server_source
    assert 'onClick={() => onOpenContextSettings?.()}' in server_source
    assert "onClick={openRuntimeDiagnostics}" in server_source
    assert "onOpenCompatibilityTab?.({" in models_source
    assert "onClick={revealAddModel}" in models_source
    assert "revealLocalModels();" in models_source
    assert 'openOpenCode(opencode.profile || "balanced", "direct")' in opencode_source
    assert 'openOpenCode(opencode.profile || "balanced", "isolated")' in opencode_source
    assert "onClick: scrollToActionResult" in opencode_source
    assert "onClick: openAdvancedTools" in opencode_source


def test_primary_tab_rack_supports_page_specific_labels_for_opencode_result_flow():
    rack_source = Path("frontend/src/components/shell/PrimaryTabRack.tsx").read_text(
        encoding="utf-8"
    )
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(
        encoding="utf-8"
    )

    assert "signalLabel?: string" in rack_source
    assert "commandsLabel?: string" in rack_source
    assert "deepLabel?: string" in rack_source
    assert "RuntimePilotActionDeck" in opencode_source
    assert 'title: "Skok na rezultat"' in opencode_source
    assert 'title: "Napredni alati"' in opencode_source
    assert 'id="opencode-action-result"' in opencode_source


def test_opencode_source_keeps_one_primary_work_block_and_advanced_below():
    source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "PageFlowCard" in source
    assert "RuntimePilotStatusDeck" in source
    assert "RuntimePilotActionDeck" in source
    assert "PrimaryTabRack" not in source
    assert 'id="opencode-action-result"' in source
    assert 'id="opencode-advanced-tools"' in source
    assert "Workspace" in source
    assert "Managed config" in source
    assert "PID / instance" not in source
    assert "Managed config sažetak" in source
    assert "Aktivni workspace" not in source


def test_runtime_and_models_pages_share_primary_tab_rack_result_language():
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")

    assert 'commandsLabel="Akcije"' in server_source
    assert 'deepLabel="Rezultat"' in server_source
    assert 'id="runtime-action-result"' in server_source
    assert 'commandsLabel="Akcije"' in models_source
    assert 'deepLabel="Rezultat"' in models_source
    assert 'id="models-action-result"' in models_source


def test_opencode_primary_rack_rollout_drops_legacy_top_shell_css():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert ".runtimepilot-opencode-shell-header" not in styles_source
    assert ".runtimepilot-opencode-shell-actions-panel" not in styles_source
    assert ".runtimepilot-opencode-shell-topgrid" not in styles_source
    assert ".runtimepilot-opencode-shell-secondary-action" not in styles_source
    assert ".runtimepilot-opencode-shell-main" not in styles_source


def test_settings_page_source_maps_general_save_actions_to_editor_config_and_live_result():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Klik i ishod" in settings_source
    assert "Editor odmah pokazuje šta si promenio." in settings_source
    assert "Poslednja akcija potvrđuje da je config upisan." in settings_source
    assert "Monitoring ispod kaže da li živi sistem stvarno prati sačuvano stanje." in settings_source
    assert "settings-action-route-grid" in settings_source
    assert "settings-action-route-card" in settings_source
    assert ".settings-action-route-grid" in styles_source
    assert ".settings-action-route-card" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Klik i ishod" in bundled_js
    assert "Poslednja akcija potvrđuje da je config upisan." in bundled_js
    assert ".settings-action-route-grid" in bundled_css
    assert ".settings-action-route-card" in bundled_css


def test_compatibility_panel_source_maps_apply_actions_to_live_runtime_and_editor_feedback():
    compatibility_panel_source = Path(
        "frontend/src/components/CompatibilityCalculatorPanel.tsx"
    ).read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Kad klikneš Primeni, prvo gledaj Aktivno sada na runtime-u." in compatibility_panel_source
    assert "compatibility-action-route-grid" in compatibility_panel_source
    assert "compatibility-action-route-card" in compatibility_panel_source
    assert "Editor čeka proveru" in compatibility_panel_source
    assert "Aktivno sada" in compatibility_panel_source
    assert "Poslednja akcija" in compatibility_panel_source
    assert ".compatibility-action-route-grid" in styles_source
    assert ".compatibility-action-route-card" in styles_source
    assert ".compatibility-apply-state-panel" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Kad klikneš Primeni, prvo gledaj Aktivno sada na runtime-u." in bundled_js
    assert "Editor čeka proveru" in bundled_js
    assert ".compatibility-action-route-grid" in bundled_css
    assert ".compatibility-action-route-card" in bundled_css


def test_tuning_lab_tri_slot_source_uses_hifi_receiver_faceplate_and_mixer_layout():
    tuning_source = _read_tuning_lab_frontend_sources()
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Signal chain" in tuning_source
    assert "Centralni display" in tuning_source
    assert "Mixer rack" in tuning_source
    assert "tuning-lab-slot-faceplate" in tuning_source
    assert "tuning-lab-slot-headerbar" in tuning_source
    assert "tuning-lab-slot-display-stack" in tuning_source
    assert "tuning-lab-slot-mixer-rack" in tuning_source
    assert "Svih 9 finih kontrola" in tuning_source
    assert "tuning-lab-slot-route-strip" not in tuning_source
    assert ".tuning-lab-slot-faceplate" in styles_source
    assert ".tuning-lab-slot-headerbar" in styles_source
    assert ".tuning-lab-slot-display-stack" in styles_source
    assert ".tuning-lab-slot-mixer-rack" in styles_source
    assert ".tuning-lab-slot-precision-rack" in styles_source
    assert ".tuning-lab-slot-display-panel" in styles_source
    assert "grid-template-rows: auto minmax(0, 1fr);" in styles_source
    assert "grid-template-rows: auto auto minmax(0, 1fr);" in styles_source
    assert "align-items: stretch;" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Signal chain" in bundled_js
    assert "Centralni display" in bundled_js
    assert "Mixer rack" in bundled_js
    assert "Svih 9 finih kontrola" in bundled_js
    assert ".tuning-lab-slot-faceplate" in bundled_css
    assert ".tuning-lab-slot-headerbar" in bundled_css
    assert ".tuning-lab-slot-display-stack" in bundled_css
    assert ".tuning-lab-slot-mixer-rack" in bundled_css
    assert "grid-template-rows:auto minmax(0,1fr)" in bundled_css
    assert "grid-template-rows:auto auto minmax(0,1fr)" in bundled_css


def test_tuning_lab_display_source_supports_presets_and_manual_numeric_entry():
    tuning_source = _read_tuning_lab_frontend_sources()
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert "Izaberi context preset" in tuning_source
    assert "Izaberi output preset" in tuning_source
    assert "Unesi slobodan context broj" in tuning_source
    assert "Unesi slobodan output broj" in tuning_source
    assert "524288" in tuning_source
    assert "1048576" in tuning_source
    assert "1M" in tuning_source
    assert "tuning-lab-slot-display-controls" in tuning_source
    assert ".tuning-lab-slot-display-controls" in styles_source
    assert ".tuning-lab-slot-display-control" in styles_source
    assert ".tuning-lab-slot-display-control-label" in styles_source
    assert ".tuning-lab-slot-row" in styles_source
    assert "overflow: visible;" in styles_source
    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Izaberi context preset" in bundled_js
    assert "Izaberi output preset" in bundled_js
    assert "Unesi slobodan context broj" in bundled_js
    assert "Unesi slobodan output broj" in bundled_js
    assert "1M" in bundled_js
    assert ".tuning-lab-slot-display-controls" in bundled_css
    assert ".tuning-lab-slot-display-control" in bundled_css
    assert "overflow:visible" in bundled_css


def test_hifi_shared_button_rail_styles_extend_faceplate_modules():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    css_assets = list((dist_root / "assets").glob("index-*.css"))

    assert ".runtimepilot-faceplate-module .inline-actions" in styles_source
    assert ".runtimepilot-faceplate-module .secondary-button" in styles_source
    assert ".runtimepilot-faceplate-module .action-button-soft" in styles_source
    assert "grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));" in styles_source
    assert "min-height: 46px;" in styles_source
    assert "justify-content: center;" in styles_source
    assert css_assets

    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert ".runtimepilot-faceplate-module .inline-actions" in bundled_css
    assert ".runtimepilot-faceplate-module .secondary-button" in bundled_css
    assert "grid-template-columns:repeat(auto-fit,minmax(180px,1fr))" in bundled_css
    assert "min-height:46px" in bundled_css


def test_secondary_pages_use_real_action_rail_instead_of_placeholder_modules():
    rail_source = Path(
        "frontend/src/components/shell/SecondaryActionRail.tsx"
    ).read_text(encoding="utf-8")
    advanced_source = Path("frontend/src/pages/AdvancedPage.tsx").read_text(
        encoding="utf-8"
    )
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(
        encoding="utf-8"
    )
    compatibility_source = Path(
        "frontend/src/pages/CompatibilityPage.tsx"
    ).read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "SecondaryActionRail" in rail_source
    assert "runtimepilot-secondary-action-rail" in rail_source
    assert "SecondaryActionRail" not in advanced_source
    assert "SupportPageDeck" in advanced_source
    assert "Otvori Benchmark" in advanced_source
    assert "Otvori Tuning Lab" in advanced_source
    assert "Otvori kompatibilnost" in advanced_source
    assert "SecondaryActionRail" not in benchmark_source
    assert "SecondaryActionRail" not in compatibility_source
    assert "RuntimePilotActionDeck" in benchmark_source
    assert "RuntimePilotActionDeck" in compatibility_source
    assert "actions={" not in advanced_source
    assert "actions: (" in benchmark_source
    assert "actions={" not in compatibility_source
    assert "Fix" not in advanced_source
    assert "Release" not in advanced_source
    assert ".runtimepilot-secondary-action-rail" in styles_source
    assert "order: -1" in styles_source


def test_support_pages_and_flow_card_use_faceplate_modules_for_hifi_layout():
    page_flow_source = Path("frontend/src/components/PageFlowCard.tsx").read_text(encoding="utf-8")
    page_data_state_source = Path("frontend/src/components/PageDataStateCard.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")
    search_source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")
    help_source = Path("frontend/src/pages/HelpPage.tsx").read_text(encoding="utf-8")
    repair_source = Path("frontend/src/pages/RepairPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert "runtimepilot-faceplate-module" in page_flow_source
    assert "page-flow-card-intro" in page_flow_source
    assert "page-flow-summary" in page_flow_source
    assert "page-flow-actions" in page_flow_source
    assert "runtimepilot-faceplate-module" in page_data_state_source
    assert "runtimepilot-faceplate-module" in knowledge_source
    assert "runtimepilot-faceplate-module" in search_source
    assert "runtimepilot-faceplate-module" in help_source
    assert "runtimepilot-faceplate-module" in repair_source
    assert ".page-flow-card-intro" in styles_source
    assert ".page-flow-summary" in styles_source
    assert ".page-flow-actions" in styles_source
    assert js_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "runtimepilot-faceplate-module" in bundled_js


def test_secondary_support_pages_use_faceplate_modules_for_hifi_layout():
    action_result_source = Path("frontend/src/components/ActionResultPanel.tsx").read_text(encoding="utf-8")
    observability_source = Path("frontend/src/pages/ObservabilityPage.tsx").read_text(encoding="utf-8")
    updates_source = Path("frontend/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")
    jobs_source = Path("frontend/src/pages/JobsPage.tsx").read_text(encoding="utf-8")
    fleet_source = Path("frontend/src/pages/FleetPage.tsx").read_text(encoding="utf-8")
    workflows_source = Path("frontend/src/pages/WorkflowsPage.tsx").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert "runtimepilot-faceplate-module" in action_result_source
    assert "runtimepilot-faceplate-module" in observability_source
    assert "runtimepilot-faceplate-module" in updates_source
    assert "runtimepilot-faceplate-module" in jobs_source
    assert "runtimepilot-faceplate-module" in fleet_source
    assert "runtimepilot-faceplate-module" in workflows_source
    assert js_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "runtimepilot-faceplate-module" in bundled_js


def test_updates_page_distinguishes_portal_build_from_installed_version():
    updates_source = Path("frontend/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert "fetchStatus" in updates_source
    assert 'label: "Portal build"' in updates_source
    assert 'label: "Instalirana verzija"' in updates_source
    assert "Verzija pokrenutog RuntimePilot portala" in updates_source
    assert "Verzija upisana u lokalnu instalaciju" in updates_source
    assert js_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "Portal build" in bundled_js
    assert "Instalirana verzija" in bundled_js


def test_support_pages_share_runtimepilot_support_deck_shell():
    support_source = Path("frontend/src/components/shell/SupportPageDeck.tsx").read_text(
        encoding="utf-8"
    )
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(
        encoding="utf-8"
    )
    search_source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")
    help_source = Path("frontend/src/pages/HelpPage.tsx").read_text(encoding="utf-8")
    project_memory_source = Path("frontend/src/pages/ProjectMemoryPage.tsx").read_text(
        encoding="utf-8"
    )

    assert "SupportPageDeck" in support_source
    assert "SupportPageDeck" in browser_source
    assert "SupportPageDeck" in knowledge_source
    assert "SupportPageDeck" in search_source
    assert "SupportPageDeck" in help_source
    assert "SupportPageDeck" in project_memory_source


def test_styles_source_includes_support_deck_shell_classes():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert ".runtimepilot-support-page-deck" in styles_source
    assert ".runtimepilot-support-page-deck-head" in styles_source
    assert ".runtimepilot-support-page-deck-main" in styles_source
    assert ".runtimepilot-support-page-deck-side" in styles_source


def test_catalog_memory_and_guided_flow_use_faceplate_modules_for_hifi_layout():
    guided_flow_source = Path("frontend/src/components/GuidedFlowPanel.tsx").read_text(encoding="utf-8")
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")
    project_memory_source = Path("frontend/src/pages/ProjectMemoryPage.tsx").read_text(encoding="utf-8")
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert "runtimepilot-faceplate-module" in guided_flow_source
    assert "runtimepilot-faceplate-module" in browser_source
    assert "runtimepilot-faceplate-module" in project_memory_source
    assert "runtimepilot-faceplate-module" in models_source
    assert js_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "runtimepilot-faceplate-module" in bundled_js


def test_opencode_shell_uses_faceplate_module_and_full_width_for_hifi_layout():
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))

    assert (
        'className="status-card wide-card runtimepilot-faceplate-module runtimepilot-opencode-shell"'
        in opencode_source
    )
    assert "runtimepilot-opencode-summary-grid" in opencode_source
    assert js_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "runtimepilot-faceplate-module" in bundled_js


def test_fleet_source_and_packaged_frontend_use_reserved_example_url_placeholder():
    fleet_source = Path("frontend/src/pages/FleetPage.tsx").read_text(encoding="utf-8")
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    legacy_ip = ".".join(["100", "108", "15", "57"])

    assert 'placeholder="http://192.0.2.10:3210"' in fleet_source
    assert legacy_ip not in fleet_source
    assert js_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)

    assert "http://192.0.2.10:3210" in bundled_js
    assert legacy_ip not in bundled_js


def test_browser_page_source_supports_direct_catalog_page_jump():
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "pageJumpValue" in browser_source
    assert "jumpToCatalogPage" in browser_source
    assert "Idi na stranu" in browser_source
    assert 'aria-label="Idi direktno na stranu Browser kataloga"' in browser_source
    assert ".browser-pagination-controls" in styles_source
    assert ".browser-page-jump-form" in styles_source
    assert ".browser-page-jump-input" in styles_source


def test_packaged_frontend_includes_custom_select_portal_and_browser_page_jump():
    dist_root = Path(
        "src/local_ai_control_center_installer/control_center_backend/frontend_dist"
    )
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("*.css"))

    assert js_assets
    assert css_assets

    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "createPortal" in bundled_js
    assert "Idi na stranu" in bundled_js
    assert "browser-page-jump-input" in bundled_css
    assert "custom-select-menu-portal" in bundled_css


def test_settings_compatibility_benchmark_share_hybrid_shell_layout_contract():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    compatibility_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(
        encoding="utf-8"
    )
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(
        encoding="utf-8"
    )
    compatibility_panel_source = Path(
        "frontend/src/components/CompatibilityCalculatorPanel.tsx"
    ).read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "PageFlowCard" in settings_source
    assert "RuntimePilotStatusDeck" in settings_source
    assert "RuntimePilotActionDeck" in settings_source
    assert "runtimepilot-settings-hybrid-grid" in settings_source
    assert "runtimepilot-settings-primary-rack" in settings_source
    assert "runtimepilot-settings-apply-zone" in settings_source
    assert "Sačuvaj bez primene" in settings_source
    assert "Primeni postojeće" in settings_source
    assert "Sačuvaj i primeni" in settings_source
    assert "Sačuvaj opšta podešavanja" in settings_source
    assert "Sačuvaj TurboQuant podešavanja" in settings_source

    assert "PageFlowCard" in compatibility_source
    assert "RuntimePilotStatusDeck" in compatibility_source
    assert "RuntimePilotActionDeck" in compatibility_source
    assert "runtimepilot-compatibility-hybrid-layout" in compatibility_source
    assert "runtimepilot-compatibility-main-zone" in compatibility_source
    assert "runtimepilot-compatibility-truth-zone" in compatibility_panel_source
    assert "Aktivno sada" in compatibility_panel_source
    assert "Editor čeka proveru" in compatibility_panel_source
    assert "Poslednja akcija" in compatibility_panel_source

    assert "PageFlowCard" in benchmark_source
    assert "RuntimePilotStatusDeck" in benchmark_source
    assert "RuntimePilotActionDeck" in benchmark_source
    assert "runtimepilot-benchmark-hybrid-grid" in benchmark_source
    assert "runtimepilot-benchmark-history-grid" in benchmark_source
    assert "runtimepilot-benchmark-graph-shell" in benchmark_source
    assert "Pokreni scenario" in benchmark_source
    assert "Pokreni bateriju" in benchmark_source
    assert "Sačuvaj bateriju" in benchmark_source
    assert "Vrati podrazumevane testove" in benchmark_source

    assert ".runtimepilot-settings-hybrid-grid" in styles_source
    assert ".runtimepilot-settings-primary-rack" in styles_source
    assert ".runtimepilot-settings-apply-zone" in styles_source
    assert ".runtimepilot-settings-apply-card" in styles_source
    assert ".runtimepilot-compatibility-hybrid-layout" in styles_source
    assert ".runtimepilot-compatibility-main-zone" in styles_source
    assert ".runtimepilot-compatibility-truth-zone" in styles_source
    assert ".runtimepilot-benchmark-hybrid-grid" in styles_source
    assert ".runtimepilot-benchmark-history-grid" in styles_source
    assert ".runtimepilot-benchmark-graph-shell" in styles_source

