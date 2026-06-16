import re
from pathlib import Path


def _assert_inline_heading_wraps_label(source: str, label: str) -> None:
    pattern = re.compile(
        rf'runtimepilot-inline-heading[\s\S]{{0,500}}?{re.escape(label)}'
    )
    assert pattern.search(source), f"Expected inline heading near label: {label}"


def test_settings_page_uses_inline_headings_for_primary_hifi_clusters():
    source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")

    for label in (
        "Disk higijena OpenCode workspace-a",
        "Profili i opseg",
        "Opšta podešavanja",
        "VRAM fit tuning",
        "Pretraga i izvori",
        "TurboQuant podešavanja",
    ):
        _assert_inline_heading_wraps_label(source, label)


def test_compatibility_page_uses_inline_headings_for_workspace_and_source_flow():
    source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(
        encoding="utf-8"
    )

    for label in (
        "Radni prostor kompatibilnosti",
        "Izbor izvora",
        "Aktivni model",
        "Trenutni lokalni izbor",
        "Trenutni udaljeni izbor",
    ):
        _assert_inline_heading_wraps_label(source, label)


def test_benchmark_page_uses_inline_headings_for_primary_faceplate_modules():
    source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")

    for label in (
        "Izbor scenarija i baterije",
        "Editor baterije",
        "Kontekst benchmarka",
        "Pokretanje benchmarka",
        "Aktivnost zahteva",
        "Grafikon benchmarka",
        "Benchmark istorija",
    ):
        _assert_inline_heading_wraps_label(source, label)
