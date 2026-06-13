# Compatibility Calculator Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ojačati compatibility calculator tako da daje smislen runtime-aware fit procenu za `llama.cpp` i `TurboQuant`, uz jači UI i istinitije preporuke.

**Architecture:** Zadržavamo postojeći `/api/compatibility/*` ugovor, ali širimo backend payload sa runtime breakdown-om i jačom formulom za VRAM/RAM/context/output pressure. Frontend modal se nadograđuje da prikaže najbolji runtime i obe runtime procene bez pravljenja novog flow-a.

**Tech Stack:** Python backend service, FastAPI routes, React/TypeScript frontend, pytest, packaged frontend_dist.

---

### Task 1: Zaključaj novu compatibility payload istinu testovima

**Files:**
- Modify: `tests/test_control_center_compatibility.py`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] Dodaj failing backend test za payload koji sadrži `bestRuntime`, `overallFitStatus` i `runtimeBreakdown`.
- [ ] Dodaj failing backend test da `MTP` model ne može dobiti `TurboQuant` pozitivan fit.
- [ ] Dodaj failing backend test da veliki `context` i `outputTokens` pojačavaju pressure i pogoršavaju fit.
- [ ] Dodaj failing frontend-dist test za novi modal tekst: `Best runtime`, `llama.cpp`, `TurboQuant`, `Output pressure`.
- [ ] Pokreni fokusirane testove i potvrdi da padaju iz očekivanog razloga.

### Task 2: Uvedi runtime-aware fit formulu u backend

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/compatibility_service.py`
- Test: `tests/test_control_center_compatibility.py`

- [ ] Implementiraj helper za normalizovan model profil koji uključuje `mtp`.
- [ ] Implementiraj posebnu procenu za `llama.cpp`.
- [ ] Implementiraj posebnu procenu za `TurboQuant`.
- [ ] Implementiraj zajednički izbor `bestRuntime`.
- [ ] Dodaj `outputPressure` i `headroom` u payload.
- [ ] Veži preporuke uz runtime-aware rezultat.
- [ ] Pokreni fokusirane compatibility testove i potvrdi da prolaze.

### Task 3: Pojačaj modal UI bez širenja flow-a

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/components/CompatibilityCalculatorModal.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] Proširi TypeScript tipove za novi payload.
- [ ] Dodaj `best runtime` summary blok.
- [ ] Dodaj dve runtime kartice sa fit/speed signalima.
- [ ] Dodaj prikaz `output pressure` i `memory headroom`.
- [ ] Zadrži postojeće preporuke i advanced controls.
- [ ] Rebuild frontend i osveži packaged `frontend_dist`.
- [ ] Pokreni frontend dist testove i potvrdi da prolaze.

### Task 4: Završna verifikacija i lokalni smoke

**Files:**
- Add: `docs/release-validation/2026-05-25-windows-compatibility-calculator-validation.md`

- [ ] Pokreni `python -m pytest -q`.
- [ ] Pokreni `python -m build`.
- [ ] Pokreni `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`.
- [ ] Proveri lokalni panel API za compatibility payload na stvarnom modelu.
- [ ] Zapiši validation rezultat u release-validation dokument.

### Task 5: GitHub sync i release

**Files:**
- Modify: `pyproject.toml`

- [ ] Podigni verziju.
- [ ] Builduj novi installer.
- [ ] Lokalno ažuriraj ovu mašinu ako je potrebno za smoke.
- [ ] Commit.
- [ ] Push na `codex/panel-integration`.
- [ ] Napravi GitHub release sa `.exe`, `wheel`, `tar.gz` i `SHA256SUMS`.


