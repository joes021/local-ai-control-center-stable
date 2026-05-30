# v0.4.77 - OpenCode launch loop guard validation

## Scope

Ova validacija pokriva zatvaranje baga u kom je `OpenCode` mogao da izazove lavinu novih terminal/prozor sesija pri ponovljenom otvaranju.

Glavni cilj je bio da se preseku oba kritična puta:

- backend `OpenCode` launch ruta
- instalirani Windows launcher skriptovi

## Promene u kodu

- `src/local_ai_control_center_installer/control_center_backend/services/opencode_service.py`
  - dodat detektor aktivnih `Open-OpenCode.cmd` launcher procesa
  - `open_opencode(...)` sada odbija novi launch kada je launcher već u toku
  - Windows `Open-OpenCode.cmd` sada sadrži guard koji proverava:
    - postojeći `opencode.exe`
    - postojeći launcher shell za isti `.cmd`
  - `OpenCode` status sada razlikuje `launching` stanje
- `src/local_ai_control_center_installer/control_center_runtime.py`
  - Windows `Open-Control-Center.cmd` sada proverava postojeći zdravi panel pre novog starta
- `frontend/src/pages/OpenCodePage.tsx`
  - prikazuje `Pokretanje u toku` za `launching` stanje
- `frontend/src/pages/HomePage.tsx`
  - prikazuje `Pokretanje u toku` za `launching` stanje
- `tests/test_control_center_opencode.py`
  - pokriven slučaj kada je `OpenCode` launcher već u toku
  - pokriven sadržaj novog Windows launcher guarda
- `tests/test_control_center_runtime_deploy.py`
  - pokriven sadržaj novog panel launcher health guarda

## Testovi

Pokrenuto:

```powershell
python -m pytest tests/test_control_center_opencode.py tests/test_control_center_runtime_deploy.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Rezultat:

- ciljani launcher testovi -> `29 passed`
- puni suite -> `588 passed, 1 warning`
- `python -m build` -> uspešno
- Windows installer build -> uspešno

## Lokalni upgrade

Lokalna instalacija je podignuta na `0.4.77`.

Potvrđeno:

- `http://127.0.0.1:3210/api/status` vraća `version = 0.4.77`
- uninstall registry:
  - `DisplayVersion = 0.4.77`
- `install-report.json`:
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `first_run_status = ready`

## Živa launcher provera

Instalirani `OpenCode` launcher sada sadrži PowerShell guard pre samog pokretanja:

- proverava postojeći `opencode.exe`
- proverava postojeći shell koji već gađa isti `Open-OpenCode.cmd`
- izlazi bez novog launch-a ako je sesija već u toku

Instalirani panel launcher sada sadrži health guard:

- proverava `http://127.0.0.1:3210/health`
- poredi `installRoot`
- ne diže novi panel ako je postojeći već zdrav

## Živi OpenCode smoke

Direktna živa provera protiv instaliranog panela:

- početni status:
  - `sessionState = runtime-ready`
  - `openActionLabel = Otvori OpenCode`
- `POST /api/opencode/open`
  - vraća `status = ok`
  - summary:
    - `OpenCode je pokrenut u novom prozoru.`
- odmah zatim ponovljeni `POST /api/opencode/open`
  - vraća postojeću sesiju umesto novog launch-a
- `GET /api/opencode/status`
  - potvrđuje:
    - `active = true`
    - `instanceCount = 1`
    - `sessionState = connected`

## Zaključak

`v0.4.77` zatvara kritičnu launch-loop rupu:

- novi `OpenCode` launch se više ne gomila kada je launcher već u toku
- panel launcher više ne podiže novi zdravi panel preko postojećeg
- UI sada ima posebno `launching` stanje umesto slepog ponavljanja akcije
- lokalni upgrade, testovi i installer build su prošli
