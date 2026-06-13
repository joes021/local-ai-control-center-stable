# RuntimePilot Phase 4 + 5 Release Validation

Datum: 2026-06-02  
Repo: `C:\repo\local-ai-control-center-stable`

## Scope

- `Phase 4`: javni Windows artefakt nazivi prelaze na `RuntimePilotSetup`, `RuntimePilotPanel` i `Open-RuntimePilot`
- `Phase 5`: portal dobija vidljiviji RuntimePilot shell kroz zajedničke surface komponente

## Provere

- `python -m pytest -q`
  - rezultat: `641 passed, 1 warning`
- `python -m build`
  - rezultat: uspešno
- `powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python`
  - rezultat: uspešno
  - novi setup: `dist\RuntimePilotSetup-v0.4.87.exe`
  - latest alias: `dist\RuntimePilotSetup-latest.exe`
- `dist\SHA256SUMS-v0.4.87.txt`
  - rezultat: generisan za setup, latest setup, wheel i sdist

## UI potvrda

- živi portal na `http://127.0.0.1:3210/` je otvoren sa cache-buster URL-om
- potvrđeno vizuelno:
  - RuntimePilot hero/header
  - novi `RuntimePilot Control Deck` shell
  - pojačan `Živi resursi` komandni strip
  - vidljivije sekcijske surface kartice na početnoj strani
- lokalni screenshot provere:
  - `tmp/runtimepilot-phase45-preview.png`

## Napomena o lokalnoj verziji

- `http://127.0.0.1:3210/api/status` u trenutku validacije i dalje vraća `version = 0.4.86`
- to je posledica postojećeg lokalnog install-report / registry stanja
- Phase 4 + 5 promene su potvrđene kroz:
  - živi portal koji servira osvežen frontend shell
  - sveže izgrađene `0.4.87` release artefakte

## Zaključak

- RuntimePilot `Phase 4` i `Phase 5` su spremne za release
- novi javni artefakt naming i vidljiviji portal shell su provereni kroz testove, build i live preview


