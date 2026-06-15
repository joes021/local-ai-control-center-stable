# RuntimePilot Final UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Završiti poslednji veliki UX/UI polish prolaz kroz RuntimePilot tako da glavni tokovi budu jasni, OpenCode i Tuning Lab dosledni, srpski tekst čist, a ključne strane upotrebljive i na užim širinama.

**Architecture:** Zadržavamo postojeći RuntimePilot shell i postojeće React/Vite strane, ali uvodimo završni audit sloj nad CTA tokovima, sređujemo OpenCode i Tuning Lab rasporede, sistematski čistimo stringove i zatim zaključavamo responsive ponašanje kroz postojeći `styles.css` i bundle regresije.

**Tech Stack:** React 19, TypeScript, Vite 7, centralni CSS u `frontend/src/styles.css`, paketovani frontend u `src/local_ai_control_center_installer/control_center_backend/frontend_dist`, pytest regresije.

---

### Task 1: Uradi action clarity audit nad ključnim stranama

**Files:**
- Modify: `frontend/src/pages/ServerPage.tsx`
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/pages/BrowserPage.tsx`
- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/components/ActionResultPanel.tsx`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] Dodaj regresione provere za „gde se vidi rezultat“ na Runtime, Modeli, OpenCode i Browser stranicama.
- [ ] Prođi CTA-jeve i osiguraj da svaki primarni klik ima jasan rezultat panel ili status karticu u blizini.
- [ ] Uskladi tekstove helper poruka da eksplicitno kažu šta se desilo i koji je sledeći korak.
- [ ] Pokreni ciljane testove za source regresije.

### Task 2: Završi OpenCode UX i napredne kontrole

**Files:**
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/components/CustomSelect.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_opencode_ui_regressions.py`

- [ ] Ukloni preostale raspade u hijerarhiji `signal -> akcije -> rezultat -> napredno`.
- [ ] Poravnaj napredne OpenCode kontrolne grupe tako da preset, bezbednost i autonomija deluju kao jedan hi-fi rack.
- [ ] Reši dropdown overlay/z-index i pozadinu menija u OpenCode sekcijama.
- [ ] Dodaj ili osveži regresije za OpenCode layout i napredne kontrole.

### Task 3: Završi Tuning Lab layout, status i istoriju

**Files:**
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_tuning_lab.py`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] Skrati i reorganizuj Tuning Lab vertikalne zone gde guše čitljivost.
- [ ] Ojačaj signal aktivnog run-a, queue-a i istorije tako da korisnik bez lutanja vidi status.
- [ ] Sredi fine kontrole i Context/Output izbor da zadrže hi-fi osećaj bez lošeg prelamanja.
- [ ] Dodaj regresije za layout i ključne statuse Tuning Lab-a.

### Task 4: Očisti encoding i srpski tekst kroz UI i poruke

**Files:**
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/pages/KnowledgePage.tsx`
- Modify: `frontend/src/pages/BrowserPage.tsx`
- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/pages/HelpPage.tsx`
- Modify: `src/local_ai_control_center_installer/control_center_backend/**`
- Modify: `tests/**`

- [ ] Nađi sve preostale pokvarene stringove sa `Å`, `Ä`, `Â` i sličnim tragovima.
- [ ] Ispravi frontend i backend poruke tako da koriste ispravan srpski prikaz.
- [ ] Dodaj test/regresioni trag koji sprečava povratak očiglednog mojibake-a u ključnim source fajlovima ili bundlu.

### Task 5: Zaključaj responsive/mobile prolaz i osveži bundle

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/pages/BrowserPage.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Refresh: `frontend/dist/**`
- Refresh: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/**`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] Utegni raspored za uži desktop i mobilne širine na ključnim gustim stranicama.
- [ ] Proveri da glavni tok ostaje prvi, a sekundarno pada ispod bez sudaranja i preklapanja.
- [ ] Napravi frontend build i sinhronizuj paketovani bundle.
- [ ] Pokreni pune frontend/regresione testove i završni smoke prolaz.

### Završna verifikacija

**Commands:**
- [ ] `py -3.12 -m pytest -q tests/test_control_center_status.py tests/test_control_center_frontend_dist.py tests/test_control_center_tuning_lab.py tests/test_opencode_ui_regressions.py tests/test_advanced_page_ui_regressions.py`
- [ ] `Push-Location frontend; npm run build; Pop-Location`
- [ ] osvežavanje `src/local_ai_control_center_installer/control_center_backend/frontend_dist`

### Napomena

Pošto je korisnik unapred odobrio punu implementaciju dok nije prisutan, ovaj plan služi kao interni trag za izvođenje i ne čeka dodatni review gate pre početka rada.
