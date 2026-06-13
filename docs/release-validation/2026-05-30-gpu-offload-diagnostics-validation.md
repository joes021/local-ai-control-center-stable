# v0.4.76 - GPU offload diagnostics validation

## Scope

Ova validacija pokriva poseban GPU offload dijagnosticki krug za:

- `llama.cpp`
- `TurboQuant`
- `Tuning Lab` slot runtime

Glavni cilj je bio da portal jasno razdvoji:

- sta launch komanda trazi
- sta runtime log stvarno potvrdjuje

## Promene u kodu

- `src/local_ai_control_center_installer/control_center_backend/services/server_service.py`
  - dodat `load_runtime_diagnostics(...)`
  - `/api/server/status` sada vraca `runtimeDiagnostics`
  - `KV buffer` vise ne sabira stare restart sekvence iz celog log fajla
- `src/local_ai_control_center_installer/control_center_backend/services/tuning_lab_service.py`
  - slot runtime sada nosi `runtimeDiagnostics`
  - aktivni slot moze da predje iz `requested` u `confirmed` kada log da dokaz
- `frontend/src/pages/ServerPage.tsx`
  - dodat blok `GPU offload dijagnostika`
- `frontend/src/pages/TuningLabPage.tsx`
  - dodat isti dijagnosticki blok u `Aktivni run cockpit`
  - jasnije razdvojene metrike:
    - `Ziva generacija`
    - `Zivi ukupno`
    - `Prompt ingest`
    - `Runtime generacija`

## Testovi

Pokrenuto:

```powershell
python -m pytest tests/test_control_center_server.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Rezultat:

- `tests/test_control_center_server.py` -> `19 passed`
- puni suite -> `585 passed`
- `python -m build` -> uspesno
- Windows installer build -> uspesno

## Ziva provera

Repo-level direktna provera nad stvarnim instaliranim logovima:

- aktivni runtime: `llama.cpp`
- aktivni binar:
  - `C:\Users\<user>\LocalAIControlCenter\runtime\llama.cpp\llama-server.exe`

Glavni runtime:

- `status = confirmed`
- `backend = CUDA`
- `device = NVIDIA GeForce RTX 3060`
- launch trazi:
  - `--n-gpu-layers 40`
  - `--flash-attn auto`
- runtime log potvrdjuje:
  - `offload 35/35 slojeva`
  - `model buffer = 2368.31 MiB`
  - `KV buffer = 522.00 MiB`
  - `compute buffer = 275.02 MiB`

Najnoviji `Tuning Lab` slot log:

- `status = requested`
- launch trazi:
  - `--n-gpu-layers 40`
  - `--flash-attn auto`
- taj konkretan slot log jos nije dao citljiv `confirmed` dokaz

## Lokalni upgrade

Lokalna instalacija je podignuta na `0.4.76`.

Potvrdjeno:

- uninstall registry:
  - `DisplayVersion = 0.4.76`
- zivi API:
  - `http://127.0.0.1:3210/api/status` vraca `version = 0.4.76`

## Zivi TurboQuant smoke

Privremeno je izabran `TurboQuant`, pokrenut runtime, proverena dijagnostika, a zatim je izbor vracen na `llama.cpp`.

Potvrdjeno kroz `http://127.0.0.1:3210/api/server/status`:

- `activeRuntime = turboquant`
- `runtimeDiagnostics.status = confirmed`
- `backend = CUDA`
- `device = NVIDIA GeForce RTX 3060`
- `confirmedGpuLayers = 43`
- `confirmedTotalLayers = 43`
- `modelBufferMiB = 2883.51`
- `kvBufferMiB = 100.00`
- `computeBufferMiB = 292.02`

Posle smoke provere runtime izbor je vracen na:

- `requestedRuntimeLabel = llama.cpp`
- `runtimeLiveStatus = started`

## Zakljucak

`v0.4.76` zatvara glavnu dijagnosticku rupu:

- portal sada ne mesa `planirano` i `dokazano`
- glavni `llama.cpp` GPU offload je zivo potvrden kroz runtime log
- `TurboQuant` i `Tuning Lab` koriste isti dijagnosticki model
- `KV buffer` vise nije lazno naduvan sabiranjem starih restart blokova


