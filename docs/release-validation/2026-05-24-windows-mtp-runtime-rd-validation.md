## Windows MTP runtime R&D validation - 2026-05-24

Ovaj zapis dokumentuje eksperimentalni rezultat za MTP GGUF podrsku na grani `codex/mtp-runtime-rd`.

### Cilj

Proveriti da li `MTP` GGUF modeli mogu stvarno da rade u ovom proizvodu, ili su trajno `download-only`.

### Zakljucak

`MTP` modeli mogu da rade, ali trenutno samo kroz `llama.cpp` runtime put sa eksplicitnim `--spec-type draft-mtp`.

`TurboQuant` trenutno ne podrzava taj put i za `MTP` model mora da padne nazad na `llama.cpp`, ili da ostane iskreno oznacen kao nepodrzan.

### Potvrdjeni dokazi

1. Aktivni `llama.cpp` binary na ovoj masini prijavljuje `draft-mtp` u `--help` izlazu.
2. Direktan live start `llama-server.exe` sa instaliranim `MTP` modelom i flagom `--spec-type draft-mtp` dolazi do `health=ok`.
3. Stvarni `/v1/chat/completions` odgovor vraca `timings.draft_n` i `timings.draft_n_accepted`, sto potvrduje da je speculative MTP put zaista aktiviran.
4. `TurboQuant` `--help` izlaz nema `draft-mtp`, pa isti model ne treba tretirati kao TurboQuant-aktivabilan.

### Proizvodna semantika na ovoj grani

- `MTP` model vise nije blanket-blocked.
- Aktivacija `MTP` modela je dozvoljena kada `llama.cpp` runtime stvarno podrzava `draft-mtp`.
- Ako je korisnik izabrao `TurboQuant`, panel za `MTP` model automatski bira `llama.cpp` kao aktivni runtime.
- Server start za `MTP` model dodaje `--spec-type draft-mtp` samo kada je aktivni runtime `llama.cpp` i kada capability probe to potvrdi.

### Verifikacija

Izvrseno:

- `python -m pytest -q`
- rezultat: `408 passed`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`

### Granice koje i dalje ostaju

- Ovo nije dokaz da svaki `MTP` GGUF radi; dokazano je da proizvodni put moze da radi za provereni instalirani `Qwen3.6-27B` `MTP` model na ovoj masini.
- `TurboQuant` i dalje nema `draft-mtp` capability i ne treba ga reklamirati kao `MTP` runtime.
- Ovaj rezultat je eksperimentalan i namerno ostaje na odvojenoj grani dok se ne odluci da li ide u glavni proizvodni tok.
