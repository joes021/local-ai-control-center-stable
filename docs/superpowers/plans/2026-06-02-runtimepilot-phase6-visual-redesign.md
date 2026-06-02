# RuntimePilot Phase 6 Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uvesti vidljiv RuntimePilot vizuelni identitet kroz navigaciju, zajedničke sekcije i početni cockpit bez menjanja backend ponašanja.

**Architecture:** Zadržati postojeću React/Vite strukturu, ali dodati jedan mali shared icon/glyph sloj i pojačati postojeće shell komponente umesto velikog prepravljanja svake stranice. Fokus je na komponentama koje se ponavljaju i koje korisnik vidi odmah.

**Tech Stack:** React, TypeScript, Vite, CSS, pytest frontend bundle regresije

---

### Task 1: Zaključaj regresije za nove RuntimePilot vizuelne elemente

**Files:**
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] Dodaj failing test koji očekuje nove RuntimePilot nav/shell/glyph klase i ključne tekstove.
- [ ] Pokreni samo taj test i potvrdi da pada pre implementacije.

### Task 2: Dodaj shared RuntimePilot icon/glyph sloj

**Files:**
- Create: `frontend/src/components/RuntimePilotIcon.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] Dodaj malu internu SVG biblioteku za RuntimePilot ikonice.
- [ ] Uvedi ikonice u navigaciju i shell markere.
- [ ] Pojačaj page shell header da izgleda kao control deck, ne kao običan wrapper.

### Task 3: Pojačaj zajedničke kartice i telemetry

**Files:**
- Modify: `frontend/src/components/PageFlowCard.tsx`
- Modify: `frontend/src/components/TelemetryPanel.tsx`
- Modify: `frontend/src/components/LiveResourceStrip.tsx`
- Modify: `frontend/src/styles.css`

- [ ] Uvedi badge/glyph/marker elemente u zajedničke kartice.
- [ ] Doteraj telemetry hero i signal kartice da budu vizuelno prepoznatljivije.
- [ ] Pojačaj `Žive resurse` tako da se i dalje čitaju brzo, ali izgledaju kao deo istog sistema.

### Task 4: Doteraj početnu kao mission control

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] Pojačaj početni overview raspored sa vizuelno izdvojenim karticama i status akcentima.
- [ ] Zadrži postojeći sadržaj, ali promeni hijerarhiju i atmosferu.

### Task 5: Rebuild, proveri i ispoliraj

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

- [ ] Pokreni ciljane frontend testove.
- [ ] Pokreni puni suite ako ciljani prođu.
- [ ] Rebuild frontend i osveži `frontend_dist`.
- [ ] Vizuelno proveri localhost i doradi sitne probleme pre zatvaranja.
