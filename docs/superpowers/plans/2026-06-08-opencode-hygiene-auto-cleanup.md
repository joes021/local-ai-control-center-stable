# OpenCode Hygiene Auto-Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uvesti automatsko periodično čišćenje disposable OpenCode workspace foldera, uz jasan signal u RuntimePilot UI da je auto-cleanup radio i šta je uradio.

**Architecture:** Dodati mali backend scheduler servis koji u pozadini periodično čisti samo `gui-scratch-*`, `gui-copy-*` i `gui-worktree-*` foldere koji nisu aktivni, plus oportunistički cleanup pre novog izolovanog OpenCode launch-a. Rezultat poslednjeg auto-cleanup ciklusa se čuva u installer-managed JSON state fajl i vraća kroz postojeći hygiene payload da ga Settings UI može prikazati.

**Tech Stack:** Python, FastAPI lifespan, background thread scheduler, React + TypeScript, pytest, packaged frontend_dist.

---

### Task 1: Dodati failing testove za backend auto-cleanup ponašanje

**Files:**
- Modify: `tests/test_control_center_opencode.py`
- Test: `tests/test_control_center_opencode.py`

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run target pytest i potvrditi RED**
- [ ] **Step 3: Dodati minimalni backend kod za scheduler state i auto cleanup**
- [ ] **Step 4: Ponovo pokrenuti target pytest i potvrditi GREEN**

### Task 2: Uvezati auto-cleanup scheduler u backend lifecycle

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/opencode_hygiene_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Test: `tests/test_control_center_opencode.py`

- [ ] **Step 1: Dodati scheduler start/stop interfejs**
- [ ] **Step 2: Uvesti state path za auto-cleanup snapshot**
- [ ] **Step 3: Startovati scheduler iz FastAPI lifespan-a**
- [ ] **Step 4: Verifikovati backend testove**

### Task 3: Prikazati poslednji auto-cleanup rezultat u Settings UI

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodati failing source assertions**
- [ ] **Step 2: Implementirati minimalni UI prikaz**
- [ ] **Step 3: Pokrenuti frontend/source testove**
- [ ] **Step 4: Refine copy da bude potpuno jasno gde se vidi rezultat**

### Task 4: Rebuild i live verifikacija

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

- [ ] **Step 1: Build frontend**
- [ ] **Step 2: Osvežiti packaged frontend_dist**
- [ ] **Step 3: Pokrenuti relevantne pytest suite**
- [ ] **Step 4: Proveriti lokalni live panel na odvojenom portu**
