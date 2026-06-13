# Windows MTP Merge Release Validation — 2026-05-24

## Scope

Post-merge validation for bringing `codex/mtp-runtime-rd` into `codex/panel-integration`, plus the final fix for Control Center launch truth during installer upgrades.

## Root Cause Closed

- Upgrade validation had a real launcher truth bug when `127.0.0.1:3210` was already owned by a **different install root**.
- `control_center_panel.py` previously treated any `200 /health` response as "this panel is already running", even when the payload belonged to another install root.
- `control_center_runtime.py` then waited for the wrong panel and eventually failed with:
  - `Control Center panel nije odgovorio na /health u predvidjenom roku.`

Closed behavior now:

- panel entry only reuses an existing UI if `/health` matches the expected install root
- installer launch now fails fast with a clear `UI port ... je vec zauzet drugim procesom.` error instead of a misleading timeout

## Automated Verification

### Python tests

Command:

```powershell
python -m pytest -q
```

Result:

- `412 passed in 55.50s`

### Python package build

Command:

```powershell
python -m build
```

Result:

- success
- artifacts built from version `0.4.11`

### Windows installer build

Command:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Result:

- success
- built installer:
  - `dist/LocalAIControlCenterSetup-v0.4.11.exe`

## Installer Smoke

### Scenario

- packaged **upgrade** installer smoke over the existing validation root:
  - `C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5`

### Result

- latest installer report finished with:
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`

Key validated paths:

- `runtime_payload_status = ready`
- `server_verification_status = ready`
- `opencode_verification_status = ready`
- `first_run_status = ready`
- `turboquant_status = ready`
- `control_center_runtime_status = ready`
- `control_center_launch_status = ready`

Install root validated:

- `C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5`

## Tests Added/Updated

- `tests/test_control_center_runtime_deploy.py`
  - foreign listener on UI port now fails fast instead of timing out
- `tests/test_control_center_panel.py`
  - panel entry rejects a foreign panel from another install root on the same port
- `tests/test_control_center_opencode.py`
  - OpenCode foreign-instance test no longer depends on ambient runtime state

## Release Readiness

This validation closes the last known blocker from the merge-and-release path:

- MTP branch merged
- full test suite green
- build green
- packaged Windows installer build green
- packaged upgrade smoke green

Product truth that still remains unchanged:

- MTP models are supported through `llama.cpp + --spec-type draft-mtp`
- TurboQuant still does **not** support the MTP runtime path


