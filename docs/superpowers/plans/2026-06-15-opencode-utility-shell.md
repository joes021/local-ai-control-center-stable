# OpenCode And Utility Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ujednačiti OpenCode, Radne tokove, Flotu i prioritetne servisne strane sa RuntimePilot home-shell/hifi obrascem bez vraćanja starog rail rasporeda.

**Architecture:** Zadržati postojeći page content, ali svakoj ciljanoj strani dodati isti vršni shell sloj: tok rada, status deck i action deck. Za manje servisne strane koristiti lakšu varijantu istog obrasca da se izbegnu prazne površine i duplirane komande.

**Tech Stack:** React, TypeScript, postojeće RuntimePilot shell komponente, Vite build, pytest frontend regression testovi.

---

### Task 1: Mapiraj preostale strane i njihove shell potrebe

**Files:**
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/pages/WorkflowsPage.tsx`
- Modify: `frontend/src/pages/FleetPage.tsx`
- Modify: `frontend/src/pages/LogsPage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Popiši postojeće vršne blokove po strani**

Zabeleži koje strane koriste `PrimaryTabRack`, koje samo `PageFlowCard`, a koje već imaju status/action deck.

- [ ] **Step 2: Odredi minimalni status signal po strani**

Za svaku stranu odaberi 4-5 najvrednijih status kartica koje korisniku odmah govore “šta je aktivno”.

- [ ] **Step 3: Odredi realne akcije po strani**

Ukloni duplirane ili slabo korisne akcije i ostavi samo klikove koji vode na jasan rezultat.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-06-15-opencode-utility-shell.md docs/superpowers/plans/2026-06-15-opencode-utility-shell.md
git commit -m "docs: plan opencode utility shell unification"
```

### Task 2: Prepakuj OpenCode u novi shell

**Files:**
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_opencode_ui_regressions.py`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Napiši ili proširi regression očekivanja za OpenCode vrh**

Dodaj proveru da OpenCode više ne koristi stari vršni raspored i da sadrži status/action deck copy.

- [ ] **Step 2: Pokreni ciljane testove da potvrdiš da očekivanje još ne prolazi**

Run: `python -m pytest tests/test_opencode_ui_regressions.py tests/test_control_center_frontend_dist.py -q`

Expected: bar jedna proverа pada dok novi shell nije implementiran.

- [ ] **Step 3: Zameni `PrimaryTabRack` vršni blok novim shell slojem**

Dodaj `PageFlowCard`, `RuntimePilotStatusDeck` i `RuntimePilotActionDeck`, pa zadrži napredne alate ispod.

- [ ] **Step 4: Dotegni stilove za OpenCode action/status raspored**

Uskladi širine, visine i razmake tako da nema preklapanja i da desni rezultat panel ostane čitljiv.

- [ ] **Step 5: Pokreni ciljane testove ponovo**

Run: `python -m pytest tests/test_opencode_ui_regressions.py tests/test_control_center_frontend_dist.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/OpenCodePage.tsx frontend/src/styles.css tests/test_opencode_ui_regressions.py tests/test_control_center_frontend_dist.py
git commit -m "feat: unify opencode shell"
```

### Task 3: Prepakuj Radne tokove i Flotu

**Files:**
- Modify: `frontend/src/pages/WorkflowsPage.tsx`
- Modify: `frontend/src/pages/FleetPage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodaj failing očekivanja za status/action deck prisustvo**

Proveri da obe strane imaju novi shell copy i da nemaju neugodan bočni action raspored.

- [ ] **Step 2: Pokreni test da potvrdi fail pre implementacije**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -q`

Expected: FAIL na novim string/prostornim očekivanjima.

- [ ] **Step 3: Uvedi status/action deck na Radne tokove**

Vrati pretragu, znanje i benchmark kao action deck, a katalog/editor kao status i skok kartice.

- [ ] **Step 4: Uvedi status/action deck na Flotu**

Na vrhu prikaži broj mašina, poslednji refresh, health signal i throughput, pa akcije za osvežavanje i dodavanje.

- [ ] **Step 5: Uskladi stilove da ostanu iste visine i pune širine**

Posebno proveri da kartice i akcije ne ostavljaju “mrtvu” praznu sredinu.

- [ ] **Step 6: Pokreni testove ponovo**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/WorkflowsPage.tsx frontend/src/pages/FleetPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: align workflow and fleet shell"
```

### Task 4: Dotegni prioritetne servisne strane

**Files:**
- Modify: `frontend/src/pages/LogsPage.tsx`
- Modify: `frontend/src/pages/RepairPage.tsx`
- Modify: `frontend/src/pages/UpdatesPage.tsx`
- Modify: `frontend/src/pages/JobsPage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodaj lagani shell pattern za servisne strane**

Koristi kraći status/action sloj bez nepotrebne kompleksnosti.

- [ ] **Step 2: Poveži akcije sa jasnim mestom rezultata**

Svaka servisna akcija mora da vodi do vidljivog `ActionResultPanel` ili glavnog izlaza ispod.

- [ ] **Step 3: Pokreni frontend regression test**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -q`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LogsPage.tsx frontend/src/pages/RepairPage.tsx frontend/src/pages/UpdatesPage.tsx frontend/src/pages/JobsPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: polish utility service shells"
```

### Task 5: Završna verifikacija i paket

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/**`
- Test: `tests/test_control_center_frontend_dist.py`
- Test: `tests/test_opencode_ui_regressions.py`
- Test: `tests/test_advanced_page_ui_regressions.py`

- [ ] **Step 1: Pokreni frontend build**

Run: `cmd /c "set PATH=C:\\Users\\<user>\\.cache\\<bundled-runtime-cache>\\codex-primary-runtime\\dependencies\\node\\bin;%PATH%&& node_modules\\.bin\\tsc.cmd -b && node_modules\\.bin\\vite.cmd build"`

Expected: build uspešan, bez TypeScript/Vite grešaka.

- [ ] **Step 2: Sinhronizuj `frontend_dist`**

Kopiraj svež `frontend/dist/*` u `src/local_ai_control_center_installer/control_center_backend/frontend_dist`.

- [ ] **Step 3: Pokreni ciljane testove**

Run: `python -m pytest tests/test_control_center_frontend_dist.py tests/test_opencode_ui_regressions.py tests/test_advanced_page_ui_regressions.py -q`

Expected: PASS.

- [ ] **Step 4: Vizuelno proveri OpenCode, Radne tokove i Flotu**

Pregledaj lokalni portal i potvrdi da novi vršni shell ne ostavlja preklapanja ni mrtve zone.

- [ ] **Step 5: Commit**

```bash
git add frontend src/local_ai_control_center_installer/control_center_backend/frontend_dist tests
git commit -m "feat: finish opencode and utility shell unification"
```
