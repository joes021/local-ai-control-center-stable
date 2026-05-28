# Windows Validation - Telemetry Live Now Truth

Datum: 2026-05-28  
Verzija: v0.4.44

## Scope

Ovaj prolaz zatvara UX problem na telemetry kartici:

- veliki broj `Uživo sada` više ne sme da prikazuje stari benchmark throughput kao da je trenutno live stanje
- kada nema aktivnog live signala, veliki broj mora da bude prazan
- poslednji throughput signal ostaje vidljiv samo kao manji referentni prikaz

## Implementirano

- backend telemetry summary sada razdvaja:
  - `liveNowTokensPerSecond`
    - samo stvarni trenutni live signal iz runtime-a
  - `lastSignalTokensPerSecond`
    - poslednji poznati throughput signal za referencu
  - `lastSignalStateLabel`
  - `lastSignalLabel`
  - `lastSignalAt`
- `TelemetryPanel` sada:
  - veliki broj koristi samo `liveNowTokensPerSecond`
  - kada live signal ne postoji, `Uživo sada` ne prikazuje stari benchmark throughput
  - prikazuje manji blok `Poslednji throughput signal` samo kada postoji referentni poslednji signal

## Testovi

Pokrenuto:

```powershell
python -m pytest tests\test_control_center_benchmark.py -q
python -m pytest tests\test_control_center_frontend_dist.py -q
python -m pytest -q
```

Rezultat:

- `11 passed`
- `43 passed`
- `512 passed`

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
  - `dist/LocalAIControlCenterSetup-v0.4.44.exe`

## Lokalni upgrade

Ova mašina je podignuta na `0.4.44`.

Potvrđeno:

- `http://127.0.0.1:3210/api/status`
  - `version = 0.4.44`
- uninstall registry:
  - `DisplayVersion = 0.4.44`
- `C:\Users\<user>\LocalAIControlCenter\logs\install-report.json`
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`

## Živi API dokaz

Na instaliranoj aplikaciji `/api/benchmark` sada vraća:

- `liveNowTokensPerSecond = null`
- `lastSignalTokensPerSecond = null`
- `flowState = quiet`

To potvrđuje da se stari throughput više ne prikazuje kao aktivan `Uživo sada` signal kada runtime trenutno nema live saobraćaj.

## Zaključak

`v0.4.44` zatvara problem lažnog live throughput prikaza na telemetry kartici i razdvaja:

- stvarno trenutno live stanje
- poslednji throughput signal kao referentni, manji prikaz
