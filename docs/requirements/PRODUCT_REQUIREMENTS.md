# Local AI Control Center Product Requirements

Date: 2026-05-20

## Purpose

Ovaj dokument zakljucava produktske zahteve za `Local AI Control Center`.

Cilj nije lep demo, nego stvarno upotrebljiv lokalni AI proizvod koji:

- moze da se instalira bez rucnog peglanja
- moze da se koristi odmah posle instalacije
- jasno pokazuje kada nesto nije uspelo i zasto

## Product Goal

`Local AI Control Center` mora da bude pouzdan lokalni AI control centar za:

- Windows
- Ubuntu x86_64
- Ubuntu arm64

Primarni fokus:

- stabilna instalacija
- jasan runtime status
- pouzdan model lifecycle
- pouzdan OpenCode tok
- transparentan UX

## Locked Decisions

- Postoji samo jedna instalaciona varijanta proizvoda.
- Windows installer treba da bude tekstualni installer sa jasnim izborima preko brojeva.
- Podrazumevana install lokacija:
  - Windows: `C:\Users\<user>\LocalAIControlCenter`
  - Ubuntu x86_64: `~/local-ai-control-center`
  - Ubuntu arm64: `~/local-ai-control-center`
- Podrazumevana lokacija za modele:
  - Windows: `C:\Users\<user>\LocalAIControlCenter\models`
  - Ubuntu x86_64: `~/local-ai-control-center/models`
  - Ubuntu arm64: `~/local-ai-control-center/models`
- Dodatne model lokacije sluze samo za citanje lokalnih modela.
- Novi download modela ide samo u glavni podrazumevani model folder.
- Aktivni model je primarno model za `llama.cpp`, i ta promena mora automatski da se prenese i na `OpenCode`.
- Ako korisnik nije eksplicitno trazio `TurboQuant`, sistem ga ne pokusava automatski.
- Download tokom instalacije ide jedan po jedan.
- Rucno skinuti modeli treba da budu automatski otkriveni pri sledecem pokretanju aplikacije.
- Ako postoji stara instalacija, installer treba da ponudi:
  - `Upgrade postojece instalacije`
  - `Fresh install u novu lokaciju`
  - default: `Upgrade postojece instalacije`

## Must Have

### Installer

- Mora da postoji pouzdan installer za:
  - Windows
  - Ubuntu x86_64
  - Ubuntu arm64
- Tokom instalacije mora da pita korisnika gde ce aplikacija biti instalirana.
- Mora jasno da prikaze podrazumevanu install lokaciju.
- Ako korisnik ne upise drugu lokaciju, koristi se prikazani default.
- Mora jasno da prikazuje:
  - sta proverava
  - sta instalira
  - sta je uspelo
  - sta nije uspelo
- Svi korisnicki izbori moraju da se zavrse pre finalnog install koraka.
- Zavrsni install/download korak mora da bude jedan objedinjeni tok koji stvarno preuzima sve potrebne fajlove.
- Tokom tog download koraka mora jasno da se prikazuje:
  - koji fajl se trenutno skida
  - koji je to fajl po redu
  - koliko ukupno fajlova treba da se skine
  - koliko je fajlova jos ostalo
  - procenjeni ETA
- Mora da se vidi i red fajlova koji ulaze u download tok.
- Ako neka obavezna komponenta nije spremna, instalacija mora da prijavi neuspeh.

### Obavezne komponente

Posle uspesne instalacije moraju biti spremni:

- `Control Center`
- `llama.cpp`
- `OpenCode`
- najmanje jedan upotrebljiv model

Na platformama gde je podrzan i izabran:

- `TurboQuant`

### Model bootstrap

- Installer mora da ponudi mali vodjeni izbor preporucenih modela.
- Mora da podrzi tri glavna preporucena modela za:
  - `6 GB`
  - `12 GB`
  - `24 GB`
- Installer mora automatski da oznaci preporuceni model.
- Installer mora jasno da prikaze iz koje lokalne lokacije cita modele.
- Mora da pita korisnika da li zeli jos dodatnih lokacija iz kojih aplikacija sme da cita modele.
- Ako postoji vise lokacija za modele, to mora biti zabelezeno u konfiguraciji.
- Dodatne model lokacije su read-only lokacije za otkrivanje postojecih modela.
- Installer mora kao deo instalacije stvarno da:
  - skine izabrani model
  - ili jasno prijavi da nije uspeo
- Model download mora da bude deo zavrsnog download koraka.
- Ne sme da proglasi bootstrap uspesnim samo zato sto postoji neki drugi model na masini.

### Runtime i server

- Portal mora da ume da:
  - pokrene `llama.cpp` server
  - zaustavi `llama.cpp` server
  - otvori `llama.cpp` web UI
- Portal mora tacno da prikazuje:
  - status servera
  - health
  - port
  - aktivni runtime
  - aktivni model

### OpenCode

- `OpenCode` mora da se pokrece iz portala.
- Mora da koristi:
  - aktivni model
  - aktivni lokalni runtime
  - podesavanja iz portala

### TurboQuant

- Na podrzanim platformama installer mora ili da:
  - stvarno instalira/build-uje `TurboQuant`
  - ili jasno prijavi zasto nije uspeo
- Na `Ubuntu arm64` ne sme da se nudi kao podrzana opcija ako nije podrzan.
- Ako je `TurboQuant` cekiran i ne uspe, to mora biti vrlo jasno istaknuto.
- Instalacija sme da se nastavi samo ako su sve druge obavezne komponente uspesne.

### Browser / model katalog

- `Refresh from internet` mora da radi pouzdano.
- U tabeli moraju da se vide velicine modela.
- `Download` iz tabele mora stvarno da radi.
- Mora da postoji direktan link ka:
  - Hugging Face
  - Unsloth
- Download UX mora da prikazuje:
  - status
  - progress bar
  - procenat
  - brzinu
  - ETA
- Download status mora da bude prikazan odmah uz aktivni detail panel modela.

### Models tab

- Mora da prikazuje:
  - skinute modele
  - aktivni model
  - rucno dodate lokalne modele
- Mora jasno da razlikuje:
  - `downloaded`
  - `local`
  - `active`
- Aktivni model mora moci da se promeni iz aplikacije.

### Updates

- Aplikacija mora da cita latest release sa GitHub-a.
- `Check updates` mora da radi.
- `Install update` mora da radi iz aplikacije.
- Update tok treba da:
  - skine novi setup
  - prikaze progress
  - automatski pokrene update setup

### Branding

- Sve mora koristiti novo ime:
  - `Local AI Control Center`
- Stari nazivi ne smeju biti primarni.

### Definition of successful installation

Uspesna instalacija znaci da su sve obavezne stavke uspesne:

- aplikacija instalirana
- `llama.cpp` radi
- `OpenCode` radi
- izabrani model je skinut i prisutan
- aktivni model je podesen
- first-run test je prosao
- sve sto je izabrano za instalaciju je stvarno skinuto i instalirano

`TurboQuant` nije hard-fail komponenta, ali ako je korisnik trazio njegovu instalaciju mora biti jasno prijavljen status i razlog neuspeha.

### Failure policy

Hard fail su:

- nema modela
- `llama.cpp` ne radi
- `OpenCode` ne radi
- first-run test ne prolazi
- bilo koja obavezna komponenta nije stvarno instalirana ili potvrdjena

`TurboQuant` nije hard fail, ali je obavezan za jasan status i razlog neuspeha ako je bio izabran.

## Should Have

- Compatibility calculator
- Benchmark grafikon i reset
- Jasan zavrsni install prikaz
- Tekstualni log + JSON report
- Jasan repo i release storefront

## Out of Scope

- dodatni UI polish
- eksperimentalne feature grane
- benchmark eksperimenti
- kozmeticki refaktori koji ne podizu pouzdanost

## Non-Negotiable Release Rule

Nova verzija ne sme biti proglasena uspesnom ako korisnik ne moze da:

1. instalira aplikaciju
2. dobije najmanje jedan stvarno spreman model
3. pokrene `llama.cpp`
4. otvori `OpenCode`
5. koristi aktivni model kroz `OpenCode`
6. vidi pravi status u portalu

## Product Direction

Ako postoji konflikt izmedju:

- lepsheg novog UI-ja
- i stabilnog starog install/runtime toka

prednost mora imati:

- stabilan install/runtime tok

Drugim recima:

- stable core first
- shell second

## Delivery Priority

1. Windows
2. Ubuntu x86_64
3. Ubuntu arm64
