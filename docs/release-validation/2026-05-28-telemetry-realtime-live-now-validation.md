# v0.4.45 - telemetry real-time live-now validation

## Šta je popravljeno

- `Uživo sada` više ne pokušava da prikazuje throughput iz skorašnjeg benchmarka kao da je i dalje aktivan.
- veliki broj u telemetry kartici sada dolazi isključivo iz stvarnog live runtime signala dok tokeni zaista teku.
- `Home` i `Benchmark` sada osvežavaju benchmark signal dovoljno brzo da kratki benchmark run više ne prođe neprimećeno.

## Tehnička istina

- backend više ne meša `recent benchmark` fallback u `telemetry.liveNowTokensPerSecond`
- `telemetry.lastSignalTokensPerSecond` i dalje čuva poslednji throughput kao manji referentni signal
- `frontend/src/pages/HomePage.tsx` ima:
  - sporo opšte osvežavanje (`5000 ms`)
  - odvojeno benchmark real-time osvežavanje (`1000 ms`)
- `frontend/src/pages/BenchmarkPage.tsx` sada benchmark summary osvežava na `1000 ms`

## Verifikacija

- `python -m pytest tests\test_control_center_benchmark.py tests\test_control_center_frontend_dist.py -q` -> `54 passed`
- `python -m pytest -q` -> `515 passed`
- `python -m build` -> uspešno
- `packaging/build_windows_installer.ps1 -PythonExe python` -> uspešno
- lokalni installer upgrade na ovoj mašini -> uspešan
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
- `http://127.0.0.1:3210/api/status` vraća `version = 0.4.45`

## Živi telemetry dokaz

Pokrenut je `long` benchmark scenario preko instalirane aplikacije na ovoj mašini i posmatran je `/api/benchmark` na svakih `500 ms`.

Posmatranje:

- `0.5s`
  - `runStatus = running`
  - `liveNow = 76.35`
  - `flowState = active-generation`
- `1.0s`
  - `runStatus = running`
  - `liveNow = 72.62`
  - `flowState = active-generation`
- `1.5s`
  - `runStatus = done`
  - `liveNow = null`
  - `lastSignal = 79.41`
  - `flowState = recent-benchmark`

Zaključak:

- broj u `Uživo sada` postoji samo dok benchmark stvarno generiše tokene
- čim generacija stane, veliki broj nestaje
- poslednji signal ostaje dostupan samo kao manji referentni throughput zapis
