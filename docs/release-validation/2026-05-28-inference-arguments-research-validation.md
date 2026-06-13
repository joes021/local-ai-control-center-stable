# Windows inference arguments research + implementation validation

Datum: 2026-05-28

## Cilj

Zatvoriti najveci produktski gap u `Settings` / `Workflows` / `Server` / `OpenCode` toku:

- istraziti najbitnije i najcesce inference argumente za `llama.cpp`, lokalni model i `OpenCode local-lacc`
- uvesti ih kao stvarna podesavanja u panel
- obezbediti da se ista podesavanja vide u runtime CLI preview-u i da stvarno uticu na inference tok

## Istrazivacki izvori

Primarni izvori koji su koristeni za ovaj slice:

1. `llama.cpp` server docs
   - `https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md`
   - potvrdjeni server argumenti:
     - `--temp`
     - `--top-k`
     - `--top-p`
     - `--min-p`
     - `--repeat-penalty`
     - `--repeat-last-n`
     - `--presence-penalty`
     - `--frequency-penalty`
     - `--seed`

2. Qwen official quickstart
   - `https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html`
   - eksplicitno pomenute preporuke:
     - instruct: `temperature=0.7`, `top_p=0.8`, `top_k=20`, `min_p=0`
     - thinking: `temperature=0.6`, `top_p=0.95`, `top_k=20`, `min_p=0`

3. OpenCode config / providers docs
   - `https://opencode.ai/docs/config`
   - `https://opencode.ai/docs/providers`
   - `https://dev.opencode.ai/docs/models/`
   - potvrda da OpenCode koristi model/config sloj i da je za `local-lacc` najzdravije prikazati efektivna inference podrazumevana podesavanja kroz runtime proxy, umesto da se lazno predstavljaju kao prosti launcher CLI flagovi

Napomena:
- trazeni set je sveden na argumente koji su dovoljno univerzalni i stabilni da imaju smisla kao first-class portal settings
- izbegnuto je ubacivanje egzoticnih ili model-spec varijanti bez jasnog sirokog signala

## Uvedena first-class podesavanja

Dodato u `Settings`, profile i workflow preset payload:

- `temperature`
- `topK`
- `topP`
- `minP`
- `repeatPenalty`
- `repeatLastN`
- `presencePenalty`
- `frequencyPenalty`
- `seed`

Vec postojeci `outputTokens` ostaje odvojena kontrola za max output.

## Gde se ta podesavanja sada stvarno primenjuju

1. Runtime start komanda
   - `llama.cpp` / `TurboQuant` command preview i realni start sada nose gore navedene argumente
   - backend koristi iste vrednosti i za preview i za realni server launch

2. Runtime proxy
   - kada `/v1/chat/completions` ili `/v1/completions` zahtev ne sadrzi sopstvene sampling vrednosti,
     Control Center ubrizgava lokalna podrazumevana:
     - `temperature`
     - `top_p`
     - `top_k`
     - `min_p`
     - `repeat_penalty`
     - `repeat_last_n`
     - `presence_penalty`
     - `frequency_penalty`
     - `seed`
     - `max_tokens`

3. OpenCode local-lacc
   - OpenCode launcher i dalje ostaje launcher + env + managed config tok
   - ali UI sada eksplicitno pokazuje efektivni `local-lacc` inference summary koji runtime proxy koristi

## Novi starter paketi za generaciju

Dodati su istrazivacki starter preset-i:

- `llama-cpp-default`
- `qwen-instruct`
- `qwen-thinking`
- `llama-instruct`
- `gemma-default`
- `deterministic-code`

Oni sluze kao zdrava pocetna tacka za brzo poredenje i sopstveno dalje doterivanje.

## UI / UX promene

### Settings

- nova sekcija `Generacija i sampling`
- starter preset kartice sa izvorom i kratkim sazetkom vrednosti
- direktna polja za:
  - `Temperature`
  - `Top-k`
  - `Top-p`
  - `Min-p`
  - `Repeat penalty`
  - `Repeat last N`
  - `Presence penalty`
  - `Frequency penalty`
  - `Seed`

### Workflows

- workflow preset editor sada cuva i inference/sampling vrednosti
- korisnicki preset sada moze da bude pravi produktski recept, ne samo context/search shortcut

### Server

- command preview sada ima:
  - `PowerShell` varijantu
  - `cmd.exe` varijantu
  - sampling summary
- time korisnik moze realno da poredi rezultate sa forumima, Reddit postovima i rucno deljenim CLI receptima

### OpenCode

- dodat `generationSummary`
- jasno je prikazano da se za `local-lacc` inference podrazumevana podesavanja ne nalaze samo u launcher komandi, nego i u runtime proxy sloju

## Fokusirani testovi

Prosli fokusirani backend testovi:

- `python -m pytest tests\test_control_center_settings.py tests\test_control_center_runtime_proxy.py tests\test_control_center_server.py tests\test_control_center_opencode.py -q`
- rezultat: `34 passed`

Prosli frontend/dist testovi:

- `python -m pytest tests\test_control_center_frontend_dist.py -q`
- rezultat: `46 passed`

## Zavrsni verification gate

1. puna baza
   - `python -m pytest -q`
   - rezultat: `521 passed`

2. python build
   - `python -m build`
   - rezultat: uspesni `wheel` i `sdist`

3. Windows installer build
   - `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
   - rezultat: uspesan `LocalAIControlCenterSetup-v0.4.52.exe`

4. lokalni installer upgrade
   - pokrenut stvarni `.exe` upgrade na ovoj masini
   - `product_installation_status = complete`
   - `control_center_launch_status = ready`
   - `/api/status` vraca `version = 0.4.52`
   - uninstall registry vraca `DisplayVersion = 0.4.52`

## Pošten zaključak

Ovaj slice nije samo kozmetika u `Settings`.

Zatvoreno je:

- istrazivanje najbitnijih inference argumenata iz primarnih izvora
- uvodjenje tih argumenata kao first-class portal settings
- povezivanje istih vrednosti sa:
  - runtime server start komandama
  - runtime proxy defaultima
  - workflow presetima
  - OpenCode local-lacc prikazom
- dokaz kroz testove, build i stvarni lokalni installer upgrade


