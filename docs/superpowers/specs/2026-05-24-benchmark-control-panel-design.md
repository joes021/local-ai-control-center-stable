# Benchmark Control Panel Design

## Goal

Vratiti `Benchmark` kao isporučenu funkcionalnost u Windows control panelu tako da korisnik može da vidi:

- trenutni throughput (`input tok/s`, `output tok/s`, `ukupno tok/s`)
- prosečne vrednosti kroz istoriju
- trend i graf kroz vreme
- benchmark scenarije i baterije
- istoriju benchmark run-ova

Ovaj slice mora da radi nad sadašnjim installer-managed runtime truth modelom, bez zavisnosti od starog `local-qwen` state sloja.

## Product Truth

`Benchmark` ne sme da glumi zaseban sistem. Njegov signal mora da bude izveden iz istih izvora kao i ostatak aplikacije:

- install root i config putanje dolaze iz `ControlCenterConfig`
- aktivni runtime, model i port dolaze iz runtime/config truth sloja
- live throughput signal dolazi iz lokalnog runtime endpoint-a
- benchmark run-ovi se izvršavaju kao kontrolisane akcije iz panela

Ako runtime nije spreman, Benchmark mora to pošteno da prijavi i da ne prikazuje lažno “live” stanje.

## Scope

### In scope

- vraćanje `Benchmark` taba u glavnu navigaciju
- backend `benchmark` API rute koje odgovaraju postojećem frontend kontraktu
- live throughput signal preko runtime `/slots` endpoint-a
- trajna istorija throughput uzoraka u control-center config root-u
- benchmark baterije/scenariji sa čuvanjem i vraćanjem podrazumevanih testova
- pojedinačni i battery benchmark run-ovi
- istorija run-ova i kratki live log preview

### Out of scope

- distribuisani ili višemašinski benchmark
- GPU telemetrija van onoga što runtime već pošteno izlaže
- novo UI redizajniranje Benchmark stranice osim neophodnog wiring-a
- Linux port ovog slice-a

## Architecture

### Backend service

Dodaje se novi service sloj:

- `control_center_backend/services/benchmark_service.py`

Njegove odgovornosti:

- čitanje i upis benchmark state fajlova
- polling runtime `/slots` endpoint-a i prevođenje u live throughput metric
- spajanje istorije stabilnih benchmark uzoraka i live uzoraka u jedinstven payload
- upravljanje benchmark baterijama
- pokretanje benchmark scenarija/baterija kroz pozive ka aktivnom runtime-u
- evidencija run statusa i istorije

### Routes

Dodaje se:

- `control_center_backend/routes/benchmark.py`

Rute:

- `GET /api/benchmark`
- `POST /api/benchmark/run-selected`
- `POST /api/benchmark/run-battery`
- `GET /api/benchmark/run-status`
- `POST /api/benchmark/batteries/save`
- `POST /api/benchmark/batteries/load`
- `POST /api/benchmark/batteries/restore-defaults`
- `POST /api/benchmark/clear-history`

### Frontend

Postojeći `BenchmarkPage.tsx` ostaje primarni UI, ali se:

- vraća u `App.tsx` navigaciju
- vezuje za stvarne backend rute
- po potrebi sitno prilagođava za runtime truth poruke

## Persistence Model

Benchmark state se čuva isključivo unutar installer-managed control-center config root-a:

- `benchmark-history.json`
- `benchmark-live-history.json`
- `benchmark-run-state.json`
- `benchmark-batteries.json`
- `benchmark-saved-runs.json`

Ovo ostaje lokalno po instalaciji i ne meša se sa starim `LocalQwenHome/state` fajlovima.

## Live Throughput Signal

Primarni živi signal dolazi iz runtime `/slots` endpoint-a na aktivnom installer-managed portu.

Pravila:

- ako `/slots` nije dostupan ili runtime nije pokrenut, live signal je `null` / nema novih uzoraka
- live history čuva samo skorije uzorke, ograničene po vremenskom prozoru i broju elemenata
- prosečne vrednosti se računaju iz stabilne benchmark istorije, ne samo iz prolaznih live polling uzoraka

## Benchmark Run Execution

Benchmark scenariji se izvršavaju preko aktivnog runtime endpoint-a, ne kroz spoljne legacy launchere.

Za svaki scenario:

- obezbediti da je runtime spreman
- poslati kontrolisani completion zahtev
- iz odgovora izvući throughput/latency metrike ako postoje
- ako direktne metrike nisu dostupne, fallback je meriti zidno vreme i broj generisanih tokena iz odgovora

Battery run je sekvencijalno izvršavanje više scenarija sa jasnim `queued/running/done/failed` statusima.

## Error Handling

- runtime offline: Benchmark payload i run akcije vraćaju jasan razlog
- benchmark already running: nove run akcije odbijaju se sa jasnom porukom
- nečitljiv state fajl: fallback na default state, bez rušenja celog panela
- `/slots` ili completion timeout: status i istorija ostaju istiniti, bez lažnog uspeha

## Testing Strategy

Potrebne su najmanje sledeće grupe testova:

- unit testovi za benchmark service state/persistence
- route testovi za benchmark API
- testovi za live `/slots` signal i istoriju
- testovi za run-state lifecycle
- frontend dist smoke da `Benchmark` opet postoji u spakovanom buildu

## Release Truth

Kada ovaj slice bude gotov, možemo pošteno da tvrdimo da isporučeni Windows panel ima:

- živ benchmark throughput pogled kroz vreme
- prosečni i trenutni throughput signal
- benchmark scenario/battery tok
- istoriju benchmark run-ova

Ali i dalje nećemo tvrditi GPU-level deep profiling ili advanced perf analytics van onoga što runtime signal stvarno daje.


