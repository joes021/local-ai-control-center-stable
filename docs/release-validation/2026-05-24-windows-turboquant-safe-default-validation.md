# Windows TurboQuant Safe Default Validation

Date: 2026-05-24
Branch: `codex/panel-integration`

## Scope

Validate the Windows fix that changes the implicit TurboQuant baseline from the aggressive
`daily` context to the safer `safe` context when `config/control-center/turboquant-config.json`
does not exist yet.

## Root cause

On <host> (`192.0.2.10`), packaged TurboQuant was installed correctly and its DLL sidecars
were present, but the product still failed through the normal panel flow because the missing
TurboQuant config file caused the runtime to fall back to the built-in `daily` baseline:

- `context = 262144`

That value was too aggressive for the remote GTX 1060 6 GB path and caused TurboQuant startup to
die before health became ready.

Direct remote probes showed:

- `ctx-size 262144` failed in the normal product flow
- `ctx-size 131072` reached `server is listening on http://127.0.0.1:39281`

## Code change

Changed `load_turboquant_config()` in:

- `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`

from the implicit `daily` baseline to the implicit `safe` baseline, so a fresh install without a
saved TurboQuant config now starts from:

- `context = 131072`
- `ctk = turbo4`
- `ctv = turbo4`
- `ncmoe = 20`

## Regression tests

Added/updated:

- `tests/test_control_center_turboquant.py`
  - verifies `/api/settings/turboquant` returns `currentConfig.context == 131072`
- `tests/test_control_center_server.py`
  - verifies TurboQuant start uses `--ctx-size 131072` when the config file is missing

## Verification

### Local targeted tests

Command:

```powershell
python -m pytest tests/test_control_center_turboquant.py tests/test_control_center_server.py -q
```

Result:

- `16 passed`

### Full test suite

Command:

```powershell
python -m pytest -q
```

Result:

- `413 passed in 61.07s`

### Packaging

Commands:

```powershell
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Result:

- `dist/LocalAIControlCenterSetup-v0.4.12.exe`
- `dist/local_ai_control_center_installer-0.4.12-py3-none-any.whl`
- `dist/local_ai_control_center_installer-0.4.12.tar.gz`

### Live remote validation on <host>

Using SSH on `<remote-user>@192.0.2.10`:

1. Wrote a TurboQuant config with `context = 131072`
2. Set runtime selection to `turboquant`
3. Started the installed Control Center panel
4. Called `POST http://127.0.0.1:3210/api/server/start`
5. Polled `GET http://127.0.0.1:3210/api/server/status`

Observed result:

- `startResult.status = ok`
- `statusPayload.status = started`
- `statusPayload.health = ok`
- `statusPayload.activeRuntime = turboquant`
- `statusPayload.port = 39281`

This confirms the product path works on the previously failing remote machine once the effective
TurboQuant baseline is reduced to the safe default.

## Release readiness

Ready for a Windows patch release that specifically fixes fresh-install TurboQuant startup on lower
VRAM NVIDIA systems where no explicit TurboQuant config file exists yet.
