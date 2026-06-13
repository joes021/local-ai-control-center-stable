Release target: `v0.4.83`

Scope:
- elegantniji `Context` chip u `Živim resursima`
- jasniji mismatch signal `Usklađeno` / `Restart potreban`
- backend i UI tok za `Restartuj runtime da poravnaš context`
- osvežen paketovani frontend bundle

Verification:
- `python -m pytest tests/test_control_center_server.py tests/test_control_center_observability.py tests/test_control_center_frontend_dist.py -q`
- `python -m pytest -q`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`

Expected release artifacts:
- `dist/LocalAIControlCenterSetup-v0.4.83.exe`
- `dist/LocalAIControlCenterSetup-latest.exe`
- `dist/local_ai_control_center_installer-0.4.83-py3-none-any.whl`
- `dist/local_ai_control_center_installer-0.4.83.tar.gz`
- `dist/SHA256SUMS-v0.4.83.txt`

Notes:
- `Context` strip sada prikazuje i stanje i brojke u jednom kompaktnom chip-u.
- `Server` tab sada ima direktno dugme za restart runtime-a kada config i živi process nisu poravnati.


