# v0.4.46 - benchmark battery repeat validation

## Šta je dodato

- `Pokreni celu bateriju` je proširen tako da postoje i duži režimi:
  - `Pokreni bateriju x2`
  - `Pokreni bateriju x5`
  - `Pokreni bateriju x10`
- backend sada isti battery scenario niz izvršava više puta u okviru jednog pokretanja, umesto da glumi dužinu veštačkim čekanjem.
- aktivni battery run sada iskreno prijavljuje:
  - `repeatCount`
  - proširen `totalScenarios`
  - proširene `scenarioStatuses`

## Tehnička istina

- `run-battery` ruta sada prima `repeatCount`
- dozvoljen opseg je `1..10`
- svaki scenario dobija prošireni identitet po prolazu, na primer:
  - `short__pass_1_of_5`
  - `long__pass_4_of_10`
- poruka pokretanja sada jasno kaže da li je baterija pokrenuta kao `x2`, `x5` ili `x10`

## Verifikacija

- `python -m pytest tests\test_control_center_benchmark.py tests\test_control_center_benchmark_routes.py tests\test_control_center_frontend_dist.py -q` -> zeleno
- `python -m pytest -q` -> `517 passed`
- `python -m build` -> uspešno
- `packaging/build_windows_installer.ps1 -PythonExe python` -> uspešno
- lokalni installer upgrade na ovoj mašini -> uspešan
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
- `http://127.0.0.1:3210/api/status` vraća `version = 0.4.46`
- uninstall registry pokazuje `DisplayVersion = 0.4.46`

## Živi benchmark dokaz

Na instaliranoj aplikaciji na ovoj mašini potvrđena su dva stvarna slučaja:

- postojeći duži run je završio sa:
  - `repeatCount = 10`
  - `totalScenarios = 40`
- novi kontrolni `x2` run je završio sa:
  - `repeatCount = 2`
  - `totalScenarios = 8`
  - završna poruka: `Benchmark baterija x2 je pokrenuta.`

## Važna napomena

- ovaj slice produžava stvarni battery benchmark tako što ponavlja scenarije i tako daje više pravih benchmark uzoraka kroz vreme
- `Uživo sada` i dalje zavisi od stvarnog live runtime signala; kada ga runtime ne emituje, telemetry ostaje pošteno prazan umesto da izmišlja tok


