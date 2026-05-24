# Windows Browser Hardening Validation

Datum: 2026-05-24

## Scope

Ovaj validation checkpoint pokriva zavrsni Browser polish slice preko Windows proizvoda:

- backend `/api/browser/catalog` sada stvarno postuje `source`, `search`, `family`, `quant`, `size`, `mtp`, `date`, `sort` i `limit`
- frontend Browser panel koristi isti server-side query ugovor umesto lokalnog duplog filter/sort mozga
- Browser redovi kroz refresh zadrzavaju truth da li je model vec dodat u lokalni katalog

## Verifikacija

1. Fokusirani Browser/Models regresioni set:
   - komanda:
     - `python -m pytest tests/test_control_center_browser_catalog_service.py tests/test_control_center_browser_routes.py tests/test_control_center_frontend_dist.py tests/test_control_center_browser_sources.py tests/test_control_center_model_downloads.py tests/test_control_center_models_service.py -q`
   - rezultat:
     - `40 passed`

2. Puna test baza:
   - komanda:
     - `python -m pytest -q`
   - rezultat:
     - `398 passed`

3. Python build artefakti:
   - komanda:
     - `python -m build`
   - rezultat:
     - uspesan `sdist` i `wheel`

4. Windows installer build:
   - komanda:
     - `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
   - rezultat:
     - uspesan `dist/LocalAIControlCenterSetup-v0.4.9.exe`

## Zivi Browser check

Pokrenut je svezi repo panel na `http://127.0.0.1:4310/` sa `PYTHONPATH=src` i install root-om:

- `C:\Users\<user>\LocalAIControlCenter`

Potvrdjeno:

1. `/health` vraca `200` i odgovarajuci install root
2. `GET /api/browser/catalog?source=unsloth&search=qwen3.6-35b-a3b&quant=IQ2_XXS&sort=quant-asc&limit=10`
   - vraca tacno `2` modela:
     - `unsloth/Qwen3.6-35B-A3B-MTP-GGUF | Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf`
     - `unsloth/Qwen3.6-35B-A3B-GGUF | Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf`
3. Isti odgovor sada nosi i local-catalog truth:
   - `addedToLocal = true`
   - ispravan `localModelId` za oba vec registrovana modela

## Truth granice koje i dalje ostaju

- `MTP` modeli su i dalje `download-only`; Browser ih prikazuje i preuzima, ali ne nudi ih kao bezbedan aktivni runtime model.
- Browser backend i dalje vraca ceo katalog kada nema filtera; to je namerno i sada je pozeljan default za pun pregled.
