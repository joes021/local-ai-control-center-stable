# RuntimePilot Project Memory Phase 1 Release Validation

Datum: 2026-06-05  
Repo: `C:\repo\local-ai-control-center-stable`

## Scope

- `Project Memory Phase 1` je uveden u RuntimePilot sa trajnim backend store slojem, API rutama, posebnom stranom i globalnim shell stripom
- `Tuning Lab` sada ume da poseje početnu projektnu memoriju iz task teksta kada run krene
- `TurboQuant parametri -> Context` sada koristi isti izborni tok kao `Opšta podešavanja -> Context`
- `Tuning Lab` rezultat panel više ne prikazuje lažnu oznaku `Greška` za `accepted` i srodne statuse u toku
- browser tab sada dobija RuntimePilot favicon
- `Lokalni modeli` više ne ostaju zarobljeni u uskoj visokoj koloni
- `Project Memory` prazna stanja i raspored kartica su doterani za normalan 2x2 prikaz

## Provere

- `python -m pytest -q`
  - rezultat: `664 passed, 1 warning`
- `python -m build`
  - rezultat: uspešno
  - novi Python artefakti:
    - `dist\local_ai_control_center_installer-0.4.89-py3-none-any.whl`
    - `dist\local_ai_control_center_installer-0.4.89.tar.gz`
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python`
  - rezultat: uspešno
  - novi setup: `dist\RuntimePilotSetup-v0.4.89.exe`
  - latest alias: `dist\RuntimePilotSetup-latest.exe`
- `dist\SHA256SUMS-v0.4.89.txt`
  - rezultat: generisan za setup, latest setup, wheel i sdist

## UI potvrda

- paketovani frontend sada sadrži:
  - `assets/index-Du9TqAML.js`
  - `assets/index-CUIZp-Y0.css`
- `Project Memory` strana sada ima:
  - širi 2x2 grid
  - jasna prazna stanja
  - shell strip sa fokusom projekta
- `TurboQuant Context` koristi isti dropdown + `custom` obrazac kao opšta podešavanja
- browser tab favicon ruta `/runtimepilot-favicon.png` je uključena u paketovani frontend

## Zaključak

- release `0.4.89` je spreman za GitHub objavu
- testovi, wheel/sdist build i Windows installer build su prošli u istom krugu verifikacije


