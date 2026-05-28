# Benchmark Metric Selector Validation

Date: 2026-05-28

## Scope

Validated benchmark chart metric switching so the user can choose `Input tokeni`, `Output tokeni`, or `Ukupno tokeni`, with the chart scale driven only by the selected metric.

## Checks

- Added failing frontend assertions for:
  - `Prikaz na grafikonu`
  - `Input tokeni`
  - `Output tokeni`
  - `Ukupno tokeni`
- Implemented single-metric benchmark chart rendering with per-metric Y-axis scaling.
- Rebuilt packaged frontend bundle and Windows installer.
- Updated local installation and verified installed panel serves the new benchmark selector.

## Verification

- `python -m pytest tests\test_control_center_frontend_dist.py -q`
- `python -m pytest -q`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python`
- Local panel verification through `http://127.0.0.1:3210/`
