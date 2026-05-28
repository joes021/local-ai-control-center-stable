# Telemetry Live Panel Stability Validation

Date: 2026-05-28

## Scope

Validated that the `Uživo sada` block no longer shifts layout when live throughput appears or disappears.

## Checks

- Added failing frontend assertions for stable live telemetry shell classes and persistent last-signal section.
- Updated `TelemetryPanel` so the live value keeps reserved space and only shows a number while there is a true live signal.
- Kept `Poslednji throughput signal` visible as a stable secondary section to avoid layout jumps.
- Added CSS for fixed live shell height, idle opacity handling, and persistent last-signal area.
- Rebuilt packaged frontend bundle and Windows installer.

## Verification

- `python -m pytest tests\test_control_center_frontend_dist.py -q`
- `python -m pytest -q`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python`
- Local panel verification through `http://127.0.0.1:3210/`
