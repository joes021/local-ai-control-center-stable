# Windows Control Center Reuse Validation - 2026-05-26

## Scope

Ova validacija zatvara realni installer kvar prijavljen sa druge Windows masine:

- `fresh install`
- isti `install root`
- vec zdrav pokrenut `Local AI Control Center` panel
- deploy pada na:
  - `Control Center panel nije mogao da se zaustavi`
  - `Access is denied`

## Root cause

`deploy_control_center_runtime()` je prerano pokusavao da ugasi postojeci panel iz istog install root-a, pre nego sto proveri da li je panel vec:

- zdrav
- isti kao binar koji novi installer nosi

To je znacilo da i kada je vec pokrenut isti odgovarajuci panel, installer i dalje pokusava nasilni terminate, pa `taskkill` / stop put moze da vrati `Access is denied` i obori ceo install tok bez pravog razloga.

## Fix

U `control_center_runtime.py` je uvedeno:

- poredjenje sadrzaja postojecnog panel binara i binara koji bi installer kopirao
- short-circuit reuse put:
  - ako je panel vec zdrav za isti install root
  - i binar je isti
  - installer vise ne pokusava da ga gasi
- `_copy_panel_executable()` takodje ne dira fajl ako je vec isti

## Test evidence

Ciljani regresioni test:

- `python -m pytest tests\test_control_center_runtime_deploy.py -q`
  - rezultat: `10 passed`

Poseban novi test:

- `test_deploy_control_center_runtime_reuses_healthy_running_panel_when_binary_matches`
  - potvrduje da:
    - nema `stop_process` pokusaja
    - nema `copy2` pokusaja
    - deployment ipak uspe

## Build evidence

- `python -m pytest -q`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`

Sve komande treba da prodju za release `v0.4.31`.

## Product truth after fix

- ako je isti zdrav panel vec podignut iz istog install root-a, installer ga reuse-uje
- ako panel nije isti ili nije zdrav, stari stop/replace tok i dalje ostaje aktivan
- ovo ne krije stvarne konflikte sa tudjim procesom ili drugim install root-om
