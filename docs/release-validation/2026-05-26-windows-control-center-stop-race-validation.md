# Windows Control Center Stop Race Validation - 2026-05-26

## Scope

Ova validacija zatvara drugi realni installer kvar otkriven na masini `192.0.2.10` tokom upgrada sa `0.4.22`:

- installer nadje zdrav postojeci panel
- panel PID se procita
- u trenutku `taskkill` taj PID vec vise ne postoji
- installer pada sa:
  - `Control Center panel nije mogao da se zaustavi: ERROR: The process "<pid>" not found.`

## Root cause

Stop put je tretirao `taskkill` / terminate poruku `process not found` kao fatalnu gresku, iako je to zapravo benigni race:

- proces je vec nestao
- port vrlo verovatno vec nije zauzet

Posle toga je installer padao iako je konflikt prakticno nestao sam od sebe.

## Fix

U `control_center_runtime.py` uvedena je tolerancija za benigni stop-race:

- `not found`
- `no such process`

Takve poruke vise ne obaraju install tok same po sebi.

Vazna granica:

- stvarne stop greske i dalje ostaju fatalne
- ako port ostane zauzet, sledeci wait/probe korak i dalje posteno pada

## Test evidence

Novi regresioni test:

- `test_deploy_control_center_runtime_tolerates_panel_process_already_gone`

Verifikacija:

- `python -m pytest tests\test_control_center_runtime_deploy.py -q`
  - rezultat: `11 passed`

## Full verification gate

Puni gate za `v0.4.32` je prosao:

- `python -m pytest -q`
  - rezultat: `484 passed`
- `python -m build`
  - rezultat: uspeh
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
  - rezultat: uspeh

## Local machine validation

Na ovoj masini je uradjen stvarni installer update preko:

- `LocalAIControlCenterSetup-v0.4.32.exe`

Potvrdjeno:

- registry:
  - `DisplayVersion = 0.4.32`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json`
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
- `http://127.0.0.1:3210/health`
  - `status = ok`

## Remote machine validation

Ovaj fix je potvrden stvarnim upgrade tokom na:

- `<remote-user>@192.0.2.10`
- install root:
  - `C:\Users\<remote-user>\LocalAIControlCenter`

Rezultat stvarnog upgrada:

- registry:
  - `DisplayVersion = 0.4.32`
- `C:\Users\<remote-user>\LocalAIControlCenter\logs\install-report.json`
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `failing_step = null`

## Honest boundary

Ova validacija zatvara installer stop-race.

Posebna ivica koja i dalje ostaje van ovog fixa:

- kada se Control Center pokrece iz cistog non-interactive SSH toka, panel proces ne ostaje pouzdano ziv posle zatvaranja te SSH sesije
- to nije blokiralo installer uspesnost niti upgrade na `192.0.2.10`
- to ostaje zaseban remote-launch polish ako kasnije budemo hteli da i taj put bude potpuno robustan
