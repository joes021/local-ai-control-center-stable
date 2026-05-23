# Windows Control Panel Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the existing Local AI Control Center panel into this installer/runtime repo so the Windows installer produces a finished product that installs dependencies, launches the control panel, shows truthful runtime/network/model state, and reliably manages models and settings.

**Architecture:** Transplant the existing `local-ai-control-center` frontend and backend shell into this repo, but replace backend truth with installer-managed artifacts/config from this repository. Reuse only the useful monitoring primitives from `llm-service-monitor` for live runtime and network status. Build and package the frontend as static assets inside the Python installer package so the final installed product launches one coherent local control panel.

**Tech Stack:** Python 3.11+, FastAPI, packaged static frontend assets, Vite/React TypeScript frontend, pytest, PowerShell launcher, existing installer manifests and runtime/OpenCode/TurboQuant modules.

---

### Task 1: Lock in panel source import skeleton

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/components/*.tsx`
- Create: `frontend/src/pages/*.tsx`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/types.ts`
- Create: `src/local_ai_control_center_installer/control_center_backend/__init__.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Test: `tests/test_control_center_package.py`

- [ ] **Step 1: Write the failing package-layout test**

```python
from pathlib import Path


def test_control_center_source_tree_exists():
    assert Path("frontend/src/App.tsx").is_file()
    assert Path("src/local_ai_control_center_installer/control_center_backend/main.py").is_file()
```

- [ ] **Step 2: Run the failing test**

Run: `python -m pytest tests/test_control_center_package.py -q`
Expected: FAIL because the frontend/backend shell does not exist yet.

- [ ] **Step 3: Copy the minimal frontend/backend shell from the reference repo**

Bring over:
- `frontend/index.html`
- `frontend/src/*`
- minimal backend entry shell

Do not change behavior yet beyond import-path adaptation and package-local naming.

- [ ] **Step 4: Add minimal backend app factory**

Create `control_center_backend/main.py` with:
- a FastAPI app
- `/health`
- placeholder router registration

- [ ] **Step 5: Re-run the package-layout test**

Run: `python -m pytest tests/test_control_center_package.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend src/local_ai_control_center_installer/control_center_backend tests/test_control_center_package.py
git commit -m "feat: import control panel source skeleton"
```

### Task 2: Package and serve the transplanted frontend

**Files:**
- Modify: `pyproject.toml`
- Modify: `packaging/build_windows_installer.ps1`
- Create: `src/local_ai_control_center_installer/control_center_backend/static/`
- Create: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/.gitkeep`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Create: `tests/test_control_center_static_serving.py`

- [ ] **Step 1: Write failing static-serving tests**

```python
from fastapi.testclient import TestClient
from local_ai_control_center_installer.control_center_backend.main import app


def test_control_center_serves_frontend_shell():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Local AI Control Center" in response.text
```

- [ ] **Step 2: Run the failing test**

Run: `python -m pytest tests/test_control_center_static_serving.py -q`
Expected: FAIL because the frontend is not yet served from the backend package.

- [ ] **Step 3: Add frontend build output packaging contract**

Implement:
- a known frontend build output directory
- package-data rules for built assets
- backend static serving for `/` and `/assets/*`

- [ ] **Step 4: Add frontend build command documentation to the packaging flow**

Ensure the Windows packaging flow knows how to build the frontend before bundling the installer.

- [ ] **Step 5: Run the static-serving tests**

Run: `python -m pytest tests/test_control_center_static_serving.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml packaging/build_windows_installer.ps1 src/local_ai_control_center_installer/control_center_backend tests/test_control_center_static_serving.py
git commit -m "feat: package and serve control panel frontend"
```

### Task 3: Re-anchor status and server routes on installer-managed truth

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/services/status_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/server_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/network_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/status.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/server.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Test: `tests/test_control_center_status.py`
- Test: `tests/test_control_center_server.py`

- [ ] **Step 1: Write failing status-route tests**

Cover:
- installer config present + runtime healthy -> `started`
- process exists but health not ready -> `warming`
- no process -> `stopped`
- tailscale missing -> `not exposed`
- runtime identity and port come from persisted installer config

- [ ] **Step 2: Run the focused failing tests**

Run: `python -m pytest tests/test_control_center_status.py tests/test_control_center_server.py -q`
Expected: FAIL because the backend still lacks installer-managed status logic.

- [ ] **Step 3: Implement installer-truth status service**

Use existing repo truth:
- `active-model.json`
- `runtime-endpoint.json`
- runtime artifact metadata
- TurboQuant metadata
- existing server/runtime verification helpers where possible

- [ ] **Step 4: Implement server actions**

Implement bounded:
- start
- stop
- restart

They must operate only on installer-managed runtime paths and return truthful action results.

- [ ] **Step 5: Run the focused status/server tests**

Run: `python -m pytest tests/test_control_center_status.py tests/test_control_center_server.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/control_center_backend tests/test_control_center_status.py tests/test_control_center_server.py
git commit -m "feat: add installer-managed status and server routes"
```

### Task 4: Harden the model table and model download pipeline

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/services/models_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/models.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/workers/model_download_worker.py`
- Modify: `frontend/src/pages/ModelsPage.tsx`
- Modify: `frontend/src/components/ModelDownloadProgressCard.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Test: `tests/test_control_center_models_service.py`
- Test: `tests/test_control_center_model_downloads.py`

- [ ] **Step 1: Write failing model-list truth tests**

Cover:
- curated + local rows merge deterministically
- active model is marked from `active-model.json`
- installed rows reflect actual disk presence
- no duplicate IDs across sources

- [ ] **Step 2: Write failing model-download flow tests**

Cover:
- queued download gets progress state
- successful download registers in the model table
- failed download reports an actionable error
- active model propagation updates OpenCode-facing config after activation

- [ ] **Step 3: Run the failing models tests**

Run: `python -m pytest tests/test_control_center_models_service.py tests/test_control_center_model_downloads.py -q`
Expected: FAIL

- [ ] **Step 4: Implement canonical model registry logic**

Use installer-managed model artifacts and configured extra model paths as the truth source.

- [ ] **Step 5: Implement background download worker and progress polling**

Requirements:
- streaming progress
- speed
- ETA
- final result
- no stale “downloading” state after completion/failure

- [ ] **Step 6: Wire frontend `Models` page to the new contract**

Preserve the existing UX where possible, but remove assumptions tied to legacy state files.

- [ ] **Step 7: Run the models tests**

Run: `python -m pytest tests/test_control_center_models_service.py tests/test_control_center_model_downloads.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/ModelsPage.tsx frontend/src/components/ModelDownloadProgressCard.tsx frontend/src/lib/api.ts frontend/src/lib/types.ts src/local_ai_control_center_installer/control_center_backend tests/test_control_center_models_service.py tests/test_control_center_model_downloads.py
git commit -m "feat: harden control panel model management"
```

### Task 5: Rebuild settings, runtime config, TurboQuant, and OpenCode preset persistence on installer truth

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/opencode_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/turboquant_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/settings.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/opencode.py`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Test: `tests/test_control_center_settings.py`
- Test: `tests/test_control_center_opencode.py`
- Test: `tests/test_control_center_turboquant.py`

- [ ] **Step 1: Write failing settings-contract tests**

Cover:
- global defaults persistence
- active-model override persistence
- runtime preference persistence
- working directory persistence
- preset save/load/delete persistence

- [ ] **Step 2: Write failing config side-effect tests**

Cover:
- saving settings updates managed OpenCode config when needed
- saving runtime preference does not silently corrupt installer-managed runtime selection
- TurboQuant presets normalize values consistently

- [ ] **Step 3: Run the failing settings tests**

Run: `python -m pytest tests/test_control_center_settings.py tests/test_control_center_opencode.py tests/test_control_center_turboquant.py -q`
Expected: FAIL

- [ ] **Step 4: Implement normalized settings contract**

Persist only validated, normalized payloads and keep clear boundaries between:
- installer truth
- panel defaults
- per-model overrides
- OpenCode step presets
- TurboQuant presets

- [ ] **Step 5: Wire the Settings and OpenCode pages to the new contract**

Preserve current page UX while replacing legacy persistence behavior.

- [ ] **Step 6: Run the focused settings tests**

Run: `python -m pytest tests/test_control_center_settings.py tests/test_control_center_opencode.py tests/test_control_center_turboquant.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/pages/OpenCodePage.tsx frontend/src/lib/api.ts frontend/src/lib/types.ts src/local_ai_control_center_installer/control_center_backend tests/test_control_center_settings.py tests/test_control_center_opencode.py tests/test_control_center_turboquant.py
git commit -m "feat: add reliable panel settings and presets"
```

### Task 6: Integrate logs, repair, updates, and installer auto-launch

**Files:**
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/logs.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/repair.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/updates.py`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/windows_release.py`
- Modify: `bootstrap/install.ps1`
- Modify: `README.md`
- Test: `tests/test_control_center_updates.py`
- Test: `tests/test_control_center_repair.py`
- Test: `tests/test_installer_panel_launch.py`

- [ ] **Step 1: Write failing auto-launch tests**

Cover:
- successful install launches control panel URL
- final installer message includes the panel URL
- failed install does not falsely claim panel launch success

- [ ] **Step 2: Write failing logs/repair/update tests**

Cover:
- logs route surfaces installer logs
- repair route reports truthful outcome
- update route maintains progress contract

- [ ] **Step 3: Run the failing installer/panel tests**

Run: `python -m pytest tests/test_control_center_updates.py tests/test_control_center_repair.py tests/test_installer_panel_launch.py -q`
Expected: FAIL

- [ ] **Step 4: Implement installer auto-launch contract**

After successful product completion:
- start control center backend if needed
- open panel URL
- print clear post-install instructions

- [ ] **Step 5: Implement logs/repair/updates routes**

Reuse stable pieces where possible, but re-anchor state paths on this repo’s install-root conventions.

- [ ] **Step 6: Run the focused installer/panel tests**

Run: `python -m pytest tests/test_control_center_updates.py tests/test_control_center_repair.py tests/test_installer_panel_launch.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_ai_control_center_installer/main.py src/local_ai_control_center_installer/defaults.py src/local_ai_control_center_installer/windows_release.py bootstrap/install.ps1 README.md src/local_ai_control_center_installer/control_center_backend tests/test_control_center_updates.py tests/test_control_center_repair.py tests/test_installer_panel_launch.py
git commit -m "feat: launch integrated control panel after install"
```

### Task 7: Full integration verification and release readiness

**Files:**
- Modify: any touched files from prior tasks
- Test: `tests/*`

- [ ] **Step 1: Build frontend production assets**

Run:

```bash
cd frontend
npm ci
npm run build
```

Expected: successful Vite build output

- [ ] **Step 2: Run the full Python test suite**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 3: Rebuild the Windows installer**

Run: `powershell -ExecutionPolicy Bypass -File .\\packaging\\build_windows_installer.ps1`
Expected: `LocalAIControlCenterSetup-v<version>.exe` rebuilt successfully

- [ ] **Step 4: Run a real local `.exe` smoke**

Verify:
- install completes
- panel launches
- `/api/status` is live
- server status is truthful
- model table loads

- [ ] **Step 5: Update release notes / README truth**

Document:
- installer now launches the control panel
- supported runtime/model/settings behavior
- known non-blockers if any remain

- [ ] **Step 6: Commit**

```bash
git add frontend README.md packaging build/dist artifacts src tests
git commit -m "feat: complete integrated Windows control panel product"
```
