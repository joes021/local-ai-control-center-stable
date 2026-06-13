# RuntimePilot UX Rewrite Design

**Datum:** 2026-06-05  
**Status:** odobren dizajn, spreman za planiranje implementacije  
**Cilj:** preurediti RuntimePilot tako da svi postojeci sistemi ostanu dostupni, ali da UI i UX jasno vode korisnika kroz osnovni tok `Runtime -> Lokalni model -> OpenCode`, uz mnogo manje lutanja, manje dugackih kolona i bolju mobilnu upotrebljivost.

## Problem

RuntimePilot je tokom rasta dobio veliki broj mocnih funkcija:

- izbor i start runtime-a
- lokalne modele
- OpenCode integraciju
- Benchmark
- Tuning Lab
- kompatibilnost i VRAM fit
- telemetriju
- logs, repair i update tokove
- Project Memory i Help

Funkcionalno to daje sirok raspon mogucnosti, ali UX problem je postao ozbiljan:

- previse delova izgleda podjednako vazno
- korisnik cesto ne zna sta je sledeci klik
- korisnik posle klika ne zna gde da gleda rezultat
- napredni paneli deluju kao drugo, odvojeno carstvo
- mnogo sadrzaja ide u duge kolone i teske vertikalne blokove
- mobilni prikaz vise lici na sabijeni desktop nego na mobile-first tok

To posebno pogadja korisnike koji nisu vestim sa AI alatima, promptovima, runtime terminologijom i parametrima modela.

## Osnovni UX cilj

RuntimePilot mora da postane proizvod koji:

- jasno pokazuje sta su tri najvaznije stvari
- pokazuje samo sledeci logican korak kada korisnik pocinje
- zadrzava napredne funkcije, ali ih smesta u smislen sekundarni sloj
- koristi isti akcioni jezik kroz ceo sistem
- radi prirodno i na mobilnim uredjajima

Korisnik mora odmah da razume:

1. koji runtime koristi
2. koji lokalni model koristi
3. kako da taj model primeni kroz OpenCode

## Zakljucane produkt odluke

Na osnovu korisnickog cilja i odobrenih dizajn koraka, sledece odluke su zakljucane:

- glavni tok proizvoda je `Runtime -> Lokalni model -> OpenCode`
- pocetna i glavni shell moraju biti organizovani oko ta tri toka
- treba da postoji i `Vodi me redom` tok za pocetnike
- sve ostalo ostaje u proizvodu, ali ide u sekundarni sloj
- glavni i napredni delovi moraju koristiti isti akcioni model
- univerzalni obrazac za parametre je:
  - `Sacuvaj i primeni` kao glavno dugme
  - `Sacuvaj bez primene` kao sekundarno dugme
- korisnik mora jasno da vidi razliku izmedju:
  - izmenjeno u editoru
  - sacuvano u configu
  - primenjeno na zivi sistem

## Informaciona arhitektura

### Glavni sloj

Glavni sloj je ono sto korisnik vidi prvo i koristi najcesce:

- Pocetna
- Runtime
- Modeli
- OpenCode
- `Vodi me redom`

To je primarni navigacioni i radni okvir proizvoda.

### Sekundarni sloj

Sekundarni sloj zadrzava sve napredne mogucnosti, ali ih grupise po svrsi umesto po istorijskom nastanku:

#### Analiza

- Benchmark
- Telemetrija
- Kompatibilnost

#### Optimizacija

- Tuning Lab
- Project Memory

#### Odrzavanje

- Logs
- Repair
- Updates

#### Pomoc

- Help
- troubleshooting i vodici

Poenta nije da sekundarne stvari nestanu, nego da vise ne budu ravnopravno glasne kao tri glavna toka.

## Pocetni komandni ekran

Pocetna strana mora da postane pravi komandni ekran, ne samo pregled svega.

Treba da sadrzi:

- sazet brand i status blok
- aktivni runtime
- aktivni model
- OpenCode status
- tri velike glavne zone
- veliko dugme `Vodi me redom`

Na pocetnom ekranu ne sme biti toliko informacija da korisnik mora da cita dugo pre prvog klika.

## Tri glavne zone

Sve tri glavne zone moraju koristiti isti UX skelet:

- `stanje sada`
- `jedna glavna akcija`
- `jedna sekundarna akcija`
- `rezultat akcije`
- `napredno`

Ovo je kljucna odluka koja sprecava da se stranice ponovo pretvore u zidove kartica i dugmadi iste tezine.

### 1. Runtime

Strana `Runtime` odgovara na tri pitanja:

- sta trenutno radi
- da li je zdravo
- sta je sledeca akcija

Predlozeni raspored:

- gornji sazetak
  - aktivni runtime
  - health
  - mismatch upozorenje ako postoji
- glavna akcija
  - `Pokreni / restartuj runtime`
- sekundarna akcija
  - `Promeni runtime`
- rezultat akcije odmah ispod
- napredna sekcija
  - TurboQuant parametri
  - server dijagnostika
  - context alignment
  - repair

### 2. Lokalni model

Strana `Modeli` mora da prestane da bude duga biblioteka kao podrazumevani prikaz.

Predlozeni raspored:

- fokus blok na vrhu
  - aktivni model
  - da li je spreman
  - da li staje
- glavna akcija
  - `Otvori i promeni model`
- sekundarna akcija
  - `Proveri kompatibilnost`
- kraci model picker za najbitnije grupe
  - aktivni
  - lokalni
  - spremni za download
- sekundarni ulazi
  - `Dodaj lokalni GGUF`
  - dodatne model source grupe
- napredni sloj
  - VRAM fit
  - hide/delete
  - kompatibilnost detalji

Korisnik prvo mora da vidi koji model koristi i kako da ga zameni, a tek onda dugu biblioteku.

### 3. OpenCode

Strana `OpenCode` mora najjasnije da govori sta se desava posle klika.

Predlozeni raspored:

- status blok
  - da li je OpenCode otvoren
  - da li je CLI sesija povezana
  - koji runtime/model koristi
- glavna akcija
  - `Otvori OpenCode`
- sekundarne akcije
  - `Pokreni task`
  - `Otvori poslednji rezultat`
- zivi signal
  - sesija
  - tokeni
  - workspace
- napredni sloj
  - cockpit
  - istorija
  - presetovi
  - Project Memory veza

Korisnik mora odmah da zna:

- da li je OpenCode spreman
- gde da klikne da pocne
- gde da gleda rezultat

## Vodi me redom

Za pocetnike treba da postoji vodjeni tok koji ne zakljucava napredne korisnike.

Wizard mora da vodi kroz:

1. Runtime
2. Lokalni model
3. OpenCode

Ali to ne sme biti jedini nacin koriscenja proizvoda. Napredni korisnik i dalje mora da moze da preskace korake i ide direktno na stranu koja mu treba.

Svaki korak u vodjenom toku treba da ima:

- veliki glavni CTA
- kratko objasnjenje
- jasnu potvrdu sta je gotovo
- indikator sta sledi

## Navigacija

Nova navigacija mora biti dvonivojska.

### Primarni nivo

Uvek vidljiv:

- Pocetna
- Runtime
- Modeli
- OpenCode
- Vodi me redom
- Vise

### Sekundarni nivo

Iza `Vise`, grupisano po smislu:

- Analiza
- Optimizacija
- Odrzavanje
- Pomoc

Navigacija vise ne sme biti lista skoro ravnopravnih tabova sa istorijskim nazivima, nego mapa puta.

## Akcioni model za napredne sekcije

Napredne sekcije su danas jedno od najvecih mesta zabune.

Zato se uvodi jedinstveni obrazac kroz ceo proizvod:

- `Sacuvaj i primeni` je glavno dugme
- `Sacuvaj bez primene` je sekundarno
- `Vrati na poslednje sacuvano` je pomocna radnja

Svaki napredni panel mora da prikaze:

- zivo trenutno stanje
- editor promena
- indikator:
  - izmenjeno u editoru
  - sacuvano u configu
  - primenjeno na zivi sistem
- rezultat odmah ispod istog panela

Ovo mora da vazi svuda gde korisnik menja parametre:

- runtime
- TurboQuant
- modeli
- OpenCode povezani tokovi
- ostale podesive napredne sekcije

Napredni delovi ne smeju da budu drugo carstvo sa drugacijim pravilima.

## Mobile-first pravila

Mobilni prikaz mora biti projektovan posebno, ne samo sabijen desktop.

Na mobilnom:

- brand i status idu u kraci vrh
- tri glavne zone idu vertikalno
- svaka zona ostaje kompaktna:
  - stanje
  - glavni CTA
  - sekundarni CTA
- `Vodi me redom` moze biti sticky CTA ili istaknuta velika akcija pri vrhu
- sekundarni alati se prikazuju kroz sklopive, grupisane sekcije
- rezultat akcije mora da se vidi odmah ispod mesta gde je klik nastao

Mobilni prikaz ne sme da koristi:

- siroke tabele kao primarni nacin citanja
- vise paralelnih kolona kao glavni layout
- duga horizontalna toolbar resenja

## Vizuelni smer

UX rewrite ne podrazumeva samo CSS polish, vec promenu vizuelne hijerarhije:

- manje ravnopravnih kartica na ekranu odjednom
- manje zidova teksta
- manje dugih kolona
- jasnije razlikovanje glavnih i sekundarnih akcija
- sazetiji status signali
- vise progresivnog otkrivanja

Vizuelni identitet RuntimePilot-a treba da ostane prepoznatljiv, ali ne sme da preoptereti korisnika dekoracijom i panelima koji se takmice za paznju.

## Sta se ne menja

Ovaj rewrite ne ukida:

- Benchmark
- Tuning Lab
- kompatibilnost
- telemetriju
- Project Memory
- Help
- logs / repair / updates

Sve to ostaje deo proizvoda. Menja se kako korisnik do njih dolazi i kako proizvod odredjuje sta je glavno, a sta sekundarno.

## Ocekivani rezultat

Posle rewrite-a, RuntimePilot treba da izgleda kao proizvod koji:

- vodi pocetnika bez zbunjivanja
- zadrzava dubinu za napredne korisnike
- daje predvidljiv rezultat posle svakog klika
- koristi isti UX jezik u glavnim i naprednim zonama
- radi prirodno na telefonu i na desktopu

Najvazniji uspeh rewrite-a nije da sve izgleda lepse, nego da korisnik manje puta pita:

- sta sada treba da kliknem
- gde cu videti rezultat
- da li je ovo samo sacuvano ili stvarno primenjeno

## Sledeci korak

Sledeci ispravan korak posle ovog dokumenta je implementacioni plan koji ce podeliti rewrite na faze, pocev od:

1. shared shell i navigacije
2. pocetne strane i tri glavne zone
3. Runtime / Modeli / OpenCode stranica
4. naprednog action modela
5. mobilnog polisha


