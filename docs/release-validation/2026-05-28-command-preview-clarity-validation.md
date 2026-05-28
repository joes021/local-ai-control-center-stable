# Windows validation - command preview clarity

Datum: 2026-05-28
Repo: `C:\Users\<user>\Documents\local-ai-control-center-stable`
Verzija: `0.4.57`

## Šta je menjano

- `Server` sada jasnije objašnjava da `&` pripada samo PowerShell varijanti
- dodata je jasna poruka da se za ručno lepljenje u Command Prompt koristi samo `cmd.exe` komanda
- `OpenCode` sada prikazuje:
  - launcher `.cmd`
  - PowerShell prikaz
  - env promenljive
  - `managed-config.json` ulaze (`provider`, `model`, `baseURL`, `enabled providers`)
  - efektivna local-lacc inference podrazumevana podešavanja

## Testovi

- `python -m pytest tests\test_control_center_opencode.py -q` -> uspešno
- `python -m pytest tests\test_control_center_frontend_dist.py -q` -> uspešno
- `python -m pytest -q` -> uspešno

## Build

- `node .\node_modules\typescript\bin\tsc -b` u `frontend` -> uspešno
- `node .\node_modules\vite\bin\vite.js build` u `frontend` -> uspešno
- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno

## Lokalni upgrade

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.57.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.57`
- uninstall registry -> `DisplayVersion = 0.4.57`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json` -> `product_installation_status = complete`
