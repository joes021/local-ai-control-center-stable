# v0.4.71 - browser catalog SSL hardening validation

## Problem

Na ovoj Windows mašini `Browser` katalog nije prikazivao modele ni posle `Refresh from internet`.

Vidljivi simptom u UI-ju:

- `HF: 0`
- `Unsloth: 0`
- greške:
  - `CERTIFICATE_VERIFY_FAILED`
  - `Basic Constraints of CA cert not marked critical`

## Root cause

`Browser` source fetch je i dalje koristio direktan `urllib.request.urlopen(...)` bez istog SSL hardening sloja koji već postoji u `Search` fetch logici.

To je značilo:

- normalan HTTPS fetch puca na ovoj Windows CA/TLS ivici
- `Hugging Face` i `Unsloth` katalog ostaju prazni
- keš čuva samo poslednju grešku i brojače `0`

## Fix

Izmena je urađena u:

- `src/local_ai_control_center_installer/control_center_backend/services/browser_sources.py`

Dodato je:

- `certifi`-bazirani outbound SSL context
- fallback retry sa relaksiranim SSL context-om samo kada je uzrok baš `SSLCertVerificationError`
- zadržan je isti javni API Browser source fetch-a

## Testovi

Pokrenuto:

```powershell
python -m pytest tests/test_control_center_browser_sources.py -q
python -m pytest tests/test_control_center_browser_sources.py tests/test_control_center_browser_catalog_service.py tests/test_control_center_browser_routes.py -q
python -m pytest -q
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Rezultat:

- `tests/test_control_center_browser_sources.py` -> `4 passed`
- browser slice -> `14 passed`
- puni suite -> `565 passed`
- `python -m build` -> uspešno
- Windows installer build -> uspešno

## Živa provera

Repo-level direktna provera:

- `fetch_huggingface_catalog(limit=5)` -> `30` modela, bez error-a
- `fetch_unsloth_catalog(limit=5)` -> `139` modela, bez error-a

Lokalni installer upgrade:

- pokrenut `dist\LocalAIControlCenterSetup-v0.4.71.exe`
- `http://127.0.0.1:3210/api/status` -> `version = 0.4.71`
- uninstall registry -> `DisplayVersion = 0.4.71`

Živi Browser refresh kroz instalirani panel:

```json
{
  "refreshAll": 5494,
  "refreshHF": 584,
  "refreshUnsloth": 4910,
  "refreshErrors": "",
  "catalogAll": 5494,
  "catalogHF": 584,
  "catalogUnsloth": 4910,
  "catalogErrors": ""
}
```

## Zaključak

`v0.4.71` zatvara Browser katalog SSL kvar na ovoj mašini. `Refresh from internet` sada stvarno puni katalog umesto da ostane na `HF: 0`, `Unsloth: 0` i `CERTIFICATE_VERIFY_FAILED`.
