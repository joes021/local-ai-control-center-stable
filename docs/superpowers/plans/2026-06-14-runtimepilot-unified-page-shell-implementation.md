# RuntimePilot Unified Page Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ujednačiti sve RuntimePilot strane po sistemu početne strane tako da svuda postoji isti shell, isti statusni pojas i samo jedan jasan glavni radni blok po ekranu.

**Architecture:** Zadržavamo postojeći React/Vite portal i već uvedene shell komponente (`SystemStatusLayer`, `HomeStatusDeck`, `PrimaryTabRack`, `SecondaryActionRail`), ali uvodimo još jedan zajednički obrazac za “support” strane i prepakujemo svaku stranu da poštuje isti redosled: globalni status, pet zaključanih kartica, glavni radni blok, napredno ispod. OpenCode ostaje prva kritična strana, zatim Runtime i Modeli, pa Napredno i ostali pomoćni ekrani.

**Tech Stack:** React 19, TypeScript, Vite 7, postojeći CSS u `frontend/src/styles.css`, Python source/bundle regresije u `tests/test_control_center_frontend_dist.py`, paketovani frontend u `src/local_ai_control_center_installer/control_center_backend/frontend_dist`.

---

## Scope Check

Ovaj plan ostaje jedan dokument zato što sve strane dele isti shell i isti build paket, ali je izvršenje podeljeno u male, proverljive grupe:

- zajednički shell ugovor
- OpenCode kao najrizičniji glavni tok
- Runtime + Modeli kao primarne operativne strane
- Napredno + sekundarni alati
- support strane
- Settings/Tuning Lab kao najgušći kontrolni ekrani
- finalni bundle i regresije

## File Structure

### Files to create

- `frontend/src/components/shell/SupportPageDeck.tsx`
  - zajednički shell za strane koje nisu “primary racks”, ali moraju da imaju isti hi-fi ritam: uvod, glavni radni blok, status/result hint i akcije

### Files to modify

- `frontend/src/App.tsx`
  - zaključava koji tabovi koriste koji shell obrazac i prosleđuje shared CTA handlere
- `frontend/src/components/Layout.tsx`
  - osigurava da svi page shell naslovi, margine i glavni sadržaj ostanu dosledni
- `frontend/src/components/PageFlowCard.tsx`
  - svodi uvodni blok na pomoćnu kartu, ne drugi komandni centar
- `frontend/src/components/TelemetryPanel.tsx`
  - zadržava kompaktnu home telemetriju i sprečava širenje u novu hero zonu
- `frontend/src/components/shell/SystemStatusLayer.tsx`
  - proverava sticky/full ponašanje i isti prikaz na svim stranama
- `frontend/src/components/shell/HomeStatusDeck.tsx`
  - ostaje referentni drugi red shell-a
- `frontend/src/components/shell/PrimaryTabRack.tsx`
  - standardizuje `signal -> komande -> duboko`
- `frontend/src/components/shell/SecondaryActionRail.tsx`
  - standardizuje akcioni rail za sekundarne strane
- `frontend/src/pages/HomePage.tsx`
  - ostaje referentna strana i ne sme da vrati stare duplikate modula
- `frontend/src/pages/OpenCodePage.tsx`
  - najveći cleanup: jedan primarni tok, napredno dole
- `frontend/src/pages/ServerPage.tsx`
  - runtime rack podređen istom shell ritmu
- `frontend/src/pages/ModelsPage.tsx`
  - aktivni model, brzi izbor i lokalni katalog u jednoj hijerarhiji
- `frontend/src/pages/AdvancedPage.tsx`
  - čisti sekundarni hub bez placeholder modula
- `frontend/src/pages/BenchmarkPage.tsx`
  - glavni blok levo, jasne akcije desno
- `frontend/src/pages/CompatibilityPage.tsx`
  - glavni kalkulator + rail akcije
- `frontend/src/pages/BrowserPage.tsx`
  - katalog i detalj panel u support shell-u
- `frontend/src/pages/KnowledgePage.tsx`
  - izvori, režim i odgovor u support shell-u
- `frontend/src/pages/SearchPage.tsx`
  - provider, upit i rezultat u support shell-u
- `frontend/src/pages/HelpPage.tsx`
  - help ostaje sadržajan, ali dobija isti shell i jasne sekcije
- `frontend/src/pages/ProjectMemoryPage.tsx`
  - fokus, pravila i sledeći koraci u zajedničkom rasporedu
- `frontend/src/pages/WorkflowsPage.tsx`
- `frontend/src/pages/LogsPage.tsx`
- `frontend/src/pages/RepairPage.tsx`
- `frontend/src/pages/UpdatesPage.tsx`
- `frontend/src/pages/FleetPage.tsx`
- `frontend/src/pages/JobsPage.tsx`
- `frontend/src/pages/ObservabilityPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/TuningLabPage.tsx`
- `frontend/src/styles.css`
  - shell pravila, razmaci, horizontalni raspored, support deck, detalji, responsive ponašanje
- `tests/test_control_center_frontend_dist.py`
  - source i bundle regresije za ujednačeni shell
- `src/local_ai_control_center_installer/control_center_backend/frontend_dist/**`
  - osveženi paketovani frontend na kraju plana

### Files to keep as-is unless integration zahteva malu izmenu

- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- backend API fajlovi

Problem je prvenstveno UX/UI struktura, ne backend logika.

---

### Task 1: Zaključaj zajednički shell ugovor i uvedi `SupportPageDeck`

**Files:**
- Create: `frontend/src/components/shell/SupportPageDeck.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/components/PageFlowCard.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing source regression for the shared support shell**

Dodaj u `tests/test_control_center_frontend_dist.py`:

```python
def test_support_pages_share_runtimepilot_support_deck_shell():
    support_source = Path("frontend/src/components/shell/SupportPageDeck.tsx").read_text(encoding="utf-8")
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")
    search_source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")

    assert "SupportPageDeck" in support_source
    assert "SupportPageDeck" in browser_source
    assert "SupportPageDeck" in knowledge_source
    assert "SupportPageDeck" in search_source


def test_styles_source_includes_support_deck_shell_classes():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert ".runtimepilot-support-page-deck" in styles_source
    assert ".runtimepilot-support-page-deck-main" in styles_source
    assert ".runtimepilot-support-page-deck-side" in styles_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "support_deck_shell" -v
```

Expected: FAIL because `SupportPageDeck.tsx` još ne postoji i support strane još nemaju isti shell obrazac.

- [ ] **Step 3: Implement the shared support shell**

Napraviti `frontend/src/components/shell/SupportPageDeck.tsx` sa interfejsom:

```tsx
type SupportPageDeckProps = {
  eyebrow: string;
  title: string;
  summary: string;
  actions?: ReactNode;
  resultHint?: ReactNode;
  children: ReactNode;
};
```

Struktura:

```tsx
<section className="runtimepilot-support-page-deck runtimepilot-faceplate-module">
  <header className="runtimepilot-support-page-deck-head">...</header>
  <div className="runtimepilot-support-page-deck-main">{children}</div>
  {resultHint ? <aside className="runtimepilot-support-page-deck-side">{resultHint}</aside> : null}
</section>
```

Pravila:

- `Layout.tsx` ne menja globalni redosled shell-a
- `PageFlowCard.tsx` ostaje uvodni blok, ali mora vizuelno biti sekundaran u odnosu na glavni radni blok
- `App.tsx` ostaje izvor svih shared navigacionih handlera
- `styles.css` dobija jedinstven raspored za support strane, bez vraćanja starih “hero” modula

- [ ] **Step 4: Run the targeted test plus frontend build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "support_deck_shell" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/components/PageFlowCard.tsx frontend/src/components/shell/SupportPageDeck.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add runtimepilot support page shell"
```

---

### Task 2: Sredi OpenCode kao prvi glavni tok po pravilu `signal -> akcije -> rezultat`

**Files:**
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/components/ActionResultPanel.tsx`
- Modify: `frontend/src/components/shell/PrimaryTabRack.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing OpenCode source regression**

Dodaj:

```python
def test_opencode_source_keeps_one_primary_work_block_and_advanced_below():
    source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "PrimaryTabRack" in source
    assert 'id="opencode-action-result"' in source
    assert 'id="opencode-advanced-tools"' in source
    assert "launcher preview" not in source.lower()
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "opencode_source_keeps_one_primary_work_block" -v
```

Expected: FAIL because OpenCode još uvek meša više površina i nema dovoljno strogu hijerarhiju rezultata i naprednih sekcija.

- [ ] **Step 3: Rewrite the OpenCode top section around one primary block**

Pravila za `frontend/src/pages/OpenCodePage.tsx`:

- `PrimaryTabRack` ostaje jedini otvoreni glavni blok na vrhu
- `signal` prikazuje:

```tsx
session state
runtime connected
aktivni workspace
managed model
```

- `commands` prikazuje samo:

```tsx
Otvori OpenCode
Otvori izolovan workspace
Popravi / instaliraj OpenCode
```

- `deep` prikazuje:

```tsx
gde se vidi rezultat
PID / instance
managed config summary
```

- `ActionResultPanel` mora odmah ispod rack-a jasno da pokaže ishod akcije
- sve ostalo ide u `<details id="opencode-advanced-tools">`
  - presetovi
  - bezbednosni režim
  - autonomija
  - launcher preview / servisne stvari

- [ ] **Step 4: Run targeted OpenCode tests plus build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "opencode_source_keeps_one_primary_work_block or opencode_shell_uses_faceplate_module_for_hifi_layout" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/OpenCodePage.tsx frontend/src/components/ActionResultPanel.tsx frontend/src/components/shell/PrimaryTabRack.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: rationalize opencode primary workflow shell"
```

---

### Task 3: Poravnaj `Runtime` i `Modeli` sa istim shell ritmom kao OpenCode

**Files:**
- Modify: `frontend/src/pages/ServerPage.tsx`
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Modify: `frontend/src/components/shell/PrimaryTabRack.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing regression for primary operational pages**

Dodaj:

```python
def test_runtime_and_models_pages_share_primary_tab_rack_language():
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")

    assert "PrimaryTabRack" in server_source
    assert "PrimaryTabRack" in models_source
    assert "Rezultat posle klika" in server_source
    assert "Rezultat posle klika" in models_source
    assert "details" in server_source.lower()
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "runtime_and_models_pages_share_primary_tab_rack_language" -v
```

Expected: FAIL because iako obe strane već koriste `PrimaryTabRack`, još nisu potpuno usklađene po visinama, rezultatima i mestu gde napredno počinje.

- [ ] **Step 3: Normalize Runtime and Models**

`frontend/src/pages/ServerPage.tsx`:

- `signal`: engine, health, context alignment, execution mode
- `commands`: start, restart, stop, open runtime web
- `deep`: health URL, local web, context CTA, dijagnostika CTA
- advanced details ispod: ručne komande, GPU offload, log/CLI detalji

`frontend/src/pages/ModelsPage.tsx`:

- `signal`: aktivni model, lifecycle, fit, katalog signal
- `commands`: aktiviraj, preuzmi/dodaj, kompatibilnost, lokalni GGUF
- `deep`: gde se vidi rezultat posle aktivacije/preuzimanja/brisanja
- lokalni modeli i katalog ostaju ispod kao glavni radni deo, ali bez raspadanja kartica i visoke uske kolone

`PrimaryTabRack.tsx`:

- zaključati širine i vertikalni ritam da `signal`, `commands` i `deep` deluju kao jedna hi-fi celina

- [ ] **Step 4: Run targeted tests plus build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "runtime_and_models_pages_share_primary_tab_rack_language or models_page_source_highlights_where_results_appear_after_actions" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ServerPage.tsx frontend/src/pages/ModelsPage.tsx frontend/src/components/shell/PrimaryTabRack.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: align runtime and models with unified primary shell"
```

---

### Task 4: Pretvori `Napredno`, `Benchmark`, `Kompatibilnost` i `Telemetriju` u čiste sekundarne radne površine

**Files:**
- Modify: `frontend/src/pages/AdvancedPage.tsx`
- Modify: `frontend/src/pages/BenchmarkPage.tsx`
- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/pages/ObservabilityPage.tsx`
- Modify: `frontend/src/components/shell/SecondaryActionRail.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing regression for the secondary hub**

Dodaj:

```python
def test_secondary_pages_use_real_action_rail_and_not_placeholder_surfaces():
    advanced_source = Path("frontend/src/pages/AdvancedPage.tsx").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    compatibility_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(encoding="utf-8")

    assert "SecondaryActionRail" in advanced_source
    assert "SecondaryActionRail" in benchmark_source
    assert "SecondaryActionRail" in compatibility_source
    assert "Otvori Benchmark" in advanced_source
    assert "Otvori Tuning Lab" in advanced_source
    assert "Fix" not in advanced_source
    assert "Release" not in advanced_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "secondary_pages_use_real_action_rail" -v
```

Expected: FAIL because ove strane još nisu potpuno poravnate po istom shell sistemu i još viri stari raspored ili mrtav tekst.

- [ ] **Step 3: Normalize the secondary action pages**

`frontend/src/pages/AdvancedPage.tsx`:

- levo: jedna jasna mapa zona
- desno: samo stvarni klikovi ka ekranima
- bez novih “velikih modula” koji ne rade ništa

`frontend/src/pages/BenchmarkPage.tsx`:

- glavni rezultat levo: kontekst benchmarka, aktivnost, grafikon, istorija
- rail desno: pokretanje, baterija, export, prelazi ka tuning/logovima

`frontend/src/pages/CompatibilityPage.tsx`:

- glavni kalkulator levo
- primena i brze akcije desno
- jasno istaknuti gde se vidi primenjena vrednost

`frontend/src/pages/ObservabilityPage.tsx`:

- živi signal, grafovi i health događaji kao glavni radni blok
- akcije ili prelasci u rail-u, ne u novim hero modulima

- [ ] **Step 4: Run targeted tests plus build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "secondary_pages_use_real_action_rail or compatibility_panel_source_maps_apply_actions_to_live_runtime_and_editor_feedback or benchmark_control_panel" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AdvancedPage.tsx frontend/src/pages/BenchmarkPage.tsx frontend/src/pages/CompatibilityPage.tsx frontend/src/pages/ObservabilityPage.tsx frontend/src/components/shell/SecondaryActionRail.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: unify advanced benchmark and compatibility shells"
```

---

### Task 5: Prepakuj support strane u isti hi-fi shell bez natrpavanja

**Files:**
- Modify: `frontend/src/pages/BrowserPage.tsx`
- Modify: `frontend/src/pages/KnowledgePage.tsx`
- Modify: `frontend/src/pages/SearchPage.tsx`
- Modify: `frontend/src/pages/HelpPage.tsx`
- Modify: `frontend/src/pages/ProjectMemoryPage.tsx`
- Modify: `frontend/src/pages/WorkflowsPage.tsx`
- Modify: `frontend/src/pages/LogsPage.tsx`
- Modify: `frontend/src/pages/RepairPage.tsx`
- Modify: `frontend/src/pages/UpdatesPage.tsx`
- Modify: `frontend/src/pages/FleetPage.tsx`
- Modify: `frontend/src/pages/JobsPage.tsx`
- Modify: `frontend/src/components/shell/SupportPageDeck.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing regression for support pages**

Dodaj:

```python
def test_support_pages_follow_home_like_shell_pattern():
    browser_source = Path("frontend/src/pages/BrowserPage.tsx").read_text(encoding="utf-8")
    knowledge_source = Path("frontend/src/pages/KnowledgePage.tsx").read_text(encoding="utf-8")
    search_source = Path("frontend/src/pages/SearchPage.tsx").read_text(encoding="utf-8")
    help_source = Path("frontend/src/pages/HelpPage.tsx").read_text(encoding="utf-8")
    memory_source = Path("frontend/src/pages/ProjectMemoryPage.tsx").read_text(encoding="utf-8")

    assert "SupportPageDeck" in browser_source
    assert "SupportPageDeck" in knowledge_source
    assert "SupportPageDeck" in search_source
    assert "SupportPageDeck" in help_source
    assert "SupportPageDeck" in memory_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "support_pages_follow_home_like_shell_pattern" -v
```

Expected: FAIL because strane još imaju različite uvodne blokove, razmake i mesta gde se vidi rezultat posle klika.

- [ ] **Step 3: Migrate the support pages**

Pravila po stranama:

- `BrowserPage.tsx`
  - glavni blok: filteri + lista + detalj
  - result hint: download / add to catalog / compatibility ishod
- `KnowledgePage.tsx`
  - glavni blok: izvori -> režim -> upit/odgovor
  - result hint: gde se vidi indeksiranje i odgovor
- `SearchPage.tsx`
  - glavni blok: provider -> query -> rezultati
  - result hint: gde se vidi lokalni odgovor naspram web rezultata
- `HelpPage.tsx`
  - glavni blok: brzi početak + tematske sekcije
  - bez zbijenih polja i bez generičke light površine
- `ProjectMemoryPage.tsx`
  - glavni blok: cilj + liste + save/seed rezultat
  - akcije poravnate i vidljive
- `Workflows/Logs/Repair/Updates/Fleet/Jobs`
  - svaki ekran dobija isti shell i samo jedan glavni blok, bez lutanja kroz duplirane panele

- [ ] **Step 4: Run targeted tests plus build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "support_pages_follow_home_like_shell_pattern or help_page or project_memory" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/BrowserPage.tsx frontend/src/pages/KnowledgePage.tsx frontend/src/pages/SearchPage.tsx frontend/src/pages/HelpPage.tsx frontend/src/pages/ProjectMemoryPage.tsx frontend/src/pages/WorkflowsPage.tsx frontend/src/pages/LogsPage.tsx frontend/src/pages/RepairPage.tsx frontend/src/pages/UpdatesPage.tsx frontend/src/pages/FleetPage.tsx frontend/src/pages/JobsPage.tsx frontend/src/components/shell/SupportPageDeck.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: migrate support pages to unified runtimepilot shell"
```

---

### Task 6: Utegni `Podešavanja` i `Tuning Lab` bez rušenja postojećih kontrola

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabSlotIdentityPanel.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing regression for dense control pages**

Dodaj:

```python
def test_settings_and_tuning_lab_keep_dense_controls_inside_hifi_shell():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    tuning_source = Path("frontend/src/pages/TuningLabPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "runtimepilot-faceplate-module" in settings_source
    assert "runtimepilot-faceplate-module" in tuning_source
    assert ".runtimepilot-settings" in styles_source or ".runtimepilot-tuning" in styles_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "dense_controls_inside_hifi_shell" -v
```

Expected: FAIL because ove strane još nisu dovoljno dosledne istom shell sistemu i previše lako skliznu u zbijen, neujednačen raspored.

- [ ] **Step 3: Normalize the dense control pages**

`frontend/src/pages/SettingsPage.tsx`:

- glavni blok na vrhu: aktivni profil, context, apply/save signal
- detaljne sekcije ispod: inference parametri, TurboQuant, OpenCode, provider setup
- rezultat primene mora uvek biti jasno vidljiv odmah ispod akcije

`frontend/src/pages/TuningLabPage.tsx`:

- tri slota ostaju glavni blok, ali u jednom hi-fi shell okviru
- fine kontrole ostaju funkcionalne, bez raspadanja po visinama ili z-index problema
- istorija, queue, import/export i napredne dijagnostike idu ispod

Komponente u `frontend/src/components/tuning-lab/*`:

- poravnati visine i širine slotova
- context/output kontrola mora podržati preset + slobodan unos bez lošeg overlaya

- [ ] **Step 4: Run targeted tests plus build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "dense_controls_inside_hifi_shell or tuning_lab" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/pages/TuningLabPage.tsx frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx frontend/src/components/tuning-lab/TuningLabSlotIdentityPanel.tsx frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: align settings and tuning lab with unified shell"
```

---

### Task 7: Osveži bundle, pokreni pune regresije i proveri da je portal svuda dosledan

**Files:**
- Modify: `tests/test_control_center_frontend_dist.py`
- Refresh: `frontend/dist/**`
- Refresh: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/**`

- [ ] **Step 1: Add final bundle assertions**

Dodaj:

```python
def test_packaged_frontend_includes_unified_page_shell():
    dist_root = Path("src/local_ai_control_center_installer/control_center_backend/frontend_dist")
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("*.css"))
    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Health" in bundled_js
    assert "Runtime" in bundled_js
    assert "OpenCode" in bundled_js
    assert "SupportPageDeck" not in bundled_js
    assert ".runtimepilot-support-page-deck" in bundled_css
    assert ".runtimepilot-primary-tab-rack" in bundled_css
    assert ".runtimepilot-secondary-action-rail" in bundled_css
```

- [ ] **Step 2: Run the targeted packaged-frontend test before refresh**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "packaged_frontend_includes_unified_page_shell" -v
```

Expected: FAIL because packaged bundle još nije osvežen.

- [ ] **Step 3: Build and sync frontend bundles**

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location

if (Test-Path 'src/local_ai_control_center_installer/control_center_backend/frontend_dist') {
  Get-ChildItem 'src/local_ai_control_center_installer/control_center_backend/frontend_dist' -Force | Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Force -Path 'src/local_ai_control_center_installer/control_center_backend/frontend_dist' | Out-Null
Copy-Item 'frontend\\dist\\*' -Destination 'src/local_ai_control_center_installer/control_center_backend/frontend_dist' -Recurse -Force
```

- [ ] **Step 4: Run the full regression suite and manual smoke**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -v
python -m pytest tests/test_control_center_static_serving.py tests/test_control_center_status.py -v
```

Expected: PASS

Manual smoke:

```powershell
Push-Location frontend
npm run dev -- --host 127.0.0.1 --port 3212
Pop-Location
```

Ručno proveriti:

- `Početna` ne vraća stare duplikate modula
- `OpenCode` ima samo jedan primarni radni blok na vrhu
- `Runtime`, `Modeli`, `OpenCode` dele isti top ritam
- `Napredno` je stvarni hub, ne scenografija
- `Browser`, `Znanje`, `Pretraga`, `Pomoć`, `Project Memory` slede isti shell
- `Podešavanja` i `Tuning Lab` ostaju gusti, ali čitljivi i hi-fi

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/shell/SupportPageDeck.tsx frontend/src/pages frontend/src/components frontend/src/styles.css tests/test_control_center_frontend_dist.py frontend/dist src/local_ai_control_center_installer/control_center_backend/frontend_dist
git commit -m "feat: ship runtimepilot unified page shell"
```

---

## Manual Verification Checklist

- `Aktivni model` i `Živi resursi` ostaju globalno prisutni na svakoj strani
- pet kartica `Health / Runtime / Model / Context / OpenCode` ostaju isti drugi red shell-a
- svaka strana ima jedan jasan glavni radni blok
- rezultat posle klika je jasan i čitljiv bez lovljenja po stranici
- napredne i retke opcije su ispod u `details` ili sekundarnim sekcijama
- OpenCode više nije zbrkan na vrhu
- Benchmark, Kompatibilnost i Napredno više ne liče na placeholder rasporede
- support strane deluju kao deo istog proizvoda, ne kao odvojeni UI eksperimenti

## Notes

- Ne uvoditi novi frontend framework ili novi state manager.
- Ne menjati backend API osim ako neka strana traži već postojeći status podatak koji nije prosleđen do komponente.
- Ako `frontend/src/styles.css` postane prevelik tokom izvršenja, dozvoljeno je izdvojiti `frontend/src/styles/shell.css`, ali tek u posebnom koraku uz ažuriranje plana.
- U ovom thread-u plan je pregledan ručno, bez delegiranja subagentu, da bismo ostali u istom toku rada i bez dodatnog grananja.
