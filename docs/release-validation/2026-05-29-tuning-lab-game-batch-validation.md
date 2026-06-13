# Windows validation - Tuning Lab Game Batch

Datum: 2026-05-29
Repo: `C:\repo\local-ai-control-center-stable`
Verzija: `0.4.62`

## Sta je uvedeno

- `Tuning Lab` sada ima gotov batch preset `Game Batch 01`
- batch je sastavljen od tri uporediva zadatka:
  - `Jumping Ball Runner`
  - `Balloon Blaster`
  - `Octopus Invaders`
- svaki zadatak moze da se:
  - ucita u editor kao `easy`, `medium` ili `hard`
  - ili da se pokrene kao deo celog batch reda
- novi backend route `POST /api/tuning-lab/queue-batch` siri jedan batch preset u vise pravih tuning run-ova
- batch koristi trenutne slot postavke iz editora:
  - `Baseline`
  - `Recommended`
  - `Custom`

## Zasto je ovo vazno

- prvi tuning batch vise nije samo slobodan prompt, nego ponovljiv skup zadataka
- lakse je uporediti:
  - nase preporuke
  - trenutni baseline
  - forum ili Reddit custom parametre
- rezultati postaju pogodniji za istoriju, export/share i kasnije poredjenje medju modelima

## Testovi

- `python -m pytest tests\test_control_center_frontend_dist.py tests\test_control_center_tuning_lab.py tests\test_control_center_tuning_lab_routes.py -q` -> uspesno (`66 passed`)
- `python -m pytest -q` -> uspesno (`544 passed`)

## Build

- frontend TypeScript build -> uspesno
- frontend Vite build -> uspesno
- `python -m build` -> uspesno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspesno
- novi installer:
  - `dist\LocalAIControlCenterSetup-v0.4.62.exe`
- latest alias:
  - `dist\LocalAIControlCenterSetup-latest.exe`

## Zivi dokaz

- lokalni installer upgrade je zavrsen uspesno
- `http://127.0.0.1:3210/api/status` vraca `version = 0.4.62`
- `http://127.0.0.1:3210/api/tuning-lab?page=1` vraca:
  - `batchPresets`
  - `game-batch-01`
  - task id-jeve:
    - `jumping-ball-runner`
    - `balloon-blaster`
    - `octopus-invaders`

## Lokalni upgrade

- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json` -> `product_installation_status = complete`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json` -> `control_center_launch_status = ready`
- uninstall registry -> `DisplayVersion = 0.4.62`

## Checksum artefakti

- `dist\SHA256SUMS-v0.4.62.txt` generisan
- `LocalAIControlCenterSetup-v0.4.62.exe` i `LocalAIControlCenterSetup-latest.exe` imaju isti SHA256, sto je ocekivano jer latest pokazuje na isti build


