# Compatibility Tab Design

## Cilj

Compatibility calculator vise ne sme da bude sakriven samo iza modal dugmadi u `Models` i `Browser`.
Treba da postoji kao first-class radni prostor unutar glavne navigacije, sa istim truth modelom koji vec koristi backend compatibility proveru.

## Problem danas

- korisnik ne vidi gde se kalkulator nalazi
- calculator postoji, ali UX zavisi od skrivenih `Check compatibility` ulaza
- nema stalnog mesta gde korisnik moze da:
  - bira lokalni ili remote model
  - uporedi runtime fit
  - vidi sistemski snapshot
  - primeni preporuke i odmah ponovi proveru

## Resenje

Uvesti novi `Compatibility` tab sa 3 sloja:

1. `Workspace header`
   - kratko objasnjenje sta calculator radi
   - quick action dugmad ka `Models` i `Browser`
   - quick action za aktivni model

2. `Model source picker`
   - `Active model`
   - `Local catalog`
   - `Remote catalog`
   - lokalni katalog cita `/api/models`
   - remote katalog cita `/api/browser/catalog`

3. `Embedded calculator`
   - koristi isti compatibility backend kontrakt:
     - `POST /api/compatibility/check`
     - `POST /api/compatibility/apply`
   - prikazuje:
     - best runtime
     - runtime breakdown
     - VRAM/RAM headroom
     - context/output pressure
     - preporuke
     - advanced override

## Truth model

- ne praviti novi compatibility backend
- ne praviti paralelnu formulu u frontend-u
- Compatibility tab mora da koristi isti payload kao modal:
  - `BrowserCompatibilityPayload`
  - `CompatibilityCheckRequest`

## Polish pass 1

- jasan empty state kada nema izabranog modela
- jasan remote search i source filter
- system snapshot izdvojen u preglednu traku
- quick action za aktivni model

## Polish pass 2

- bolja vizuelna hijerarhija i kompaktniji raspored
- jasna povezanost sa `Models` i `Browser`
- modal ostaje za brze provere, ali tab postaje glavni radni prostor

## Granice

- ne uvoditi novi backend endpoint ako isti rezultat moze da se dobije kroz postojece `models` i `browser` rute
- ne menjati compatibility matematiku bez potrebe
- ne uklanjati modal, nego ga zadrzati kao brzu ulaznu tacku
