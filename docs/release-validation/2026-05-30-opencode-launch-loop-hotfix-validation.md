# v0.4.78 - OpenCode launch loop hotfix validation

## Scope

Ova validacija pokriva hotfix preko `v0.4.77` za dve preostale ivice:

- lazni `launching` status kada pomocni shell samo pominje launcher putanju
- mrtav `cmd.exe` koji ostaje iza uspesnog `OpenCode` starta zbog `cmd /k`

## Promene u kodu

- `src/local_ai_control_center_installer/control_center_backend/services/opencode_service.py`
  - detektor `detect_opencode_launcher_instances(...)` sada prihvata samo stvarne `cmd.exe` launcher procese
  - Windows launcher guard sada proverava samo `cmd.exe` procese za isti `.cmd`
  - backend launch je prebacen sa:
    - `cmd.exe /d /k`
    - na `cmd.exe /d /c`
  - `launchPreview.launcherCommand` sada prikazuje isti novi `/c` tok
- `tests/test_control_center_opencode.py`
  - dodat regresioni test koji dokazuje da `powershell` sum sa istom putanjom ne sme da se vodi kao aktivni launcher
  - ocekivanja su azurirana na `/c` launcher tok

## Testovi

Pokrenuto:

```powershell
python -m pytest tests/test_control_center_opencode.py tests/test_control_center_runtime_deploy.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Rezultat:

- ciljani launcher testovi -> `30 passed, 1 warning`
- puni suite -> `589 passed, 1 warning`
- `python -m build` -> uspesno
- Windows installer build -> uspesno

## Lokalni upgrade

Lokalna instalacija je podignuta na `0.4.78`.

Potvrdjeno:

- `http://127.0.0.1:3210/api/status` vraca `version = 0.4.78`
- uninstall registry:
  - `DisplayVersion = 0.4.78`
- `install-report.json`:
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `first_run_status = ready`

## Ziva provera

Pre hotfix-a je stari `cmd.exe /d /k Open-OpenCode.cmd` mogao da ostane otvoren i posle uspesnog rada, pa je panel prikazivao:

- `sessionState = launching`
- `canOpen = false`

Posle hotfix-a:

- stari zaostali `cmd.exe` je uklonjen
- detektor vraca praznu listu kada nema stvarnog aktivnog launchera
- `GET /api/opencode/status` vraca:
  - `sessionState = runtime-ready`
  - `canOpen = true`
  - `openActionLabel = Otvori OpenCode`
- brza ziva provera sa dva uzastopna `POST /api/opencode/open` poziva daje:
  - prvi odgovor: `OpenCode je pokrenut u novom prozoru.`
  - drugi odgovor: `OpenCode je vec otvoren; backend je pripremljen za postojecu sesiju.`
  - aktivni procesi posle toga:
    - `cmdCount = 1`
    - `opencodeCount = 1`

## Zakljucak

`v0.4.78` zatvara i drugi sloj istog problema:

- pomocni `powershell` vise ne moze lazno da drzi `launching`
- uspesan `OpenCode` start vise ne ostavlja bespotrebni `cmd` zbog `cmd /k`
- portal vraca istinito stanje `runtime-ready` cim stvarni launcher nestane
- ponovljeni open vise ne moze da preraste u terminal storm
