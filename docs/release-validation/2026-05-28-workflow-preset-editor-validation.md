# Windows workflow preset editor validation

Date: 2026-05-28
Version: v0.4.42

## Scope

- korisnički workflow preset-i kroz portal
- dugme `Vrati na default podešavanja` u editoru workflow preseta
- paketovani frontend bundle i Windows installer
- lokalni installer upgrade na ovoj mašini

## Verification

- `python -m pytest tests/test_control_center_settings.py tests/test_control_center_frontend_dist.py -q`
  - `46 passed`
- `python -m pytest -q`
  - `510 passed`
- `python -m build`
  - success
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
  - success

## Local installer confirmation

- installer: `dist/LocalAIControlCenterSetup-v0.4.42.exe`
- local install report:
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `first_run_status = ready`
- installed panel status:
  - `/api/status -> version = 0.4.42`
- uninstall registry:
  - `DisplayVersion = 0.4.42`

## Live smoke

- `POST /api/settings/workflow-presets/save`
  - `status = ok`
- `GET /api/settings`
  - novi preset pronađen kao `kind = user`
- `POST /api/settings/workflow-presets/delete`
  - `status = ok`

## Notes

- ugrađeni workflow preset-i ostaju read-only osnova
- korisnik sada može da:
  - učita preset u editor
  - vrati editor na default podešavanja učitanog preseta
  - sačuva kao novi korisnički preset
  - sačuva izmene nad korisničkim presetom
  - obriše korisnički preset


