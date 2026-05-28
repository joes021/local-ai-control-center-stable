# Windows validation - inference spotlight helper polish

Datum: 2026-05-28
Repo: `C:\Users\<user>\Documents\local-ai-control-center-stable`
Verzija: `0.4.55`

## Šta je menjano

- gornji blok `Aktivna inference podešavanja` u `Podešavanja -> Opšta podešavanja` više nije samo status pregled
- dodat je `Brzi orijentiri` deo za:
  - kodiranje
  - chat
  - benchmark
- svaka aktivna inference kartica sada ima kratku mikro-napomenu uz samu vrednost
- sekundarne inference kartice su prelomljene u kompaktniji 3-kolonski raspored na širim ekranima

## Testovi

- `python -m pytest tests\test_control_center_frontend_dist.py -q` -> `48 passed`
- `python -m pytest -q` -> `523 passed`

## Build

- `node .\node_modules\typescript\bin\tsc -b` u `frontend` -> uspešno
- `node .\node_modules\vite\bin\vite.js build` u `frontend` -> uspešno
- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno

## Lokalni upgrade

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.55.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.55`
- uninstall registry -> `DisplayVersion = 0.4.55`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json` -> `product_installation_status = complete`
