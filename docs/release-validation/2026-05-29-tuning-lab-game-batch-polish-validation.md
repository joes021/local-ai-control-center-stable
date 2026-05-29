# Windows validation - Tuning Lab Game Batch Polish

Datum: 2026-05-29
Repo: `C:\Users\<user>\Documents\local-ai-control-center-stable`
Verzija: `0.4.63`

## Šta je ispolirano

- `Game Batch 01` u `Tuning Lab`-u sada ima jasniji pregled umesto obične liste taskova
- batch kartica sada prikazuje:
  - koliko ima zadataka
  - koliko ukupno ima success check-ova
  - da jedan klik pravi više stvarnih run-ova
- dodat je blok `Šta ovaj batch meri`
- svaki task sada ima preglednije badge-eve:
  - težina
  - scope
  - broj success check-ova
  - fokus testa
  - očekivani artefakt
- jasno se vidi koji je task trenutno učitan u editor
- `Pokreni ceo batch` sada mnogo jasnije objašnjava da koristi trenutne slot postavke i radni direktorijum

## Backend / payload polish

- batch preset sada nosi dodatne metadata podatke:
  - `focusAreas`
  - `scopeLabel`
  - `focusLabel`
  - `expectedArtifact`
- to omogućava da UI prikaže smisleniji tuning pregled bez tvrdog kodiranja svakog detalja u samoj stranici

## Testovi

- `python -m pytest tests\test_control_center_frontend_dist.py tests\test_control_center_tuning_lab.py tests\test_control_center_tuning_lab_routes.py -q` -> uspešno (`66 passed`)
- `python -m pytest -q` -> uspešno (`544 passed`)

## Build

- frontend TypeScript build -> uspešno
- frontend Vite build -> uspešno
- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno
- novi installer:
  - `dist\LocalAIControlCenterSetup-v0.4.63.exe`
- latest alias:
  - `dist\LocalAIControlCenterSetup-latest.exe`

## Živa potvrda

- lokalni installer upgrade je prošao uspešno
- `http://127.0.0.1:3210/api/status` vraća `version = 0.4.63`
- uninstall registry pokazuje `DisplayVersion = 0.4.63`
- `http://127.0.0.1:3210/api/tuning-lab?page=1` vraća novi batch metadata payload:
  - `focusAreas`
  - `scopeLabel`
  - `focusLabel`
  - `expectedArtifact`

## Frontend bundle potvrda

- spakovani frontend sadrži novi JS i CSS bundle za ovu verziju
- bundled CSS sadrži nove batch klase:
  - `tuning-lab-batch-overview`
  - `tuning-lab-batch-focus-list`
  - `tuning-lab-batch-task-badges`
  - `tuning-lab-batch-run-hint`
- bundled JS sadrži novi copy:
  - `Šta ovaj batch meri`
  - `Trenutno u editoru`
  - `Koristi trenutne slot postavke`

## Checksum artefakti

- `dist\SHA256SUMS-v0.4.63.txt` generisan
- `LocalAIControlCenterSetup-v0.4.63.exe` i `LocalAIControlCenterSetup-latest.exe` imaju isti SHA256, što je očekivano jer latest pokazuje na isti build
