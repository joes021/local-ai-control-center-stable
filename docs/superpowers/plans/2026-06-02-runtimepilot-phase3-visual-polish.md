# RuntimePilot Phase 3 / Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Učiniti da RuntimePilot rebrand bude stvarno vidljiv kroz ceo portal, uz dosledan srpski UI copy sa pravilnim dijakriticima.

**Architecture:** Zadržati postojeću funkcionalnu strukturu portala, ali pojačati globalni shell (`Layout`, `App`, `styles.css`) i ključne landing sekcije (`Home`, telemetrija, zajedničke state kartice) tako da proizvod više ne izgleda kao stari skin sa novim headerom. Vidljive tekstove i helper copy poravnati na RuntimePilot jezik i ispravne srpske znakove bez menjanja internih tehničkih identifikatora.

**Tech Stack:** React 19, TypeScript, Vite, global CSS theme system, pytest source/bundle regresije, in-app browser za vizuelnu proveru.

---

### Task 1: Test-first zaštita za diakritike i brand shell

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`

- [ ] **Step 1: Napisati failing test za ključni RuntimePilot visual shell**
- [ ] **Step 2: Napisati failing test za srpske dijakritike i odsustvo mojibake u ciljanim UI stringovima**
- [ ] **Step 3: Pokrenuti ciljani frontend dist test i potvrditi RED stanje**

### Task 2: Očistiti vidljive copy kvarove

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\pages\BenchmarkPage.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\components\CompatibilityCalculatorPanel.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\tuning_lab_service.py`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\benchmark_service.py`
- Modify: ostali pogođeni frontend/backend copy fajlovi po potrebi
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`

- [ ] **Step 1: Ispraviti ključne “ćelave” ili polomljene stringove koje korisnik zaista vidi**
- [ ] **Step 2: Očistiti targetovane mojibake fallback poruke u backend summary/help copy-ju**
- [ ] **Step 3: Pokrenuti ciljane testove i potvrditi GREEN stanje**

### Task 3: Uvesti pravi RuntimePilot vizuelni uplift

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\components\Layout.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\App.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\pages\HomePage.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\components\TelemetryPanel.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\styles.css`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodati vidljiv brand shell sloj oko hero/navigacije bez rušenja postojećeg toka**
- [ ] **Step 2: Prelomiti home i zajedničke kartice da deluju više kao RuntimePilot sistem, ne samo stari portal**
- [ ] **Step 3: Dodati ili pojačati vizuelne hook-ove koje test može da proveri u source/bundle-u**
- [ ] **Step 4: Pokrenuti ciljani frontend dist test i potvrditi GREEN stanje**

### Task 4: Rebuild, paketovanje i živa verifikacija

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\frontend_dist\*`

- [ ] **Step 1: Rebuild frontend preko lokalnog Node runtime-a**
- [ ] **Step 2: Osvežiti packaged `frontend_dist`**
- [ ] **Step 3: Pokrenuti `python -m pytest tests\\test_control_center_frontend_dist.py -q`**
- [ ] **Step 4: Pokrenuti `python -m pytest -q`**
- [ ] **Step 5: Potvrditi izgled u in-app browseru na `http://127.0.0.1:3210/`**


