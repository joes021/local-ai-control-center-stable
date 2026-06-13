# Benchmark Button Labels Validation

## Verzija

- `v0.4.49`

## Šta je provereno

- benchmark dugmad koriste kratke natpise `BX2`, `BX5` i `BX10`
- puna značenja ostaju dostupna kroz `title` tooltip
- paketovani frontend bundle sadrži nove kratke oznake

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


