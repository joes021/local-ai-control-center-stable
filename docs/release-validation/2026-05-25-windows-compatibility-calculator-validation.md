# Windows Compatibility Calculator Validation - 2026-05-25

## Scope

Release target: `v0.4.20`

Closed work in this slice:

- compatibility calculator now exposes runtime-aware fit estimation for both `llama.cpp` and `TurboQuant`
- result payload now includes `bestRuntime`, `overallFitStatus`, `runtimeBreakdown`, `outputPressure`, and memory headroom
- packaged compatibility modal now renders the new runtime comparison and budget details
- Windows installer upgrade no longer fails on `server-port-bind` when the managed runtime port is already held by the same installation through `TurboQuant`
- PyInstaller entry now prefers repo `src/` during packaging so the built installer reflects current source code instead of stale `site-packages`

## Automated verification

Commands run successfully:

```powershell
python -m pytest tests\test_server_verification.py tests\test_first_run_validation.py tests\test_control_center_server.py tests\test_windows_packaging.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python
```

Observed results:

- focused regression suite: passed
- full suite: `446 passed`
- source distribution build: passed
- wheel build: passed
- Windows installer build: passed

## Local installer upgrade validation

Built installer:

- `dist/LocalAIControlCenterSetup-v0.4.20.exe`

Real upgrade was executed on the current machine over an existing live installation with:

- existing control panel already bound on `127.0.0.1:3210`
- existing managed runtime already bound on `127.0.0.1:39281`
- runtime listener owned by:
  - `C:\Users\<user>\LocalAIControlCenter\tools\turboquant\windows-x64-cuda12.4\llama-server.exe`

Final upgrade result:

- `product_installation_status = complete`
- `server_verification_status = ready`
- `first_run_status = ready`
- `control_center_launch_status = ready`

Installer report:

- `C:\Users\<user>\AppData\Local\Temp\LocalAIControlCenterInstaller\runs\2026-05-25T01-17-13+00-00\install-report.json`

## Installed application smoke

Live panel verification:

- `http://127.0.0.1:3210/api/status` returned `version = 0.4.20`

Live compatibility API verification:

- endpoint: `POST /api/compatibility/check`
- verified fields present in installed app response:
  - `bestRuntime`
  - `bestRuntimeLabel`
  - `overallFitStatus`
  - `runtimeBreakdown`
  - `memoryBudget.outputPressure`
  - `memoryBudget.vram.headroomGiB`

Observed live behavior on the installed app:

- `bestRuntime = "turboquant"`
- `runtimeBreakdown["llama.cpp"]` present
- `runtimeBreakdown["turboquant"]` present
- `memoryBudget.outputPressure.level = "high"`
- `memoryBudget.vram.headroomGiB = 1.79`

## Honest remaining limits

- `MTP` support remains runtime-constrained:
  - supported through `llama.cpp + --spec-type draft-mtp`
  - not supported as a `TurboQuant` runtime path
- compatibility math is heuristic guidance, not a formal upstream memory model
- live compatibility smoke on this pass validated the installed backend payload; it did not include a separate manual browser click-through of every calculator interaction
