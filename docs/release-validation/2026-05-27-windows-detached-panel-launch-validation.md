# Windows Detached Panel Launch Validation

Date: 2026-05-27
Branch: `codex/panel-integration`
Version validated: `0.4.40`

## Scope

This slice closes the practical installer gap where the Control Center panel could be marked ready during install, but fail to remain reachable after the installer process/session ended on a remote Windows machine.

The fix changes the Windows panel launch path to use detached child-process creation flags so the panel survives installer/session teardown.

## Root cause

Observed on `192.0.2.10`:

- installer completed successfully
- `control_center_launch_status = ready`
- but a separate post-install check could not reach `http://127.0.0.1:3210/api/status`
- manually launching the installed panel restored service immediately

Additional live investigation showed:

- starting the panel from an SSH session through normal Windows process launch inheritance did **not** survive the session ending
- launching the panel executable with a stronger detached Windows creation-flag set allowed the service to remain alive after the initiating session exited

## Code change

Files changed:

- `src/local_ai_control_center_installer/platform_paths.py`
  - added `detached_subprocess_creationflags()`
- `src/local_ai_control_center_installer/control_center_runtime.py`
  - panel launch now uses detached Windows creation flags
- `tests/test_control_center_runtime_deploy.py`
  - added regression coverage for detached panel launch flags

## Automated verification

- `python -m pytest tests\test_control_center_runtime_deploy.py -q`
  - `12 passed`
- `python -m pytest -q`
  - `503 passed`
- `python -m build`
  - success
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python`
  - success

## Local machine verification

This machine was upgraded with:

- `dist\LocalAIControlCenterSetup-v0.4.40.exe`

Confirmed:

- uninstall registry `DisplayVersion = 0.4.40`
- local `install-report.json`
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `first_run_status = ready`
- live local API
  - `http://127.0.0.1:3210/api/status`
  - `version = 0.4.40`

## Remote machine verification

Remote target:

- `192.0.2.10`

Upgrade path used:

- copied `dist\LocalAIControlCenterSetup-v0.4.40.exe`
- ran installer against existing `C:\Users\<remote-user>\LocalAIControlCenter`

Confirmed after installer completion from a separate follow-up session:

- uninstall registry `DisplayVersion = 0.4.40`
- `C:\Users\<remote-user>\LocalAIControlCenter\logs\install-report.json`
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `first_run_status = ready`
- live remote-local API:
  - `curl.exe -s http://127.0.0.1:3210/api/status`
  - returned `version = 0.4.40`
  - returned `health = ok`

This is the key regression proof: the panel remained reachable after installer completion without a manual launcher recovery step.

## Honest remaining edge

- the remote non-interactive SSH session still can linger on the installer's final `Press Enter to close the installer window...` pause line
- that is a remote-shell ergonomics issue, but it no longer prevents the panel from being alive and reachable after install
