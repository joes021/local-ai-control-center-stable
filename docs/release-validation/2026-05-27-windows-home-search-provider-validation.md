## Windows Home + Search Provider Validation

Datum: 2026-05-27
Grana: `codex/panel-integration`
Cilj: spojiti Home pregled u jednu karticu, sloziti ga u svesniji dashboard raspored i dodati stvarni izbor search providera sa DuckDuckGo opcijom.

### Sta je promenjeno

- `Home` sada koristi jednu `System overview` karticu za:
  - `Control Center health`
  - `Aktivan runtime`
  - `Status runtime servera`
  - `Aktivni model`
  - `Profil`
  - `Dostupni runtime-i`
- `Server` i `OpenCode` kartice ostaju odvojene i nepromenjene.
- `Home` vise ne izgleda kao tri visoka stuba; `System overview` ide preko cele sirine, a `Server` i `OpenCode` ostaju u kompaktnom drugom redu.
- `Search` sada podrzava:
  - `SearxNG`
  - `DuckDuckGo`
- `Search` i `Settings` sada imaju provider picker.
- `Search` sada ima i `Compare providers` tok koji prikazuje isti upit kroz oba providera.
- `DuckDuckGo` je dodat kao no-key best-effort public web provider.
- `SearxNG` ostaje jedini managed bootstrap provider.
- `DuckDuckGo` sada ima i TLS fallback za Windows okruzenja gde standardna CA verifikacija vraca `unable to get local issuer certificate`.

### Backend verifikacija

- `python -m pytest tests/test_control_center_search_service.py -q`
- `python -m pytest tests/test_control_center_search_provider.py -q`
- `python -m pytest tests/test_control_center_search_routes.py -q`
- `python -m pytest tests/test_control_center_settings.py -q`

Rezultat:
- svi ciljani testovi prolaze

### Frontend verifikacija

- frontend TypeScript build:
  - `node frontend/node_modules/typescript/bin/tsc -b`
- frontend Vite build:
  - `node frontend/node_modules/vite/bin/vite.js build`
- paketovani frontend test:
  - `python -m pytest tests/test_control_center_frontend_dist.py -q`

Rezultat:
- novi bundle sadrzi:
  - `System overview`
  - `Compare providers`
  - `DuckDuckGo`
  - `Search provider`

### Full gate

- `python -m pytest -q`

Rezultat:
- `493 passed`

### Ziva verifikacija

- lokalni repo smoke:
  - `perform_search_query('openai news', provider_override='duckduckgo')`
- lokalna instalirana aplikacija:
  - `POST /api/search/query` sa `provider = duckduckgo`
- udaljena Windows masina `192.0.2.10`:
  - upgrade na `0.4.37`
  - `GET /api/status`
  - `POST /api/search/query` sa `provider = duckduckgo`

Rezultat:
- `status = ok`
- `resultCount = 5`
- prvi rezultat vraca `OpenAI News`
- udaljena masina takodje vraca `SEARCH_STATUS = ok`

### Napomena o provider istini

- `DuckDuckGo` koristi best-effort HTML parsing i ne predstavlja zvanican API backend.
- `SearxNG` ostaje preporuceni managed/local provider kada korisnik zeli vecu kontrolu i lokalni setup.


