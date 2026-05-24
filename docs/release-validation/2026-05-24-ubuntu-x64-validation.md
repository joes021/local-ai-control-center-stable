# Ubuntu x86_64 Validation

Date: 2026-05-24

## Status

`blocked`

Ubuntu x86_64 repo slice je kodno integrisan do source-bootstrap i Linux shell launcher nivoa, ali zivi end-to-end validation run nije mogao da se zatvori zbog spoljasnjeg WSL okruzenjskog blokera.

## Verified repo state

Na trenutnom checkout-u su prosli:

- `python -m pytest -q`
  - rezultat: `389 passed`
- `python -m build`
  - rezultat: `sdist` i `wheel` uspesni

Ubuntu x64 repo truth koji je sada pokriven:

- Linux runtime i `OpenCode` manifest selection
- `bootstrap/install.sh`
- Linux default install root
- Linux `Open-Control-Center.sh`
- Linux `Open-OpenCode.sh`
- Linux panel host wrapper `local-ai-control-center-panel`
- Linux picker fallback preko `zenity`
- bootstrap interpreter search sada proverava:
  - `python3.13`
  - `python3.12`
  - `python3.11`
  - `python3`
  - `python`

## Live environment that was tested

WSL distro:

- `Ubuntu 22.04.4 LTS`
- arhitektura: `x86_64`

Utvrdeno zivo stanje:

- `python3 --version`
  - `Python 3.10.12`
- `python3.11`
  - nije instaliran
- `node`
  - prisutan
- `npm`
  - prisutan

## Live validation attempt

Pokusaj zatvaranja Ubuntu bootstrap puta je stao pre stvarnog install run-a:

1. postojece WSL okruzenje nema `Python 3.11+`
2. projekat zahteva `Python >= 3.11`
3. `install.sh` sada ume da pronadje verzionisani interpreter ako postoji, ali u ovom WSL-u takav interpreter jos ne postoji
4. autonomni pokusaj instalacije `python3.11` preko `apt` nije mogao da se dovrsi jer:
   - `sudo` zahteva lozinku koja nije dostupna agentu
   - trenutni WSL `apt` source koristi `http://archive.ubuntu.com/...`
   - direktan HTTP pristup ka tom izvoru iz ove WSL sesije pokazao je neuspesan repo put, dok HTTPS probe rade

Relevantni zivi nalazi:

- `sudo -n true`
  - rezultat: `sudo: a password is required`
- `wsl -d Ubuntu python3 -c "...urllib.request.urlopen('http://archive.ubuntu.com/...')..."`
  - rezultat: `URLError`
- `wsl -d Ubuntu python3 -c "...urllib.request.urlopen('https://archive.ubuntu.com/...')..."`
  - rezultat: `200`

## Blocker classification

Ovo je `external blocker`, ne repo-code blocker.

Trenutni repo sada poštenije i otpornije trazi podrzani Python interpreter na Ubuntu putu, ali zivi validation na dostupnoj Ubuntu masini ne moze dalje bez jedne od sledecih spoljasnjih akcija:

- instaliran `python3.11+` u WSL-u
- ili dostupan `sudo`/repo pristup da agent to instalira
- ili alternativno Ubuntu test okruzenje koje vec ima `Python 3.11+`

## Honest current claim

Repo trenutno moze pošteno da tvrdi:

- Ubuntu x86_64 source-bootstrap kodni put je implementiran do Linux shell launcher nivoa
- puna Python test baza i build su zeleni
- ziva Ubuntu validation checklist nije zatvorena

Repo trenutno ne treba da tvrdi:

- da je Ubuntu x86_64 produkt end-to-end validated
- da je Ubuntu x86_64 fresh install checklist zatvorena
- da postoji spreman Ubuntu release artifact

## Next unblock step

Nastavak rada je smislen odmah nakon jednog od sledecih uslova:

1. WSL dobije `python3.11+`
2. agent dobije mogucnost da izvrsi `sudo apt` korake
3. obezbedi se cist Ubuntu x86_64 test host sa vec spremnim `Python 3.11+`

Posle toga slede direktno:

- fresh install run
- runtime payload verification
- `OpenCode` launch path
- Browser direct download path
- update path
