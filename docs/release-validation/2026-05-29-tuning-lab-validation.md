# Windows validation - Tuning Lab

Datum: 2026-05-29
Repo: `C:\repo\local-ai-control-center-stable`
Verzija: `0.4.60`

## Šta je uvedeno

- novi `Tuning Lab` tab pod `Više`
- poređenje tri tuning slota:
  - `Baseline`
  - `Recommended`
  - `Custom`
- pravi OpenCode task nad izolovanim workspace-om po slotu
- sekvencijalni queue, aktivni run status i posebna istorija eksperimenata
- success check lanac do 3 koraka
- import forumskog/Reddit snippeta za inference parametre
- `export / share` za završene run-ove
- `primeni pobednički set` za winner slot
- tuning runtime proxy koji omogućava slot-specifične inference vrednosti bez menjanja globalnog runtime stanja

## Root-cause bug koji je zatvoren

- na prvom živom smoke run-u svi slotovi su kreirali fajl i prošli success check, ali su i dalje bili označeni kao `failed`
- root cause je bio u proceni `taskCompleted`:
  - `processReturncode = 0` prolazio je kroz izraz sa `or 1`
  - zbog toga je uspešan return code bio lažno tumačen kao neuspešan
- dodat je regresioni test koji dokazuje da slot sa:
  - `processReturncode = 0`
  - bez tokena
  - i uspešnim success check-om
  i dalje mora da bude označen kao `completed`

## Testovi

- `python -m pytest tests\test_control_center_tuning_lab.py -k zero_returncode_without_tokens -q` -> uspešno (`1 passed`)
- `python -m pytest tests\test_control_center_runtime_proxy.py tests\test_control_center_tuning_lab.py tests\test_control_center_tuning_lab_routes.py tests\test_control_center_frontend_dist.py -q` -> uspešno (`68 passed`)
- `python -m pytest tests\test_windows_packaging.py -q` -> uspešno (`7 passed`)
- `python -m pytest -q` -> uspešno (`541 passed`)

## Build

- frontend TypeScript + Vite build -> uspešno
- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno
- novi installer: `dist\LocalAIControlCenterSetup-v0.4.60.exe`
- latest alias: `dist\LocalAIControlCenterSetup-latest.exe`

## Release build polish

- `packaging\build_windows_installer.ps1` više ne zavisi slepo od spoljnog `npm`
- ako `npm` nije na PATH-u, a `frontend\node_modules` i lokalni build binari već postoje, installer build i dalje može da prođe
- time je release tok otporniji u lokalnim Windows okruženjima

## Živi smoke dokaz

- podignut je repo backend na posebnom portu `3310`
- korišćen je stvarni lokalni install root:
  - `C:\Users\<user>\LocalAIControlCenter`
- pokrenut je pravi Tuning Lab eksperiment sa zadatkom:
  - kreiraj `tuning_lab_ready.txt` sa sadržajem `READY`
- korišćen je success check koji proverava da fajl postoji i da sadržaj tačno odgovara
- import snippeta je uspešan za:
  - `--temp 0.2`
  - `--top-k 20`
  - `--top-p 0.9`
  - `--min-p 0.0`
  - `--repeat-penalty 1.02`
  - `--repeat-last-n 64`
  - `--seed 7`

## Ishod živog smoke run-a

- `runId = tuning-2976c879b2`
- sva tri slota su završila zadatak
- sva tri slota su prošla success check
- winner je predložen kao `recommended`
- `export` je uspešan
- `apply winner` je uspešan

Sažetak ishoda:

- `baseline` -> `completed`
- `recommended` -> `completed`
- `custom` -> `completed`

## Lokalni upgrade

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.60.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.60`
- `http://127.0.0.1:3210/api/tuning-lab?page=1` -> vraća živ payload sa Tuning Lab istorijom i smoke run rezultatima
- uninstall registry -> `DisplayVersion = 0.4.60`

## Checksum artefakti

- `dist\SHA256SUMS-v0.4.60.txt` generisan
- `LocalAIControlCenterSetup-v0.4.60.exe` i `LocalAIControlCenterSetup-latest.exe` imaju isti SHA256, što je očekivano jer latest pokazuje na isti build


