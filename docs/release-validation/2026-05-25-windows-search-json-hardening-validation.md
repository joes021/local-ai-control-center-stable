# Windows SearxNG JSON Hardening Validation

## Scope

Ovaj validation zapis pokriva search fix za situaciju kada:

- `webSearchBaseUrl` vec pokazuje na `/search`
- SearxNG vrati HTML ili prazan odgovor umesto JSON-a

## Root cause

Problem je bio dvostruk:

- backend je slepo dodavao `/search`, pa je `http://host/search` postajao `http://host/search/search`
- kada odgovor nije bio JSON, korisnik je dobijao sirovu Python poruku tipa:
  - `Expecting value: line 1 column 1 (char 0)`

## Verifikacija

### 1. Ciljani search testovi

Komanda:

```powershell
python -m pytest tests\test_control_center_search_service.py tests\test_control_center_search_routes.py tests\test_control_center_knowledge.py tests\test_control_center_runtime_proxy.py -q
```

Ishod:

- `12 passed`

Pokriće:

- `webSearchBaseUrl = http://127.0.0.1:18080/search` vise ne pravi `.../search/search`
- HTML odgovor sada vraca jasnu korisnicku poruku da SearxNG nije vratio JSON i da treba proveriti base URL ili `/search` endpoint

### 2. Puna test baza

Komanda:

```powershell
python -m pytest -q
```

Ishod:

- `468 passed`

### 3. Artefakti

Planirani release artefakti:

- `dist/LocalAIControlCenterSetup-v0.4.25.exe`
- `dist/local_ai_control_center_installer-0.4.25-py3-none-any.whl`
- `dist/local_ai_control_center_installer-0.4.25.tar.gz`

## Rezultat

Search sloj sada prihvata i root SearxNG URL i URL koji vec pokazuje na `/search`, a u slucaju HTML/praznog odgovora vise ne prijavljuje neupotrebljiv JSON parser traceback, nego jasnu poruku o tome da SearxNG nije vratio JSON i da treba proveriti endpoint.


