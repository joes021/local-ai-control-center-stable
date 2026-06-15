# RuntimePilot Final UX Polish Design

**Datum:** 2026-06-15  
**Status:** korisnik je unapred odobrio implementaciju svih predloženih faza  
**Cilj:** zatvoriti poslednji veliki prolaz kroz RuntimePilot tako da glavni tokovi budu jasni, OpenCode i Tuning Lab dosledni hi-fi jeziku, srpski tekst čist i mobilni raspored upotrebljiv.

## Sažetak

Ovaj dokument ne uvodi novi vizuelni pravac. Umesto toga, zaključava završni polish prolaz nad postojećim RuntimePilot shell-om koji je već odobren i objavljen kroz `v0.4.94`.

Fokus je na pet preostalih oblasti:

1. `action clarity` kroz glavne ekrane i akcije
2. završni `OpenCode` UX prolaz
3. završni `Tuning Lab` UX prolaz
4. sistematsko čišćenje `encoding` i srpskog teksta
5. `responsive/mobile` poravnanje bez rušenja desktop hijerarhije

## Problem

Portal je sada funkcionalan i vizuelno daleko bliže željenom hi-fi smeru, ali još postoje mesta gde korisnik mora da razmišlja više nego što treba:

- posle klika nije svuda potpuno jasno gde se vidi rezultat
- OpenCode ima još pregustih delova, naročito u naprednim kontrolama
- Tuning Lab ima bogatu funkcionalnost, ali previše dugačkih vertikalnih zona i slabiju hijerarhiju u statusima
- kroz više strana i poruka povremeno probija pogrešan encoding (`Å`, `Ä`, `Â`)
- mobilni i uži desktop rasporedi još nisu dovoljno pažljivo zategnuti

## Dizajn cilj

Korisnik mora na svakom ključnom ekranu odmah da razume:

1. šta je trenutno stanje
2. šta je glavna sledeća akcija
3. gde će se videti ishod
4. šta radi ako rezultat nije dobar

Drugim rečima, završni polish mora da pretvori postojeći UI iz „dovoljno dobrog“ u „sam objašnjava tok rada“.

## Zaključane odluke

### 1. Početna hijerarhija ostaje referenca

Ne vraćamo stare duplikate modula niti uvodimo novi hero raspored. Postojeći shell ostaje baza:

- header
- aktivni model + živi resursi
- status kartice
- jedan glavni radni blok
- napredno ispod

### 2. Action clarity je važniji od dodatnih ukrasa

Ako postoji izbor između „lepšeg dekora“ i „jasnijeg toka posle klika“, prednost ide jasnoći toka.

To posebno važi za:

- OpenCode launch akcije
- aktivaciju modela i lokalni GGUF import
- Tuning Lab queue i istoriju
- compatibility apply tok
- browser katalog akcije

### 3. OpenCode i Tuning Lab ostaju najgušći ekrani, ali ne smeju da deluju zbrkano

Nećemo ih osiromašiti. Umesto toga:

- akcije se grupišu strože
- rezultat i status dobijaju jači prioritet
- napredne kontrole ostaju dostupne, ali vizuelno mirnije

### 4. Encoding cleanup je sistemski posao

Pogrešni prikazi srpskih znakova ne smeju se rešavati pojedinačno samo na mestima koja upadnu u oči. Treba pregledati:

- frontend stringove
- backend poruke koje izlaze u UI
- test očekivanja
- bundle regresije

### 5. Responsive prolaz mora da čuva desktop logiku

Mobilni prikaz ne sme da vrati staro stanje „sve otvoreno odjednom“. Na užim širinama:

- glavni tok ostaje prvi
- sekundarno se prirodno spušta ispod
- guste kontrole se prelamaju, ali ne gube smisao

## Dizajn po fazama

### Faza 1: Action clarity audit

Za svaku glavnu akciju proverava se:

- da li je CTA jasno imenovan
- da li postoji mesto gde se vidi ishod
- da li je to mesto blizu akcije
- da li postoji jasan sledeći korak u slučaju uspeha ili neuspeha

Ovo posebno pokriva:

- Runtime
- Modeli
- OpenCode
- Browser
- Compatibility
- Tuning Lab

### Faza 2: OpenCode završni prolaz

OpenCode mora još jasnije da prati obrazac:

`signal -> akcija -> rezultat -> napredno`

Napredne kontrole treba dodatno poravnati tako da:

- dropdown i input polja deluju kao jedan kontrolni rack
- rezultat ostane prva stvar koju korisnik čita posle klika
- pomoćni alati ne deluju kao drugi nezavisni ekran

### Faza 3: Tuning Lab završni prolaz

Tuning Lab ostaje široka radna konzola, ali uz tri jasna pravila:

- glavni slotovi i run signal ostaju prvi plan
- istorija i detalji se ne pretvaraju u predugačke nečitljive stubove
- gustoća informacija ne sme da razbije hi-fi osećaj

### Faza 4: Encoding cleanup

Cilj je da svuda budu ispravni:

- `č`
- `ć`
- `š`
- `ž`
- `đ`

Isto važi za mešanje engleskog i srpskog: gde je UI već preveden, ostajemo dosledni srpskom jeziku osim kada je tehnički termin stvarno smisleniji u originalu.

### Faza 5: Responsive i mobile polish

Glavni fokus su:

- header i status kartice
- OpenCode top rail
- Tuning Lab slotovi i fine kontrole
- browser detalj panel
- support strane sa više kontrola i filtera

## Prihvatni kriterijumi

Rad je uspešan ako:

1. korisnik na glavnim ekranima odmah vidi gde čita ishod posle klika
2. OpenCode više nema utisak naslaganih nezavisnih zona
3. Tuning Lab je čitljiviji bez gubitka funkcionalnosti
4. loš encoding više ne izlazi u UI
5. ključne strane ostaju upotrebljive i na užim širinama

## Namerno van opsega

Ovaj dokument namerno ne uključuje:

- novi vizuelni identitet
- novi navigacioni sistem
- backend feature dodatke koji nisu nužni za action clarity
- code signing ili dublje installer trust teme

## Sledeći korak

Na osnovu ovog dokumenta pravi se kratak implementacioni plan za:

1. audit i testove
2. OpenCode/Tuning Lab izmene
3. encoding cleanup
4. responsive prilagođavanja
5. završnu proveru i bundle refresh
