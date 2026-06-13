# Control Center Themes, Fleet, Jobs, Observability, Knowledge, and Workflow Polish Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add theme selection, workflow presets, observability, remote fleet basics, jobs/automation basics, and deeper knowledge ergonomics to the Windows control plane without regressing the current stable runtime/install flow.

**Architecture:** Keep the product as a single installer-managed FastAPI + React application. Extend the existing settings payload for visual themes and workflow defaults, add new backend services/routes for fleet, jobs, and observability, and integrate those capabilities into new or expanded pages in the current panel. Prefer incremental foundations that are shippable now over speculative abstraction.

**Tech Stack:** FastAPI, installer-managed JSON state files, React + TypeScript + Vite, existing benchmark/search/knowledge services, Windows-first local runtime orchestration.

---

### Task 1: Theme System

**Files:**
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/styles.css`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`
- Test: `tests/test_control_center_settings.py`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] Add failing tests for persisted theme selection and themed frontend copy.
- [ ] Extend settings payload/state with named themes and default `dark-chocolate`.
- [ ] Apply theme class/data attribute at the layout root and convert current palette to CSS variables.
- [ ] Add themed options in Settings with names colored to match each theme.
- [ ] Rebuild packaged frontend and verify bundled assets expose theme strings.

### Task 2: Workflow Presets

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/SearchPage.tsx`
- Modify: `frontend/src/pages/KnowledgePage.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`
- Test: `tests/test_control_center_settings.py`

- [ ] Add failing tests for built-in workflow presets and user-facing payload.
- [ ] Define built-in presets such as `Research`, `Code`, `Low VRAM`, `Long context`, `Docs + web`, `Benchmark battery`.
- [ ] Surface current preset and quick-apply actions in Settings and relevant pages.
- [ ] Keep implementation thin by mapping presets onto existing settings/search/knowledge knobs.

### Task 3: Observability

**Files:**
- Create: `frontend/src/pages/ObservabilityPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/observability.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/observability_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Test: `tests/test_control_center_observability.py`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] Add failing tests for observability payload and packaged navigation.
- [ ] Provide CPU, RAM, optional GPU/VRAM, runtime latency snapshot, and crash/restart history summary.
- [ ] Reuse telemetry styling so observability feels like part of the same dashboard language.
- [ ] Keep GPU probing best-effort and truthful when unavailable.

### Task 4: Fleet Base

**Files:**
- Create: `frontend/src/pages/FleetPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/fleet.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/fleet_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Test: `tests/test_control_center_fleet.py`

- [ ] Add failing tests for manual machine registry, refresh, and aggregated status.
- [ ] Implement installer-managed remote machine list with add/remove/refresh.
- [ ] Show per-machine version, runtime, model, health, URLs, update status, and benchmark summary.
- [ ] Keep remote control limited to safe actions at first: open URL, refresh status, compare telemetry.

### Task 5: Jobs / Automations Base

**Files:**
- Create: `frontend/src/pages/JobsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `src/local_ai_control_center_installer/control_center_backend/routes/jobs.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/jobs_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`
- Test: `tests/test_control_center_jobs.py`

- [ ] Add failing tests for CRUD of scheduled jobs and job execution summaries.
- [ ] Support initial job types: benchmark battery, health check, update check.
- [ ] Keep scheduler simple and local-first: persisted jobs + in-process timer loop while panel runs.
- [ ] Surface recent runs and next-run status in the Jobs page.

### Task 6: Knowledge Polish

**Files:**
- Modify: `frontend/src/pages/KnowledgePage.tsx`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/knowledge.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/services/knowledge_service.py`
- Test: `tests/test_control_center_knowledge.py`
- Test: `tests/test_control_center_knowledge_routes.py`

- [ ] Add failing tests for collections, tags, citations, reindex status, and export.
- [ ] Extend source records with collection/tag metadata.
- [ ] Return answer citations and “which docs were used”.
- [ ] Add export of answers with source metadata.

### Task 7: Verification and Release

**Files:**
- Modify as needed: `README.md`
- Add: `docs/release-validation/2026-05-27-control-center-product-expansion-validation.md`

- [ ] Run targeted tests after each subsystem.
- [ ] Rebuild frontend and packaged frontend after UI changes.
- [ ] Run full `pytest`.
- [ ] Build wheel/sdist and Windows installer.
- [ ] Locally upgrade this machine and verify live panel behavior.
- [ ] Push branch and prepare release checkpoint when green.


