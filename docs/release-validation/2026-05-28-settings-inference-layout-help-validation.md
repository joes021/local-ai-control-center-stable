# Windows validation - inference layout and parameter help

Datum: 2026-05-28
Repo: `C:\Users\<user>\Documents\local-ai-control-center-stable`
Verzija: `0.4.54`

## Šta je menjano

- gornji inference sažetak u `Podešavanja -> Opšta podešavanja` više nije jedna visoka kolona
- `Aktivna inference podešavanja` sada imaju kompaktniji dvodelni raspored:
  - levi opisni blok sa aktivnim sažetkom
  - desni pregled ključnih metrika i sekundarnih vrednosti
- svaki inference parametar sada ima kratko objašnjenje:
  - čemu služi
  - preporuke za kodiranje
  - preporuke za kreativniji chat
  - preporuke za stabilne benchmarke

## Testovi

- `python -m pytest tests\test_control_center_frontend_dist.py -q` -> `48 passed`
- `python -m pytest -q` -> `523 passed`

## Build

- `node .\node_modules\typescript\bin\tsc -b` u `frontend` -> uspešno
- `node .\node_modules\vite\bin\vite.js build` u `frontend` -> uspešno
- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno

## Lokalni upgrade

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.54.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.54`
- uninstall registry -> `DisplayVersion = 0.4.54`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json` -> `product_installation_status = complete`

## Napomena

- proveru sam zaključao kroz source, spakovani frontend bundle, puni test gate i lokalni installer upgrade
- dve stare nepovezane untracked docs datoteke iz `2026-05-20` nisu dirane
