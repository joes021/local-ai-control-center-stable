# RuntimePilot UX Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preurediti RuntimePilot oko tri glavna toka `Runtime -> Lokalni model -> OpenCode`, uvesti jasan sekundarni sloj za napredne alate i uskladiti akcioni model tako da korisnik uvek zna sta je glavni klik, sta je samo sacuvano i sta je stvarno primenjeno.

**Architecture:** Zadrzati postojeci React/Vite frontend i postojece backend API-je gde god je moguce, ali prelomiti shared shell, navigaciju i tri glavne strane u novi UX okvir. Rewrite ide fazno: prvo shell i navigacija, zatim Pocetna i tri glavne zone, zatim Runtime/Modeli/OpenCode, pa univerzalni action model za napredne sekcije i na kraju mobilni polish i regresije.

**Tech Stack:** React, TypeScript, Vite, CSS, pytest frontend bundle regresije, lokalni browser smoke test na `http://127.0.0.1:3210/`

---

## File Structure and Ownership

### Shared shell and navigation

- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/components/BrandLockup.tsx`
- Modify: `frontend/src/components/RuntimePilotIcon.tsx`

**Responsibility:** Novi globalni shell, dvonivojska navigacija, tri glavna toka, sekundarni `Vise` sloj, globalni `Vodi me redom` ulaz i mobile-first osnovni raspored.

### New shared UX components

- Create: `frontend/src/components/PrimaryFlowCard.tsx`
- Create: `frontend/src/components/GuidedFlowPanel.tsx`
- Create: `frontend/src/components/ApplyStatePanel.tsx`
- Create: `frontend/src/components/SectionAccordion.tsx`

**Responsibility:** Ponovljivi gradivni blokovi za glavne zone, vodjeni tok, prikaz `izmenjeno / sacuvano / primenjeno` i mobilno sklopive napredne sekcije.

### Primary pages

- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/ServerPage.tsx`
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Modify: `frontend/src/pages/OpenCodePage.tsx`

**Responsibility:** Nova UX hijerarhija za tri glavne strane i novi komandni pocetni ekran.

### Advanced/secondary pages

- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/pages/BenchmarkPage.tsx`
- Modify: `frontend/src/pages/ObservabilityPage.tsx`
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/HelpPage.tsx`
- Modify: `frontend/src/pages/ProjectMemoryPage.tsx`
- Modify: `frontend/src/pages/LogsPage.tsx`
- Modify: `frontend/src/pages/RepairPage.tsx`
- Modify: `frontend/src/pages/UpdatesPage.tsx`

**Responsibility:** Uklapanje sekundarnih alata u novi sloj bez gubitka funkcionalnosti, plus uvodjenje istog akcionog jezika i boljeg mobilnog ritma.

### Shared feedback and API glue

- Modify: `frontend/src/components/ActionResultPanel.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`

**Responsibility:** Jedinstven prikaz poslednje akcije i statusa `izmenjeno / sacuvano / primenjeno` bez lutanja po nepovezanim panelima.

### Tests and dist

- Modify: `tests/test_control_center_frontend_dist.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

**Responsibility:** Regresije za novu navigaciju, shell, CTA hijerarhiju i buildovani frontend.

---

### Task 1: Zakljucaj frontend regresije za novi shell i tri glavna toka

**Files:**
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodaj failing test za novi shell i primarnu navigaciju**

Dodaj ocekivanja za:
- `Vodi me redom`
- primarni nav bez punog starog admin rasporeda
- tri glavne zone `Runtime`, `Lokalni model`, `OpenCode`
- novi shared tekst za sekundarni `Vise` sloj

- [ ] **Step 2: Dodaj failing test za shared action model**

Test treba da trazi kljucne akcione tekstove:
- `Sacuvaj i primeni`
- `Sacuvaj bez primene`
- `Primenjeno na zivi sistem`

- [ ] **Step 3: Pokreni ciljane frontend testove i potvrdi da padaju**

Run: `python -m pytest tests\\test_control_center_frontend_dist.py -q`

Expected:
- test pada jer novi shell i novi action model jos ne postoje

- [ ] **Step 4: Commit failing test baseline**

```bash
git add tests/test_control_center_frontend_dist.py
git commit -m "test: lock ux rewrite shell expectations"
```

### Task 2: Prelomi shared shell, navigaciju i `Vodi me redom`

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/components/BrandLockup.tsx`
- Modify: `frontend/src/components/RuntimePilotIcon.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/components/GuidedFlowPanel.tsx`

- [ ] **Step 1: U App definisi novu primarnu navigaciju**

Promeni page map tako da glavni nivo bude:
- `Pocetna`
- `Runtime`
- `Modeli`
- `OpenCode`
- `Vodi me redom`
- `Vise`

Sekundarne stranice grupisi po smislu, ne po istorijskom redosledu.

- [ ] **Step 2: U Layout uvedi dvonivojski shell**

Implementiraj:
- compact command header
- jasan brand + status red
- primarni nav
- sekundarni panel za `Vise`
- mesto za `Vodi me redom` ulaz

- [ ] **Step 3: Napravi `GuidedFlowPanel` komponentu**

Komponenta mora prikazati:
- korak 1 runtime
- korak 2 model
- korak 3 OpenCode
- aktivni korak
- CTA za nastavak

- [ ] **Step 4: U CSS zakljucaj novu shell hijerarhiju**

Dodaj stilove za:
- primarni nav
- `Vise` drawer/panel
- mobile-first collapse
- sticky guided CTA gde ima smisla

- [ ] **Step 5: Pokreni frontend test i proveri prolaz**

Run: `python -m pytest tests\\test_control_center_frontend_dist.py -q`

Expected:
- novi shell/nav testovi prolaze ili padaju samo na jos neimplementirane glavne zone

- [ ] **Step 6: Commit shell i navigaciju**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/components/BrandLockup.tsx frontend/src/components/RuntimePilotIcon.tsx frontend/src/components/GuidedFlowPanel.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add ux rewrite shell and guided navigation"
```

### Task 3: Pretvori Pocetnu u komandni ekran sa tri glavne zone

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Create: `frontend/src/components/PrimaryFlowCard.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Napravi `PrimaryFlowCard` komponentu**

Komponenta mora imati standardni skelet:
- stanje sada
- glavna akcija
- sekundarna akcija
- rezultat akcije
- optional `napredno` ulaz

- [ ] **Step 2: HomePage preuredi u tri velike zone**

Prikazi:
- Runtime
- Lokalni model
- OpenCode

Iznad njih:
- aktivni runtime
- aktivni model
- OpenCode status
- `Vodi me redom`

- [ ] **Step 3: Uvedi jasan rezultat posle klika na Pocetnoj**

Rezultat ne sme da ide u nepovezan panel. Mora biti lokalno vezan za zonu ili za command deck.

- [ ] **Step 4: Proveri da HomePage ostane upotrebljiva na mobilnom**

Zona raspored:
- desktop: 3 kolone
- tablet: 2 + 1
- mobilno: 1 kolona

- [ ] **Step 5: Pokreni ciljane testove**

Run: `python -m pytest tests\\test_control_center_frontend_dist.py -q`

Expected:
- novi Home shell indikatori prisutni u bundle testu

- [ ] **Step 6: Commit novu Pocetnu**

```bash
git add frontend/src/pages/HomePage.tsx frontend/src/components/PrimaryFlowCard.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: redesign home as runtimepilot command deck"
```

### Task 4: Runtime stranu pretvori u jasan health-and-action ekran

**Files:**
- Modify: `frontend/src/pages/ServerPage.tsx`
- Create: `frontend/src/components/ApplyStatePanel.tsx`
- Modify: `frontend/src/components/ActionResultPanel.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Napravi `ApplyStatePanel` komponentu**

Komponenta mora da prikaze:
- izmenjeno u editoru
- sacuvano u configu
- primenjeno na runtime

- [ ] **Step 2: ServerPage preuredi po novom skeletu**

Prikazi:
- stanje runtime-a
- health
- glavni CTA `Pokreni / restartuj runtime`
- sekundarni CTA `Promeni runtime`
- rezultat odmah ispod

- [ ] **Step 3: Napredne runtime sekcije prebaci u sklopive ili sekundarne blokove**

Sekcije:
- TurboQuant parametri
- context alignment
- repair
- dijagnostika

ne smeju da guse glavni deo strane.

- [ ] **Step 4: Uskladi `ActionResultPanel` sa novim shared jezikom**

Panel mora da razlikuje:
- info
- u toku
- uspesno
- primenjeno
- greska

- [ ] **Step 5: Pokreni ciljani frontend test**

Run: `python -m pytest tests\\test_control_center_frontend_dist.py -q`

Expected:
- shell i novi runtime CTA tekstovi prisutni

- [ ] **Step 6: Commit Runtime stranu**

```bash
git add frontend/src/pages/ServerPage.tsx frontend/src/components/ApplyStatePanel.tsx frontend/src/components/ActionResultPanel.tsx frontend/src/lib/api.ts frontend/src/lib/types.ts frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: redesign runtime page around clear actions"
```

### Task 5: Modeli stranu preuredi iz biblioteke u fokusirani picker

**Files:**
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Modify: `frontend/src/components/CompatibilityCalculatorPanel.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Gornji fokus blok postavi oko aktivnog modela**

Prikazi:
- aktivni model
- spremnost
- VRAM fit status

- [ ] **Step 2: Uvedi glavni CTA i sekundarni CTA**

Glavno:
- `Otvori i promeni model`

Sekundarno:
- `Proveri kompatibilnost`

- [ ] **Step 3: Skrati podrazumevani prikaz liste modela**

Prvo prikazi:
- aktivni
- lokalni
- spremni za download

Ostale grupe prebaci u sekundarni sloj ili sklopive sekcije.

- [ ] **Step 4: Uskladi delete/hide/download tok sa novim action jezikom**

Korisnik mora odmah videti:
- sta je akcija
- sta je posledica
- gde je rezultat

- [ ] **Step 5: Pokreni ciljani frontend test**

Run: `python -m pytest tests\\test_control_center_frontend_dist.py -q`

Expected:
- modeli tekstovi i novi CTA indikatori prolaze

- [ ] **Step 6: Commit Modeli stranu**

```bash
git add frontend/src/pages/ModelsPage.tsx frontend/src/components/CompatibilityCalculatorPanel.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: redesign models page as focused picker"
```

### Task 6: OpenCode stranu pretvori u jasan radni cockpit

**Files:**
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Status blok na vrhu usmeri na 3 odgovora**

Prikazi:
- da li je sesija otvorena
- da li je CLI povezan
- koji runtime/model koristi

- [ ] **Step 2: Uvedi glavni i sekundarni CTA**

Glavno:
- `Otvori OpenCode`

Sekundarno:
- `Pokreni task`
- `Otvori poslednji rezultat`

- [ ] **Step 3: Zivi signal i cockpit zadrzi, ali ga prebaci u sekundarni ritam**

Cockpit, istorija, task presetovi i Project Memory veza treba da ostanu dostupni, ali ne smeju da zaklone glavni pocetni klik.

- [ ] **Step 4: Pokreni ciljani frontend test**

Run: `python -m pytest tests\\test_control_center_frontend_dist.py -q`

Expected:
- OpenCode strana i dalje eksplicitno govori da radi CLI sesija u terminalu
- novi CTA tekstovi prisutni

- [ ] **Step 5: Commit OpenCode stranu**

```bash
git add frontend/src/pages/OpenCodePage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: redesign opencode page around clear session actions"
```

### Task 7: Spusti novi action model u napredne i sekundarne stranice

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/pages/BenchmarkPage.tsx`
- Modify: `frontend/src/pages/ObservabilityPage.tsx`
- Modify: `frontend/src/pages/ProjectMemoryPage.tsx`
- Modify: `frontend/src/pages/HelpPage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: SettingsPage uskladi sa shared `Sacuvaj i primeni` modelom**

Svuda gde ima smisla prikazi:
- glavno dugme `Sacuvaj i primeni`
- sekundarno `Sacuvaj bez primene`
- indikator sta je samo promenjeno, a sta je zaista primenjeno

- [ ] **Step 2: TuningLabPage preuredi da glavni tok bude jasniji**

Jasna hijerarhija:
- ucitaj
- pokreni
- otvori rezultat

Istorija i batch detalji ostaju sekundarni.

- [ ] **Step 3: Benchmark/Observability/Compatibility preuredi kao analiticke ekrane**

Ne smeju vise izgledati kao mesto sa deset ravnopravnih callout-a. Primarno:
- kratak sazetak
- glavni signal
- detalji na otvaranje

- [ ] **Step 4: ProjectMemory i Help uskladi sa novim shell ritmom**

Ove stranice treba da ostanu citljive, ali ne kao visoke uske kolone.

- [ ] **Step 5: Pokreni frontend test**

Run: `python -m pytest tests\\test_control_center_frontend_dist.py -q`

Expected:
- shared action jezik i dalje prisutan posle preuredenja vise stranica

- [ ] **Step 6: Commit napredne i sekundarne strane**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/pages/TuningLabPage.tsx frontend/src/pages/CompatibilityPage.tsx frontend/src/pages/BenchmarkPage.tsx frontend/src/pages/ObservabilityPage.tsx frontend/src/pages/ProjectMemoryPage.tsx frontend/src/pages/HelpPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: apply shared ux model to advanced pages"
```

### Task 8: Mobile-first polish, bundle refresh i zavrsna verifikacija

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

- [ ] **Step 1: Prodji kroz breakpointe i ukloni desktop-only lomove**

Posebno proveri:
- navigaciju
- tri glavne zone
- guided flow
- lokalne model kartice
- Project Memory
- OpenCode cockpit

- [ ] **Step 2: Pokreni ciljane frontend regresije**

Run: `python -m pytest tests\\test_control_center_frontend_dist.py -q`

Expected:
- svi frontend bundle testovi prolaze

- [ ] **Step 3: Pokreni puni suite**

Run: `python -m pytest -q`

Expected:
- puni suite prolazi

- [ ] **Step 4: Rebuild frontend**

Run:
- `npm --prefix frontend run build`
  - ili postojecom repo komandom koja generise `frontend_dist`

Expected:
- novi `frontend_dist` asseti su osvezeni bez greske

- [ ] **Step 5: Vizuelno proveri localhost**

Proveri:
- desktop shell
- mobilni narrow width
- Pocetna
- Runtime
- Modeli
- OpenCode
- `Vise` sekundarni sloj

- [ ] **Step 6: Commit finalni UX rewrite bundle**

```bash
git add frontend/src/styles.css src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets
git commit -m "feat: complete runtimepilot ux rewrite"
```

### Task 9: Zavrsni release koraci

**Files:**
- Modify: `pyproject.toml`
- Create/Modify: `docs/release-validation/<date>-runtimepilot-ux-rewrite-validation.md`
- Modify: `dist/*`

- [ ] **Step 1: Bump verziju tek kada je UX rewrite stvarno gotov**

- [ ] **Step 2: Napravi release validation zapis**

- [ ] **Step 3: Izgradi wheel i installer**

Run:
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging\\build_windows_installer.ps1 -PythonExe python`

- [ ] **Step 4: Proveri lokalni `/api/status` i frontend bundle**

- [ ] **Step 5: Commit release pripremu**

```bash
git add pyproject.toml docs/release-validation
git commit -m "chore: prepare runtimepilot ux rewrite release"
```
