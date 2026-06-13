# Benchmark Control Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the shipped Benchmark tab with live throughput, averages, historical trend, benchmark batteries, and saved run history backed by the installer-managed runtime.

**Architecture:** Add a native benchmark backend service under the current control-center stack, persist benchmark state under the control-center config root, mount benchmark routes in the FastAPI app, and reconnect the existing Benchmark frontend page to those routes. Live signal comes from the active runtime `/slots` endpoint; explicit benchmark runs use controlled runtime completion requests.

**Tech Stack:** FastAPI, Python service modules, runtime HTTP polling via `urllib`, React/Vite frontend, pytest, packaged `frontend_dist`.

---

### Task 1: Define benchmark state paths in control-center config

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\config.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_benchmark.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run the benchmark config test to verify it fails**
- [ ] **Step 3: Add benchmark path properties to `ControlCenterConfig`**
- [ ] **Step 4: Run the benchmark config test to verify it passes**

### Task 2: Implement benchmark service state and summary payload

**Files:**
- Create: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\benchmark_service.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_benchmark.py`

- [ ] **Step 1: Write failing tests for default summary payload, averages, and persisted history loading**
- [ ] **Step 2: Run the targeted benchmark service tests to verify they fail**
- [ ] **Step 3: Implement minimal benchmark state helpers and `load_benchmark_summary()`**
- [ ] **Step 4: Run the targeted benchmark service tests to verify they pass**

### Task 3: Add live `/slots` throughput sampling and live history

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\benchmark_service.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_benchmark.py`

- [ ] **Step 1: Write failing tests for `/slots` polling, live history retention, and merged signal history**
- [ ] **Step 2: Run the targeted live-signal tests to verify they fail**
- [ ] **Step 3: Implement live throughput sampling and history retention**
- [ ] **Step 4: Run the targeted live-signal tests to verify they pass**

### Task 4: Implement benchmark batteries and run-state lifecycle

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\services\benchmark_service.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_benchmark.py`

- [ ] **Step 1: Write failing tests for saving/loading batteries and default restore**
- [ ] **Step 2: Write failing tests for selected run/battery run state transitions**
- [ ] **Step 3: Run the targeted battery/run-state tests to verify they fail**
- [ ] **Step 4: Implement minimal battery persistence and run-state transitions**
- [ ] **Step 5: Run the targeted battery/run-state tests to verify they pass**

### Task 5: Add benchmark HTTP routes and mount them

**Files:**
- Create: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\routes\benchmark.py`
- Modify: `C:\repo\local-ai-control-center-stable\src\local_ai_control_center_installer\control_center_backend\main.py`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_benchmark_routes.py`

- [ ] **Step 1: Write failing route tests for `/api/benchmark` and its POST actions**
- [ ] **Step 2: Run the targeted route tests to verify they fail**
- [ ] **Step 3: Implement benchmark routes and include router in the app**
- [ ] **Step 4: Run the targeted route tests to verify they pass**

### Task 6: Restore Benchmark tab in the shipped frontend

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\App.tsx`
- Modify: `C:\repo\local-ai-control-center-stable\frontend\src\pages\BenchmarkPage.tsx`
- Test: `C:\repo\local-ai-control-center-stable\tests\test_control_center_frontend_dist.py`

- [ ] **Step 1: Write failing frontend-dist test that expects Benchmark nav to be present in packaged output**
- [ ] **Step 2: Run the targeted frontend-dist test to verify it fails**
- [ ] **Step 3: Restore `Benchmark` in app navigation and make small truth-driven UI adjustments if needed**
- [ ] **Step 4: Build the frontend bundle**
- [ ] **Step 5: Run the targeted frontend-dist test to verify it passes**

### Task 7: End-to-end verification and release

**Files:**
- Modify: `C:\repo\local-ai-control-center-stable\pyproject.toml`
- Modify: `C:\repo\local-ai-control-center-stable\README.md`
- Create: `C:\repo\local-ai-control-center-stable\docs\release-validation\2026-05-24-windows-benchmark-validation.md`

- [ ] **Step 1: Run targeted benchmark tests**
- [ ] **Step 2: Run full test suite**
- [ ] **Step 3: Run frontend build**
- [ ] **Step 4: Run `python -m build`**
- [ ] **Step 5: Run Windows installer build**
- [ ] **Step 6: Do a local control-center smoke against the live panel or local test panel**
- [ ] **Step 7: Bump version and update README release references**
- [ ] **Step 8: Write validation note with exact evidence**


