# Windows RC Validation - 2026-05-24

## Scope

Ova beleska hvata trenutni Windows release-candidate validation pass za installer-managed proizvod iz grane `codex/panel-integration`, pre bilo kakvog Ubuntu porta.

## Code and build evidence

- `python -m pytest -q`
  - rezultat: `365 passed`
- `python -m build`
  - uspesni `sdist` i `wheel`
- `packaging/build_windows_installer.ps1`
  - uspesan build installera
  - izlaz: `dist/LocalAIControlCenterSetup-v0.4.5.exe`
  - provereno i kada `build/` vec postoji od prethodnog `python -m build`

## Live workstation validation

### Control Center boot

- Potvrdjeno da installer-managed panel radi na `http://127.0.0.1:3210/`
- `GET /health` vraca:
  - `status = ok`
  - `app = local-ai-control-center-stable`
  - ispravan `installRoot = C:\Users\<user>\LocalAIControlCenter`

Napomena:
- Tokom validacije je na `3210` zatecen strani lokalni smoke panel iz temp foldera.
- To nije bio installer-managed proizvod.
- Razlikovanje je uradjeno preko `/health` identiteta, zatim je strani listener ugasen i podignut pravi installer-managed panel.

### Fresh install path

Clean-machine-style proveru sam uradio sa temp install root-om:
- `C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5`

Na istoj workstation sesiji je u pozadini ostao ziv glavni proizvodni runtime na:
- `http://127.0.0.1:39281`

To je bilo namerno, da proverim realan RC rizik oko konflikta managed runtime porta.

Potvrdjen tok:
1. prethodni neuspeo fresh root je ostavio stari `runtime-endpoint.json` sa `39281`
2. `fresh install` sada vise ne veruje slepo tom fajlu
3. novi run je zavrsio sa:
   - `product_installation_status = complete`
   - `managed_runtime_port = 55091`
   - `verified_server_url = http://127.0.0.1:55091`
4. finalni panel health je vratio:
   - `status = ok`
   - `installRoot = C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5`

Ovim je potvrden stvarni fix za RC blocker:
- `fresh reinstall` preko polu-popunjenog root-a sada ume da preslozi managed runtime port umesto da opet padne na zauzetom `39281`

### Upgrade path

Nad istim temp root-om je zatim pokrenut pravi `upgrade` run.

Potvrdjen tok:
- `Download plan ready: 0 item(s).`
- `llama.cpp server verification status: ready`
- `OpenCode live-route verification status: ready`
- `First-run smoke status: ready`
- `Control panel launch status: ready`
- `Product installation status: complete`

To potvrduje da upgrade preko vec instaliranog root-a i aktivnog panel shell-a prolazi do kraja bez novog download zahteva kada su artefakti vec prisutni.

### Runtime status truth

- `GET /api/status` i `GET /api/server/status` sada dosledno razlikuju:
  - `requestedRuntimeLabel`
  - stvarno aktivni runtime
  - `runtimeSelectionSummary`
  - `runtimeLiveStatus`
- Validirano je da panel vise ne glumi da je backend spreman kada health nije spreman.

### Runtime switch path

Live validacija je radjena nad aktivnim modelom:
- `Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf`

Potvrdjeni tok:
1. pocetno stanje: `TurboQuant` warming/started na portu `39281`
2. `POST /api/runtime/select {"runtime":"llama.cpp"}`
   - rezultat: `ok`
   - posle toga `GET /api/server/status` prelazi u:
     - `activeRuntimeLabel = llama.cpp`
     - `health = ok`
     - `status = started`
3. `POST /api/runtime/select {"runtime":"turboquant"}`
   - rezultat: `ok`
   - posle toga `GET /api/server/status` prelazi u:
     - `activeRuntimeLabel = TurboQuant`
     - `health = ok`
     - `status = started`

Ovaj deo je posebno hardenovan zato sto je raniji validation pass otkrio realan bug:
- `select-runtime` je prepisivao izbor pre gasenja starog runtime-a
- zbog toga je `stop-server` gledao pogresan binar
- fix je sada potvrdjen zivim smoke-om

### OpenCode path

- `POST /api/opencode/open {"profile":"balanced"}`
  - rezultat: `ok`
  - kada je OpenCode vec otvoren, ne pravi novu instancu bez potrebe
  - summary sada iskreno kaze da je backend pripremljen za postojecu sesiju
- `GET /api/opencode/status`
  - potvrdjeno:
    - `available = true`
    - `active = true`
    - `instanceCount = 1`
    - `runtimeConnected = true`
    - `sessionState = connected`

### Browser direct download path

Live provereno preko `POST /api/browser/catalog/download` za vec prisutni model:
- `unsloth/Qwen3.6-35B-A3B-GGUF`
- `Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf`

Rezultat:
- `status = ok`
- `summary = Model je vec prisutan na disku.`

Time je potvrdjen installer-managed Browser download endpoint put i u live proizvodu, bez novog visegigabajtnog transfera.

### Local model import path

Live provereno sa temp `.gguf` fajlom:
- `POST /api/models/add-local`
  - rezultat: `ok`
  - model je dodat u lokalni katalog
- zatim `POST /api/models/delete`
  - rezultat: `ok`
  - temp unos je uklonjen iz kataloga

Time je potvrdjen `add-local -> catalog visible -> delete` lifecycle put.

### Update path

- `GET /api/updates/check`
  - rezultat: `ok`
  - summary: `Vec koristis najnoviju verziju (0.4.5).`

Ovim je potvrdjen live `check-updates` path za trenutno "up to date" stanje.

## Supported truth at this checkpoint

- Windows installer build: supported
- Fresh install path on current workstation: supported
- Upgrade path on current workstation: supported
- Installer-managed Control Center launch: supported
- Installer-managed runtime status truth: supported
- Runtime switch `llama.cpp <-> TurboQuant`: supported
- OpenCode launch against managed runtime: supported
- Browser catalog direct download route: supported
- Local model import/delete: supported
- Update check route: supported

## Still explicit product boundaries

- `MTP` modeli i dalje nisu podrzani kao aktivni runtime model i moraju ostati jasno blokirani.
- Ovaj validation pass nije jos pokrivao pravi "new-version installer download + handoff" update tok, jer je validiran `up-to-date` put na trenutnoj verziji.
- Ovaj validation pass nije jos radio poseban drugi fizicki Windows host; trenutni RC signal je zasnovan na clean-machine-style proveri iz ove workstation sesije.
