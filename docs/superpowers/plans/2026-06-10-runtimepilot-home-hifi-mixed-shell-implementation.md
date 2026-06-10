# RuntimePilot Home Hi-Fi Mixed Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prelomiti pravi RuntimePilot UI u odobreni `mesano` Home resenje sa vodjenim tokom gore, tri velika hi-fi modula ispod i petokomandnim header shell-om.

**Architecture:** Zadrzati postojeci React/Vite shell, ali preurediti `App.tsx`, `Layout.tsx` i `HomePage.tsx` oko nove informacione arhitekture. Novi Home ne treba da bude jos jedan niz kartica, vec kompozicija od fokusiranih, namenski izdvojenih komponenti: hi-fi nav shell, vodjeni rail, tri glavna modula i zaseban `Napredno` ekran koji grupise sekundarne alate bez starog dropdown haosa.

**Tech Stack:** React 19, TypeScript, Vite 7, postojeci CSS u `frontend/src/styles.css`, postojeci Python source/bundle regresioni testovi u `tests/test_control_center_frontend_dist.py`.

---

## File Structure

### Files to create

- `frontend/src/pages/AdvancedPage.tsx`
  - novi peti glavni ekran za grupisanje sekundarnih alata u istom hi-fi jeziku
- `frontend/src/components/home/HomeHiFiModule.tsx`
  - zajednicki skelet velikog Home modula: levi signal, srednji display, desni komandni stub, donja statusna traka
- `frontend/src/components/home/HomeHiFiCommandButton.tsx`
  - desna komandna dugmad koja vizuelno dele DNK sa gornjom navigacijom
- `frontend/src/components/home/HomeHiFiSignalRail.tsx`
  - levi LED/status panel za svaku od tri glavne zone
- `frontend/src/components/home/HomeSecondaryToolCard.tsx`
  - kartica za sekundarne alate na Home i/ili `Napredno` strani

### Files to modify

- `frontend/src/App.tsx`
  - nova petokomandna navigacija (`Početna`, `Runtime`, `Modeli`, `OpenCode`, `Napredno`)
  - uklanjanje `Vodi me redom` iz primarne nav trake
  - uslovno sakrivanje globalnog `activeModelStrip` na Home strani
  - renderovanje nove `AdvancedPage`
- `frontend/src/components/Layout.tsx`
  - shell prilagodjavanja za novi header/nav ritam
  - Home-specifcno gasenje vizuelnog suma koji jede gornji ekran
- `frontend/src/pages/HomePage.tsx`
  - kompletno preslaganje u odobreni `mixed shell`
- `frontend/src/styles.css`
  - hi-fi shell, modul, signal rail, command button, advanced launcher i responsive stilovi
- `tests/test_control_center_frontend_dist.py`
  - source/bundle regresioni testovi za novu nav arhitekturu, Home kompoziciju i `Napredno` ekran

### Existing files to keep as-is in ovoj fazi

- `frontend/src/components/GuidedFlowPanel.tsx`
  - ostaje kao odvojeni detaljniji walkthrough ekran, ali vise nije primarni header tab
- `frontend/src/components/PrimaryFlowCard.tsx`
  - ne dirati ako Home potpuno predje na nove hi-fi module; zadrzati ga za druge stranice koje ga vec koriste
- `frontend/src/components/LiveResourceStrip.tsx`
  - ne redizajnirati u ovoj fazi; samo proveriti da ne razbija novi Home ritam

---

### Task 1: Zakucaj petokomandni shell i `Napredno` ulaz

**Files:**
- Create: `frontend/src/pages/AdvancedPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing regression test for primary navigation**

Dodaj nove source-level testove u `tests/test_control_center_frontend_dist.py`:

```python
def test_app_source_promotes_five_command_runtimepilot_shell():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'advanced: { label: "Napredno", cue: "Alati", icon: "control" }' in app_source
    assert 'const PRIMARY_PAGES: PageKey[] = ["home", "server", "models", "opencode", "advanced"]' in app_source
    assert 'const GUIDED_FLOW_PAGE: PageKey = "guidedFlow"' in app_source
    assert 'onStartGuidedFlow={() => setPage("guidedFlow")}' in app_source


def test_layout_and_app_source_drop_guided_flow_from_header_nav():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    layout_source = Path("frontend/src/components/Layout.tsx").read_text(encoding="utf-8")

    assert 'label: "Vodi me redom"' in app_source
    assert 'nav-button-guided' not in app_source
    assert "runtimepilot-nav-shell-title" in layout_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "five_command_runtimepilot_shell or drop_guided_flow_from_header_nav" -v
```

Expected: FAIL because `advanced` page metadata and the new nav structure are not implemented yet.

- [ ] **Step 3: Implement the shell wiring in `App.tsx` and `Layout.tsx`**

U `frontend/src/App.tsx`:

- dodaj:

```ts
advanced: { label: "Napredno", cue: "Alati", icon: "control" }
```

- promeni:

```ts
const PRIMARY_PAGES: PageKey[] = ["home", "server", "models", "opencode", "advanced"];
```

- ukloni `nav-button-guided` iz header navigacije
- zadrzi `guidedFlow` page state i CTA iz Home strane
- privremeno renderuj novu stranu:

```tsx
{page === "advanced" ? <AdvancedPage ... /> : null}
```

U `frontend/src/components/Layout.tsx`:

- zadrzi postojeci `brand`, `eyebrow`, `subtitle`
- prilagodi copy oko nav shell-a tako da govori o direktnim tokovima i alatu `Napredno`
- ne uvodi novi dropdown za Home redizajn

U `frontend/src/pages/AdvancedPage.tsx` napravi minimalan skeleton:

```tsx
export function AdvancedPage() {
  return (
    <section className="status-card wide-card runtimepilot-advanced-shell">
      <span className="status-label">Napredno</span>
      <strong className="status-value">Analiza, tuning i pomoćni alati</strong>
      <p className="helper-text">
        Ovde dolaze Benchmark, Tuning Lab, Kompatibilnost, Project Memory i ostali sekundarni tokovi.
      </p>
    </section>
  );
}
```

- [ ] **Step 4: Run the targeted test again plus frontend build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "five_command_runtimepilot_shell or drop_guided_flow_from_header_nav" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: Vite build completes without TypeScript errors.

- [ ] **Step 5: Commit the shell wiring**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/pages/AdvancedPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add runtimepilot five-command shell"
```

---

### Task 2: Uvedi reusable Home hi-fi module komponente

**Files:**
- Create: `frontend/src/components/home/HomeHiFiModule.tsx`
- Create: `frontend/src/components/home/HomeHiFiCommandButton.tsx`
- Create: `frontend/src/components/home/HomeHiFiSignalRail.tsx`
- Create: `frontend/src/components/home/HomeSecondaryToolCard.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing source test for the new Home component split**

Dodaj:

```python
def test_home_hifi_component_split_exists():
    module_source = Path("frontend/src/components/home/HomeHiFiModule.tsx").read_text(encoding="utf-8")
    command_source = Path("frontend/src/components/home/HomeHiFiCommandButton.tsx").read_text(encoding="utf-8")
    rail_source = Path("frontend/src/components/home/HomeHiFiSignalRail.tsx").read_text(encoding="utf-8")

    assert "export function HomeHiFiModule" in module_source
    assert "export function HomeHiFiCommandButton" in command_source
    assert "export function HomeHiFiSignalRail" in rail_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "home_hifi_component_split_exists" -v
```

Expected: FAIL because the new component files do not exist yet.

- [ ] **Step 3: Create the reusable components with minimal interfaces**

`frontend/src/components/home/HomeHiFiCommandButton.tsx`

```tsx
type HomeHiFiCommandButtonProps = {
  code: string;
  title: string;
  subtitle: string;
  tone?: "default" | "primary" | "danger";
  icon?: RuntimePilotIconName;
  disabled?: boolean;
  titleAttr?: string;
  onClick: () => void;
};
```

`frontend/src/components/home/HomeHiFiSignalRail.tsx`

```tsx
type HomeHiFiSignalItem = {
  label: string;
  value: string;
  detail: string;
  tone?: "success" | "accent" | "signal";
};
```

`frontend/src/components/home/HomeHiFiModule.tsx`

```tsx
type HomeHiFiModuleProps = {
  eyebrow: string;
  title: string;
  railItems: readonly HomeHiFiSignalItem[];
  summaryTitle: string;
  summaryText: string;
  readouts: readonly { label: string; value: string; detail: string }[];
  actions: readonly ReactNode[];
  footer: readonly { label: string; value: string; detail: string }[];
};
```

Cilj ove faze nije finalna stilizacija, nego cista podela odgovornosti da `HomePage.tsx` ne ostane ogromna prezentaciona datoteka.

- [ ] **Step 4: Run the targeted test and typecheck/build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "home_hifi_component_split_exists" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit the Home component extraction**

```bash
git add frontend/src/components/home frontend/src/pages/HomePage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "refactor: extract runtimepilot home hifi modules"
```

---

### Task 3: Prelomi `HomePage.tsx` u odobreni mixed shell

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing Home regression tests**

Dodaj testove koji potvrdjuju novu kompoziciju:

```python
def test_home_source_promotes_mixed_hifi_shell_and_vertical_modules():
    home_source = Path("frontend/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "HomeHiFiModule" in home_source
    assert "Runtime → Lokalni model → OpenCode" in home_source
    assert "Vodi me redom" in home_source
    assert ".runtimepilot-home-mixed-shell" in styles_source
    assert ".runtimepilot-home-guided-rail" in styles_source
    assert ".runtimepilot-home-module-stack" in styles_source


def test_app_source_hides_global_active_model_strip_on_home():
    app_source = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'activeModelStrip={page === "home" ? null : activeModelStrip}' in app_source
```

- [ ] **Step 2: Run the targeted tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "mixed_hifi_shell or hides_global_active_model_strip_on_home" -v
```

Expected: FAIL because Home still uses the old intro + sequence + `PrimaryFlowCard` layout and the global active model strip is always mounted.

- [ ] **Step 3: Rewrite `HomePage.tsx` using the new building blocks**

Implement the following structure:

```tsx
<section className="status-card wide-card runtimepilot-home-mixed-shell ...">
  <div className="runtimepilot-home-guided-rail">...</div>
</section>

<div className="runtimepilot-home-module-stack wide-card">
  <HomeHiFiModule ...runtimeProps />
  <HomeHiFiModule ...modelProps />
  <HomeHiFiModule ...openCodeProps />
</div>

<section className="status-card wide-card runtimepilot-home-support-rack ...">
  ...
</section>
```

Specific implementation constraints:

- zadrzi postojeci data loading (`fetchStatus`, `fetchServerStatus`, `fetchOpenCodeStatus`, `fetchBenchmark`)
- zadrzi `openOpenCode(profile, "direct" | "isolated")`
- prebaci Home iz `PrimaryFlowCard` na `HomeHiFiModule`
- uvuci runtime/model/opencode stanje direktno u module
- zadrzi `Vodi me redom` CTA kao ulaz u posebni walkthrough page
- ukloni vizuelnu zavisnost Home od globalnog `activeModelStrip`

U `frontend/src/App.tsx` promeni:

```tsx
activeModelStrip={page === "home" ? null : activeModelStrip}
```

To je namerna odluka da Home ne izgubi pola gornjeg prostora na globalni strip koji je sada dupliciran kroz same module.

- [ ] **Step 4: Run the targeted tests plus the existing Home bundle test**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "home_source_promotes_mixed_hifi_shell_and_vertical_modules or app_source_hides_global_active_model_strip_on_home or home_source_exposes_command_deck_intro_and_primary_flow_grid" -v
```

Expected: PASS after prilagodjavanja starog Home testa na novu terminologiju.

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit the Home mixed shell rewrite**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/pages/HomePage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: rewrite runtimepilot home into hifi mixed shell"
```

---

### Task 4: Napravi pravi `Napredno` ekran u istom hi-fi jeziku

**Files:**
- Modify: `frontend/src/pages/AdvancedPage.tsx`
- Create: `frontend/src/components/home/HomeSecondaryToolCard.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing test for grouped advanced tools**

Dodaj:

```python
def test_advanced_page_source_groups_secondary_tools():
    page_source = Path("frontend/src/pages/AdvancedPage.tsx").read_text(encoding="utf-8")
    styles_source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Analiza i alati" in page_source
    assert "Benchmark" in page_source
    assert "Tuning Lab" in page_source
    assert "Kompatibilnost" in page_source
    assert "Project Memory" in page_source
    assert ".runtimepilot-advanced-grid" in styles_source
    assert ".runtimepilot-advanced-tool-card" in styles_source
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "advanced_page_source_groups_secondary_tools" -v
```

Expected: FAIL because `AdvancedPage.tsx` is still only a placeholder.

- [ ] **Step 3: Implement the grouped `Napredno` launcher page**

U `frontend/src/pages/AdvancedPage.tsx` napravi tri grupe:

```tsx
const sections = [
  {
    title: "Analiza i alati",
    items: ["Benchmark", "Kompatibilnost", "Znanje", "Pretraga", "Telemetrija"],
  },
  {
    title: "Optimizacija",
    items: ["Tuning Lab", "Project Memory", "Podešavanja"],
  },
  {
    title: "Održavanje",
    items: ["Logovi", "Popravka", "Ažuriranja"],
  },
];
```

Svaki item treba da bude klikabilan launcher card koji samo poziva prosledjeni `onOpenX` callback iz `App.tsx`.

Nemoj vracati stari dropdown meni pod novim imenom. `Napredno` mora da bude prava stranica, ne novo pakovanje starog menija.

- [ ] **Step 4: Run the targeted tests plus build**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "advanced_page_source_groups_secondary_tools" -v
```

Expected: PASS

Run:

```powershell
Push-Location frontend
npm run build
Pop-Location
```

Expected: PASS

- [ ] **Step 5: Commit the Advanced page**

```bash
git add frontend/src/pages/AdvancedPage.tsx frontend/src/components/home/HomeSecondaryToolCard.tsx frontend/src/App.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add runtimepilot advanced hifi launcher page"
```

---

### Task 5: Osvezi bundled portal i zavrsi regresionu proveru

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/AdvancedPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`
- Refresh: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/**`

- [ ] **Step 1: Add the final bundled-output assertions**

Prosiri `tests/test_control_center_frontend_dist.py` da proveri i source i bundle:

```python
def test_packaged_frontend_includes_home_hifi_shell_and_advanced_page():
    dist_root = Path("src/local_ai_control_center_installer/control_center_backend/frontend_dist")
    js_assets = list((dist_root / "assets").glob("*.js"))
    css_assets = list((dist_root / "assets").glob("index-*.css"))
    bundled_js = "\n".join(path.read_text(encoding="utf-8") for path in js_assets)
    bundled_css = "\n".join(path.read_text(encoding="utf-8") for path in css_assets)

    assert "Napredno" in bundled_js
    assert "Runtime → Lokalni model → OpenCode" in bundled_js
    assert "Sekundarni alati" in bundled_js
    assert ".runtimepilot-home-mixed-shell" in bundled_css
    assert ".runtimepilot-advanced-grid" in bundled_css
```

- [ ] **Step 2: Run the targeted bundle test before refreshing `frontend_dist`**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -k "packaged_frontend_includes_home_hifi_shell_and_advanced_page" -v
```

Expected: FAIL because `frontend_dist` still contains the old bundled portal.

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

Ovo mora da ostane identicno logici iz `packaging/build_windows_installer.ps1`, da ne dobijemo razliku izmedju lokalnog portala i onoga sto se pakuje za installer.

- [ ] **Step 4: Run the full frontend regression suite**

Run:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -v
```

Expected: PASS

Optional smoke check:

```powershell
python -m pytest tests/test_control_center_server.py -v
```

Expected: PASS or no regressions on server/frontend integration.

- [ ] **Step 5: Commit the bundled refresh**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/components/home frontend/src/pages/HomePage.tsx frontend/src/pages/AdvancedPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py src/local_ai_control_center_installer/control_center_backend/frontend_dist
git commit -m "feat: ship runtimepilot home hifi mixed shell"
```

---

## Manual Verification Checklist

Posle Task 5, proveriti rucno u browseru:

- Home otvara vodjeni rail gore i tri velika modula jedan ispod drugog
- Home vise nema globalni `Aktivni model` strip koji jede vrh ekrana
- Runtime modul jasno pokazuje gde se vidi health rezultat
- Model modul jasno pokazuje koji je aktivni model i kako se menja
- OpenCode modul jasno razlikuje direktno otvaranje i izolovani workspace
- Header prikazuje pet glavnih komandi i `Napredno` umesto starog `Više`
- `Napredno` stranica otvara sekundarne tokove kao prave launch kartice
- `Ctrl+F5` nad portalom ne vraca stari izgled iz zastarelog bundle-a

## Notes

- Ne uvoditi Vitest ili novi frontend test stack u ovoj iteraciji. Repo vec koristi Python source/bundle regresije kao glavni obrazac za frontend promene i treba pratiti taj obrazac.
- Ne dirati `LiveResourceStrip` i duboke napredne stranice osim onoliko koliko je potrebno da novi shell ostane stabilan.
- Ako `HomePage.tsx` ponovo krene da raste preko razumne granice, nastaviti ekstrakciju komponenti umesto vracanja na jedan veliki fajl.
