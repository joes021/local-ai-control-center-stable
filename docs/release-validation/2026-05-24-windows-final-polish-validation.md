# Windows Final Polish Validation - 2026-05-24

## Scope

Ova beleska zatvara Windows final-polish slice na grani `codex/panel-integration`, sa fokusom na:

- `Models` + `Browser` lifecycle truth
- `OpenCode` + runtime truth
- clean-machine / custom-root upgrade ivice
- novi Windows installer paket `v0.4.8`

Linux rad je namerno van scope-a dok se Windows proizvod ne ispegla do test-ready stanja.

## Code and build evidence

- `python -m pytest -q`
  - rezultat: `394 passed`
- `python -m build`
  - uspesni `sdist` i `wheel`
  - izlaz:
    - `dist/local_ai_control_center_installer-0.4.8.tar.gz`
    - `dist/local_ai_control_center_installer-0.4.8-py3-none-any.whl`
- `packaging/build_windows_installer.ps1 -PythonExe python`
  - uspesan build installera
  - izlaz:
    - `dist/LocalAIControlCenterSetup-v0.4.8.exe`

## Key fixes validated in code

### Browser source completeness

- `browser_sources.py` vise ne truncira GGUF listu po repo-u na prvih `64` fajla.
- Time katalog vise ne gubi quant varijante iz vecih repo-a.

### OpenCode install-root truth

- `opencode_service.py` sada broji samo `opencode.exe` procese koji zaista pripadaju trenutnom installer-managed install root-u.
- Strana `OpenCode` instanca iz drugog install root-a vise ne sme da glumi aktivnu sesiju u pogresnom panelu.

### MTP activation guardrails

- `MTP` modeli ostaju vidljivi u katalogu i downloaduju se normalno.
- UI i backend ih sada jasno tretiraju kao `download-only` dok ne postoji pouzdan runtime put za aktivaciju.

### Custom existing-root installer path

- `prompts.py` sada prepoznaje kada korisnik u prvom koraku unese postojeci custom install root.
- U tom slucaju installer prelazi na `Upgrade / Fresh install` izbor umesto da slepo upadne u fresh instalaciju.

## Live packaged validation

### Upgrade run through packaged installer

Validacija je uradjena nad postojecim temp install root-om:

- `C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5`

Pokrenut je stvarni paketovani installer:

- `dist/LocalAIControlCenterSetup-v0.4.8.exe`

Potvrdjeno je:

1. prvi korak ostaje `Install root`
2. kada je unet postojeci custom root, installer prikazuje:
   - `[2/7] Install mode`
3. izabran je `Upgrade`
4. run se zavrsava sa:
   - `Product installation status: complete`
5. finalni report:
   - `C:\Users\<user>\AppData\Local\Temp\LocalAIControlCenterInstaller\runs\2026-05-24T10-44-26+00-00\install-report.json`

Iz tog reporta je potvrdjeno:

- `bootstrap_status = ready`
- `runtime_payload_status = ready`
- `server_verification_status = ready`
- `opencode_verification_status = ready`
- `first_run_status = ready`
- `turboquant_status = ready`
- `control_center_launch_status = ready`
- `product_installation_status = complete`

### Installed panel truth after upgrade

Posle upgrade-a je proverena ziva instalirana verzija na:

- `http://127.0.0.1:3210/`

`/api/status` vraca:

- `version = 0.4.8`
- `activeRuntimeLabel = llama.cpp`
- `runtimeLiveStatus = started`
- `activeModel = gemma-4-E4B-it-Q4_K_M.gguf`

`/api/server/status` vraca:

- `status = started`
- `health = ok`
- `port = 60029`
- `activeRuntimeLabel = llama.cpp`

### Foreign OpenCode instance no longer pollutes panel

Na istoj workstation sesiji je namerno ostavljena strana `OpenCode` instanca iz drugog install root-a:

- `C:\Users\<user>\LocalAIControlCenter\tools\opencode\opencode.exe`

I pored toga, installer-managed panel za temp root sada iskreno vraca:

- `/api/opencode/status`
  - `available = true`
  - `active = false`
  - `instanceCount = 0`
  - `runtimeConnected = true`
  - `sessionState = runtime-ready`

Ovim je potvrden fix da panel vise ne mesа tudju `OpenCode` sesiju sa trenutnim install root-om.

### Browser catalog truth for requested Qwen quant

Validacija je radjena nad stvarnim installer-managed cache fajlom:

- `C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5\config\control-center\browser-catalog-cache.json`

Istom logikom kojom Browser tabela filtrira lokalno provereno je da katalog sada sadrzi `Qwen3.6-35B-A3B` `IQ2_XXS` izbor:

- `MATCH_COUNT = 2`

Pogodjene stavke:

1. `unsloth/Qwen3.6-35B-A3B-MTP-GGUF | Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf | UD-IQ2_XXS | has-mtp`
2. `unsloth/Qwen3.6-35B-A3B-GGUF | Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf | UD-IQ2_XXS | no-mtp`

To zatvara konkretan korisnicki primer da `IQ2_XXS` vise ne nestaje iz Browser tabele kada postoji u upstream katalogu.

## Supported truth at this checkpoint

- Windows installer build: supported
- Custom existing-root upgrade through packaged installer: supported
- Installer-managed panel version truth: supported
- Installer-managed runtime truth: supported
- Foreign `OpenCode` process isolation by install root: supported
- Browser catalog GGUF completeness for large repos: supported
- Browser visibility of `Qwen3.6-35B-A3B` `IQ2_XXS`: supported
- `MTP` guardrail as download-only choice: supported

## Still explicit product boundaries

- `MTP` modeli i dalje nisu podrzani kao aktivni runtime model.
- Browser backend `GET /api/browser/catalog` i dalje vraca ceo katalog; korisnicki filteri u tabeli trenutno rade client-side.
- Ovaj validation pass i dalje nije radio drugi fizicki Windows host; signal je zasnovan na clean-machine-style proveri i installer-managed temp root-u na istoj workstation sesiji.


