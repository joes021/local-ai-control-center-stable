# 2026-05-29 OpenCode Bootstrap and Tuning Lab Unblock Validation

## Scope

Zatvoren je kvar gde je `Tuning Lab` na lokalnoj mašini delovao kao da se ništa ne dešava posle `Run`, a `OpenCode` tab je prijavljivao da `OpenCode` nije instaliran.

## Root cause

1. `OpenCode` stvarno nije bio prisutan u install root-u.
2. Novi `OpenCode bootstrap` tok je pucao pre download-a zato što je koristio puni installer download plan, a taj plan je zahtevao `starter_model` koji u repair/install-only toku nije bio postavljen.
3. Na ovoj Windows mašini Python `urlopen` download do GitHub release artefakta i dalje je padao sa `CERTIFICATE_VERIFY_FAILED`, pa je bio potreban Windows-native fallback.
4. `Tuning Lab` je imao ispravan blocker, ali UX nije dovoljno jasno pokazivao:
   - da `OpenCode` nedostaje
   - gde se editor nalazi
   - gde se vidi rezultat akcije

## Implemented fix

- `OpenCode bootstrap` sada koristi namenski `opencode-only` download plan i više ne zavisi od `starter_model`.
- `downloads.py` sada na Windows-u koristi `Invoke-WebRequest` fallback kada Python SSL padne na cert verification grešci.
- `OpenCode` tab sada prikazuje `Instaliraj ili popravi OpenCode`.
- `Tuning Lab` vršni blocker sada prikazuje isto dugme kada `OpenCode` nedostaje.
- rezultat akcije je pomeren više u `Tuning Lab` UI da ne ostane sakriven duboko na strani.
- copy za učitavanje task-a sada jasno kaže da je editor niže na strani, u sekciji `Eksperiment`.

## Verification

### Automated

- `python -m pytest -q`
  - `556 passed`
- `python -m build`
  - success
- `packaging/build_windows_installer.ps1 -PythonExe python`
  - success

### Live local verification

Lokalna instalacija je podignuta na `0.4.67` i panel je restartovan na glavnom portu `3210`.

- `GET /api/status`
  - `version = 0.4.67`
  - `health = ok`
  - `runtimeLiveStatus = started`
- `GET /api/opencode/status`
  - `available = true`
  - `canOpen = true`
  - `sessionState = runtime-ready`
- `POST /api/opencode/bootstrap`
  - `status = ok`
- `GET /api/tuning-lab`
  - `canQueue = true`
  - `runtimeBinaryReady = true`
  - `activeModelReady = true`
  - `opencodeReady = true`
  - `runBlockers = []`
- `POST /api/tuning-lab/queue`
  - accepted on live panel
- `GET /api/tuning-lab/run-status`
  - returned active run payload with non-empty `runId`, `status = running`, current slot and phase

## Result

`Tuning Lab` više nije blokiran lažno ili tiho zbog nedostajućeg `OpenCode`-a. Na ovoj mašini sada postoji:

- radni `OpenCode` bootstrap
- instaliran `OpenCode`
- živi `Run` acceptance i aktivan tuning run
- jasniji UI signal gde je editor i zašto je run ranije bio blokiran


