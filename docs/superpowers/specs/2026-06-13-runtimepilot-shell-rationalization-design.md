# RuntimePilot Shell Rationalization Design

**Datum:** 2026-06-13  
**Status:** odobren dizajn iz razgovora, ceka korisnicki pregled dokumenta  
**Cilj:** pojednostaviti RuntimePilot shell tako da proizvod prestane da duplira navigaciju i placeholder module, a da korisnik na svakom ekranu odmah vidi sistemsko stanje i jasan sledeci korak.

## Problem

Dosadasnji RuntimePilot shell je kroz vise iteracija dobio vise dobrih hi-fi delova, ali i tri ozbiljna UX problema:

- isti ulazi su se ponavljali u `header`-u i opet u telu stranice
- pojedini veliki moduli su imali samo nekoliko stvarnih dugmadi, a ostatak prostora je delovao kao placeholder scenografija
- korisnik je morao da "cita" ekran da bi shvatio sta je signal, sta je akcija, a sta samo opis

Najgori efekat toga je bio na `Pocetnoj` i `Napredno`:

- `Pocetna` je istovremeno pokusavala da bude navigacija, komandni centar i uvodni dashboard
- `Napredno` je postao skup velikih modula od kojih neki nose premalo stvarnog rada za prostor koji zauzimaju

Ovo je posebno lose za korisnika koji nije vest sa AI alatima, jer mu proizvod ne govori dovoljno jasno:

1. da li je sistem ziv  
2. koji runtime/model su aktivni  
3. gde treba da klikne sledece  
4. gde ce videti rezultat posle klika

## Dizajn cilj

RuntimePilot treba da dobije jedan strogo hijerarhijski shell:

- `header` je navigacija
- `sistemski sloj` je istina o trenutnom radu
- `sadrzaj strane` je mesto gde se konkretna akcija stvarno obavlja

To znaci:

- nema dupliranja header komandi u telu strane
- nema velikih modula bez dovoljno stvarnog sadrzaja
- nema "lepih" placeholder kartica koje ne vode nigde
- svaka velika povrsina mora da bude ili:
  - zivi signal
  - direktna akcija
  - jasan rezultat

## Zakljucane odluke

Na osnovu korisnickog odobrenja, sledece odluke su zakljucane.

### 1. Globalni shell

Svi tabovi koriste isti osnovni raspored:

1. `header`
2. `sistemski sloj`
3. `sadrzaj konkretne strane`

`header` ostaje glavno mesto navigacije i ne sme se ponavljati kroz dodatne velike navigacione module u telu stranica.

### 2. Sistemski sloj postoji na svakom ekranu

Na svakom ekranu korisnik mora da vidi:

- aktivni model
- zive resurse

Ali taj sloj ne sme da bude glomazan pri skrolovanju.

Zato je zakljucan hibridni model:

- na vrhu strane prikazuje se `puna` verzija sistemskog sloja
- pri skrolovanju se taj sloj sabija u `kompaktnu sticky status traku`

Ovo daje dve koristi:

- na vrhu stranice korisnik dobija pun kontekst
- dublje na strani korisnik ne gubi signal, ali ekran ostaje slobodan za sadrzaj

### 3. `Pocetna` vise ne duplira glavne tabove

Na `Pocetnoj` vise ne postoje veliki moduli koji ponavljaju:

- Runtime
- Lokalni model
- OpenCode

Razlog:

- te komande vec postoje u `header`-u
- njihovo dodatno ponavljanje u telu strane samo trosi prostor i slabi hijerarhiju

`Pocetna` prestaje da bude drugi navigacioni meni.

### 4. `Napredno` ne nestaje

`Napredno` ostaje posebno dugme u `header`-u i posebno odrediste.

Kompaktne preprecice na `Pocetnoj` ne zamenjuju `Napredno`.

Pravilo:

- `Pocetna` daje brze ulaze
- `Napredno` ostaje puni hub dubljih sekcija

## Struktura `Pocetne`

`Pocetna` dobija cist raspored:

1. `Header`
2. `Stanje sada`
3. `Zivi resursi`
4. `Sazeta telemetrija`

Nema dodatnih velikih hero modula ni dupliranih komandnih blokova.

### `Stanje sada`

`Stanje sada` ide odmah ispod `header`-a kao jedan horizontalni red od 5 klikabilnih kartica.

Redosled je zakljucan:

1. `Health`
2. `Runtime`
3. `Model`
4. `Context`
5. `OpenCode`

Svaka kartica je klikabilna i vodi direktno na relevantan ekran ili sekciju:

- `Health` -> `Runtime` health / dijagnostika
- `Runtime` -> `Runtime`
- `Model` -> `Modeli`
- `Context` -> `Podesavanja`
- `OpenCode` -> `OpenCode`

Svrha ovih kartica nije dubinsko objasnjavanje, nego odgovor na pitanje:

- "mogu li odmah da radim"

Predlozeni sadrzaj po kartici:

- `Health`
  - glavna vrednost: `OK` / `Offline` / `Upozorenje`
  - mali red: kratka poruka o health endpoint-u
- `Runtime`
  - glavna vrednost: `TurboQuant` ili `llama.cpp`
  - mali red: `aktivan engine`
- `Model`
  - glavna vrednost: skraceno ime aktivnog modela
  - mali red: profil ili spremnost
- `Context`
  - glavna vrednost: npr. `128K`
  - mali red: `config = live` ili upozorenje o neuskladjenosti
- `OpenCode`
  - glavna vrednost: `Spreman` / `Otvoren` / `Ceka`
  - mali red: stanje CLI veze

### `Zivi resursi`

Ispod `Stanja sada` ide kompaktni horizontalni strip preko cele sirine.

Na desktopu ima 8 uzih kartica u jednom redu:

1. `CPU`
2. `RAM`
3. `VRAM`
4. `GPU`
5. `Rezim`
6. `Offload`
7. `Context live`
8. `Model proces`

Prve 4 kartice daju hardversku sliku, druge 4 runtime / fit sliku.

Svaka kartica ima:

- naslov
- glavnu vrednost
- eventualno tanku progress liniju

Kartice mogu da budu klikabilne ako vec postoji smislen detalj ili odrediste, ali primarna uloga im je gust signal, ne duboka navigacija.

### `Sazeta telemetrija`

Ispod `Zivih resursa` ide sazet telemetrijski blok.

Na `Pocetnoj` telemetrija ne sme da postane laboratorija sa velikim grafikonima.

Zakljucano je da `Pocetna` ima samo kratku verziju sa 4 kartice:

1. `tok/s sada`
2. `input / output odnos`
3. `aktivnost modela`
4. `poslednji signal`

Puni grafikoni, istorija i duboke metrike ostaju u posebnom `Telemetrija` tabu.

## Glavni tabovi sa jacim top rack-om

Zakljucano je da tri glavna radna taba smeju da budu "bogatija" od ostalih:

- `Runtime`
- `Modeli`
- `OpenCode`

Ali to ne sme da vrati stare prazne velike module.

Top rack na ova tri taba mora biti:

- kompaktniji od starog hero pristupa
- funkcionalan
- bez placeholder readout kartica

### Zajednicka anatomija top rack-a

Sva tri top rack-a dele istu anatomiju:

- leva kolona: `Signal`
- srednja kolona: `Komande`
- desna kolona: `Duboko`

#### Leva kolona - `Signal`

Ovde stoje 2 do 3 najvaznija lokalna status signala za dati tab.

Primer:

- na `Runtime`: health, aktivni engine, GPU fit
- na `Modeli`: aktivni model, spremnost, fit
- na `OpenCode`: sesija, workspace, aktivni model

#### Srednja kolona - `Komande`

Ovde stoje glavne transport / radne komande tog taba.

Primer:

- `Runtime`: otvori / restartuj / zaustavi
- `Modeli`: brzi izbor / dodaj lokalni GGUF / otvori katalog
- `OpenCode`: otvori / izolovan workspace / poslednji rezultat

Ovo je glavni akcioni blok stranice.

#### Desna kolona - `Duboko`

Ovde stoje dublji ulazi za napredne slucajeve.

Primer:

- `Runtime`: health detalj, dijagnostika, logovi
- `Modeli`: lokalni katalog, kompatibilnost, download status
- `OpenCode`: managed config, runtime veza, napredni alati

Ova kolona nije za glavne komande, nego za precizne skokove bez pretrage po stranici.

## Ostali tabovi dobijaju strozi raspored

Za sve ostale tabove ne koristi se "veliki modul" logika.

Zakljucan obrazac je:

- `levo`: glavni sadrzaj
- `desno`: uza akciona kolona

Desna kolona sme da sadrzi samo:

- stvarne akcije
- kratki status
- eventualno jednu kratku napomenu

Ne sme da postane nova placeholder scenografija.

## Prioritet implementacije za novi raspored

Prva tri taba koja dobijaju ovaj novi strogi raspored su:

1. `Napredno`
2. `Benchmark`
3. `Kompatibilnost`

Razlog:

- `Napredno` trenutno najvise pati od prevelikih sekcija i nejasnog toka
- `Benchmark` ima puno sadrzaja i lako "pojede" komande
- `Kompatibilnost` mesa objasnjenja, brojke i primenu i zato joj treba jasna desna akciona kolona

## Sta se namerno izbacuje

Ovaj dizajn eksplicitno izbacuje sledece obrasce:

- dupliranje header komandi u telu stranice
- veliki moduli koji imaju malo stvarnih akcija
- mrtve info kartice koje ne vode nigde
- "hero" uvode na svakom tabu
- placeholder readout kartice koje samo popunjavaju prostor

## Vizuelni i UX principi

### 1. Svaka velika povrsina mora da opravda svoju visinu

Ako neka sekcija zauzima veliki prostor, ona mora da nosi:

- stvaran signal
- ili stvarnu akciju
- ili jasan rezultat

Ako to ne radi, treba je smanjiti ili ukloniti.

### 2. Klik mora odmah da ima prostornu logiku

Korisnik ne sme da klikne, pa da se pita:

- gde se vidi rezultat
- da li se ista promenilo
- koji je sledeci korak

### 3. Hi-fi jezik ostaje, ali bez scenografije

Hi-fi `deck / rack / transport / signal` jezik ostaje vizuelna osnova proizvoda.

Ali:

- ne koristi se radi ukrasa
- ne sme da proizvodi lazni osecaj dubine bez stvarnog sadrzaja

## Responsivno ponasanje

Na desktopu:

- `Stanje sada` ostaje u jednom horizontalnom redu
- `Zivi resursi` ostaju gust strip
- top rack glavnih tabova ostaje 3-kolonski

Na tablet / manjem desktopu:

- top rack moze da se prelomi u 2 reda
- sistemski sloj se i dalje sabija pri skrolu

Na mobilnom:

- `Stanje sada` ide u 1 ili 2 reda
- `Zivi resursi` se prelamaju u vise redova
- sticky sistemski sloj ostaje, ali u jos kompaktnijoj varijanti

## Prihvatni kriterijumi

Novi shell je prihvatljiv ako:

1. korisnik vise ne vidi iste glavne ulaze i u `header`-u i u telu strane  
2. `Pocetna` odmah govori da li je sistem spreman za rad  
3. tokom skrola korisnik ne gubi signal o modelu i resursima  
4. `Runtime`, `Modeli` i `OpenCode` imaju jasan lokalni cockpit bez velikih praznih modula  
5. `Napredno`, `Benchmark` i `Kompatibilnost` postanu citljiviji kroz `levo sadrzaj + desno akcije` raspored  
6. placeholder kartice i mrtvi readout blokovi nestanu iz glavnih tokova

## Veza sa starijim dokumentima

Ovaj dokument ne brise stare hi-fi odluke, nego ih racionalizuje.

Posebno menja ili suzava ideje iz ranijih dizajn faza koje su:

- `Pocetnu` tretirale kao mesto za vise velikih modula
- sekundarne tokove crtale kao velike uvodne rack sekcije
- previse oslanjale layout na narativne kartice umesto na stvarni rad

Ovaj dokument postaje nova referenca za:

- shell hijerarhiju
- `Pocetna`
- sistemski sloj
- top rack za `Runtime`, `Modeli`, `OpenCode`
- prioritetni redizajn `Napredno`, `Benchmark`, `Kompatibilnost`

## Sledeci korak

Posle korisnickog pregleda ovog dokumenta treba napraviti poseban implementacioni plan koji:

- razbija rad po tabovima i komponentama
- jasno odvaja shell refaktor od pojedinacnih tab preraspodela
- posebno planira:
  - sistemski sloj
  - novu `Pocetnu`
  - top rack za `Runtime`, `Modeli`, `OpenCode`
  - novi raspored za `Napredno`, `Benchmark`, `Kompatibilnost`
