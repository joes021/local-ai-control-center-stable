# Tuning Lab Design

**Datum:** 2026-05-29  
**Status:** odobreno za implementaciju  
**Cilj:** dodati prvi ozbiljan `Tuning Lab` za poređenje i primenu setova podešavanja za `llama.cpp + lokalni model + OpenCode local-lacc`.

## Problem

Control Center danas ume da:
- podigne runtime
- prikaže aktivne CLI komande
- meri benchmark
- čuva workflow preset-e

Ali još nema centralno mesto koje:
- poredi više setova inference podešavanja
- pokreće stvarni `OpenCode` task nad projektom
- radi u izolovanom radnom prostoru
- meri uspeh, brzinu i diff
- automatski predlaže pobednika
- nudi dugme `Primeni`

## Zaključane odluke

Na osnovu korisničkih odluka tokom brainstorminga, `Tuning Lab` v1 mora da radi ovako:

- poseban novi tab pod `Više`
- `compare-first, recommendation-assisted`
- 3 slota po eksperimentu:
  - `Baseline`
  - `Recommended`
  - `Custom`
- sva tri slota su editabilna
- glavni kriterijum je:
  1. da li zadatak stvarno može da se izvrši na toj mašini
  2. da li prolazi success check
  3. brzina i vreme
- podržava korisnički `OpenCode` zadatak, ne samo ugrađene prompt testove
- `OpenCode` task mora da sme da:
  - čita
  - menja
  - kreira
  - izvršava
- svaki slot run radi u izolovanom radnom prostoru:
  - prioritet `git worktree`
  - fallback kopija u posebnom podfolderu
- `Tuning Lab` ima dugme `Primeni pobednički set`
- jedan eksperiment poredi 3 seta, a više eksperimenata ide sekvencijalno kroz queue
- `Recommended` se pravi iz:
  1. internih pravila
  2. lokalne istorije mašine
  3. istorije po modelu / familiji modela
- istorija `Tuning Lab`-a je odvojena od `Benchmark`
- čuvaju se i neuspešni / prekinuti run-ovi
- podrazumevano se čuvaju:
  - logovi
  - metrike
  - diff
  - izmenjeni fajlovi
- ceo worktree/folder se ne čuva automatski
- svaki eksperiment može da ima success check lanac do 3 koraka
- postoje šabloni + auto-detect + ručni override
- cost nije kriterijum pobede u v1
- `Custom` slot mora da ume da proguta nalepljenu forum/Reddit komandu ili snippet i da izvuče parametre

## Opseg v1

### Parametri koje Tuning Lab menja u v1

`Tuning Lab` menja samo glavne parametre:

- `temperature`
- `top-k`
- `top-p`
- `min-p`
- `repeat penalty`
- `repeat last N`
- `presence penalty`
- `frequency penalty`
- `seed`
- `context`
- `output tokens`
- `thinking mode`
- `OpenCode profile`

Duboki runtime flagovi ostaju za kasniji `advanced` sloj:

- `threads`
- `batch`
- `ubatch`
- `gpu-layers`
- `flash-attn`
- `ctk`
- `ctv`
- `ncmoe`

## Arhitektura

## 1. Backend domen

Dodaje se novi backend domen:

- `tuning_lab_service.py`
- `routes/tuning_lab.py`

Novi domen vodi:

- queue stanja
- istoriju eksperimenata
- aktivni run
- slot rezultate
- proxy profile za per-run sampling override

## 2. Izolacija radnog prostora

Svaki slot run dobija svoj izolovani radni prostor:

- ako je ciljna putanja git repo:
  - `git worktree add --detach`
- ako nije:
  - kopija foldera u `install_root/config/control-center/tuning-lab/runs/...`

Svaki slot rezultat beleži:

- `workspaceMode`: `git-worktree` ili `copy`
- `workspacePath`
- `workspaceRetained`

## 3. OpenCode izvršavanje

`Tuning Lab` koristi stvarni `OpenCode` non-interactive run:

- `opencode --pure run --format json`
- uz `--dir` na izolovani radni prostor
- uz `--dangerously-skip-permissions`
- uz `--model local-lacc/<model>`

Za svaki slot se generiše privremeni `OPENCODE_CONFIG_CONTENT` koji:

- zaključava provider na `local-lacc`
- šalje `baseURL` na poseban tuning runtime proxy put
- zaključava model na aktivni model

## 4. Sampling override po slotu

Postojeći `/api/runtime-proxy/v1/...` već ume da ubaci default sampling parametre.

Za `Tuning Lab` se dodaje posebna putanja:

- `/api/runtime-proxy/tuning/{token}/v1/{upstream_path:path}`

Taj token mapira na konkretan tuning slot patch, tako da svaki `OpenCode` run dobija svoje:

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

bez menjanja globalnih sistemskih podešavanja.

## 5. Success check lanac

Eksperiment ima `0-3` success check koraka.

Svaki korak sadrži:

- `label`
- `command`
- `kind`

Podržani izvori:

- auto-detect šabloni
- ručni izbor šablona
- potpuno ručan komandni unos

Run je uspešan samo ako:

- OpenCode task završi bez procesa-failure-a
- svi success check koraci prođu

## 6. Score i pobednik

Auto-predlog pobednika koristi ovaj redosled:

1. `taskCompleted == true`
2. `successChecksPassed == true`
3. manji `totalDurationMs`
4. veći `averageOutputTokensPerSecond`
5. veći `averageTotalTokensPerSecond`

Ako nijedan slot ne prođe success check, pobednik ostaje `null`.

Korisnik i dalje ručno potvrđuje `Primeni`.

## 7. Istorija i export

`Tuning Lab` ima svoju istoriju eksperimenata sa:

- statusom
- pobednikom
- zadatkom
- modelom
- runtime-om
- diff sažetkom
- izmenjenim fajlovima
- logovima

Export format za v1:

- JSON ceo eksperiment

## 8. Uvoz iz komande ili snippeta

`Custom` slot ume da parsira:

- `llama.cpp` PowerShell komandu
- `llama.cpp` cmd komandu
- `OpenCode` config snippet
- sirov tekst tipa `temperature=0.6 top_p=0.95 top_k=20`

Prva verzija radi heuristički parser za glavne inference parametre.

## UI dizajn

`Tuning Lab` tab ima ove sekcije:

1. `Pregled`
- aktivni model
- runtime
- working directory
- recommended izvor (`pravila`, `istorija modela`, `istorija familije`)

2. `Eksperiment`
- naziv eksperimenta
- cilj rada
- OpenCode task prompt
- working directory
- isolation summary
- success check builder

3. `Tri slota`
- `Baseline`
- `Recommended`
- `Custom`

Svaki slot prikazuje:

- inference parametre
- context
- output tokens
- thinking mode
- OpenCode profil
- izvor seta

4. `Queue i aktivni run`
- aktivni eksperiment
- čekajući eksperimenti
- slot progres

5. `Rezultati`
- gornji winner banner
- kompaktna tabela poređenja slotova
- detalji na klik:
  - stdout/stderr
  - token usage
  - throughput
  - success checks
  - diff
  - izmenjeni fajlovi

6. `Istorija`
- posebna istorija sa paginacijom

## Istraživanje i izvori

Za v1 zaključujemo glavne parametre iz ovih primarnih izvora:

- `llama.cpp` server README:
  - `--temp`, `--top-k`, `--top-p`, `--min-p`, `--repeat-penalty`, `--repeat-last-n`, `--presence-penalty`, `--frequency-penalty`, `--seed`
- `Qwen` official quickstart:
  - preporučene vrednosti za `Instruct` i `Thinking`
- `Hugging Face` generation docs:
  - opšti opis i standardni smisao sampling parametara
- `Gemma` official generation config:
  - realni podrazumevani sampling primer
- `OpenCode` CLI docs:
  - `run`
  - `--format json`
  - `--dir`
- `OpenCode` providers docs:
  - `baseURL` override za custom proxy tok

## Nefunkcionalni zahtevi

- sekvencijalno izvršavanje, nikad paralelno
- bez menjanja globalnih settings-a tokom slot run-a
- čisti cleanup privremenih worktree/folder run-ova
- bez rušenja postojećeg `Benchmark`, `OpenCode` i `runtime-proxy` toka
- svi novi istorijski fajlovi moraju biti installer-managed JSON artefakti

## Rizici

- `OpenCode` task može da bude nedeterminističan i pored istog seed-a
- success check komande mogu da budu skupe
- diff za negit projekte mora da bude ograničen na razumne tekstualne fajlove
- `--dangerously-skip-permissions` mora biti ograničen samo na izolovan radni prostor

## Minimum za “done”

`Tuning Lab` v1 je gotov kada:

- postoji novi tab pod `Više`
- ume da pokrene pravi `OpenCode` task u izolovanom radnom prostoru
- ume da uporedi 3 slota
- ume da predloži pobednika
- ume da prikaže diff, izmenjene fajlove i success check rezultate
- ume da primeni pobednički set na sistem
- ume da izveze rezultat
- čuva i uspešne i neuspešne run-ove
