# v0.4.72 - tuning lab cockpit validation

## Problem

`Tuning Lab` je stvarno pokretao `OpenCode` taskove u pozadini, ali UI nije ulivao poverenje:

- korisnik nije imao jasan vrh strane koji pokazuje sta je aktivno
- nije bilo dovoljno ocigledno da queue radi sekvencijalno
- nije se jasno video runtime/workspace/log kontekst dok run traje
- batch akcije su delovale rasute i trazile su previse skrolovanja

## Root cause

Portal je imao status poruke i istoriju, ali nije imao jedinstven "cockpit" za aktivni run.

Zbog toga je pravi background `OpenCode` rad ostajao sakriven iza:

- poruke tipa `OpenCode task radi`
- odvojenog queue prikaza
- donjeg editora i istorije

Korisnik nije imao jedan jasan pogled koji odgovara na:

- koji task sada radi
- koji slot sada radi
- da li queue ide redom ili paralelno
- gde je workspace
- koji log i komanda pripadaju tom run-u

## Fix

Izmene su uradjene u:

- `frontend/src/pages/TuningLabPage.tsx`
- `frontend/src/styles.css`
- `frontend/src/lib/types.ts`
- `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`

Dodato je:

- vrh strane `Aktivni run cockpit`
- jasan sekvencijalni queue signal:
  - jedan run po jedan
  - jedan slot po jedan
- guided tok u batch kartici:
  - `1. Ucitaj task`
  - `2. Pokreni task`
  - `3. Otvori rezultat`
- aktivni run pregled sa:
  - aktivnim slotom
  - fazom
  - workspace putanjom
  - runtime base URL-om
  - live throughput signalom
  - poslednjim log signalom
  - copy akcijama za workspace, log i OpenCode komandu
- backend aktivnog run-a sada ume da upisuje live slot detalje tokom izvrsavanja:
  - `runtimePid`
  - `runtimeLogPath`
  - `opencodePid`
  - `stdoutPath`
  - `stderrPath`
  - `workspacePath`
  - `liveOutputTokensPerSecond`
  - `liveTotalTokensPerSecond`
  - `lastLiveMeasuredAt`

## Testovi

Pokrenuto:

```powershell
python -m pytest tests/test_control_center_tuning_lab.py -k visible_session -q
python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q
python -m pytest tests/test_control_center_tuning_lab.py tests/test_control_center_tuning_lab_routes.py tests/test_control_center_frontend_dist.py -q
python -m pytest tests/test_control_center_benchmark.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Rezultat:

- focused Tuning Lab session test -> prosao
- frontend dist Tuning Lab slice -> prosao
- combined tuning lab slice -> prosao
- benchmark slice -> `15 passed`
- puni suite -> `566 passed`
- `python -m build` -> uspesno
- Windows installer build -> uspesno

## Ziva provera

Lokalni installer upgrade:

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.72.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.72`
- `health = ok`
- `runtimeLiveStatus = started`

Zivi Tuning Lab status posle upgrada:

```json
{
  "activeRun": "Game Batch 01 · Balloon Blaster",
  "currentPhaseLabel": "OpenCode task radi",
  "currentStepSummary": "Baseline trenutno izvrsava zadatak nad izolovanim projektom.",
  "queue": ["Game Batch 01 · Octopus Invaders"]
}
```

Time je potvrdjeno:

- batch queue ostaje sekvencijalan
- portal prikazuje da je konkretan task stvarno aktivan
- nova verzija servira cockpit-ready Tuning Lab bundle

## Napomena

Ako je neki batch vec bio zapocet pre upgrada, njegov stari snapshot moze kratko da ostane siromasniji od potpuno novog cockpit prikaza. Sledeci novi run koristi puni `v0.4.72` cockpit tok od pocetka.

## Zakljucak

`v0.4.72` zatvara glavni trust/UX problem u `Tuning Lab`-u: korisnik sada dobija jedan jasan aktivni run cockpit umesto razbacanih statusa, a backend ume da nosi live session detalje koji takav cockpit hrane.
