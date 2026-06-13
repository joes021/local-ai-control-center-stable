# Windows Models and Runtime Final Validation - 2026-05-24

## Scope

Ova beleska zatvara sledeci Windows-only polish krug na grani `codex/panel-integration`, sa fokusom na:

- `Models` lifecycle truth u installer-managed panelu
- `runtime/OpenCode` capability truth za stvarne akcije (`Start`, `Open runtime web`, `Open OpenCode`)
- paketovani Windows installer upgrade smoke za novu verziju `v0.4.10`

Linux rad ostaje van scope-a dok se ovaj Windows checkpoint ne potvrdi na dodatnoj masini.

## Code and build evidence

1. Puna test baza:
   - komanda:
     - `python -m pytest -q`
   - rezultat:
     - `407 passed`

2. Python build artefakti:
   - komanda:
     - `python -m build`
   - rezultat:
     - uspesan `sdist` i `wheel`
   - izlaz:
     - `dist/local_ai_control_center_installer-0.4.10.tar.gz`
     - `dist/local_ai_control_center_installer-0.4.10-py3-none-any.whl`

3. Windows installer build:
   - komanda:
     - `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
   - rezultat:
     - uspesan `dist/LocalAIControlCenterSetup-v0.4.10.exe`

## Models lifecycle truth

`/api/models` sada po svakom redu iznosi kanonsku lifecycle istinu:

- `lifecycleStatus`
- `lifecycleLabel`
- `lifecycleSummary`
- `supportsActivation`
- `downloadActive`
- `canDownload`

Prakticno potvrdjeno na repo-local panelu:

- `http://127.0.0.1:4310/`

Potvrdjeni primeri:

1. aktivni starter model:
   - `gemma-4-E4B-it-Q4_K_M.gguf (recommended-6gb)`
   - `lifecycleStatus = active`
   - `supportsActivation = true`

2. kurirani ali jos neskidani modeli:
   - `recommended-12gb`
   - `recommended-24gb`
   - `lifecycleStatus = downloadable`
   - `supportsActivation = false`

3. vec skinut non-MTP model:
   - `gemma-4-E4B-it-Q4_K_M.gguf`
   - `lifecycleStatus = ready`
   - `supportsActivation = true`

4. MTP varijanta ostaje jasno ogranicena:
   - `Qwen3.6-27B-UD-IQ2_XXS.gguf`
   - `lifecycleStatus = unsupported`
   - `supportsActivation = false`
   - `activationSummary` jasno upucuje na `non-MTP` model

## Runtime and OpenCode truth

Zivi repo-local panel na:

- `http://127.0.0.1:4310/`

posle restarta backend procesa vraca sledece capability signale:

### `/api/server/status`

- `status = started`
- `canStart = true`
- `canStop = true`
- `canOpenWeb = true`

### `/api/opencode/status`

- `sessionState = connected`
- `canOpen = true`
- `openActionLabel = OpenCode je vec otvoren`
- `openBlockedReason = ""`

To zatvara prethodnu sivu zonu da UI mora sam da pogadja da li akcija ima smisla. Sada backend unapred iznosi istinu o akciji i razlog blokade kada ona postoji.

## Packaged upgrade smoke

Uraden je stvarni paketovani upgrade run nad postojecim temp install root-om:

- `C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5`

Pokrenut installer:

- `dist/LocalAIControlCenterSetup-v0.4.10.exe`

Run je zavrsio sa:

- `Product installation status: complete`

Finalni report:

- `C:\Users\<user>\AppData\Local\Temp\LocalAIControlCenterInstaller\runs\2026-05-24T12-02-02+00-00\install-report.json`

Iz izlaza i reporta je potvrdeno:

- `bootstrap_status = ready`
- `runtime_payload_status = ready`
- `server_verification_status = ready`
- `opencode_verification_status = ready`
- `first_run_status = ready`
- `turboquant_status = ready`
- `control_center_launch_status = ready`
- `product_installation_status = complete`

Napomena:

- paketovani run je na kraju cekao standardni `Press Enter to close the installer window...`
- to je ocekivano i nije znak neuspeha

## Installed panel truth after packaged upgrade

Posle tog upgrade run-a proverena je ziva instalirana verzija na:

- `http://127.0.0.1:3210/`

`/health` vraca install root:

- `C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5`

`/api/status` vraca:

- `version = 0.4.10`
- `activeRuntimeLabel = llama.cpp`
- `runtimeLiveStatus = started`
- `activeModel = gemma-4-E4B-it-Q4_K_M.gguf`

`/api/server/status` vraca:

- `status = started`
- `health = ok`
- `port = 60029`
- `activeRuntimeLabel = llama.cpp`
- `canStart = true`
- `canOpenWeb = true`

`/api/opencode/status` vraca:

- `sessionState = runtime-ready`
- `canOpen = true`
- `openActionLabel = Open OpenCode`

## Explicit boundaries that still remain

- `MTP` modeli i dalje nisu podrzani kao aktivni runtime model; ostaju `download-only`.
- Ovaj validation pass i dalje nije drugi fizicki Windows host; signal je zasnovan na packaged upgrade smoke-u i repo-local/live panel proverama na istoj workstation sesiji.


