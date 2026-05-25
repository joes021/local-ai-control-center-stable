## Windows Benchmark Final Polish Validation

Date: 2026-05-25
Branch: `codex/panel-integration`
Target version: `0.4.19`

### Scope

Validated the final benchmark polish slice on Windows:

- benchmark metadata truth in saved runs and live summary
- compare view backend contract
- JSON/CSV export backend contract
- packaged frontend refresh
- local installer upgrade with control-center port takeover
- installed app smoke on this machine

### Verification commands

#### Repo verification

```powershell
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python
```

Observed results:

- `python -m pytest -q` -> `439 passed`
- `python -m build` -> success
- Windows installer build -> success
- built installer: `dist\LocalAIControlCenterSetup-v0.4.19.exe`

#### Local installer upgrade

```powershell
cmd /c "(echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.) | dist\LocalAIControlCenterSetup-v0.4.19.exe"
```

Observed results from latest installer report:

- `product_installation_status = complete`
- `control_center_launch_status = ready`
- `first_run_status = ready`
- `turboquant_status = ready`
- `failing_step = null`

Install root:

- `C:\Users\<user>\LocalAIControlCenter`

#### Installed app truth checks

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalAIControlCenter' | Select-Object DisplayName,DisplayVersion
Invoke-RestMethod 'http://127.0.0.1:3210/api/status'
Invoke-RestMethod 'http://127.0.0.1:3210/api/benchmark'
```

Observed results:

- uninstall registry `DisplayVersion = 0.4.19`
- panel `/api/status` reports `version = 0.4.19`
- active runtime on this machine during validation: `TurboQuant`
- benchmark summary exposes:
  - `environment`
  - `liveState`
  - `savedRuns`
  - `selectedBattery`

#### Benchmark smoke on installed app

Executed two real benchmark runs through the installed panel backend:

```powershell
POST /api/benchmark/run-selected {"scenarioId":"short"}
POST /api/benchmark/run-selected {"scenarioId":"medium"}
GET  /api/benchmark/run-status
GET  /api/benchmark
GET  /api/benchmark/compare?runIds=<medium>&runIds=<short>
GET  /api/benchmark/export?format=json&runIds=<medium>&runIds=<short>
GET  /api/benchmark/export?format=csv&runIds=<medium>&runIds=<short>
```

Observed results:

- short run completed: `bench-a1c2f691d6`
- medium run completed: `bench-66fec73261`
- compare route summary:
  - `2 benchmark run-a su spremna za poredjenje.`
- export route returned valid JSON and CSV payloads

Saved run sample from installed app:

- `Medium` / `TurboQuant` / `70.11 tok/s total` / `2738.62 ms`
- `Short` / `TurboQuant` / `78.44 tok/s total` / `267.72 ms`

#### Minimal UI proof

Used Chrome headless DOM dump against the installed panel:

```powershell
"C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu --virtual-time-budget=10000 --dump-dom http://127.0.0.1:3210/
```

Observed results:

- rendered header shows `Local AI Control Center 0.4.19`
- top navigation includes `Benchmark`

### Product truths after this slice

- Benchmark is shipped in the installed panel, not only in repo source.
- Saved benchmark runs now preserve runtime/model/settings context.
- Compare and export are available through installer-managed backend routes.
- Live benchmark state is truthful when runtime is idle and does not invent throughput.
- Installer now successfully upgrades this machine even when port `3210` is already occupied by another Local AI Control Center instance from a different install root.

### Known limits

- This validation used API-level benchmark smoke plus headless DOM proof; full visual interaction automation was not run because Playwright was not available in the local tool environment.
- Throughput values depend on the currently active runtime, active model, and machine load; the numbers above are smoke evidence, not universal benchmark baselines.
