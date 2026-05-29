## Sta je novo

- `Tuning Lab` sada ima gotov `Game Batch 01`
- batch donosi tri unapred pripremljena game zadatka za realnije poredjenje podesavanja:
  - `Jumping Ball Runner`
  - `Balloon Blaster`
  - `Octopus Invaders`
- svaki zadatak mozes posebno da ucitas u editor kao `easy`, `medium` ili `hard`
- dodat je i `Pokreni ceo batch`, koji jedan preset siri u tri stvarna tuning run-a

## Sta to donosi

- lakse poredjenje:
  - trenutnog `Baseline`
  - naseg `Recommended`
  - tvog `Custom` seta
- ponovljiviji tuning eksperimenti
- bolji temelj za procenu kvaliteta inference podesavanja na pravim OpenCode zadacima

## Verifikacija

- `python -m pytest tests\test_control_center_frontend_dist.py tests\test_control_center_tuning_lab.py tests\test_control_center_tuning_lab_routes.py -q` -> uspesno (`66 passed`)
- `python -m pytest -q` -> uspesno (`544 passed`)
- `python -m build` -> uspesno
- `packaging/build_windows_installer.ps1 -PythonExe python` -> uspesno
- lokalni upgrade na `0.4.62` -> uspesno
- zivi `/api/tuning-lab` payload potvrduje `game-batch-01` i sva tri task-a

## Artefakti

- `LocalAIControlCenterSetup-v0.4.62.exe`
- `LocalAIControlCenterSetup-latest.exe`
- `local_ai_control_center_installer-0.4.62-py3-none-any.whl`
- `local_ai_control_center_installer-0.4.62.tar.gz`
- `SHA256SUMS-v0.4.62.txt`
