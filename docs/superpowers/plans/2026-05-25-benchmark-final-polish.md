# Benchmark Final Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dovesti benchmark u potpuno produkciono stanje za Windows control panel: jasan throughput truth, bogatiji metadata sloj, compare/export tok i lokalno potvrđen installer upgrade.

**Architecture:** Benchmark ostaje installer-managed funkcija u postojećem FastAPI backendu i React panelu. Backend postaje izvor istine za run metadata, compare i export payload, dok frontend prikazuje gustu, poštenu analitiku bez izmišljanja signala kada runtime miruje.

**Tech Stack:** Python, FastAPI, React, TypeScript, pytest, Vite, PowerShell, PyInstaller

---

### Task 1: Benchmark Metadata Truth

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\benchmark_service.py`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\status_service.py`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\settings_service.py`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\lib\types.ts`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_benchmark.py`

- [ ] **Step 1: Write failing metadata tests**

Add tests that require benchmark summary and saved runs to include:
- active model file label
- active runtime label
- settings-derived context/output tokens
- active profile / thinking mode
- explicit idle reason when no live sample exists

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `python -m pytest tests/test_control_center_benchmark.py -q`
Expected: FAIL on missing benchmark metadata fields / idle-state contract

- [ ] **Step 3: Implement minimal backend metadata enrichment**

Teach benchmark service to derive run metadata from installer-managed runtime + settings state and include it in:
- `current`
- `liveCurrent`
- `savedRuns`
- `scenarioResults`
- summary-level benchmark payload

- [ ] **Step 4: Run targeted tests to verify pass**

Run: `python -m pytest tests/test_control_center_benchmark.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/control_center_backend/services/benchmark_service.py frontend/src/lib/types.ts tests/test_control_center_benchmark.py
git commit -m "feat: enrich benchmark metadata truth"
```

### Task 2: Compare and Export Backend

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\routes\benchmark.py`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\benchmark_service.py`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\lib\api.ts`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\lib\types.ts`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_benchmark_routes.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_benchmark.py`

- [ ] **Step 1: Write failing compare/export tests**

Add route/service tests that require:
- compare payload for 2+ saved runs
- CSV export payload
- JSON export payload
- graceful errors for missing run ids

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `python -m pytest tests/test_control_center_benchmark.py tests/test_control_center_benchmark_routes.py -q`
Expected: FAIL on missing routes / export / compare behavior

- [ ] **Step 3: Implement minimal compare/export backend**

Add:
- `GET /api/benchmark/compare?runIds=...`
- `GET /api/benchmark/export?format=json|csv`
- backend helpers that normalize saved runs, flatten scenario metrics and produce machine-readable exports

- [ ] **Step 4: Run targeted tests to verify pass**

Run: `python -m pytest tests/test_control_center_benchmark.py tests/test_control_center_benchmark_routes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_ai_control_center_installer/control_center_backend/routes/benchmark.py src/local_ai_control_center_installer/control_center_backend/services/benchmark_service.py frontend/src/lib/api.ts frontend/src/lib/types.ts tests/test_control_center_benchmark.py tests/test_control_center_benchmark_routes.py
git commit -m "feat: add benchmark compare and export backend"
```

### Task 3: Benchmark UI Compare, Export, and Dense Truth

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\pages\BenchmarkPage.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\styles.css`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`

- [ ] **Step 1: Write failing frontend assertions**

Add dist/source assertions for:
- compare controls / compare summary
- export actions
- explicit idle-state copy
- runtime/model metadata visible on saved runs

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -q`
Expected: FAIL on missing benchmark UI strings/contracts

- [ ] **Step 3: Implement compact benchmark UI polish**

Update benchmark page to show:
- current run metadata card
- explicit “runtime idle / no live throughput yet” state
- compare selection for saved runs
- export buttons
- denser saved run cards with model/runtime/context/profile badges

- [ ] **Step 4: Run targeted tests to verify pass**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/BenchmarkPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: polish benchmark compare and export ui"
```

### Task 4: Local Product Validation and Installer Refresh

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\pyproject.toml`
- Modify: `C:\repo\local-ai-control-center-stable\packaging\build_windows_installer.ps1` if validation finds packaging gaps
- Create: `C:\repo\local-ai-control-center-stable\docs\release-validation\2026-05-25-windows-benchmark-final-polish-validation.md`

- [ ] **Step 1: Run full verification**

Run:
- `python -m pytest -q`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`

Expected: all pass, installer artifact generated

- [ ] **Step 2: Upgrade this local machine to the new installer**

Run installer against current local install root and confirm:
- `/api/status` reports the new version
- benchmark tab is visible
- benchmark summary renders
- selected benchmark run completes

- [ ] **Step 3: Run browser-based smoke**

Use in-app browser on `http://127.0.0.1:3210/` and verify:
- Benchmark tab visible
- compare controls visible
- export controls visible
- live idle copy truthful

- [ ] **Step 4: Record validation note**

Write exact commands, artifacts, and observed results to:
- `docs/release-validation/2026-05-25-windows-benchmark-final-polish-validation.md`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml docs/release-validation/2026-05-25-windows-benchmark-final-polish-validation.md
git commit -m "chore: validate benchmark final polish release"
```

### Task 5: GitHub Release Sync

**Files:**
- Create/update artifacts in `C:\repo\local-ai-control-center-stable\dist`

- [ ] **Step 1: Push branch**

Run: `git push origin codex/panel-integration`

- [ ] **Step 2: Create release assets**

Generate:
- versioned `.exe`
- `wheel`
- `tar.gz`
- `SHA256SUMS-v<version>.txt`
- release notes text

- [ ] **Step 3: Publish GitHub release**

Use `gh release create ...`

- [ ] **Step 4: Verify release**

Run:
- `gh release view v<version>`
- confirm `.exe` is attached



