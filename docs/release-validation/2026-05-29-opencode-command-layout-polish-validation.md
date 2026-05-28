# Windows validation - OpenCode command layout polish

Datum: 2026-05-29
Repo: `C:\Users\<user>\Documents\local-ai-control-center-stable`
Verzija: `0.4.58`

## Šta je menjano

- `OpenCode` komande više nisu prikazane kao dugačak niz grubih blokova
- `Launcher .cmd` i `PowerShell` sada stoje u urednom dvokolonskom rasporedu
- `Managed config ulazi` su prebačeni u pregledne info kartice
- `Env promenljive` su prikazane kao odvojene čitljive stavke, umesto jedne velike tekstualne gomile

## Testovi

- `python -m pytest tests\test_control_center_frontend_dist.py -q` -> uspešno
- `python -m pytest tests\test_control_center_opencode.py -q` -> uspešno
- `python -m pytest -q` -> uspešno

## Build

- `node .\node_modules\typescript\bin\tsc -b` u `frontend` -> uspešno
- `node .\node_modules\vite\bin\vite.js build` u `frontend` -> uspešno
- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno

## Lokalni upgrade

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.58.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.58`
- uninstall registry -> `DisplayVersion = 0.4.58`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json` -> `product_installation_status = complete`
