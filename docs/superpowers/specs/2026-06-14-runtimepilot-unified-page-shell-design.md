# RuntimePilot Unified Page Shell Design

**Datum:** 2026-06-14  
**Status:** odobren dizajn iz razgovora, ceka korisnicki pregled dokumenta  
**Cilj:** ujednaciti sve RuntimePilot strane po logici pocetne strane tako da korisnik na svakom ekranu odmah vidi sistemsko stanje, glavni tok rada te strane i napredne opcije tek kada mu stvarno zatrebaju.

## Problem

RuntimePilot trenutno ima dobru pocetnu stranu kao smer, ali ostatak portala nije dovoljno dosledan tom jeziku.

Glavni problemi su:

- razlicite strane imaju razlicitu hijerarhiju i drugaciji raspored
- korisnik cesto vidi vise "podjednako vaznih" velikih blokova i ne zna gde je centar paznje
- OpenCode strana je posebno zbrkana jer mesa signal, pokretanje, launcher detalje, presetove, bezbednost i dijagnostiku u previse otvorenih povrsina
- iste informacije ili slicni uvodi se ponavljaju na vise mesta
- sekundarne i retke opcije previse rano ulaze u prvi ekran i guse glavni tok

To je lose posebno za korisnika koji nije vest sa AI alatima, jer proizvod ne govori jasno:

1. sta je trenutno stanje sistema  
2. sta je glavna radnja ove strane  
3. gde treba kliknuti  
4. gde ce se videti rezultat posle klika

## Dizajn cilj

Ceo portal treba da koristi jedan isti shell sistem:

1. `header`
2. `aktivni model + zivi resursi`
3. `pet zakljucanih status kartica`
4. `jedan glavni otvoreni radni blok`
5. `napredno ispod kroz skupljive sekcije`

Ovaj dokument ne uvodi novi vizuelni identitet. Umesto toga, prosiruje jezik pocetne strane na ostatak portala kako bi ceo proizvod delovao kao jedna komandna povrsina.

## Zakljucane odluke

Na osnovu korisnickog odobrenja sledece odluke su zakljucane.

### 1. Sve strane dele isti globalni shell

Svaka strana koristi isti raspored:

1. `Header`
2. `Aktivni model` i `Zivi resursi`
3. `Health / Runtime / Model / Context / OpenCode`
4. glavni sadrzaj strane
5. napredne sekcije

To postaje strogo pravilo za:

- `Runtime`
- `Modeli`
- `OpenCode`
- `Napredno`
- `Podesavanja`
- `Browser`
- `Znanje`
- `Kompatibilnost`
- `Tuning Lab`
- ostale pomocne strane

### 2. `Aktivni model` i `Zivi resursi` ostaju globalni sloj

Korisnik je odobrio da se na svakom ekranu vide:

- `Aktivni model`
- `Zivi resursi`

Njihova svrha nije da postanu nova navigacija, nego da daju stalan signal o tome:

- koji model je stvarno aktivan
- da li je runtime ziv
- kakvo je trenutno stanje CPU / RAM / VRAM / GPU i fit signala

Ovaj sloj ostaje zajednicki i ne sme da se stilisticki raspadne od strane do strane.

### 3. Pet status kartica su zakljucan drugi red shell-a

Ispod globalnog signalnog sloja uvek ide isti red od 5 kartica:

1. `Health`
2. `Runtime`
3. `Model`
4. `Context`
5. `OpenCode`

Te kartice:

- ostaju na svakoj strani
- zadrzavaju isti raspored i istu vizuelnu tezinu
- sluze kao brzi skokovi ka glavnim oblastima
- ne smeju da budu zamenjene novim lokalnim navigacijama po strani

Poenta je da korisnik na svakoj strani dobije isti brzi komandni pojas bez ucenja novog rasporeda.

### 4. Svaka strana ima samo jedan glavni otvoreni radni blok

Najvaznija odluka ovog dizajna je:

- na prvom ekranu sme da postoji samo jedan glavni otvoreni blok koji nosi primarni tok te strane

To znaci:

- nema vise velikih otvorenih sekcija koje se takmice za paznju
- nema vise tri ili cetiri "hero" modula na istom ekranu
- nema vise placeholder readout blokova koji deluju vazno, a ne rade nista

Svaka strana mora odmah da odgovori na pitanje:

- "Sta je glavni posao ovde?"

### 5. Napredne i redje opcije idu ispod kroz `details`

Sve sekundarne, tehnicke, retke ili dijagnosticke stvari vise ne stoje otvorene na vrhu strane.

One idu ispod kao:

- `details`
- skupljive sekcije
- jasno imenovani napredni blokovi

To posebno vazi za:

- launcher preview i shell komande
- duboke runtime dijagnostike
- napredne preset / safety / autonomy kontrole
- servisne i debugging povrsine
- dublje metapodatke i sporedne liste

## Struktura glavnih strana

### OpenCode

OpenCode je zakljucan kao najprioritetnija problematicka strana.

Njegov glavni otvoreni blok mora biti strogo podeljen u tri nivoa:

1. `Signal`
2. `Akcije`
3. `Rezultat`

#### OpenCode signal

Bez skrola korisnik mora da vidi:

- da li je OpenCode spreman
- da li vidi runtime
- koji model koristi
- koji workspace je aktivan

To je prvi red glavnog bloka.

#### OpenCode akcije

Drugi red glavnog bloka sadrzi samo tri glavne komande:

- `Otvori OpenCode`
- `Otvori izolovan workspace`
- `Popravi / instaliraj OpenCode`

To su jedine akcije koje moraju biti otvorene i jasno naglasene u prvom ekranu.

#### OpenCode rezultat

Treci red glavnog bloka mora odmah posle klika da prikaze:

- da li je otvaranje uspelo
- koja sesija ili PID je aktivan
- zasto nije uspelo ako nije uspelo
- sta je sledeci korak

OpenCode vise ne sme da lici na komandni centar za deset podsistema. Mora da radi po logici:

`proveri spremnost -> klikni akciju -> vidi rezultat`

#### OpenCode napredno

Sve ostalo se spusta ispod u napredne sekcije:

- launcher preview
- PowerShell / CLI ekvivalenti
- managed config detalji
- step presetovi
- step editor
- bezbednosni rezim
- autonomija
- lista instanci
- servisne / dijagnosticke povrsine

### Runtime

Runtime strana dobija jedan glavni otvoreni blok ciji fokus je:

- pokretanje runtime-a
- restart
- stop
- health
- aktivni runtime signal

Korisnik mora odmah da vidi:

- koji engine je aktivan
- da li je health zelen
- gde se cita ishod posle start / restart / stop akcije

Napredne stvari se spustaju ispod:

- rucne komande
- napredna dijagnostika
- offload detalji
- logovi i servisni helperi

### Modeli

Modeli strana dobija jedan glavni otvoreni blok sa fokusom na:

- izbor aktivnog modela
- aktivaciju modela
- brzu promenu modela
- eventualno dodavanje lokalnog GGUF-a kao deo istog toka

Glavni tok mora da bude:

`vidi aktivni model -> promeni model -> potvrdi rezultat`

Napredne ili sporedne stvari idu ispod:

- browser katalozi
- dodatni metapodaci
- dublji import tokovi
- kompatibilnost detalji
- pomocni browser prikazi

### Napredno

Napredno ne sme da bude nova glavna kontrolna tabla niti duplikat glavnih tabova.

Njegov glavni otvoreni blok treba da bude cist sekundarni hub sa stvarnim grupama alata:

- `Analiza i tuning`
- `Znanje i izvori`
- `Fokus i memorija`
- `Servis i oporavak`

Unutar tog bloka svaka grupa mora da vodi ka stvarnim ekranima i alatima, a ne ka placeholder karticama ili tekstovima koji ne rade nista.

Napredno mora da izgleda kao:

- mapa sekundarnih tokova
- ne kao skup praznih velikih modula

## Pravilo za ostale strane

Sve ostale strane dobijaju isti princip:

- jedan glavni otvoreni blok za primarnu radnju
- napredno i pomocno ispod

To vazi i za:

- `Podesavanja`
- `Browser`
- `Znanje`
- `Kompatibilnost`
- `Tuning Lab`
- `Benchmark`
- `Help`
- `Project Memory`
- ostale pomocne tabove

Ovim dokumentom nije jos zakljucan detaljan unutrasnji layout svake od tih strana, ali jeste zakljucana hijerarhija:

- prvo glavni rad
- potom napredno

## UX pravila

### 1. Strana mora da ima jasan centar paznje

Korisnik ne sme da vidi vise jednakih kandidata za "glavni sadrzaj".

Ako dva ili tri velika bloka izgledaju podjednako vazno, hijerarhija nije dobra.

### 2. Klik mora da ima jasan rezultat

Posle klika korisnik ne sme da se pita:

- da li se ista desilo
- gde se to vidi
- sta je sledeci korak

Svaka glavna strana mora da ima vidljivo mesto gde se rezultat cita.

### 3. Sekundarno ne sme da gusi primarno

Napredne i retke opcije ne smeju da stoje iznad glavnog rada.

One moraju da budu:

- dostupne
- jasno imenovane
- ali van glavne radne putanje

### 4. Pocetna ostaje referentni jezik

Vizuelni identitet koji je korisnik odobrio na pocetnoj strani ostaje baza.

Ovaj dokument ne uvodi novi stil, nego prosiruje postojeci hi-fi shell jezik:

- isti materijal
- ista hijerarhija
- ista logika komandnih povrsina

## Responsivno ponasanje

Na desktopu:

- `Aktivni model` i `Zivi resursi` ostaju vidljivi kao globalni sloj
- 5 status kartica ostaju u jednom horizontalnom redu ili kontrolisanom prelomu
- glavni otvoreni blok ostaje prvi fokus svake strane

Na uzim sirinama:

- status kartice mogu u dva reda
- glavni blok se prelama, ali i dalje ostaje jedan glavni tok
- napredne sekcije ostaju ispod i ne izlaze ispred glavne akcije

Na mobilnom:

- isti redosled ostaje
- ne sme se vratiti stara logika "sve otvoreno odjednom"

## Prihvatni kriterijumi

Novi page shell je prihvatljiv ako:

1. sve strane koriste isti redosled shell elemenata  
2. `Aktivni model` i `Zivi resursi` ostaju globalno prisutni  
3. 5 status kartica ostaju zajednicki drugi red shell-a  
4. svaka strana ima samo jedan glavni otvoreni radni blok  
5. OpenCode postaje citljiv po pravilu `signal -> akcije -> rezultat`  
6. Runtime i Modeli imaju po jedan jasan primarni tok  
7. Napredno prestaje da deluje kao placeholder scenografija  
8. sekundarne i retke opcije se spustaju ispod u skupljive sekcije  
9. korisnik na svakoj strani odmah zna gde klikce i gde cita rezultat

## Sta se namerno ne radi u ovom dokumentu

Ovaj dokument namerno ne zakljucava:

- detaljan mikro-layout svake sporedne strane
- nove boje, nove fontove ili novi brend jezik
- implementacione detalje komponenti i fajlova
- finalni mobilni polish

To ce biti predmet posebnog implementacionog plana.

## Redosled implementacije

Na osnovu korisnickog odobrenja zakljucan je sledeci redosled:

1. standardizacija shell-a na svim stranama
2. OpenCode kao prvi i najvazniji redizajn
3. Runtime i Modeli
4. Napredno kao sekundarni hub
5. ostale strane po istom sistemu

## Veza sa prethodnim dokumentima

Ovaj dokument naslanja se na prethodne RuntimePilot hi-fi i shell dokumente, ali uvodi novu strogu hijerarhiju:

- pocetna strana postaje referentni shell model
- ostale strane se vise ne dizajniraju kao nezavisni layout eksperimenti
- OpenCode vise ne ostaje izuzetak sa preopterecenim vrhom

Ovaj dokument postaje nova referenca za:

- ujednacenje svih strana
- hijerarhiju shell-a
- prepakivanje OpenCode strane
- primenu principa `jedan glavni blok + napredno ispod`

## Sledeci korak

Posle korisnickog pregleda ovog dokumenta treba napraviti poseban implementacioni plan koji:

- razbija rad po shell slojevima i po stranicama
- posebno planira OpenCode kao najrizicniji redizajn
- odvaja shell standardizaciju od page-specific preraspodela
- uvodi proveru da li svaka strana stvarno ima jasan glavni tok i jasan rezultat posle klika
