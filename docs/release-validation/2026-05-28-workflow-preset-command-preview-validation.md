# Windows Validation - Workflow Preset UX i CLI Preview

Datum: 2026-05-28  
Verzija: v0.4.43

## Scope

Ovaj prolaz zatvara dva korisnička pravca:

- workflow preset-i više nisu samo fiksni ugrađeni izbori, već imaju pravi korisnički editor sa kloniranjem, validacijom i jasnim reset tokom
- portal sada jasno prikazuje ekvivalentne komande za `llama.cpp`, `TurboQuant` i `OpenCode`, tako da korisnik može da poredi podešavanja sa forumima, Reddit objavama i ručnim CLI tokovima

## Implementirano

- `Workflows` editor sada ima:
  - `Učitaj u editor`
  - `Kloniraj preset`
  - `Poništi izmene u editoru`
  - `Sačuvaj kao novi preset`
  - `Sačuvaj izmene preseta`
  - `Obriši korisnički preset`
- prikazano je da li je preset `ugrađeni preset` ili `korisnički preset`
- dodat je indikator `Nesačuvane izmene`
- uvedena je validacija za:
  - prazno ime
  - duplirano ime
  - predugačak opis
  - previše badge oznaka
  - predugačku badge oznaku
- `Server` stranica sada prikazuje ekvivalentne PowerShell komande za:
  - `llama.cpp`
  - `TurboQuant`
  - aktivni model kroz `--model`
- `OpenCode` stranica sada prikazuje:
  - launcher `.cmd` komandu
  - PowerShell prikaz sa radnim direktorijumom i env promenljivama

## Testovi

Pokrenuto:

```powershell
python -m pytest -q
```

Rezultat:

- `512 passed`

Posebno su pokriveni:

- `tests/test_control_center_settings.py`
- `tests/test_control_center_server.py`
- `tests/test_control_center_opencode.py`
- `tests/test_control_center_frontend_dist.py`

## Build

Pokrenuto:

```powershell
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Rezultat:

- uspešan `sdist`
- uspešan `wheel`
- uspešan Windows installer build:
  - `dist/LocalAIControlCenterSetup-v0.4.43.exe`

## Lokalni installer upgrade

Na ovoj mašini je pokrenut stvarni lokalni upgrade preko:

- `dist/LocalAIControlCenterSetup-v0.4.43.exe`

Važna napomena:

- automation wrapper koji je slao podrazumevane `Enter` odgovore je timeout-ovao dok je čekao zatvaranje procesa
- ali sam installer tok je stvarno završen uspešno, što potvrđuju installer report i živi panel

Potvrđeno:

- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json`
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `first_run_status = ready`
- `http://127.0.0.1:3210/api/status`
  - `version = 0.4.43`
- uninstall registry:
  - `DisplayVersion = 0.4.43`

## Živi API dokaz

`/api/server/status` sada vraća `commandPreview` sa:

- `shellLabel = PowerShell`
- `activeCommand`
- `modelPath`
- runtime varijantama za `llama.cpp` i `TurboQuant`

`/api/opencode/status` sada vraća `launchPreview` sa:

- `launcherCommand`
- `powershellCommand`
- `workingDirectory`
- env promenljivama za managed OpenCode tok

## Zaključak

`v0.4.43` je validiran kao isporučena verzija za:

- korisnički editabilne workflow preset-e
- jasniji workflow UX
- stvarne ekvivalentne CLI komande za runtime i OpenCode
- uspešan lokalni installer upgrade na ovoj mašini


