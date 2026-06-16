# OpenCode + utility shell spec

## Cilj

Sledeći UX paket treba da dovede `OpenCode`, `Radne tokove`, `Flotu` i manje servisne strane u isti
RuntimePilot shell jezik koji već koriste početna, Settings, Compatibility i Benchmark.

## Primećeni problemi

- `OpenCode` još koristi stariji `PrimaryTabRack` raspored koji funkcionalno radi, ali je vizuelno
  odvojen od novog home-shell sistema.
- `Radni tokovi` imaju dugačak uvodni blok sa bočnim akcijama koje ostavljaju prazan prostor i
  ne daju isti ritam kao noviji status/action deck ekrani.
- `Flota` i manje servisne strane (`Logovi`, `Popravka`, `Ažuriranja`, `Poslovi`) još uglavnom žive
  kao `PageFlowCard + sadržaj`, bez kratkog status presjeka i bez jasnog vršnog action layer-a.
- Korisnik i dalje na nekim ekranima mora da “čita raspored” umesto da odmah vidi stanje, naredni
  klik i mesto gde će rezultat da se pojavi.

## Zajednički obrazac

Novi paket treba da koristi isti vrh strane:

1. `PageFlowCard` ili `SupportPageDeck` kao kratak tok rada.
2. `RuntimePilotStatusDeck` za 4-5 stvarnih status kartica.
3. `RuntimePilotActionDeck` za realne klikove bez duplikata i bez mrtvih blokova.
4. Glavni radni moduli preko pune širine, složeni vertikalno.

## OpenCode

- Zameniti gornji `PrimaryTabRack` novim shell rasporedom.
- Status deck treba da pokaže:
  - stanje sesije
  - runtime vezu
  - workspace
  - managed config / model
  - poslednji rezultat ili instance signal
- Action deck treba da drži:
  - `Otvori OpenCode`
  - `Izolovan workspace`
  - `Reinstall / popravi OpenCode`
  - skok na rezultat
  - skok na napredne alate
- Napredni alati ostaju u disclosure delu, ali glavni vrh strane mora odmah da kaže:
  “da li je agent spreman”, “gde radi”, “koji model koristi” i “šta se desilo posle klika”.

## Radni tokovi

- Strana treba da pređe sa “dugog flow card-a sa tri bočna dugmeta” na isti vršni status/action model.
- Status deck treba da pokaže:
  - aktivni preset
  - preset učitan u editor
  - dirty stanje editora
  - search / knowledge smer
  - benchmark launch smer
- Action deck treba da drži:
  - otvori pretragu
  - otvori znanje
  - otvori benchmark
  - skok na katalog preseta
  - skok na editor

## Flota i servisne strane

- `Flota` dobija status deck za broj mašina, poslednje osvežavanje, zdravlje i throughput signal.
- `Logovi`, `Popravka`, `Ažuriranja` i `Poslovi` ne moraju svi odmah da dobiju pun kompleksan
  raspored, ali treba da koriste isti vršni shell princip:
  - kratko stanje
  - jedan red stvarnih akcija
  - glavni rezultat ispod bez praznog prostora
- Prioritet je da se ukloni osećaj “velike površine sa malo smisla”.

## Dizajn pravila

- Nema dupliranja komandi između uvoda i glavnog modula.
- Kartice u istom redu moraju da ostanu iste visine.
- Akcije moraju da budu očigledno klikabilne i da pokazuju gde se ishod vidi posle klika.
- Ne vraćati stari bočni rail obrazac tamo gde je već zamenjen novim shell-om.
