## Šta je novo

- `Game Batch 01` u `Tuning Lab`-u je vizuelno i UX smislenije ispoliran
- batch sada odmah pokazuje:
  - šta meri
  - koliko ima zadataka
  - koliko success check-ova koristi
  - da jedan klik pravi više pravih run-ova
- svaki task sada prikazuje:
  - `easy / medium / hard`
  - scope
  - fokus testa
  - očekivani artefakt
- jasno se vidi koji je batch task trenutno učitan u editor
- `Pokreni ceo batch` sada jasnije objašnjava da koristi trenutne `Baseline / Recommended / Custom` slot postavke

## Zašto je ovo važno

- `Tuning Lab` sada manje deluje kao interna lista promptova
- lakše je razumeti šta se tačno poredi
- lakše je izabrati pravi task pre queue-a
- batch se prirodnije povezuje sa editorom i postojećim tuning slotovima

## Verifikacija

- `python -m pytest -q` -> uspešno (`544 passed`)
- `python -m build` -> uspešno
- `packaging/build_windows_installer.ps1 -PythonExe python` -> uspešno
- lokalni upgrade na `0.4.63` -> uspešno
- živi `/api/tuning-lab` payload potvrđuje novi batch metadata sloj

## Artefakti

- `LocalAIControlCenterSetup-v0.4.63.exe`
- `LocalAIControlCenterSetup-latest.exe`
- `local_ai_control_center_installer-0.4.63-py3-none-any.whl`
- `local_ai_control_center_installer-0.4.63.tar.gz`
- `SHA256SUMS-v0.4.63.txt`
