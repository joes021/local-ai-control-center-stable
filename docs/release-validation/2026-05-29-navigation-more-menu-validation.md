# Windows validation - navigation `Više` menu polish

Datum: 2026-05-29
Repo: `C:\Users\<user>\Documents\local-ai-control-center-stable`
Verzija: `0.4.59`

## Šta je menjano

- osnovni meni više ne prikazuje sve sekcije kao jedan dugačak red tabova
- uvedeno je `6 glavnih tabova + Više`
- `Više` otvara grupisan dropdown sa sekcijama:
  - `Analiza i alati`
  - `Tokovi i automatizacija`
  - `Održavanje`
- kada je otvorena neka stranica iz `Više`, samo dugme `Više` ostaje aktivno
- uži ekrani sada dobijaju jednostavniji stack raspored umesto prenatrpane horizontalne trake

## Testovi

- `python -m pytest tests\test_control_center_frontend_dist.py -q` -> uspešno (`50 passed`)
- `python -m pytest -q` -> uspešno (`525 passed`)

## Build

- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno
- novi installer: `dist\LocalAIControlCenterSetup-v0.4.59.exe`
- latest alias: `dist\LocalAIControlCenterSetup-latest.exe`

## Živa browser provera

- na svežem lokalnom preview-u potvrđeno je:
  - stalno vidljivi tabovi: `Početna`, `Server`, `Modeli`, `OpenCode`, `Pretraga`, `Podešavanja`
  - `Više` dugme postoji i otvara grupisan meni
  - dropdown sadrži:
    - `Browser`, `Znanje`, `Kompatibilnost`, `Benchmark`, `Telemetrija`
    - `Radni tokovi`, `Poslovi`, `Flota`
    - `Logovi`, `Popravka`, `Ažuriranja`

## Lokalni upgrade

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.59.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.59`
- uninstall registry -> `DisplayVersion = 0.4.59`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json` -> `product_installation_status = complete`

## Checksum artefakti

- `dist\SHA256SUMS-v0.4.59.txt` generisan
- setup i latest alias imaju isti SHA256, što je očekivano jer latest pokazuje na isti build
