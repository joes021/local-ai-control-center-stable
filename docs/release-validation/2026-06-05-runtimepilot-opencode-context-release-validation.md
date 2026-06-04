# RuntimePilot v0.4.90 Release Validation

Datum: 2026-06-05

## Opseg

Ovaj release zatvara dva povezana OpenCode problema:

- UI vise ne tvrdi da je otvoren poseban OpenCode GUI prozor kada je zapravo pokrenuta CLI sesija u terminalu.
- Managed OpenCode config sada nosi pravi `limit.context` i `limit.output`, tako da OpenCode moze da racuna realan procenat iskoriscenog konteksta umesto laznog `0% used`.

## Provere

- `python -m pytest tests\\test_control_center_models_service.py tests\\test_opencode_verification.py tests\\test_first_run_validation.py tests\\test_control_center_tuning_lab.py -q`
  - rezultat: `108 passed, 1 warning`
- `python -m pytest -q`
  - rezultat: `666 passed, 1 warning`
- `python -m build`
  - rezultat: uspesno
- `packaging/build_windows_installer.ps1 -PythonExe python`
  - rezultat: uspesno

## Lokalna verifikacija

- zivi OpenCode managed config:
  - `C:\Users\<user>\LocalAIControlCenter\config\opencode\managed-config.json`
  - potvrdjeno:
    - `limit.context = 262144`
    - `limit.output = 8192`
- `GET http://127.0.0.1:3210/api/status`
  - ocekivano posle reinstalacije: `version = 0.4.90`
- OpenCode strana sada jasno govori da je pokrenuta CLI sesija u terminalu, ne poseban GUI prozor.

## Artefakti

- `dist\\local_ai_control_center_installer-0.4.90-py3-none-any.whl`
- `dist\\local_ai_control_center_installer-0.4.90.tar.gz`
- `dist\\RuntimePilotSetup-v0.4.90.exe`
- `dist\\RuntimePilotSetup-latest.exe`
- `dist\\SHA256SUMS-v0.4.90.txt`

## Zakljucak

Release `v0.4.90` je spreman za GitHub objavu.
