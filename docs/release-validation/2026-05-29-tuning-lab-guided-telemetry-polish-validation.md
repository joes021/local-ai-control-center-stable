# v0.4.70 - Tuning Lab guided telemetry polish validation

## Scope

Ova validacija pokriva dva povezana polish zahvata:

- `Tuning Lab` batch task kartice sada vode korisnika kroz jedan jasan tok u istoj kartici:
  - `1. Učitaj task`
  - `2. Pokreni task`
  - `3. Otvori rezultat`
- `Benchmark` graf sada jasnije objašnjava da prikazuje sav `llama.cpp`-kompatibilni `/slots` throughput, uključujući `Tuning Lab` signal i druge lokalne tokove.

## Promene u kodu

- `frontend/src/pages/TuningLabPage.tsx`
  - osnovne akcije su grupisane u `tuning-lab-batch-action-rail`
  - brzi tok više ne tera korisnika da juri dugmad između kartice i donjeg editora
- `frontend/src/pages/BenchmarkPage.tsx`
  - dodat je blok `Izvori llama.cpp signala`
  - prikazuju se dinamički izvori signala u aktuelnom opsegu, uz fallback orijentire
- `frontend/src/styles.css`
  - dodat je stil za novu task action rail grupu
  - dodat je stil za benchmark source summary i chip red

## Testovi

Pokrenuto:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Rezultat:

- `tests/test_control_center_frontend_dist.py` -> `52 passed`
- puni suite -> `564 passed`
- `python -m build` -> uspešno
- Windows installer build -> uspešno

## Živa provera

Lokalni installer upgrade:

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.70.exe`
- installer report:
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`

Živi API:

- `http://127.0.0.1:3210/api/status` -> `version = 0.4.70`
- uninstall registry -> `DisplayVersion = 0.4.70`

Živi frontend bundle:

- `http://127.0.0.1:3210/` referencira:
  - `assets/index-CENhB34j.js`
  - `assets/index-mq7vyyTK.css`
- provereno da bundle sadrži:
  - `1. Učitaj task`
  - `Sve osnovne akcije za ovaj task ostaju u istoj kartici.`
  - `Izvori llama.cpp signala`

## Zaključak

`v0.4.70` zatvara UX problem razbacanog osnovnog toka u `Tuning Lab` batch sekciji i čini `Benchmark` graf poštenijim i razumljivijim kada signal dolazi iz više `llama.cpp`-kompatibilnih tokova.
