# RuntimePilot Project Memory Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ugraditi `Project Memory` v1 u RuntimePilot tako da korisnik i agent imaju jednu jasnu, vidljivu i trajnu radnu memoriju projekta sa ciljem, pravilima, odlukama, napretkom i sledećim korakom.

**Architecture:** Backend dobija novi `project_memory_service` domen sa JSON persistence slojem i FastAPI rutama za čitanje, kreiranje, ažuriranje i zaključavanje memory zapisa. Frontend dobija novu `Project Memory` stranu pod `Više`, globalni tanki strip u shell-u i osnovne akcije za ručno uređivanje i seed iz task teksta; agent integracija ostaje ograničena na v1 “starter extraction” i prikaz, bez punog automatskog prompt injection sloja.

**Tech Stack:** FastAPI, Python service/routes sloj, JSON persistence u `install_root/config/control-center`, React + TypeScript + Vite frontend, pytest, packaged `frontend_dist`.

---

## File Structure

### Create

- `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\project_memory_service.py`
- `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\routes\project_memory.py`
- `C:\repo\local-ai-control-center-stable\frontend\src\pages\ProjectMemoryPage.tsx`
- `C:\repo\local-ai-control-center-stable\tests\test_control_center_project_memory.py`
- `C:\repo\local-ai-control-center-stable\tests\test_control_center_project_memory_routes.py`

### Modify

- `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\main.py`
- `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\tuning_lab_service.py`
- `C:\repo\local-ai-control-center-stable\frontend\src\App.tsx`
- `C:\repo\local-ai-control-center-stable\frontend\src\components\Layout.tsx`
- `C:\repo\local-ai-control-center-stable\frontend\src\lib\api.ts`
- `C:\repo\local-ai-control-center-stable\frontend\src\lib\types.ts`
- `C:\repo\local-ai-control-center-stable\frontend\src\styles.css`
- `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`

### Responsibilities

- `project_memory_service.py`
  - centralna business logika
  - disk persistence
  - default state
  - lock pravila
  - seed heuristika iz task teksta
- `project_memory.py`
  - HTTP API za summary, full document i edit akcije
- `ProjectMemoryPage.tsx`
  - puna strana za pregled i uređivanje memorije
- `App.tsx` + `Layout.tsx`
  - nova navigaciona tačka i globalni shell strip
- `types.ts` + `api.ts`
  - frontend contract za payload i akcije
- `tuning_lab_service.py`
  - v1 seed hook kada postoji task tekst i cilj
- test fajlovi
  - backend service behavior
  - route contract
  - source + packaged frontend assertions

## Execution Notes

- Pre implementacije obavezno raditi u izolovanom worktree-u ili prethodno odvojiti postojeće nezavršene UI izmene.
- Ovaj plan je za `Phase 1`, ne za full agent memory automation.
- V1 fokus:
  - shell strip
  - full page
  - persistence
  - manual edit
  - lock cilj/pravila
  - seed from task
- Ne uvoditi:
  - embeddings
  - RAG
  - Obsidian sync
  - prompt injection za sve agent tokove

---

### Task 1: Backend Project Memory domen i persistence

**Files:**
- Create: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\project_memory_service.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_project_memory.py`

- [ ] **Step 1: Write the failing service tests**

```python
def test_project_memory_service_returns_default_memory_when_store_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))

    payload = project_memory_service.get_project_memory()

    assert payload["status"] == "idle"
    assert payload["goal"]["text"] == ""
    assert payload["rules"] == []
    assert payload["decisions"] == []
    assert payload["progress"] == []
    assert payload["nextSteps"] == []


def test_project_memory_service_updates_goal_rules_and_next_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))

    project_memory_service.save_project_memory(
        {
            "goal": {"text": "Napraviti playable HTML igru", "locked": True},
            "rules": [{"id": "one-file", "text": "Jedan HTML fajl", "locked": True}],
            "decisions": [{"id": "canvas", "text": "Koristi canvas"}],
            "progress": [{"id": "loop", "text": "Postavljena game loop logika"}],
            "nextSteps": [{"id": "collision", "text": "Dovršiti collision"}],
        }
    )

    payload = project_memory_service.get_project_memory()

    assert payload["goal"]["text"] == "Napraviti playable HTML igru"
    assert payload["goal"]["locked"] is True
    assert payload["rules"][0]["text"] == "Jedan HTML fajl"
    assert payload["nextSteps"][0]["text"] == "Dovršiti collision"


def test_project_memory_seed_from_task_extracts_goal_rules_and_next_step():
    seeded = project_memory_service.seed_project_memory_from_task(
        goal="Napraviti HTML igru",
        task_prompt=\"\"\"Napravi playable HTML igru u jednom fajlu.
Mora imati score i restart.
Prvo dovrši collision i game over flow.\"\"\",
    )

    assert seeded["goal"]["text"] == "Napraviti HTML igru"
    assert any("jednom fajlu" in item["text"].lower() for item in seeded["rules"])
    assert any("score" in item["text"].lower() for item in seeded["rules"])
    assert any("collision" in item["text"].lower() for item in seeded["nextSteps"])
```

- [ ] **Step 2: Run the service tests to verify RED**

Run:
```powershell
python -m pytest tests\test_control_center_project_memory.py -q
```

Expected:
- FAIL because `project_memory_service` ne postoji ili nema tražene funkcije

- [ ] **Step 3: Implement minimal persistence service**

Implementirati minimalne funkcije:

```python
def get_project_memory() -> dict[str, object]:
    ...

def save_project_memory(payload: dict[str, object]) -> dict[str, object]:
    ...

def update_project_memory_section(section: str, payload: dict[str, object]) -> dict[str, object]:
    ...

def seed_project_memory_from_task(goal: str, task_prompt: str) -> dict[str, object]:
    ...
```

Persistence smer:

- folder:
  - `install_root/config/control-center/project-memory/`
- glavni fajl:
  - `current-memory.json`

Minimalni shape:

```json
{
  "status": "active",
  "goal": { "text": "…", "locked": true },
  "rules": [],
  "decisions": [],
  "progress": [],
  "nextSteps": [],
  "updatedAt": "2026-06-04T12:00:00Z",
  "updatedBy": "system"
}
```

- [ ] **Step 4: Re-run the service tests to verify GREEN**

Run:
```powershell
python -m pytest tests\test_control_center_project_memory.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/test_control_center_project_memory.py src/local_ai_control_center_installer/control_center_backend/services/project_memory_service.py
git commit -m "feat: add project memory persistence service"
```

---

### Task 2: FastAPI routes i contract za Project Memory

**Files:**
- Create: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\routes\project_memory.py`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\main.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_project_memory_routes.py`

- [ ] **Step 1: Write failing route tests**

```python
def test_project_memory_route_returns_current_document(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    client = TestClient(app)

    response = client.get("/api/project-memory")

    assert response.status_code == 200
    payload = response.json()
    assert "goal" in payload
    assert "rules" in payload
    assert "nextSteps" in payload


def test_project_memory_seed_route_builds_memory_from_goal_and_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    client = TestClient(app)

    response = client.post(
        "/api/project-memory/seed",
        json={
            "goal": "Napraviti HTML igru",
            "taskPrompt": "Mora imati score. Prvo dovrši collision.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["goal"]["text"] == "Napraviti HTML igru"
    assert any("score" in item["text"].lower() for item in payload["rules"])


def test_project_memory_update_route_persists_manual_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    client = TestClient(app)

    response = client.post(
        "/api/project-memory/save",
        json={
            "goal": {"text": "Sačuvani cilj", "locked": False},
            "rules": [],
            "decisions": [],
            "progress": [],
            "nextSteps": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["summary"].startswith("Project Memory")
```

- [ ] **Step 2: Run route tests to verify RED**

Run:
```powershell
python -m pytest tests\test_control_center_project_memory_routes.py -q
```

Expected:
- FAIL because route ne postoji

- [ ] **Step 3: Implement route file and wire into main**

Dodati rute:

- `GET /api/project-memory`
- `POST /api/project-memory/save`
- `POST /api/project-memory/seed`
- `POST /api/project-memory/lock`

Minimalni response oblik:

```python
{
    "status": "ok",
    "summary": "Project Memory je sačuvan.",
    "goal": {...},
    "rules": [...],
    "decisions": [...],
    "progress": [...],
    "nextSteps": [...],
}
```

- [ ] **Step 4: Re-run route tests to verify GREEN**

Run:
```powershell
python -m pytest tests\test_control_center_project_memory_routes.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/test_control_center_project_memory_routes.py src/local_ai_control_center_installer/control_center_backend/routes/project_memory.py src/local_ai_control_center_installer/control_center_backend/main.py
git commit -m "feat: add project memory api routes"
```

---

### Task 3: Frontend contract, page i shell strip

**Files:**
- Create: `C:\repo\local-ai-control-center-stable\frontend\src\pages\ProjectMemoryPage.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\lib\types.ts`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\lib\api.ts`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\App.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\components\Layout.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\styles.css`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`

- [ ] **Step 1: Write failing frontend dist assertions**

Dodati/izmeniti assertions u `tests/test_control_center_frontend_dist.py` tako da traže:

```python
assert "Project Memory" in app_source
assert "runtimepilot-project-memory-strip" in app_source
assert "Otvori Project Memory" in app_source
assert "Glavni cilj" in project_memory_page_source
assert "Važna pravila" in project_memory_page_source
assert "Već odlučeno" in project_memory_page_source
assert "Napredak" in project_memory_page_source
assert "Sledeće" in project_memory_page_source
```

I u bundled JS/CSS:

```python
assert "Project Memory" in bundled_js
assert "Otvori Project Memory" in bundled_js
assert ".runtimepilot-project-memory-strip" in bundled_css
```

- [ ] **Step 2: Run the targeted frontend test to verify RED**

Run:
```powershell
python -m pytest tests\test_control_center_frontend_dist.py -q
```

Expected:
- FAIL because nova strana i strip još ne postoje

- [ ] **Step 3: Add frontend types and API helpers**

U `types.ts` dodati:

```ts
export type ProjectMemoryEntry = {
  id: string;
  text: string;
  locked?: boolean;
};

export type ProjectMemoryPayload = {
  status: string;
  summary?: string;
  goal: { text: string; locked: boolean };
  rules: ProjectMemoryEntry[];
  decisions: ProjectMemoryEntry[];
  progress: ProjectMemoryEntry[];
  nextSteps: ProjectMemoryEntry[];
  updatedAt?: string;
  updatedBy?: string;
};
```

U `api.ts` dodati:

```ts
export async function fetchProjectMemory(): Promise<ProjectMemoryPayload> { ... }
export async function saveProjectMemory(payload: ProjectMemoryPayload): Promise<ProjectMemoryPayload> { ... }
export async function seedProjectMemory(goal: string, taskPrompt: string): Promise<ProjectMemoryPayload> { ... }
```

- [ ] **Step 4: Implement `ProjectMemoryPage.tsx`**

Strana mora imati:

- naslov `Project Memory`
- 5 sekcija:
  - `Glavni cilj`
  - `Važna pravila`
  - `Već odlučeno`
  - `Napredak`
  - `Sledeće`
- osnovna dugmad:
  - `Sačuvaj`
  - `Zaključaj cilj`
  - `Dodaj pravilo`
  - `Dodaj sledeći korak`

V1 UX pravilo:

- jednostavno
- čitljivo
- bez komplikovanih nested editora

- [ ] **Step 5: Add global strip and navigation entry**

U `App.tsx`:

- dodati novi `PageKey`, npr. `projectMemory`
- ubaciti ga u `Više`
- dodati globalni strip iznad radne zone ili odmah iznad `Živih resursa`

Strip treba da prikazuje:

- `Cilj`
- `Sledeće`
- `Napredak`
- dugme `Otvori Project Memory`

Primer UI copy:

- `Cilj: Napraviti playable HTML igru`
- `Sledeće: Dovršiti collision`
- `Napredak: 3 stavke`

- [ ] **Step 6: Style the page and strip**

U `styles.css` dodati klase tipa:

- `.runtimepilot-project-memory-strip`
- `.project-memory-grid`
- `.project-memory-card`
- `.project-memory-list`
- `.project-memory-actions`

Vizuelni smer:

- isto RuntimePilot okruženje
- ne nova “teška” hero zona
- kartice moraju biti mirne i pregledne

- [ ] **Step 7: Build frontend and refresh packaged `frontend_dist`**

Run:
```powershell
python -m pytest tests\test_control_center_frontend_dist.py -q
```

Ako test i dalje pada zbog stale bundle-a:

```powershell
$node = 'C:\Users\<user>\.cache\<bundled-runtime-cache>\codex-primary-runtime\dependencies\node\bin\node.exe'
Push-Location frontend
& $node '.\node_modules\typescript\bin\tsc' -b
& $node '.\node_modules\vite\bin\vite.js' build
Pop-Location
Copy-Item frontend\dist\* src\local_ai_control_center_installer\control_center_backend\frontend_dist -Recurse -Force
```

Expected:
- targeted frontend test PASS

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/pages/ProjectMemoryPage.tsx frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py src/local_ai_control_center_installer/control_center_backend/frontend_dist
git commit -m "feat: add project memory page and shell strip"
```

---

### Task 4: Manual edit flow i lock ponašanje

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\project_memory_service.py`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\routes\project_memory.py`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\pages\ProjectMemoryPage.tsx`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_project_memory.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_project_memory_routes.py`

- [ ] **Step 1: Add failing lock behavior tests**

```python
def test_locked_goal_is_not_rewritten_by_seed_update(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))
    project_memory_service.save_project_memory(
        {
            "goal": {"text": "Zaključani cilj", "locked": True},
            "rules": [],
            "decisions": [],
            "progress": [],
            "nextSteps": [],
        }
    )

    payload = project_memory_service.seed_project_memory_from_task(
        goal="Novi cilj",
        task_prompt="Promeni smer rada",
        merge_into_current=True,
    )

    assert payload["goal"]["text"] == "Zaključani cilj"
```

- [ ] **Step 2: Run tests to verify RED**

Run:
```powershell
python -m pytest tests\test_control_center_project_memory.py tests\test_control_center_project_memory_routes.py -q
```

Expected:
- FAIL because lock merge pravilo još nije implementirano

- [ ] **Step 3: Implement lock-aware save/update behavior**

Pravila:

- zaključan `goal` se ne prepisuje seed-om
- zaključana `rule` stavka se ne briše automatski
- ručni korisnički `save` sme da menja zaključano samo ako eksplicitno menja lock stanje

- [ ] **Step 4: Add simple frontend lock controls**

U `ProjectMemoryPage.tsx`:

- checkbox ili toggle za `Zaključaj cilj`
- lock indikator za pravila
- vidljiv tekst:
  - `Zaključano`
  - `Agent ovo ne treba da menja automatski`

- [ ] **Step 5: Re-run route and service tests**

Run:
```powershell
python -m pytest tests\test_control_center_project_memory.py tests\test_control_center_project_memory_routes.py -q
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```powershell
git add tests/test_control_center_project_memory.py tests/test_control_center_project_memory_routes.py src/local_ai_control_center_installer/control_center_backend/services/project_memory_service.py src/local_ai_control_center_installer/control_center_backend/routes/project_memory.py frontend/src/pages/ProjectMemoryPage.tsx
git commit -m "feat: add project memory lock behavior"
```

---

### Task 5: Basic task seeding from Tuning Lab

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\tuning_lab_service.py`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\project_memory_service.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_tuning_lab.py`

- [ ] **Step 1: Write a failing Tuning Lab seed integration test**

```python
def test_tuning_lab_queue_seeds_project_memory_from_goal_and_task(tmp_path, monkeypatch):
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(tmp_path / "install-root"))

    run = tuning_lab_service.queue_experiment(
        {
            "name": "Game task",
            "goal": "Napraviti HTML igru",
            "taskPrompt": "Mora imati score. Prvo uradi collision.",
            "workingDirectory": str(tmp_path),
            "successChecks": [],
            "slots": [],
        }
    )

    payload = project_memory_service.get_project_memory()

    assert payload["goal"]["text"] == "Napraviti HTML igru"
    assert any("score" in item["text"].lower() for item in payload["rules"])
```

- [ ] **Step 2: Run the targeted test to verify RED**

Run:
```powershell
python -m pytest tests\test_control_center_tuning_lab.py -q
```

Expected:
- FAIL because Tuning Lab još ne seed-uje Project Memory

- [ ] **Step 3: Implement minimal Tuning Lab hook**

Pravilo za v1:

- kada korisnik queue-uje novi run sa jasnim `goal` i `taskPrompt`
- sistem može da osveži aktivni `Project Memory`
- ali samo ako goal nije zaključan

Nema još:

- slot-level memory
- full agent transcript summarization
- drift analyzer

- [ ] **Step 4: Re-run targeted Tuning Lab test**

Run:
```powershell
python -m pytest tests\test_control_center_tuning_lab.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/test_control_center_tuning_lab.py src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py src/local_ai_control_center_installer/control_center_backend/services/project_memory_service.py
git commit -m "feat: seed project memory from tuning lab tasks"
```

---

### Task 6: Final verification, packaged frontend, and help touchpoint

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\pages\HelpPage.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`

- [ ] **Step 1: Add one short Help mention for Project Memory**

Dodati u `Pomoć`:

- šta je `Project Memory`
- zašto pomaže kada agent radi duže
- gde se otvara

Primer teksta:

```tsx
<p>
  Project Memory čuva cilj, pravila, odluke, napredak i sledeći korak projekta,
  tako da agent manje luta kada task traje dugo.
</p>
```

- [ ] **Step 2: Rebuild frontend and refresh packaged assets**

Run:
```powershell
$node = 'C:\Users\<user>\.cache\<bundled-runtime-cache>\codex-primary-runtime\dependencies\node\bin\node.exe'
Push-Location frontend
& $node '.\node_modules\typescript\bin\tsc' -b
& $node '.\node_modules\vite\bin\vite.js' build
Pop-Location
Copy-Item frontend\dist\* src\local_ai_control_center_installer\control_center_backend\frontend_dist -Recurse -Force
```

Expected:
- novi bundle prisutan u `frontend_dist/assets`

- [ ] **Step 3: Run targeted and full verification**

Run:
```powershell
python -m pytest tests\test_control_center_project_memory.py tests\test_control_center_project_memory_routes.py tests\test_control_center_frontend_dist.py tests\test_control_center_tuning_lab.py -q
python -m pytest -q
```

Expected:
- svi ciljani testovi PASS
- puni suite PASS

- [ ] **Step 4: Optional live smoke check**

Run:
```powershell
Invoke-WebRequest http://127.0.0.1:3210/ -UseBasicParsing | Select-Object -ExpandProperty Content
```

Vizuelno proveriti:

- `Više -> Project Memory`
- shell strip sa `Cilj` i `Sledeće`
- `Otvori Project Memory`
- osnovne save/lock akcije

- [ ] **Step 5: Final commit**

```powershell
git add frontend/src/pages/HelpPage.tsx frontend/src/pages/ProjectMemoryPage.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/lib/api.ts frontend/src/lib/types.ts frontend/src/styles.css src/local_ai_control_center_installer/control_center_backend/main.py src/local_ai_control_center_installer/control_center_backend/routes/project_memory.py src/local_ai_control_center_installer/control_center_backend/services/project_memory_service.py src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py tests/test_control_center_project_memory.py tests/test_control_center_project_memory_routes.py tests/test_control_center_frontend_dist.py tests/test_control_center_tuning_lab.py src/local_ai_control_center_installer/control_center_backend/frontend_dist
git commit -m "feat: add RuntimePilot project memory phase 1"
```

---

## Recommended Implementation Order

1. Task 1 — backend persistence
2. Task 2 — API routes
3. Task 3 — frontend page + strip
4. Task 4 — lock behavior
5. Task 5 — Tuning Lab seed hook
6. Task 6 — final verification and help mention

## Success Criteria

Phase 1 se smatra završenim kada:

- postoji stalni `Project Memory` strip u RuntimePilot shell-u
- korisnik može da otvori punu `Project Memory` stranu
- vidi svih 5 sekcija
- može ručno da sačuva promene
- može da zaključa cilj i pravila
- `Tuning Lab` task može da seed-uje memory osnovu
- frontend bundle i backend API rade lokalno
- ciljani i puni testovi prolaze

## Non-Goals for This Plan

Ovaj plan ne pokriva:

- automatsko summarizovanje kompletnog `OpenCode` transcript-a
- per-slot memory za svaki Tuning Lab slot
- drift warning engine
- workflow-based memory policies
- Obsidian sync
- RAG / embeddings / graph memory

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-runtimepilot-project-memory-phase1.md`.

Recommended next move:

- **Inline Execution** using `superpowers:executing-plans`, because Phase 1 has a clean linear dependency chain and should stay under one ownership context.


