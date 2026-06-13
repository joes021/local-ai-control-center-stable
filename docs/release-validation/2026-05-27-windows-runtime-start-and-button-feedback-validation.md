## Windows runtime start and button feedback validation

Date: 2026-05-27

Scope:
- uklonjen je preostri compatibility hard-block iz `Start runtime server` toka
- dodata su hover / active / focus-visible stanja za glavna panel dugmad
- verifikovan je lokalni upgrade i upgrade na masini `192.0.2.10`

### Kod promene

- `src/local_ai_control_center_installer/control_center_backend/services/server_service.py`
  - `start_server()` vise ne odbija start samo zato sto compatibility procena kaze `ne radi`
  - hardverski rizik ostaje upozorenje i confirmation u model activation toku, ne runtime start blok
- `frontend/src/styles.css`
  - dodati su transition, hover, active i focus-visible stilovi za glavna dugmad panela
- `tests/test_control_center_server.py`
  - regresija zakljucava da se hardware-risky aktivni model ipak pokusava startovati
- `tests/test_control_center_frontend_dist.py`
  - regresija zakljucava prisustvo hover/active/focus CSS stanja u spakovanom bundle-u

### Testovi

```powershell
python -m pytest tests\test_control_center_server.py -q
python -m pytest tests\test_control_center_models_service.py -q
python -m pytest tests\test_control_center_frontend_dist.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging\build_windows_installer.ps1 -PythonExe python
```

Rezultat:
- `tests/test_control_center_server.py` -> `16 passed`
- `tests/test_control_center_models_service.py` -> `13 passed`
- `tests/test_control_center_frontend_dist.py` -> `31 passed`
- `python -m pytest -q` -> `487 passed`
- `python -m build` -> uspeh
- `packaging/build_windows_installer.ps1 -PythonExe python` -> uspeh

### Lokalna masina

Upgrade:
- `dist/LocalAIControlCenterSetup-v0.4.34.exe`

Potvrda:
- `http://127.0.0.1:3210/api/status` vraca `version = 0.4.34`
- spakovani panel servira CSS asset sa:
  - `:hover:not(:disabled)`
  - `:active:not(:disabled)`
  - `translateY(-1px)`
  - `translateY(1px)`

### Masina 192.0.2.10

Upgrade:
- `LocalAIControlCenterSetup-v0.4.34.exe` je kopiran i pokrenut preko SSH
- installer je zavrsio sa `product_installation_status = complete`

Zivi panel tok potvrden u istom remote run-u:
- `GET /api/status`
  - `version = 0.4.34`
  - `activeRuntimeLabel = llama.cpp`
- `GET /api/server/status` pre klika
  - `status = degraded`
  - `pid = 8252`
  - `healthReason = Runtime proces postoji, ali health endpoint ne odgovara.`
- `POST /api/server/start`
  - `status = ok`
  - `summary = Runtime server je vec u fazi zagrevanja i health jos nije spreman.`
- `GET /api/server/status` posle klika
  - `status = warming`
  - `health = loading`
  - `activeRuntimeLabel = llama.cpp`

Poštena napomena:
- poseban novi non-interactive SSH shell i dalje nije pouzdan dokaz da desktop panel proces ostaje ziv izvan korisnicke sesije
- to je vec poznata ivica remote-admin toka
- ali konkretni korisnicki kvar iz GUI panela je zatvoren: `Start runtime server` vise nije odbijen laznim compatibility hard-block-om


