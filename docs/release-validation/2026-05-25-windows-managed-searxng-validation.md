# Windows managed SearxNG validation - 2026-05-25

## Scope

Potvrda da `v0.4.26` vise:

- ne podrazumeva lazni `http://127.0.0.1:8080`
- jasno prikazuje `SearxNG nije podesen`
- ume da podigne sopstveni managed `SearxNG` preko `Windows + WSL`

## Automated verification

- `python -m pytest -q`
  - rezultat: `476 passed`
- `python -m build`
  - rezultat: uspesan `sdist` i `wheel`
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
  - rezultat: uspesan `LocalAIControlCenterSetup-v0.4.26.exe`

## Regression fixes closed in this slice

- Stari `webSearchBaseUrl = http://127.0.0.1:8080` iz legacy settings-a se sada migrira u `not-configured` stanje umesto da se tretira kao validan manual endpoint.
- `WSL` lista distribucija vise ne lomi bootstrap zbog nul-bajtova u izlazu.
- Managed bootstrap skripta se sada zapisuje sa Unix newline formatom.
- Managed bootstrap koristi `$HOME/...` putanje umesto neprosirenog `~`.
- Managed bootstrap izvozi potrebne env promenljive za unutrasnji Python korak.
- Managed bootstrap cisti polovicno kloniran repo pre novog clone pokusaja.

## Local installed-app smoke

Masina:

- lokalna Windows instalacija u `C:\Users\<user>\LocalAIControlCenter`
- Control Center UI na `http://127.0.0.1:3210/`

Potvrdeno:

1. Lokalni upgrade na `0.4.26` je prosao.
   - registry `DisplayVersion = 0.4.26`
   - `GET /api/status` vraca `version = 0.4.26`

2. Nakon upgrade-a `GET /api/search` vise ne prijavljuje legacy `8080`.
   - `settings.baseUrl = ""`
   - `providerStatus.status = not-configured`
   - `providerStatus.summary = "SearxNG nije podesen..."`

3. Nakon gasenja managed stanja i brisanja `search-provider.json`, instalirana aplikacija je uspesno podigla SearxNG kroz:
   - `POST /api/search/provider/bootstrap`
   - rezultat: `status = ok`
   - `providerStatus.status = healthy`
   - `providerStatus.effectiveBaseUrl = http://127.0.0.1:18083/search`

4. Ziva search query provera na instaliranoj aplikaciji:
   - `POST /api/search/query`
   - primer query: `koji je danas dan`
   - rezultat: `status = ok`
   - `resultCount = 5`

## Honest limits

- Managed SearxNG bootstrap je trenutno namenjen `Windows + WSL` putu.
- Provider state trenutno cuva WSL putanje sa `$HOME/...` oblikom, sto je namerno i citljivo, ali nisu ekspandovane Windows putanje.
- Shared local search sloj i dalje vazi za `Search` tab i lokalni `local-lacc` runtime proxy; cloud `opencode` provider nije ukljucen u ovaj local proxy tok.
