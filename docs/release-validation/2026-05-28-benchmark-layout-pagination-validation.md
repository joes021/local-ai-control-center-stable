# Benchmark Layout And Pagination Validation

## Verzija

- `v0.4.48`

## Šta je provereno

- `Grafikon benchmarka` stoji neposredno ispod `Telemetrija`
- `Benchmark istorija` prikazuje najviše `10` rezultata po strani
- istorija ima paginaciju sa `Prethodna strana` i `Sledeća strana`
- paketovani frontend bundle sadrži novu benchmark paginaciju i novi raspored

## Komande

- `python -m pytest tests/test_control_center_frontend_dist.py -q`
- `python -m pytest -q`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`

## Rezultati

- `python -m pytest tests/test_control_center_frontend_dist.py -q` -> `44 passed`
- `python -m pytest -q` -> `518 passed`
- `python -m build` -> uspešno
- `packaging/build_windows_installer.ps1 -PythonExe python` -> uspešno
- lokalni installer upgrade na ovoj mašini -> uspešan


