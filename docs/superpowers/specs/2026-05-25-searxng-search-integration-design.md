# SearxNG Search Integration Design

Date: 2026-05-25

## Goal

Dodati jedan zajednicki `SearxNG` search sloj koji moze da se koristi:

- kroz lokalni model iz `Local AI Control Center` panela
- kroz `OpenCode` kada koristi installer-managed `local-lacc` provider

Cilj nije "jos jedan browser tab", nego istinit web-search alat koji deli isti backend, ista podesavanja i ista pravila za lokalni model i OpenCode.

## Product truth

Ovaj slice ne menja osnovni runtime truth model:

- aktivni lokalni runtime i dalje ostaje installer-managed
- aktivni model i dalje ostaje jedan kanonski model za lokalni runtime
- `OpenCode` i dalje koristi isti aktivni lokalni runtime kada radi preko `local-lacc`

Novi truth koji uvodimo:

- web search se ne desava "u modelu", nego kroz control-center backend
- isti search servis se koristi za lokalni model i za OpenCode `local-lacc` put
- cloud `opencode` provider ostaje dozvoljen izbor modela, ali ne prolazi kroz lokalni search proxy osim ako ga jednog dana posebno integrisemo

## Shared architecture

Uvodi se jedan shared search sloj:

- `search_service.py`
- `search` API rute
- `runtime proxy` rute

Taj sloj radi tri stvari:

1. cita search settings i odlucuje da li search treba da se koristi
2. zove `SearxNG`
3. ubacuje prociscene web rezultate u prompt pre slanja lokalnom runtime-u

## Search modes

Podrzana tri rezima:

- `off`
- `on-demand`
- `always`

Semantika:

- `off`
  - nikad ne poziva `SearxNG`
- `on-demand`
  - search se pali samo kada korisnik eksplicitno trazi web search
  - za OpenCode/local-lacc to ide preko prefiksa, podrazumevano `/web`
- `always`
  - svaki lokalni chat completion pokusava da dobije web rezultate pre inferencije

## Settings contract

Global settings dobijaju shared search polja:

- `webSearchMode`
- `webSearchProvider`
- `webSearchBaseUrl`
- `webSearchMaxResults`
- `webSearchTimeoutSeconds`
- `webSearchPromptPrefix`

Ova polja nisu deo settings profila za model/context, jer predstavljaju sistemski orchestration sloj, ne profil modelskog rada.

## SearxNG contract

Primarni provider je `SearxNG`.

Minimalni ugovor:

- backend poziva `GET /search`
- koristi `format=json`
- salje `q=<query>`
- opciono limitira rezultat na backend strani

Backend normalizuje rezultate u jedan stabilan oblik:

- title
- url
- snippet/content
- engine
- score/rank kada postoji

## Search tab

Panel dobija poseban `Search` tab.

On omogucava:

- unos search pitanja
- direktan pregled web rezultata
- `Answer with local model` tok nad istim rezultatima
- pregled aktivnog search rezima i kljucnih ogranicenja

Ovo je "model side" search put.

## OpenCode integration

`OpenCode` danas koristi `local-lacc` provider preko `openai-compatible` base URL-a.

Umesto direktnog runtime URL-a, taj provider treba da pokazuje na lokalni control-center proxy:

- `http://127.0.0.1:3210/api/runtime-proxy/v1`

Proxy:

- forwarduje sve standardne lokalne runtime pozive
- za `/chat/completions` moze da obogati prompt web rezultatima
- postuje shared search settings

## On-demand trigger for OpenCode

Za `on-demand` mod uvodi se prompt prefiks:

- podrazumevano `/web`

Primer:

- `/web pronadji najnovije informacije o ...`

Proxy:

- prepoznaje prefiks u poslednjoj user poruci
- skida prefiks iz prosledjenog prompta
- radi web search
- ubacuje search context

## Prompt augmentation rules

Search context se ubacuje kao poseban sistemski blok pre user poruke.

Blok mora:

- jasno da oznaci da su to web rezultati
- da navede naslove i URL-ove
- da trazi od modela da ne izmisli sta nije nasao u rezultatima
- da koristi rezultate kao dodatni context, ne kao jedini izvor istine

## Boundaries

Ovaj slice namerno ne obecava:

- da cloud `opencode` provider prolazi kroz lokalni search proxy
- da `SearxNG` sam cisti ceo web page content
- da postoji full browser automation ili scraping unutar search toka

Prvi proizvodni slice koristi:

- search result title
- snippet
- url

To je dovoljno za brz i stabilan search augmentation put.

## Validation gate

Feature nije gotov dok ne prodje:

- settings save/load
- `Search` tab query + answer tok
- `OpenCode` `local-lacc` put sa `off`
- isti put sa `on-demand`
- isti put sa `always`
- lokalni installer build
- lokalni upgrade na ovoj masini

## Non-goals

- cloud-provider-native web tools
- multi-provider search marketplace
- page scraping beyond search snippets
- Ubuntu port u ovom slice-u
