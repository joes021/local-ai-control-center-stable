Release target: `v0.4.86`

Scope:
- RuntimePilot `Phase 3` vizuelni shell uplift u portalu
- marker kartice u headeru i jači branded nav surface
- cleanup preostalih javnih srpskih tekstova i dijakritika
- osvežen paketovani frontend bundle i installer

Verification:
- `python -m pytest tests/test_control_center_frontend_dist.py -q`
- `python -m pytest -q`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`

Expected release artifacts:
- `dist/LocalAIControlCenterSetup-v0.4.86.exe`
- `dist/LocalAIControlCenterSetup-latest.exe`
- `dist/local_ai_control_center_installer-0.4.86-py3-none-any.whl`
- `dist/local_ai_control_center_installer-0.4.86.tar.gz`
- `dist/SHA256SUMS-v0.4.86.txt`

Notes:
- Portal sada pokazuje vidljivu RuntimePilot shell promenu, ne samo novi header i ikone.
- Browser tab može da traži `Ctrl+F5` zbog keša starih hashed asset fajlova.


