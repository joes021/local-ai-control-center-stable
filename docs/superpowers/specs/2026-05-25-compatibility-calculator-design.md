# Compatibility Calculator Design

## Goal

Ojačati postojeći compatibility calculator tako da daje smisleniju procenu da li model staje na dati hardver i kako se ponaša kroz `llama.cpp` i `TurboQuant` varijante, umesto da daje jednu grubu zajedničku procenu.

## Problem

Postojeći kalkulator:

- računa previše grubo
- ne razdvaja jasno `llama.cpp` i `TurboQuant`
- ne objašnjava dovoljno šta pritiska VRAM, RAM i context
- ne daje dovoljno jasan fit signal za runtime izbor

Zbog toga korisnik ne može da veruje kalkulatoru kao pravoj operativnoj pomoći pri izboru modela i podešavanja.

## Design

Kalkulator ostaje na postojećem backend/frontend entrypoint-u, ali payload postaje jači.

### Backend truth model

Za dati model i snapshot sistema računamo:

- zajednički model profil:
  - quant
  - approx size
  - context window
  - output baseline
  - `moe`
  - `mtp`
- dve runtime procene:
  - `llama.cpp`
  - `TurboQuant`

Svaka runtime procena vraća:

- `fitStatus`
- `fitLabel`
- `speedStatus`
- `speedLabel`
- procenjeni VRAM budžet
- procenjeni RAM budžet
- context pressure
- output pressure
- efektivni capacity signal
- kratko runtime objašnjenje

Uz to vraćamo i ukupni zaključak:

- `bestRuntime`
- `bestRuntimeLabel`
- `overallFitStatus`
- `overallFitLabel`
- `summary`

### Formula direction

Formula ne sme da tvrdi lažnu preciznost, ali mora biti dosledna i objašnjiva.

Koristi sledeće ulaze:

- veličina modela
- quant class
- da li je model `MoE`
- da li je model `MTP`
- izabrani context
- izabrani output tokens
- dostupni VRAM
- dostupni RAM
- `TurboQuant` cache parametri:
  - `ctk`
  - `ctv`
  - `ncmoe`

Pravila:

- `MTP` modeli nikad ne dobijaju `TurboQuant` fit kao pozitivan put
- `TurboQuant` može da smanji VRAM/context pritisak, ali ne uklanja RAM i output cenu
- veći context i output povećavaju pressure odvojeno
- `MoE` dobija dodatni CPU/RAM/context oprez
- rezultat mora da razlikuje:
  - `radi`
  - `granicno`
  - `ne radi`

### UI changes

Modal ostaje isti entrypoint, ali dobija:

- jasan `best runtime` header
- dve runtime kartice:
  - `llama.cpp`
  - `TurboQuant`
- poseban red za:
  - context pressure
  - output pressure
  - memory headroom
- jasnije reasoning sekcije

Postojeće preporuke ostaju, ali se vezuju za konkretniji runtime zaključak.

## Testing

Dodati fokusirane testove za:

- `TurboQuant` bolji od `llama.cpp` na manjim quant modelima
- `MTP` model blokira `TurboQuant` fit
- veliki context povećava pressure i obara fit
- veliki output povećava pressure i obara fit
- payload sadrži runtime breakdown i `bestRuntime`
- frontend dist sadrži novi kalkulator tekst i runtime sekcije

## Non-goals

- benchmark integracija u compatibility calculator
- hardverski vendor-specifični perf model
- lažno precizan `tokens/s` predictor
