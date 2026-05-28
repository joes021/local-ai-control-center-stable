# Windows validation - home runtime binary card polish

Datum: 2026-05-28
Repo: `C:\Users\<user>\Documents\local-ai-control-center-stable`
Verzija: `0.4.56`

## Šta je menjano

- `Home -> Binar u upotrebi` više ne prikazuje celu putanju kao glavni naslov kartice
- glavni fokus je sada na nazivu fajla, na primer `llama-server.exe`
- lokacija binara je pomerena u zaseban, vizuelno mirniji blok
- duga putanja je skraćena za prikaz i ostaje čitljiva bez ružnog lomljenja
- puna putanja ostaje dostupna kroz `title` hover detalj

## Testovi

- `python -m pytest tests\test_control_center_frontend_dist.py -q` -> `49 passed`
- `python -m pytest -q` -> `524 passed`

## Build

- `node .\node_modules\typescript\bin\tsc -b` u `frontend` -> uspešno
- `node .\node_modules\vite\bin\vite.js build` u `frontend` -> uspešno
- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno

## Lokalni upgrade

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.56.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.56`
- uninstall registry -> `DisplayVersion = 0.4.56`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json` -> `product_installation_status = complete`
