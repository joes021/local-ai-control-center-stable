# 2026-05-28 Inference Visibility Polish Validation

## Cilj

Popraviti UX problem zbog kog su inference argumenti postojali u sistemu, ali nisu bili dovoljno vidljivi u portalu.

## Šta je promenjeno

- `Podešavanja` sada imaju jasan vršni blok `Aktivna inference podešavanja`
- `Workflow presets` u `Podešavanja` sada odmah prikazuju `Inference sažetak`
- `Workflows` preset kartice sada odmah prikazuju `Inference sažetak`
- frontend fallback za workflow preset-e sada dopunjava nedostajuće sampling vrednosti i kada backend vrati stariji oblik built-in preset-a
- backend built-in workflow preset-i sada kroz `/api/settings` stvarno nose sampling polja:
  - `temperature`
  - `topK`
  - `topP`
  - `minP`
  - `repeatPenalty`
  - `repeatLastN`
  - `presencePenalty`
  - `frequencyPenalty`
  - `seed`

## Fajlovi

- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/WorkflowsPage.tsx`
- `frontend/src/lib/workflowPresets.ts`
- `frontend/src/styles.css`
- `src/local_ai_control_center_installer/control_center_backend/services/settings_service.py`
- `tests/test_control_center_frontend_dist.py`
- `tests/test_control_center_settings.py`

## Test-first dokaz

- dodat je novi failing frontend dist test koji traži:
  - `Aktivna inference podešavanja`
  - `Inference sažetak`
- potvrđeno je da je test prvo padao, pa zatim prošao posle izmene i rebundlovanja frontenda

## Verifikacija

- `python -m pytest tests/test_control_center_frontend_dist.py tests/test_control_center_settings.py -q` -> `52 passed`
- `python -m pytest -q` -> `522 passed`
- `packaging/build_windows_installer.ps1 -PythonExe python` -> uspešno

## Lokalni installer upgrade

- lokalni installer upgrade na ovoj mašini je ponovo pokrenut nad novim paketom
- `GET /api/settings` potvrđuje da built-in workflow preset-i sada zaista vraćaju inference vrednosti
- `GET /api/status` potvrđuje da instalirani panel radi
- `install-report.json` potvrđuje:
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `first_run_status = ready`

## Napomena

- pokušao sam i headless vizuelnu proveru kroz `playwright`, ali alat nije bio dostupan u lokalnom okruženju
- zato je završni dokaz zatvoren kroz source, spakovani frontend bundle, API payload i pun test gate
