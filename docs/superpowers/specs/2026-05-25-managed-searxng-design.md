# Managed SearxNG Design

Date: 2026-05-25

## Goal

`Local AI Control Center` ne sme vise da podrazumeva lazni `http://127.0.0.1:8080` search endpoint. Search sloj mora jasno da zna da li je `SearxNG`:

- nepodesen
- pogresno usmeren na drugi servis
- nedostupan
- zdrav i spreman

Kada je moguce, aplikacija treba sama da podigne svoj lokalni `SearxNG` umesto da ocekuje rucni setup.

## Product truth

- Search ne sme da tvrdi da je spreman samo zato sto postoji neka adresa u settings-u.
- Ako endpoint vraca HTML ili drugi servis, korisnik mora da vidi jasan status, ne Python parser gresku.
- Podrazumevani search URL za nove instalacije treba da bude prazan, ne `127.0.0.1:8080`.
- Postojeci legacy `127.0.0.1:8080` treba tretirati kao nepouzdan istorijski default, ne kao “configured” istinu.

## Managed provider model

Dodaje se zaseban provider sloj za `SearxNG`:

- status/health provera
- legacy default migracija
- best-effort bootstrap lokalnog managed `SearxNG`
- metadata o managed instanci

Provider status treba da razlikuje:

- `not-configured`
- `healthy`
- `unreachable`
- `wrong-service`
- `error`
- `bootstrap-blocked`

## Bootstrap strategy

Primarni managed bootstrap za Windows ide preko `WSL Ubuntu`, jer upstream `SearxNG` repo nije prirodno Windows-native checkout/install put.

Bootstrap tok:

1. proveri da li postoji pokrenjiv `WSL` distro
2. proveri `python3`, `pip3`, `git`, `openssl`
3. instalira user-space `virtualenv` ako treba
4. klonira/azurira `SearxNG` repo u WSL home
5. pravi virtualenv
6. instalira `requirements.txt`
7. za Python `<3.11` dodaje mali `tomllib` shim preko `tomli`
8. generise managed `settings.yml`
9. ukljucuje `json` format podrsku
10. podize `searx.webapp`
11. verifikuje `/search?...&format=json`

Ako `WSL` nije dostupan ili bootstrap ne moze da prodje, provider status mora pošteno da kaze zasto i sta je blocker.

## Runtime details

Managed instanca koristi zaseban lokalni port koji aplikacija kontrolise, a ne `8080`.

Metadata treba da cuva:

- da li je managed provider aktivan
- koji je `baseUrl`
- koji je WSL distro
- gde su repo, venv, settings i pid fajl
- poslednji bootstrap status i poruku

## UX

### Search tab

Search tab dobija vidljiv provider status:

- “SearxNG nije podešen”
- “Na adresi radi drugi servis: Open WebUI”
- “Managed SearxNG radi”
- “Managed bootstrap je blokiran: ...”

Akcije:

- `Check health`
- `Setup local SearxNG`
- `Open Settings`

Search i answer dugmad ne treba da se ponašaju kao da mogu da rade kad provider nije zdrav.

### Settings

Web search sekcija treba da:

- prikaze provider status
- objasni da `base URL` moze biti prazan
- jasno razlikuje rucni URL i managed bootstrap

## Testing

TDD pokrice treba da obuhvati:

- legacy default nije vise efektivni default
- status detektuje `wrong-service` kada vrati HTML
- status detektuje `healthy` kada vrati validan JSON search payload
- bootstrap wrapper vraca jasan `bootstrap-blocked` kad WSL nije dostupan
- Search summary i Search page koriste novi provider status kontrakt

## Honest limits

- Ovo nije pun Linux/systemd deployment za `SearxNG`
- Managed bootstrap je best-effort user-space tok
- Za cloud `opencode` provider i dalje ne dodajemo direktan lokalni search sloj


