# Windows validation - Tuning Lab Run / Play

Datum: 2026-05-29
Repo: `C:\repo\local-ai-control-center-stable`
Verzija: `0.4.64`

## Šta je dodato

- `Game Batch 01` u `Tuning Lab`-u sada ima zasebna dugmad:
  - `Run`
  - `Play`
- `Run` pravi konkretan tuning eksperiment za izabrani batch task i odmah ga dodaje u queue
- `Play` otvara poslednji uspešan playable rezultat za dati task ili slot kada takav izlaz postoji
- istorija tuning run-ova sada može da nosi playable metadata polja:
  - `playableEntryPath`
  - `playableFilesPreserved`

## Backend potvrda

- dodat je route:
  - `/api/tuning-lab/play/{runId}/{slotId}/{assetPath}`
- uspešan slot sada pre cleanup-a čuva playable artefakte u:
  - `config/control-center/tuning-lab/runs/<runId>/<slotId>/playable`
- HTML entry i lokalni asset fajlovi se kopiraju tako da rezultat ostane otvoriv i posle čišćenja radnog workspace-a

## Zatvoren stvarni bug

- tuning eksperimenti više ne ostaju zaglavljeni ako radni direktorijum još ne postoji
- `prepare_tuning_workspace(...)` sada pravi nedostajući folder umesto da padne pre slot error-handling toka
- slot sada workspace prepare grešku pretvara u uredan `failed` rezultat umesto da ubije worker thread

## Testovi

- `python -m pytest tests\test_control_center_tuning_lab.py -q` -> uspešno (`12 passed`)
- `python -m pytest tests\test_control_center_tuning_lab_routes.py -q` -> uspešno (`7 passed`)
- `python -m pytest tests\test_control_center_frontend_dist.py -q` -> uspešno (`51 passed`)
- `python -m pytest -q` -> uspešno (`548 passed`)

## Build

- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno
- novi installer:
  - `dist\LocalAIControlCenterSetup-v0.4.64.exe`
- latest alias:
  - `dist\LocalAIControlCenterSetup-latest.exe`

## Živa potvrda na instaliranom panelu

- lokalni installer upgrade je završen uspešno
- `http://127.0.0.1:3210/api/status` vraća `version = 0.4.64`
- uninstall registry pokazuje `DisplayVersion = 0.4.64`
- browser provera nad živim UI-jem potvrđuje:
  - `Tuning Lab` je dostupan kroz `Više`
  - `Game Batch 01` prikazuje `Run`
  - `Game Batch 01` prikazuje `Play`
  - vidi se i pomoćni tekst `Nema playable rezultata još.`

## Živi smoke za bug fix i playable route

- pokrenut je stvarni tuning eksperiment:
  - naziv: `Tuning Lab playable smoke fixed`
  - radni direktorijum: prethodno nepostojeći `.tmp\tuning-lab-playable-smoke-fixed`
- rezultat:
  - sva 3 slota završila `completed`
  - svaki slot je napravio `index.html`
  - svaki slot ima `playableEntryPath = index.html`
- živa route provera:
  - `curl.exe http://127.0.0.1:3210/api/tuning-lab/play/tuning-db6f17c427/recommended/index.html`
  - vraća HTML sa `PLAYABLE_OK`

## Frontend bundle potvrda

- spakovani frontend sadrži `Run` i `Play` copy za `Tuning Lab`
- bundled CSS sadrži `tuning-lab-batch-task-actions`
- bundled JS sadrži `Nema playable rezultata još`

## Checksum artefakti

- `dist\SHA256SUMS-v0.4.64.txt` je generisan
- `LocalAIControlCenterSetup-v0.4.64.exe` i `LocalAIControlCenterSetup-latest.exe` imaju isti SHA256, što je očekivano jer latest pokazuje na isti build


