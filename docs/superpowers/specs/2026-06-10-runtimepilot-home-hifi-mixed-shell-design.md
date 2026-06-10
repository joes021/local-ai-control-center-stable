# RuntimePilot Home Hi-Fi Mixed Shell Design

**Datum:** 2026-06-10  
**Status:** odobren dizajn, spreman za planiranje implementacije  
**Cilj:** zakljucati novi pocetni ekran RuntimePilot-a kao `mesano` resenje sa vodjenim tokom gore i tri velika hi-fi modula ispod, tako da korisnik odmah razume osnovni radni put `Runtime -> Lokalni model -> OpenCode`, dok napredni delovi ostaju dostupni bez vizuelnog haosa.

## Problem

Dosadasnja pocetna strana i glavni shell nose previse podjednako glasnih elemenata:

- previse kartica izgleda jednako vazno
- aktivni model, zivi resursi i pomocni paneli lako pojedu veliki deo ekrana
- korisnik cesto ne zna koji je pravi prvi klik
- posle klika nije dovoljno jasno gde treba gledati rezultat
- neki delovi deluju kao pregled svega, a ne kao komandni centar
- vizuelni jezik je bio mesavina standardnog web UI-a i parcijalnog hi-fi smera

To posebno pogadja korisnika koji nije vest sa AI alatima i kome treba jasan put, ne katalog svih mogucnosti odjednom.

## Zakljucane odluke

Na osnovu korisnickog odobrenja, sledece odluke su zakljucane:

- Home koristi `mesano` resenje:
  - gore je vodjeni tok
  - ispod su tri velika modula
- zadrzava se pet glavnih komandi u header-u:
  - Pocetna
  - Runtime
  - Modeli
  - OpenCode
  - Napredno
- header ostaje u hi-fi komandnom jeziku i zadrzava:
  - originalni RuntimePilot wordmark
  - broj verzije
- tri velika modula predstavljaju tri glavna toka proizvoda:
  - Runtime
  - Lokalni model
  - OpenCode
- desne komandne kolone u modulima moraju vizuelno pripadati istoj porodici kao gornja navigacija
- Home mora da ima i jedan napredni ekran u istom jeziku, da se proveri kako se novi shell ponasa i van samog prvog pogleda

## Osnovni UX cilj

Pocetna strana mora da radi kao komandna povrsina, ne kao zbir svih funkcija.

Korisnik mora odmah da razume:

1. da li runtime radi
2. koji model je stvarno aktivan
3. kako da otvori OpenCode i krene da radi

Posle svakog glavnog klika, korisnik mora da zna gde ce se videti rezultat.

## Struktura Home ekrana

### 1. Gornji komandni sloj

Na vrhu stoji kompaktan shell:

- brend blok sa originalnim logo wordmark-om
- oznaka verzije
- pet velikih komandnih dugmadi

Ta dugmad vise nisu obicne tab kartice, nego hi-fi komande:

- numerisani indeks
- glavni naziv
- kratak podnaslov
- signal LED / marker desno

Poenta je da navigacija deluje kao komandna tabla, a ne kao genericki sajt meni.

### 2. Vodjeni tok gore

Odmah ispod header-a ide vodjeni ulaz za pocetnike.

Njegova uloga nije da zameni ostatak proizvoda, nego da skrati razmisljanje:

- prvo proveri Runtime
- zatim potvrdi Lokalni model
- onda predji u OpenCode

Ovde copy mora biti kratak i operativan. To nije mesto za duboka objasnjenja, vec za usmeravanje.

### 3. Tri velika modula ispod

Ispod vodjenog toka stoje tri velika siroka modula, jedan ispod drugog:

- Runtime
- Lokalni model
- OpenCode

Vertikalni redosled je odobren jer deluje smirenije i manje natrpano nego raspored u tri kolone na samoj pocetnoj.

## Anatomija velikog modula

Svaki veliki modul koristi isti hi-fi skelet sa tri zone:

- levi signalni stub
- srednji glavni display
- desni komandni stub

Ispod toga ide donja statusna traka sa cetiri sazetka.

### Levi signalni stub

Levi stub vise ne sme da deluje kao mala obicna kartica.

On postaje signal panel:

- LED/status karakter
- jaka vertikalna signalna traka
- kratki label + glavna vrednost + kratko tumacenje

Za svaku od tri stavke boja i signal treba da pomognu citanju:

- zeleno kada je potvrdeno / aktivno
- zlatno za konfiguraciju / context / fokus
- hladniji ton za fit / signal / vezu kada ima smisla

Poenta nije dekoracija nego brza orijentacija.

### Srednji glavni display

Srednji blok je glavni ekran modula.

On sadrzi:

- jednu veliku recenicu koja objasnjava svrhu modula
- kratak pomocni tekst koji govori gde se vidi rezultat
- tri manja readout bloka ispod

Taj srednji deo mora ostati najvazniji po citljivosti i sirini.

### Desni komandni stub

Desni stub je glavni akcioni blok i mora da bude poravnat sa srednjim delom:

- gornja ivica desnog dela u istoj ravni kao gornja ivica srednjeg dela
- donja ivica desnog dela u istoj ravni kao donja ivica srednjeg dela
- cetiri komande ravnomerno razvucene od vrha do dna

Vizuelni jezik komandi:

- isti DNK kao gornja navigacija
- numericki / kodni levi segment
- tekstualni srednji segment
- signalni desni segment
- kockastiji, tvrdji, metalni `faceplate` izgled

Te komande moraju delovati kao komandni tasteri na audio opremi, ne kao obla web dugmad.

### Donja statusna traka

Na dnu svakog modula idu cetiri sazetka:

- sta se vidi posle klika
- veza / pristup / signal
- trenutno stanje
- sledeci logican korak

Ova traka sprecava problem gde korisnik klikne, a onda mora da nagadja sta se zapravo promenilo.

## Sadrzaj po modulu

### Runtime modul

Runtime modul mora da govori:

- koji runtime je ziv
- da li je health potvrden
- da li je context aktivan
- da li je GPU fit razumljiv

Glavne komande tipa:

- otvori runtime
- restartuj runtime
- zaustavi engine
- napredna dijagnostika

Posle klika korisnik mora odmah da zna da gleda:

- health
- pristup
- runtime signal

### Lokalni model modul

Model modul mora da odgovori na pitanje:

- koji model je stvarno aktivan sada

Ne sme ponovo da sklizne u dugu biblioteku kao prvi pogled.

Glavne komande tipa:

- otvori modele
- brza promena modela
- proveri kompatibilnost
- dodaj lokalni GGUF

Najvazniji rezultat posle klika:

- aktivni model se menja jasno i bez sumnje
- fit i spremnost se vide bez ulaska u duboku kolonu

### OpenCode modul

OpenCode modul mora najjasnije da govori sta se desava posle klika.

Glavne komande tipa:

- otvori OpenCode
- CLI sesija sada
- izolovani workspace
- otvori rezultat

Najvazniji rezultat posle klika:

- da li se OpenCode stvarno otvorio
- u kom rezimu je otvoren
- gde korisnik vidi izlaz

## Vizuelni jezik

Home koristi `hi-fi control deck` smer sa `champagne / tamni metal` finisom.

Zakljucane osobine:

- vise plocasto nego mekano
- manje generickih web kartica
- ostriji uglovi na komandama
- metalni `faceplate` utisak
- LED i signal markeri kao informativni elementi
- hijerarhija preko rasporeda i materijala, ne preko gomile boja

Posebno je zakljucano da:

- desne velike komande i gornja navigacija moraju biti stilski iz iste porodice
- pomocne transport komande takodje ulaze u isti jezik
- levi signalni stubovi dobijaju pravi status-panel identitet

## Action clarity pravila

Ovo je kljucni deo dizajna.

Svaka glavna akcija mora da prati isto pravilo:

- korisnik vidi gde da klikne
- korisnik vidi gde da gleda rezultat
- korisnik vidi sta je sledeci korak

Home zato nije samo landing, nego operativna tabla.

Posebno za tri glavna modula:

- Runtime rezultat se cita kroz health i signal
- Model rezultat se cita kroz aktivni model i fit
- OpenCode rezultat se cita kroz status otvaranja i radni izlaz

## Napredni ekran

Uz Home smer zakljucano je i da postoji makar jedan napredni ekran u istom vizuelnom jeziku.

To sluzi da novi shell ne ostane samo lep pocetni sloj, vec da se proveri:

- kako isti jezik radi dublje u sistemu
- da li se napredne kontrole mogu prelomiti bez vracanja na stari web izgled
- da li glavna i napredna iskustva deluju kao jedan proizvod

Ovaj dokument ne zakljucava jos sve detalje naprednih strana, ali zakljucava da njihov buduci redizajn mora slediti isti komandni jezik.

## Responsive smer

Desktop je primarni fokus za ovaj Home, ali raspored mora ostati upotrebljiv i kad se suzi:

- header komande se sabijaju pre nego sto pucaju
- veliki moduli se na uzim sirinama lome u jedan tok
- poruka i akcija ostaju citljive bez horizontalnog haosa

Mobilni i tablet dizajn ce se raditi kao poseban sledeci sloj, ali Home shell ne sme biti slepa desktop kompozicija.

## Sta Home namerno ne radi

Da bi ostao jasan, Home namerno ne pokusava da:

- prikaze celu biblioteku modela
- prikaze sve tuning parametre
- bude logs, benchmark i help stranica u malom
- zameni detaljne sekcije proizvoda

Njegov posao je:

- jasan ulaz
- jasan status
- jasan sledeci klik

## Referentni prototip

Tokom brainstorminga odobren je klikabilni vizuelni prototip za ovaj smer.

Referenca:

- lokalni companion HTML: `.superpowers/brainstorm/home-mixed-20260610-192934/interactive-prototype-v1.html`
- lokalni preview URL tokom rada: `http://127.0.0.1:62688`

Ovaj prototip je referenca za dizajn smer, ne produkcioni UI.

## Kriterijumi uspeha

Ovaj dizajn je uspesan kada:

- korisnik na pocetnoj odmah vidi tri glavna toka
- Home vise ne deluje kao pretrpan pregled svega
- glavne komande deluju kao deo jednog hi-fi sistema
- rezultat posle klika je jasno vezan za mesto na kome se cita
- napredni ekran moze da nasledi isti jezik bez raspada
- pocetna strana izgleda smirenije, skuplje i namenski projektovano, a ne kao genericki dashboard
