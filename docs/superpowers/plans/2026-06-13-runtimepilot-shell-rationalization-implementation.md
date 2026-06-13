# RuntimePilot Shell Rationalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevesti odobreni RuntimePilot shell u cist, hijerarhijski UI gde `header` ostaje navigacija, sistemski sloj ostaje stalno vidljiv, a svaka strana pokazuje samo stvarne akcije i rezultate bez placeholder modula.

**Architecture:** Zadrzati postojeci React/Vite portal i njegov hi-fi vizuelni jezik, ali prelomiti shell oko tri nova nivoa: globalni `header`, objedinjeni `sistemski sloj` i strogo namenski `sadrzaj strane`. Implementacija treba da ide kroz reusable React komponente za statusni sloj, Home status deck, top rack za glavne tabove i desni action rail za sekundarne stranice, uz minimalno diranje backend-a jer je problem prvenstveno u frontend informacijskoj arhitekturi.

**Tech Stack:** React 19, TypeScript, Vite 7, postojeci CSS u `frontend/src/styles.css`, Python source/bundle regresioni testovi u `tests/test_control_center_frontend_dist.py`, FastAPI static serving smoke testovi.

---

## Scope Note

Ovaj plan ostaje jedan dokument zato sto:

- `App.tsx`, `Layout.tsx` i `styles.css` nose zajednicki shell za sve tabove
- `Home`, `Runtime`, `Modeli`, `OpenCode`, `Napredno`, `Benchmark` i `Kompatibilnost` dele isti hi-fi jezik i iste regresione testove
- paketni build (`frontend/dist` -> `src/local_ai_control_center_installer/control_center_backend/frontend_dist`) mora da se proveri tek kada se svi shell delovi ukljuce zajedno

Duboki sekundarni ekrani kao `SettingsPage.tsx`, `TuningLabPage.tsx`, `KnowledgePage.tsx`, `SearchPage.tsx` i ostali ostaju van ove faze osim ako novi shell zahteva male prilagodbe klase ili razmaka.

## File Structure

### Files to create

- `frontend/src/components/shell/SystemStatusLayer.tsx`
  - novi objedinjeni sistemski sloj: aktivni model + zivi resursi, sa punim prikazom gore i kompaktnim sticky rezimom na scroll
- `frontend/src/components/shell/HomeStatusDeck.tsx`
  - petokarticni `Stanje sada` red za `Pocetnu`, u tacnom redosledu `Health -> Runtime -> Model -> Context -> OpenCode`
- `frontend/src/components/shell/PrimaryTabRack.tsx`
  - reusable top rack za `Runtime`, `Modeli` i `OpenCode`, sa levim signalom, srednjim komandama i desnim `Duboko` blokom
- `frontend/src/components/shell/SecondaryActionRail.tsx`
  - reusable desni action rail za `Napredno`, `Benchmark` i `Kompatibilnost`, bez mrtvih kartica i placeholder readout-a

### Files to modify

- `frontend/src/App.tsx`
  - centralni routing za klikove iz `Stanje sada`, shell wiring za novi sistemski sloj i prelom tabova na nove reusable rack komponente
- `frontend/src/components/Layout.tsx`
  - zamena starog `activeModelStrip + LiveResourceStrip` reda objedinjеним sistemskim slojem
- `frontend/src/components/LiveResourceStrip.tsx`
  - podrska za puni i kompaktni sticky prikaz, uz zadrzavanje postojece metrike i click-to-detail logike
- `frontend/src/components/TelemetryPanel.tsx`
  - novi kompaktniji `home` rezim koji daje samo sazeti telemetrijski signal za `Pocetnu`
- `frontend/src/pages/HomePage.tsx`
  - uklanjanje starih velikih modula 1/2/3 i uvodjenje svedenog Home rasporeda: `Stanje sada`, `Zivi resursi`, `sazeta telemetrija`
- `frontend/src/pages/ServerPage.tsx`
  - top rack prelazak na `PrimaryTabRack` i jasnije veze ka health/context akcijama
- `frontend/src/pages/ModelsPage.tsx`
  - top rack prelazak na `PrimaryTabRack`, uz zadrzavanje postojećeg model workflow-a ispod
- `frontend/src/pages/OpenCodePage.tsx`
  - top rack prelazak na `PrimaryTabRack`, uz ocuvanje launcher i advanced tools logike
- `frontend/src/pages/AdvancedPage.tsx`
  - uklanjanje placeholder modula i pravljenje pravog sekundarnog huba sa realnim akcijama
- `frontend/src/pages/BenchmarkPage.tsx`
  - prelom u levi sadrzaj + desni action rail raspored
- `frontend/src/pages/CompatibilityPage.tsx`
  - prelom u levi sadrzaj + desni action rail raspored
- `frontend/src/styles.css`
  - nove shell klase, sticky status sloj, Home deck, primary tab rack, secondary action rail i responsive pravila
- `tests/test_control_center_frontend_dist.py`
  - source/bundle regresije za novi shell, Home, top rack i sekundarni hub

### Files to keep as-is unless shell integration zahteva malu izmenu

- `frontend/src/components/PrimaryFlowCard.tsx`
  - ne koristiti kao glavni obrazac za novu shell arhitekturu; ostaviti za starije ili lokalne tokove ako i dalje imaju smisla
- `frontend/src/components/PageFlowCard.tsx`
  - moze ostati kao uvodni blok na nekim stranicama, ali ne sme vise da glumi akcioni centar
- `frontend/src/pages/TuningLabPage.tsx`
  - van scope-a ove iteracije
- `frontend/src/pages/SettingsPage.tsx`
  - van scope-a ove iteracije osim ako `Context` CTA sa Home/Runtime mora da fokusira deo koji vec postoji
- `src/local_ai_control_center_installer/control_center_backend/frontend_dist/**`
  - ne dirati rucno dok ne dodje finalni bundle refresh task

---

### Task 1: Uvedi objedinjeni sistemski sloj i zakucaj shell regresije

**Files:**
- Create: `frontend/src/components/shell/SystemStatusLayer.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/components/LiveResourceStrip.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing source regression for the new shell anatomy**

Dodaj u `tests/test_control_center_frontend_dist.py`:

```python
def test_shell_source_uses_unified_system_status_layer():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")
    layer_source = Path("frontend/src/components/shell/SystemStatusLayer.tsx").read_text(encoding="utf-8")

    assert "SystemStatusLayer" in app_source
    assert "systemStatusLayer={" in layout_source
    assert "activeModelStrip={" not in app_source
    assert "LiveResourceStrip" in layer_source
    assert "sticky" in layer_source.lower()


def test_styles_source_includes_full_and_compact_system_status_modes():
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert ".runtimepilot-system-status-layer" in styles_source
    assert ".runtimepilot-system-status-layer-sticky" in styles_source
    assert ".runtimepilot-system-status-layer-compact" in styles_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "unified_system_status_layer or compact_system_status_modes" -v
```

Expected: FAIL because `Layout.tsx` jos uvek koristi odvojeni `activeModelStrip` i `LiveResourceStrip`, a nova komponenta ne postoji.

- [ ] **Step 3: Implement the shell scaffolding**

Napraviti `frontend/src/components/shell/SystemStatusLayer.tsx` sa minimalnim interfejsom:

```tsx
type SystemStatusLayerProps = {
  activeModelStrip: ReactNode;
  onOpenSettingsSection?: (sectionId: string) => void;
};
```

Implementaciona pravila:

- komponenta renderuje:

```tsx
<div className="runtimepilot-system-status-layer">
  <div className="runtimepilot-system-status-layer-full">{activeModelStrip}<LiveResourceStrip ... /></div>
  <div className="runtimepilot-system-status-layer-sticky">...</div>
</div>
```

- `Layout.tsx` treba da primi novi prop:

```tsx
systemStatusLayer?: ReactNode;
```

- `Layout.tsx` vise ne renderuje direktno `activeModelStrip` ni `LiveResourceStrip`
- `App.tsx` prestaje da skriva aktivni model na `home` strani i umesto toga salje objedinjeni sistemski sloj u `Layout`
- `LiveResourceStrip.tsx` dobija kompaktan mod, na primer:

```tsx
type LiveResourceStripProps = {
  onOpenSettingsSection?: (sectionId: string) => void;
  compact?: boolean;
};
```

- kompaktan mod ne menja metriku ni detalj logiku, vec samo raspored i gustinu CSS-a

- [ ] **Step 4: Run the targeted test plus frontend build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "unified_system_status_layer or compact_system_status_modes" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS without TypeScript errors.

- [ ] **Step 5: Commit the shell layer**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/components/LiveResourceStrip.tsx frontend/src/components/shell/SystemStatusLayer.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add runtimepilot unified system status layer"
```

---

### Task 2: Prelomi `Pocetnu` u status dashboard bez duplirane navigacije

**Files:**
- Create: `frontend/src/components/shell/HomeStatusDeck.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/components/TelemetryPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing Home regression**

Dodaj:

```python
def test_home_source_uses_five_card_status_deck_in_locked_order():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    deck_source = Path("frontend/src/components/shell/HomeStatusDeck.tsx").read_text(encoding="utf-8")
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
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "five_card_status_deck or drops_big_runtime_model_opencode_modules" -v
```

Expected: FAIL because `HomePage.tsx` jos uvek koristi tri velika `HomeHiFiModule` bloka.

- [ ] **Step 3: Rewrite `HomePage.tsx` around `Stanje sada` and compact telemetry**

`frontend/src/components/shell/HomeStatusDeck.tsx` neka prima:

```tsx
type HomeStatusDeckItem = {
  label: "Health" | "Runtime" | "Model" | "Context" | "OpenCode";
  value: string;
  detail: string;
  onClick: () => void;
};
```

`HomePage.tsx` treba da se svede na:

```tsx
<>
  <HomeStatusDeck items={...} />
  <TelemetryPanel benchmark={benchmark} variant="home" />
</>
```

Implementaciona pravila:

- vise ne renderovati `Veliki modul 1`, `Veliki modul 2`, `Veliki modul 3`
- koristiti ove CTA destinacije:
  - `Health` -> `onOpenServer`
  - `Runtime` -> `onOpenServer`
  - `Model` -> `onOpenModels`
  - `Context` -> otvori `settings` fokus na `context`
  - `OpenCode` -> `onOpenOpenCode`
- `TelemetryPanel` `home` varijanta treba da ostane hi-fi, ali kompaktnija i bez ogromne hero kompozicije
- ne vracati duplicirane `Runtime / Lokalni model / OpenCode` launch kartice unutar Home tela

- [ ] **Step 4: Run the targeted tests plus the existing Home bundle assertions**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "five_card_status_deck or drops_big_runtime_model_opencode_modules or home_source_exposes_command_deck_intro_and_primary_flow_grid" -v
```

Expected: PASS after prilagodjavanja starih Home source/bundle asercija na novu terminologiju.

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit the Home rewrite**

```bash
git add frontend/src/App.tsx frontend/src/components/TelemetryPanel.tsx frontend/src/components/shell/HomeStatusDeck.tsx frontend/src/pages/HomePage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: simplify runtimepilot home into status dashboard"
```

---

### Task 3: Napravi reusable top rack i primeni ga na `Runtime`, `Modeli` i `OpenCode`

**Files:**
- Create: `frontend/src/components/shell/PrimaryTabRack.tsx`
- Modify: `frontend/src/pages/ServerPage.tsx`
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing source test for primary tab racks**

Dodaj:

```python
def test_primary_pages_share_primary_tab_rack():
    rack_source = Path("frontend/src/components/shell/PrimaryTabRack.tsx").read_text(encoding="utf-8")
    server_source = Path("frontend/src/pages/ServerPage.tsx").read_text(encoding="utf-8")
    models_source = Path("frontend/src/pages/ModelsPage.tsx").read_text(encoding="utf-8")
    opencode_source = Path("frontend/src/pages/OpenCodePage.tsx").read_text(encoding="utf-8")

    assert "PrimaryTabRack" in rack_source
    assert "Signal" in rack_source
    assert "Komande" in rack_source
    assert "Duboko" in rack_source
    assert "PrimaryTabRack" in server_source
    assert "PrimaryTabRack" in models_source
    assert "PrimaryTabRack" in opencode_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "primary_pages_share_primary_tab_rack" -v
```

Expected: FAIL because glavne stranice jos uvek imaju sopstvene neujednacene top kompozicije.

- [ ] **Step 3: Implement the reusable rack and rewire the three main pages**

`frontend/src/components/shell/PrimaryTabRack.tsx` neka primi:

```tsx
type PrimaryTabRackProps = {
  eyebrow: string;
  title: string;
  signal: ReactNode;
  commands: ReactNode;
  deep: ReactNode;
};
```

Struktura:

```tsx
<section className="runtimepilot-primary-tab-rack">
  <div className="runtimepilot-primary-tab-rack-signal">{signal}</div>
  <div className="runtimepilot-primary-tab-rack-commands">{commands}</div>
  <div className="runtimepilot-primary-tab-rack-deep">{deep}</div>
</section>
```

Prelom po stranicama:

- `ServerPage.tsx`
  - `signal`: runtime state + health + context alignment signal
  - `commands`: start/restart/stop/open web
  - `deep`: health URL, local web link, context CTA, dijagnostika ulaz
- `ModelsPage.tsx`
  - `signal`: aktivni model, lifecycle, fit, lokalni katalog count
  - `commands`: aktivacija, brza promena, kompatibilnost, dodaj lokalni GGUF
  - `deep`: gde gledas rezultat posle aktivacije/preuzimanja/brisanja
- `OpenCodePage.tsx`
  - `signal`: session state + runtime veza
  - `commands`: otvori desktop, izolovan workspace, bootstrap/fix
  - `deep`: managed config, aktivni workspace, poslednji rezultat

Bitno:

- ne dirati dublje sekcije ispod top rack-a u ovoj fazi
- cilj je da prve tri glavne strane dobiju isti ritam pre nego sto se ide na sekundarne hub-ove

- [ ] **Step 4: Run the targeted test plus focused page assertions**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "primary_pages_share_primary_tab_rack or opencode_shell_uses_faceplate_module_for_hifi_layout or models_page_source_highlights_where_results_appear_after_actions" -v
```

Expected: PASS after azuriranja starih source testova koji vise ne smeju da ocekuju stari top layout.

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit the primary tab rack rollout**

```bash
git add frontend/src/components/shell/PrimaryTabRack.tsx frontend/src/pages/ServerPage.tsx frontend/src/pages/ModelsPage.tsx frontend/src/pages/OpenCodePage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add shared runtimepilot primary tab rack"
```

---

### Task 4: Preuredi `Napredno`, `Benchmark` i `Kompatibilnost` u stvarni action hub

**Files:**
- Create: `frontend/src/components/shell/SecondaryActionRail.tsx`
- Modify: `frontend/src/pages/AdvancedPage.tsx`
- Modify: `frontend/src/pages/BenchmarkPage.tsx`
- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/components/PageFlowCard.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing regression for the secondary hub layout**

Dodaj:

```python
def test_secondary_pages_use_real_action_rail_instead_of_placeholder_modules():
    rail_source = Path("frontend/src/components/shell/SecondaryActionRail.tsx").read_text(encoding="utf-8")
    advanced_source = Path("frontend/src/pages/AdvancedPage.tsx").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")
    compatibility_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(encoding="utf-8")

    assert "SecondaryActionRail" in rail_source
    assert "Otvori Benchmark" in advanced_source
    assert "Otvori Tuning Lab" in advanced_source
    assert "Otvori kompatibilnost" in advanced_source
    assert "SecondaryActionRail" in benchmark_source
    assert "SecondaryActionRail" in compatibility_source
    assert "Fix" not in advanced_source
    assert "Release" not in advanced_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "secondary_pages_use_real_action_rail_instead_of_placeholder_modules" -v
```

Expected: FAIL because `AdvancedPage.tsx` jos uvek koristi velike placeholder module, a `BenchmarkPage.tsx` i `CompatibilityPage.tsx` nemaju zajednicki action rail obrazac.

- [ ] **Step 3: Implement the secondary action rail and rewire the three pages**

`frontend/src/components/shell/SecondaryActionRail.tsx`:

```tsx
type SecondaryActionRailItem = {
  code: string;
  title: string;
  subtitle: string;
  onClick?: () => void;
};
```

Struktura:

```tsx
<aside className="runtimepilot-secondary-action-rail">
  {items.map(...)}
</aside>
```

Page-level rules:

- `AdvancedPage.tsx`
  - postaje cist sekundarni hub sa realnim launch akcijama
  - nema vise `Veliki modul 4/5/6/7`
  - glavni sadrzaj levo je sazeti opis grupa: analiza, znanje, fokus, servis
  - desno stoji akcioni rail sa stvarnim klikovima ka `Benchmark`, `Tuning Lab`, `Kompatibilnost`, `Znanje`, `Pretraga`, `Project Memory`, `Settings`, `Logs`, `Repair`, `Updates`, `Fleet`, `Jobs`
- `BenchmarkPage.tsx`
  - zadrzava graf, aktivnost i istoriju levo
  - desno dobija rail sa akcijama: pokreni scenario, pokreni bateriju, otvori Tuning Lab, otvori Logove, izvozi
- `CompatibilityPage.tsx`
  - levo ostaje izbor opsega + kalkulator
  - desno ide rail sa ulazima: koristi aktivni model, otvori Modele, otvori Browser katalog, otvori izvorni link kad postoji

`PageFlowCard.tsx` po potrebi smanjiti da bude uvodna pomoc, ne drugi komandni centar.

- [ ] **Step 4: Run the targeted regression plus focused bundle checks**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "secondary_pages_use_real_action_rail_instead_of_placeholder_modules or compatibility_panel_source_maps_apply_actions_to_live_runtime_and_editor_feedback or benchmark_control_panel or support_pages_and_flow_card_use_faceplate_modules_for_hifi_layout" -v
```

Expected: PASS after prilagodjavanja imena starih benchmark/advanced asercija tamo gde je potrebno.

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit the secondary hub rationalization**

```bash
git add frontend/src/components/shell/SecondaryActionRail.tsx frontend/src/components/PageFlowCard.tsx frontend/src/pages/AdvancedPage.tsx frontend/src/pages/BenchmarkPage.tsx frontend/src/pages/CompatibilityPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: rationalize runtimepilot secondary action hub"
```

---

### Task 5: Osvjezi bundle, pokreni punu verifikaciju i zakljucaj paketovani portal

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/components/LiveResourceStrip.tsx`
- Modify: `frontend/src/components/TelemetryPanel.tsx`
- Modify: `frontend/src/components/shell/SystemStatusLayer.tsx`
- Modify: `frontend/src/components/shell/HomeStatusDeck.tsx`
- Modify: `frontend/src/components/shell/PrimaryTabRack.tsx`
- Modify: `frontend/src/components/shell/SecondaryActionRail.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/ServerPage.tsx`
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/pages/AdvancedPage.tsx`
- Modify: `frontend/src/pages/BenchmarkPage.tsx`
- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`
- Refresh: `frontend/dist/**`
- Refresh: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/**`

- [ ] **Step 1: Add final bundle assertions for the shell rationalization**

Prosiri `tests/test_control_center_frontend_dist.py` sa bundle-level proverama:

```python
def test_packaged_frontend_includes_rationalized_shell():
    dist_root = Path("src/local_ai_control_center_installer/control_center_backend/frontend_dist")
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))
    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Health" in bundled_js
    assert "OpenCode" in bundled_js
    assert "Brzi signal" in bundled_js
    assert "Otvori Benchmark" in bundled_js
    assert "Otvori kompatibilnost" in bundled_js
    assert ".runtimepilot-system-status-layer" in bundled_css
    assert ".runtimepilot-home-status-deck" in bundled_css
    assert ".runtimepilot-primary-tab-rack" in bundled_css
    assert ".runtimepilot-secondary-action-rail" in bundled_css
```

- [ ] **Step 2: Run the targeted bundle test before refreshing packaged assets**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "packaged_frontend_includes_rationalized_shell" -v
```

Expected: FAIL because `frontend_dist` jos uvek sadrzi stari bundle.

- [ ] **Step 3: Build and sync the packaged frontend**

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

Napomena: ovo je bezbedno jer se operacija izvrsava samo unutar workspace `frontend_dist` foldera koji je namenjen generisanom buildu.

- [ ] **Step 4: Run the full regression suite relevant to the frontend shell**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -v
```

Expected: PASS

Run:

```powershell
python -m pytest tests/test_control_center_static_serving.py tests/test_control_center_status.py -v
```

Expected: PASS, bez regresije u serviranju portala i status snapshot-u.

Optional manual browser smoke:

```powershell
Push-Location frontend
npm run dev -- --host 127.0.0.1 --port 3212
Pop-Location
```

Rucno proveriti:

- `Pocetna` prikazuje `Health, Runtime, Model, Context, OpenCode` u jednoj horizontali
- `Zivi resursi` i aktivni model su vidljivi na svakom ekranu
- `Runtime`, `Modeli`, `OpenCode` imaju isti left/middle/right top rack ritam
- `Napredno`, `Benchmark`, `Kompatibilnost` imaju stvarni desni action rail bez placeholder polja

- [ ] **Step 5: Commit the packaged shell refresh**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/components/LiveResourceStrip.tsx frontend/src/components/TelemetryPanel.tsx frontend/src/components/shell frontend/src/pages/HomePage.tsx frontend/src/pages/ServerPage.tsx frontend/src/pages/ModelsPage.tsx frontend/src/pages/OpenCodePage.tsx frontend/src/pages/AdvancedPage.tsx frontend/src/pages/BenchmarkPage.tsx frontend/src/pages/CompatibilityPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py src/local_ai_control_center_installer/control_center_backend/frontend_dist
git commit -m "feat: ship runtimepilot shell rationalization"
```

---

## Manual Verification Checklist

Posle Task 5 proveriti rucno:

- `Pocetna` vise ne ponavlja `Runtime / Lokalni model / OpenCode` kao ogromne module
- `Stanje sada` ima tacno 5 kartica i klikovi vode na prava mesta
- `Context` kartica vodi na `Settings` fokusiran na context
- aktivni model i zivi resursi ostaju vidljivi i kada korisnik skroluje dublje na stranici
- `Runtime`, `Modeli` i `OpenCode` dele isti top rack jezik
- `Napredno` vise nema mrtve kartice tipa `Fix / Release / Red / Mreza` bez stvarne akcije
- `Benchmark` i `Kompatibilnost` imaju jasno desno mesto za akcije i levo mesto za rezultat
- osvezen packaged portal prikazuje isti novi shell kao i `frontend/dist`

## Notes

- Ne uvoditi novi frontend test framework u ovoj iteraciji. Postojeci Python source/bundle regresioni testovi su vec uspostavljen obrazac i treba ga slediti.
- Ne dirati backend API osim ako frontend shell zatrazi dodatni vec postojeci status podatak ili link; problem je pre svega UX/UI raspored.
- Ako `styles.css` nastavi da raste neudobno, dozvoljeno je u toku implementacije iz planiranog taska izdvojiti `frontend/src/styles/shell.css`, ali tek ako je to neophodno i ako se plan azurira pre takvog reza.
- Posle odobrenja ovog plana sledeci korak nije ad-hoc kodiranje, nego izvrsavanje task po task uz TDD/red-green-refactor disciplinu i male commitove.
