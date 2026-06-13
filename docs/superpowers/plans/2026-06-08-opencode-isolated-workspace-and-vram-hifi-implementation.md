# OpenCode Isolated Workspace And VRAM Hi-Fi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uvesti dva ručna OpenCode režima (`direktan` i `izolovan workspace`) i prelomiti `Settings -> VRAM fit` u odobreni hi-fi raspored `menjanje -> primena -> monitoring`.

**Architecture:** Backend dobija eksplicitni `launchMode` za ručno otvaranje OpenCode-a i helper za pripremu izolovanog workspace-a. Frontend uvodi novi akcioni par za OpenCode i novi VRAM fit `mixer + transport + monitoring` raspored bez menjanja osnovne runtime logike.

**Tech Stack:** FastAPI backend, React + TypeScript frontend, pytest, Vite frontend build.

---

### Task 1: OpenCode API i launch režimi

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/opencode.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/opencode_service.py`
- Test: `tests/test_control_center_opencode.py`

- [ ] **Step 1: Napisati failing test za novi `launchMode` payload**
- [ ] **Step 2: Pokrenuti ciljani test i potvrditi da pada zbog starog API potpisa**
- [ ] **Step 3: Dodati `launchMode` u FastAPI request model i proslediti ga servisu**
- [ ] **Step 4: Implementirati `direct` i `isolated` granu u `open_opencode`**
- [ ] **Step 5: Dodati helper za pripremu izolovanog workspace-a i eksplicitni project path za GUI launch**
- [ ] **Step 6: Pokrenuti ciljani test i potvrditi prolaz**

### Task 2: Frontend OpenCode akcije i copy

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Napisati failing frontend test za `Otvori OpenCode` + `Otvori u izolovanom workspace-u`**
- [ ] **Step 2: Pokrenuti ciljani test i potvrditi pad**
- [ ] **Step 3: Proširiti `openOpenCode(...)` API helper da prima `launchMode`**
- [ ] **Step 4: Prebaciti Početnu i OpenCode stranu na direktan + izolovani režim**
- [ ] **Step 5: Očistiti copy da ne tvrdi da je sve terminal CLI tok**
- [ ] **Step 6: Pokrenuti frontend test i potvrditi prolaz**

### Task 3: VRAM fit hi-fi raspored i akcije

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Napisati failing test za `menjanje -> primena -> monitoring` raspored i novu akciju `Primeni postojeće`**
- [ ] **Step 2: Pokrenuti ciljani test i potvrditi pad**
- [ ] **Step 3: Dodati frontend akciju `Primeni postojeće` kao primenu poslednjeg sačuvanog stanja na runtime**
- [ ] **Step 4: Prelomiti VRAM fit markup u tri široka deck reda**
- [ ] **Step 5: Dodati `REC + PLAY` kontrolni jezik i monitoring red**
- [ ] **Step 6: Pokrenuti frontend test i potvrditi prolaz**

### Task 4: Live build i verifikacija

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

- [ ] **Step 1: Pokrenuti puni relevantni pytest skup**
- [ ] **Step 2: Pokrenuti `vite build`**
- [ ] **Step 3: Osvežiti lokalni `frontend_dist`**
- [ ] **Step 4: Proveriti u browseru da rade oba OpenCode režima i novi VRAM fit raspored**


