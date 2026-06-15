# Tuning Lab B-Light Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Učiniti `Tuning Lab` čitljivim kao Početna strana kroz jasniju hijerarhiju modula, bez gubitka postojećih funkcija.

**Architecture:** Zadržati postojeće podatke i akcije, ali preurediti React render hijerarhiju i CSS raspored tako da vrh ekrana daje jasan signal, tri-slot receiver ostane glavni deck, a batch/eksperiment/progres/istorija dobiju čiste sekundarne uloge. Fokus je na TDD proveri prisustva novih shell zona i stabilnom hi-fi layout-u.

**Tech Stack:** React, TypeScript, postojeći RuntimePilot CSS, pytest frontend source regresije

---

### Task 1: Zaključaj novu Tuning Lab hijerarhiju testom

**Files:**
- Modify: `tests/test_control_center_frontend_dist.py`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing test**

Dodati regresioni test koji proverava da `frontend/src/pages/TuningLabPage.tsx` sadrži novu shell hijerarhiju za:

- `Tuning Lab signal i spremnost`
- `Aktivni run cockpit`
- `Tri slota`
- `Batch tok`
- `Eksperiment`
- `Progres i red čekanja`
- `Istorija`

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.12 -m pytest -q tests/test_control_center_frontend_dist.py -k tuning_lab_shell`

Expected: FAIL jer novi shell tekst i/ili struktura još nisu ubačeni.

- [ ] **Step 3: Implement minimal source changes**

Presložiti `frontend/src/pages/TuningLabPage.tsx` tako da nove sekcije postoje bez menjanja API ponašanja.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3.12 -m pytest -q tests/test_control_center_frontend_dist.py -k tuning_lab_shell`

Expected: PASS

### Task 2: Presloži React sekcije u B-light tok

**Files:**
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Move top-level section order**

Premestiti render redosled tako da ide:

1. signal i spremnost
2. cockpit
3. tri slota
4. batch
5. eksperiment
6. progres i red čekanja
7. istorija

- [ ] **Step 2: Strip duplicated explanatory copy**

Smanjiti ponovljene helper blokove i zadržati samo one koji odmah objašnjavaju sledeći klik ili signal.

- [ ] **Step 3: Add/rename section headings to match shell**

Naslove i podnaslove uskladiti sa Početnom i hi-fi jezikom.

- [ ] **Step 4: Update CSS layout**

Dodati ili korigovati stilove za:

- vršni readiness modul
- jasniji deck spacing
- kompaktniji progres modul
- batch / experiment / history vertikalni ritam

### Task 3: Verifikacija i live provera

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/*` (preko build output-a ako treba)

- [ ] **Step 1: Run targeted frontend regression tests**

Run: `py -3.12 -m pytest -q tests/test_control_center_frontend_dist.py -k "tuning_lab or opencode"`

Expected: PASS

- [ ] **Step 2: Build frontend**

Run: `npm --prefix frontend run build`

Expected: successful Vite build

- [ ] **Step 3: Refresh bundled dist if build changes output**

Prekopirati novi build u `src/local_ai_control_center_installer/control_center_backend/frontend_dist`.

- [ ] **Step 4: Verify in local portal**

Otvoriti ili osvežiti lokalni portal i proveriti da Tuning Lab prati Početnu po hijerarhiji i da nijedna akcija nije izgubljena.
