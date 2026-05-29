# Windows validation - Tuning Lab polish

Datum: 2026-05-29
Repo: `C:\Users\<user>\Documents\local-ai-control-center-stable`
Verzija: `0.4.61`

## Šta je uvedeno

- jasnije objašnjenje pobedničkog slota u `Tuning Lab`
- aktivni progress panel sa:
  - trenutnim korakom
  - poslednjim log signalom
  - proteklim vremenom
- diff/file browser po slotu
- filteri istorije po upitu, cilju, runtime-u i statusu
- copy/export polish po slotu:
  - `Kopiraj parametre`
  - `Kopiraj runtime komandu`
  - `Kopiraj OpenCode komandu`
  - `Export samo ovaj slot`
- pošteniji prikaz uspešnog run-a bez token telemetrije:
  - `Token telemetry nije prijavljen`

## Backend i servisni polish

- aktivni tuning run sada emituje detaljnije faze:
  - `workspace`
  - `runtime`
  - `opencode`
  - `checks`
  - `success-check`
  - `slot-finished`
- OpenCode task više daje živi log excerpt dok radi
- diff artefakti sada čuvaju strukturirane `diffFiles` blokove po fajlu
- snapshot logika sada čuva dovoljno teksta da diff browser radi verodostojno i za male tekstualne izmene

## Testovi

- `python -m pytest tests\test_control_center_frontend_dist.py tests\test_control_center_tuning_lab.py tests\test_control_center_tuning_lab_routes.py -q` -> uspešno (`64 passed`)
- `python -m pytest -q` -> uspešno (`542 passed`)

## Build

- frontend TypeScript + Vite build -> uspešno
- frontend dist osvežen u `src\local_ai_control_center_installer\control_center_backend\frontend_dist`
- `python -m build` -> uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python` -> uspešno
- novi installer: `dist\LocalAIControlCenterSetup-v0.4.61.exe`
- latest alias: `dist\LocalAIControlCenterSetup-latest.exe`

## Lokalni upgrade

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.61.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.61`
- uninstall registry -> `DisplayVersion = 0.4.61`
- install report -> `product_installation_status = complete`
- install report -> `control_center_launch_status = ready`

## Živa browser provera

- otvoren lokalni panel na `http://127.0.0.1:3210/`
- potvrđeno da `Više` meni sadrži `Tuning Lab`
- potvrđeno da `Tuning Lab` prikazuje:
  - `Zašto je ovaj slot pobedio`
  - `Filtriraj istoriju`
  - `Aktivni korak`
  - `Poslednji log signal`
  - `Izmenjeni fajlovi`
  - `Kopiraj parametre`
  - `Kopiraj runtime komandu`
  - `Kopiraj OpenCode komandu`

## Živi smoke dokaz

- proveren završeni istorijski run sa winner objašnjenjem i `diffFiles`
- pokrenut novi tuning run i uhvaćen payload dok je aktivan
- tokom aktivnog run-a potvrđeno:
  - `phase = opencode`
  - `phaseLabel = OpenCode task radi`
  - `stepSummary` pokazuje koji slot trenutno radi
  - `logExcerpt` donosi živi izlaz
  - `elapsedMs` raste tokom izvršavanja
- finalni ishod živog smoke run-a:
  - status `completed`
  - winner `recommended`

## Checksum artefakti

- `dist\SHA256SUMS-v0.4.61.txt` generisan
- `LocalAIControlCenterSetup-v0.4.61.exe` i `LocalAIControlCenterSetup-latest.exe` imaju isti SHA256, što je očekivano jer latest pokazuje na isti build
