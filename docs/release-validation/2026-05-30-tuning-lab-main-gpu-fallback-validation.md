# 2026-05-30 Tuning Lab `main_gpu` fallback validation

## Scope

- zatvoren je kvar gde `Tuning Lab` slot runtime pada odmah pri startu sa:
  - `invalid value for main_gpu: 0 (available devices: 0)`
- fallback se aktivira samo za taj konkretan kvar:
  - prvi pokušaj koristi puni launch sa `--main-gpu` i `--split-mode`
  - drugi pokušaj automatski ponavlja start bez ta dva argumenta
- korisnički signal ostaje pošten:
  - runtime dijagnostika sada ume da kaže da je fallback bio primenjen

## Root cause

`Tuning Lab` je slot runtime-u bezuslovno prosleđivao isti eksplicitni GPU izbor koji glavni runtime koristi uspešno. Kod dela `llama.cpp` launch situacija to je dovodilo do ranog fatalnog pada pre nego što runtime postane spreman, i ceo slot se vodio kao `failed`.

## Test evidence

Pokrenuto:

```powershell
python -m pytest tests/test_control_center_tuning_lab.py -q
python -m pytest tests/test_control_center_server.py -q
python -m pytest tests/test_control_center_observability.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Rezultati:

- `tests/test_control_center_tuning_lab.py` -> `29 passed`
- `tests/test_control_center_server.py` -> `21 passed`
- `tests/test_control_center_observability.py` -> `1 passed`
- puni suite -> `594 passed, 1 warning`
- `python -m build` -> uspešno
- Windows installer build -> uspešno

## Regression coverage

Dodat je ciljani test za scenario:

- prvi launch sadrži `--main-gpu 0 --split-mode none`
- runtime log vrati `invalid value for main_gpu`
- drugi launch automatski uklanja `--main-gpu` i `--split-mode`
- slot runtime uspešno nastavlja

## Release outcome

- verzija podignuta na `0.4.80`
- novi setup artefakti napravljeni u `dist/`
