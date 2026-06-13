# Windows Search WSL Clarity Validation

Date: `2026-05-25`
Version: `0.4.27`
Branch: `codex/panel-integration`

## Goal

Make the Search and Settings UI explicit about the two different SearxNG paths:

- managed local SearxNG that the app boots with `Windows + WSL`
- manual SearxNG base URL that does not require WSL

## Code Changes

- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `tests/test_control_center_frontend_dist.py`
- packaged frontend bundle in `src/local_ai_control_center_installer/control_center_backend/frontend_dist`

## Verification

### Targeted bundled-frontend test

Command:

```powershell
python -m pytest tests\test_control_center_frontend_dist.py -q
```

Result:

- `28 passed`

### Full test suite

Command:

```powershell
python -m pytest -q
```

Result:

- `476 passed`

### Python package build

Command:

```powershell
python -m build
```

Result:

- success
- produced:
  - `dist/local_ai_control_center_installer-0.4.27.tar.gz`
  - `dist/local_ai_control_center_installer-0.4.27-py3-none-any.whl`

### Windows installer build

Command:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Result:

- success
- produced:
  - `dist/LocalAIControlCenterSetup-v0.4.27.exe`

## Local Machine Upgrade Validation

Upgrade command:

```powershell
cmd /c "(echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.) | dist\LocalAIControlCenterSetup-v0.4.27.exe"
```

Result:

- installer exited successfully
- local machine upgraded to `0.4.27`

### Registry version

Command:

```powershell
reg query HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalAIControlCenter /v DisplayVersion
```

Result:

- `DisplayVersion = 0.4.27`

### Live panel status

Command:

```powershell
Invoke-RestMethod http://127.0.0.1:3210/api/status | ConvertTo-Json -Depth 8
```

Result:

- `version = 0.4.27`
- `health = ok`

### Live bundled asset check

Commands:

```powershell
Invoke-WebRequest http://127.0.0.1:3210/ -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:3210/assets/index-CvJ78jpO.js -UseBasicParsing
```

Confirmed strings in the served bundle:

- `Managed local SearxNG (Windows + WSL)`
- `Setup managed SearxNG (Windows + WSL)`
- `Manual SearxNG base URL (optional, no WSL)`
- `Open Search settings`

## Final Product Truth

This release does not change the search backend architecture itself.

It makes the shipped UI honest and explicit about the two supported modes:

1. managed local SearxNG via `Windows + WSL`
2. manual SearxNG URL without WSL


