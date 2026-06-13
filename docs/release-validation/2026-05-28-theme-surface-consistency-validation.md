# Theme Surface Consistency Validation

## Verzija

- `v0.4.47`

## Šta je provereno

- promene teme sada boje `Settings` labele i placeholder tekst
- `CustomSelect` trigger, meni i izabrane stavke više ne ostaju u bojama podrazumevane teme
- `Compatibility` badge-evi sada koriste theme promenljive
- `Browser` tabela, source badge-evi i sort dugmad sada koriste theme promenljive
- paketovani frontend bundle sadrži nove theme-aware stilove

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
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.47`
- uninstall registry -> `DisplayVersion = 0.4.47`
- installer report -> `product_installation_status = complete`


