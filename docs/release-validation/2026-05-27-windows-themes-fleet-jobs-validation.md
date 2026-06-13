# Windows Themes + Fleet + Jobs Validation

Date: 2026-05-27
Branch: `codex/panel-integration`
Version validated: `0.4.39`

## Scope

This slice closes the requested Windows-only product expansion before any Linux follow-up:

- named color themes with installer-managed persistence
- workflow presets as first-class product behavior
- observability page
- fleet / remote machines workspace
- scheduled jobs / automations workspace
- knowledge workspace polish with collections, tags, citations, and export

## Git safety checkpoint

Before feature work continued, the branch already had a pushed recovery tag:

- `checkpoint-v0.4.38-before-themes-fleet-jobs`

## Five polish rounds

1. Test -> Fleet
   - wrote failing tests for config path, backend service, and frontend presence
   - implemented fleet registry, remote refresh, and `Fleet` tab
   - targeted tests passed

2. Test -> Jobs + Knowledge
   - wrote failing tests for jobs registry/service and knowledge collections/tags behavior
   - implemented jobs scheduler, `Jobs` tab, workflow-aware job kinds, and knowledge metadata filters
   - targeted tests passed

3. Improvement -> platform polish
   - migrated backend scheduler lifecycle from deprecated `on_event` hooks to FastAPI lifespan
   - reran full `pytest`
   - result: warnings removed and suite stayed green

4. Test -> frontend contract
   - ran TypeScript build and Vite build
   - fixed `SettingsPage.tsx` nullability + preset state issues
   - synced fresh `frontend/dist` into packaged `frontend_dist`
   - reran frontend dist tests

5. Test -> real installer / local machine
   - built Python artifacts
   - built Windows installer
   - upgraded this machine with `LocalAIControlCenterSetup-v0.4.39.exe`
   - verified registry version, installer report, live `/api/status`, and live API endpoints for new workspaces

## Verification evidence

### Automated

- `python -m pytest -q`
  - `502 passed`
- `python -m pytest tests\test_control_center_frontend_dist.py -q`
  - `38 passed`
- `node .\node_modules\typescript\bin\tsc -b`
  - success
- `node .\node_modules\vite\bin\vite.js build`
  - success
- `python -m build`
  - success
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python`
  - success

### Local installer truth

Latest temp installer report confirmed:

- `product_installation_status = complete`
- `first_run_status = ready`
- `control_center_launch_status = ready`
- `runtime_payload_status = ready`
- `server_verification_status = ready`
- `opencode_verification_status = ready`

Registry confirmed:

- `DisplayName = Local AI Control Center`
- `DisplayVersion = 0.4.39`
- `InstallLocation = C:\Users\<user>\LocalAIControlCenter`

Live local panel confirmed:

- `http://127.0.0.1:3210/api/status`
  - `version = 0.4.39`
- live root served:
  - `/assets/index-wBsiXY34.js`
  - `/assets/index-BrzXzCPW.css`
- live API smoke returned `200` for:
  - `/api/fleet`
  - `/api/jobs`
  - `/api/observability`
  - `/api/knowledge`

Bundle smoke confirmed presence of new product strings:

- `Fleet`
- `Jobs`
- `Workflows`
- `Workflow workspace`
- `Remote machines`
- `Scheduled jobs`
- `Knowledge workspace`
- `Token Pulse`

## Shipped result

New installer built locally:

- `dist/LocalAIControlCenterSetup-v0.4.39.exe`

Python artifacts built locally:

- `dist/local_ai_control_center_installer-0.4.39-py3-none-any.whl`
- `dist/local_ai_control_center_installer-0.4.39.tar.gz`

## Honest remaining limits

- Fleet currently focuses on registry + refresh + remote snapshot truth; it is not yet a full remote control shell.
- Jobs run while the Control Center backend is active; they are not yet backed by Windows Task Scheduler.
- Knowledge export is frontend-driven from the current answer payload, not yet a dedicated backend export route.


