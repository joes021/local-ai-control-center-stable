# Windows Search Provider WSL Timeout Validation - 2026-05-26

## Scope

Ova validacija zatvara realni kvar prijavljen sa masine `192.0.2.10`:

- otvaranje `Settings` trazi `searchProviderStatus`
- `searchProviderStatus` proverava managed SearxNG bootstrap preko:
  - `wsl -l -q`
- kada taj WSL poziv visi, backend baca:
  - `subprocess.TimeoutExpired: Command '['wsl', '-l', '-q']' timed out ...`
- rezultat je `500` na `/api/settings`

## Root cause

`_describe_bootstrap_capability()` nije hvatala `subprocess.TimeoutExpired`.

Zbog toga je pomocna WSL provera mogla da:

- obori ceo `Settings` payload
- ponovi isti spori timeout na svakom sledecem request-u

## Fix

U `search_provider_service.py` je dodato:

- hvatanje `subprocess.TimeoutExpired`
- pošten fallback razlog:
  - `WSL trenutno ne odgovara na proveru distro liste.`
- kratak cache za bootstrap capability rezultat
  - da sledeci request ne ponavlja odmah isti spori WSL timeout
- iskreniji `not-configured` summary kada managed bootstrap trenutno nije dostupan

## Test evidence

Novi regresioni testovi:

- `test_search_provider_status_handles_wsl_probe_timeout_without_raising`
- `test_search_provider_status_caches_wsl_probe_timeout_result`

Verifikacija:

- `python -m pytest tests\test_control_center_search_provider.py -q`
  - rezultat: `9 passed`

Puni gate:

- `python -m pytest -q`
  - rezultat: `486 passed`
- `python -m build`
  - rezultat: uspeh
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
  - rezultat: uspeh

## Real machine validation

Lokalna masina posle upgrada na `0.4.33`:

- `http://127.0.0.1:3210/api/settings`
  - vraca normalan JSON payload
  - ne baca `500`

Masina `192.0.2.10` posle upgrada na `0.4.33`:

- registry:
  - `DisplayVersion = 0.4.33`
- installer report:
  - `product_installation_status = complete`
- zivi `api/settings` payload iz iste udaljene sesije:
  - `searchStatus = not-configured`
  - `searchSummary = SearxNG nije podesen. Managed bootstrap trenutno nije dostupan: WSL trenutno ne odgovara na proveru distro liste.`
  - `canBootstrap = false`

To znaci da isti scenario vise ne obara backend, nego vraca pošten status.

## Expected product behavior

Kada WSL trenutno ne odgovara:

- `Settings` vise ne sme da vrati `500`
- UI treba da dobije normalan payload
- `searchProviderStatus` treba da kaze da managed bootstrap trenutno nije dostupan
- sledeci request ne treba odmah opet da blokira na punom WSL timeout-u
