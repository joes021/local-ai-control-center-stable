# Browser Model Table Reliability Implementation Plan

Date: 2026-05-23
Spec: `docs/superpowers/specs/2026-05-23-browser-model-table-reliability-design.md`

## Goal

Restore the integrated `Browser` tab and make internet-backed model browsing and click-`Download` reliable on Windows.

## Task 1: Add failing backend tests for browser catalog and routes

Files:

- Create: `tests/test_control_center_browser_routes.py`
- Create: `tests/test_control_center_browser_catalog_service.py`

Steps:

- add route tests for:
  - `/api/browser/catalog`
  - `/api/browser/catalog/refresh`
  - `/api/browser/catalog/add`
  - `/api/browser/catalog/download`
- add catalog cache tests for:
  - load from cache
  - refresh GGUF-only filtering
  - fit-status persistence
- run focused tests and confirm failure

## Task 2: Implement browser catalog backend

Files:

- Create: `src/local_ai_control_center_installer/control_center_backend/routes/browser.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/browser_catalog_service.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/browser_sources.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/config.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/main.py`

Steps:

- add config path for browser catalog cache
- port and adapt catalog cache service to installer-managed config root
- port and adapt source fetchers for Hugging Face and Unsloth
- include browser router in the active backend app
- make refresh/load responses match the existing frontend `BrowserPage` contract

## Task 3: Harden local model registration and browser download routing

Files:

- Modify: `src/local_ai_control_center_installer/control_center_backend/services/models_service.py`
- Modify: `src/local_ai_control_center_installer/control_center_backend/routes/models.py`
- Modify: `tests/test_control_center_model_downloads.py`
- Extend: `tests/test_control_center_browser_routes.py`

Steps:

- make `add_hf_model` and `add_unsloth_model` return deterministic `localModelId`
- make browser add/download routes reuse those results directly
- keep fallback local-id resolution only as a defensive recovery path
- test that browser direct download reaches the canonical model download worker and surfaces progress/failure truthfully

## Task 4: Add compatibility backend support for internet models

Files:

- Create: `src/local_ai_control_center_installer/control_center_backend/routes/compatibility.py`
- Create: `src/local_ai_control_center_installer/control_center_backend/services/compatibility_service.py`
- Create: `tests/test_control_center_compatibility.py`

Steps:

- implement compatibility check route expected by existing frontend
- support `catalogModelId` and explicit model payloads
- persist last known fit back into browser catalog cache
- add focused tests for check/apply flows

## Task 5: Re-enable Browser tab in the integrated frontend

Files:

- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/pages/BrowserPage.tsx`

Steps:

- restore `Browser` to main navigation
- ensure the page uses the active backend contract without stale endpoints
- verify direct `Download` and `Add to local` UI behavior
- keep `Models` as the installer-managed local catalog

## Task 6: Regression-proof the download UX

Files:

- Modify: `frontend/src/components/ModelDownloadProgressCard.tsx`
- Extend: `tests/test_control_center_model_downloads.py`
- Extend: `tests/test_control_center_browser_routes.py`

Steps:

- verify browser downloads and local downloads share the same progress semantics
- verify `error`, `completed`, and idle states are visible and truthful
- verify no silent failure path remains

## Task 7: Full verification, installer rebuild, and release

Steps:

- run focused browser/model/compatibility tests
- run full `python -m pytest -q`
- rebuild frontend
- rebuild Windows installer
- smoke-test the integrated panel and browser tab locally
- bump version and publish new GitHub release only after the click-`Download` flow is actually working


