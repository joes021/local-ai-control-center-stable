# Knowledge / Documents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodati prvi installer-managed Knowledge/Documents workspace sa lokalnim indeksiranjem, query-jem i answer tokom nad dokumentima.

**Architecture:** Uvodi se SQLite FTS indeks, JSON truth fajlovi za izvore i istoriju, novi backend `knowledge_service` i posebna `Knowledge` stranica u panelu. Answer tok deli isti lokalni runtime i po potrebi koristi postojeci shared web-search sloj.

**Tech Stack:** FastAPI, SQLite (`sqlite3`), standard library ZIP/XML parser za `docx`, `pypdf` za PDF, React/Vite, pytest.

---

### Task 1: Zakljucati config i state contract

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Test: `tests/test_control_center_knowledge.py`

- [ ] Dodati failing test za nove knowledge putanje u config-u
- [ ] Dodati `knowledge_sources_path`, `knowledge_history_path` i `knowledge_index_path`
- [ ] Pokrenuti ciljani test

### Task 2: Napraviti backend knowledge servis

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/services/knowledge_service.py`
- Modify: `pyproject.toml`
- Test: `tests/test_control_center_knowledge.py`

- [ ] Dodati failing testove za source registry, indexing, query i answer metadata
- [ ] Implementirati source registry i SQLite indeks
- [ ] Implementirati ekstrakciju teksta za plain text, `docx` i `pdf`
- [ ] Implementirati `documents-only`, `documents+web` i `web-only` answer put
- [ ] Pokrenuti ciljane testove

### Task 3: Izloziti Knowledge API rute

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/knowledge.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Test: `tests/test_control_center_knowledge_routes.py`

- [ ] Dodati failing route testove za summary, add/remove source, reindex, query i answer
- [ ] Implementirati rute
- [ ] Pokrenuti ciljane testove

### Task 4: Dodati Knowledge UI

**Files:**
- Create: `frontend/src/pages/KnowledgePage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] Dodati `Knowledge` tab
- [ ] Dodati source list, add/remove/reindex akcije, query i answer sekciju
- [ ] Dodati answer mode izbor: `documents-only`, `documents+web`, `web-only`
- [ ] Rebuildovati frontend i osveziti packaged `frontend_dist`
- [ ] Pokrenuti frontend/source testove

### Task 5: Zatvoriti Windows isporuku

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Create: `docs/release-validation/2026-05-25-windows-knowledge-documents-validation.md`

- [ ] Pokrenuti `python -m pytest -q`
- [ ] Pokrenuti `python -m build`
- [ ] Pokrenuti `packaging/build_windows_installer.ps1 -PythonExe python`
- [ ] Lokalno podici ovu masinu na novu verziju
- [ ] Proveriti zivi `Knowledge` tab i answer tok
- [ ] Commit, push i release


