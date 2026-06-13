# RuntimePilot Phase 7 Advanced Decks Design

## Cilj

Posle `v0.4.92` release sync-a sledeci veliki UX blok treba da prosiri hi-fi jezik sa uspesne pocetne strane na preostale duboke i "napredne" tokove, bez razbijanja postojeceg glavnog puta:

1. runtime
2. lokalni model
3. OpenCode rad

Fokus ove faze je da korisnik i na sekundarnim ekranima odmah vidi:

- gde se menja vrednost
- gde se ta promena snima ili primenjuje
- gde se posle klika vidi rezultat

Uz to, isti jezik mora da radi i na uzem laptop prikazu i na telefonu, bez vertikalnih zidova teksta i bez "gde je sad nestalo dugme" trenutaka.

## Problem

Pocetna strana je danas najbliza zeljenom RuntimePilot identitetu, ali vise dubokih tokova jos uvek odskace:

- `Napredno` nema isti hi-fi ritam kao pocetni control deck
- `Benchmark`, `Compatibility`, `Knowledge`, `OpenCode advanced` i delovi `Tuning Lab` jos uvek imaju mesavinu starog admin rasporeda i novog shell-a
- na mnogim mestima korisnik vidi dugacke vertikalne stubove umesto jasnih receiver/deck modula
- desktop raspored nije dovoljno kompresovan za uze sirine, pa isti sadrzaj lako postane previsok ili zbijen
- duboke akcije nisu dovoljno "action-clarity" orijentisane: nije uvek ocigledno da li klik menja stanje, otvara drugi ekran ili samo pokazuje informaciju

## Razmotrene opcije

### A. Lokalni page-by-page polish

Svaku problematicnu stranicu doterivati odvojeno, bez novog shared sloja.

Prednost:

- najbrzi prvi pomaci

Mana:

- vrlo lako zavrsava u novoj nedoslednosti
- isti problemi sa spacing-om, action clarity i mobile raspadom se ponavljaju na vise mesta

### B. Shared advanced-deck sistem

Uvesti jedan zajednicki "secondary control deck" sloj za sve napredne tokove, pa strane prepakovati u isti modularni jezik.

Prednost:

- najvise cuva doslednost sa postojecom pocetnom
- lakse odrzavanje i laksi mobile pass
- action clarity pravila mogu da se sprovedu svuda isto

Mana:

- trazi jedan pocetni shared refactor

### C. Potpuni mobile-first rewrite svih sekundarnih strana

Krenuti iznova sa mobile prioritetom i precrtati skoro ceo raspored sekundarnih tokova.

Prednost:

- najcistiji teorijski rezultat

Mana:

- previsok rizik i presirok zahvat za sledecu fazu
- prevelika verovatnoca regresija u vec stabilizovanim tokovima

## Odluka

Biramo opciju **B: shared advanced-deck sistem**.

To znaci:

- pocetna strana ostaje referentni uzor
- duboki tokovi dobijaju isti "component hi-fi" jezik
- ne radimo potpuni rewrite svake stranice, vec uvodimo shared shell i potom ga primenjujemo na najvaznije napredne stranice

## Opseg ove faze

Ova faza obuhvata:

- `Napredno` kao pravi sekundarni hub
- `Benchmark`
- `Compatibility`
- `Knowledge`
- gornji i napredni delovi `OpenCode`
- `Tuning Lab` tamne/siroke deck zone koje jos ne lice na prave hi-fi module
- responsive kompresiju za laptop/tablet/mobile sirine
- action-clarity prolaz kroz sekundarne ekrane

Ova faza ne obuhvata:

- backend/API promene osim ako su nuzne zbog citljivijeg status feedback-a
- menjanje glavne logike runtime/model/OpenCode ugovora
- novi funkcionalni subsistem van UX restrukturiranja

## Dizajn pravila

### 1. Velika polja moraju da lice na hi-fi komponente

Sekundarni ekrani vise ne smeju da izgledaju kao "vise kartica nabacanih na admin tabli". Svaki glavni blok mora da deluje kao zaseban deck/receiver modul:

- ravniji, plocastiji oblici
- jasna leva/srednja/desna podela kada ima smisla
- stabilne visine modula po redu
- komandna dugmad kao citljiv transport/control strip

### 2. Akcije se dele na tri nivoa

Na sekundarnim ekranima svaki modul mora jasno da pokaze:

- **menjanje**: polja, izbori, slider-i, toggle-i
- **primenu**: sacuvaj, primeni, pokreni, proveri
- **rezultat**: status, poruka, signal, sledeci korak

Ta tri sloja ne smeju vise da budu pomesana u istoj vizuelnoj masi.

### 3. Gde klik vodi mora da bude ocigledno

Svaka primarna akcija mora imati makar jednu od sledecih istina direktno u istom modulu:

- "posle klika gledas ovde"
- "otvara drugi ekran"
- "menja aktivno stanje"
- "pokrece task i rezultat dolazi u signal panel"

Ako to nije ocigledno bez citanja cele stranice, dizajn nije dovoljno dobar.

### 4. Sirina se koristi aktivno, ne pasivno

Na desktopu ne zelimo uske vertikalne stubove sa kilometrima praznog prostora oko njih. Sekundarni ekrani treba da koriste horizontalu:

- metrics i status u kracim stripovima
- komande u kontrolnim kolonama ili redovima
- forms u sirokim faceplate zonama
- rezultati u odvojenim prikaznim modulima

### 5. Mobile nije poseban skin, nego kompresovani isti sistem

Na manjim sirinama:

- hero i signal trake se sabijaju u stacking raspored
- sekundarne komande prelaze iz kolone u pune redove
- blokovi zadrzavaju isti hi-fi identitet, samo menjaju slaganje
- sticky pomocne kontrole poput `scroll to top` i kljucnih akcija ostaju dostupne

## Predlozena arhitektura UI sloja

Treba uvesti shared sekundarni shell umesto ad-hoc CSS pravila po stranama.

### Shared slojevi

- `SecondaryDeckShell`
  - zajednicki okvir za duboke stranice
  - hero naslov, kratka svrha, signal tacke, desni command strip

- `DeckSection`
  - jedan veliki hi-fi modul sa kontrolisanom unutrasnjom mrezom

- `DeckActionRail`
  - desna kolona ili gornja traka primarnih i sekundarnih komandi

- `DeckStatusStrip`
  - kompaktan red za aktivno stanje, filtere, scope i live brojke

- `DeckResultPanel`
  - standardizovan "sta se promenilo / gde gledas rezultat" panel

- `ResponsiveControlRow`
  - shared pravila za laptop/mobile prelaz dugmadi, inputa i select kontrola

## Kako to treba da se vidi po stranicama

### Napredno

`Napredno` mora da prestane da bude obicna lista linkova. Treba da postane pravi sekundarni hub:

- levo: kratka svrha sekcije
- sredina: pregled sta je u grupi i kada se koristi
- desno: komandni izlazi ka `Benchmark`, `Tuning Lab`, `Compatibility`, `Knowledge`, `Observability`

### Benchmark

`Benchmark` treba da lici na merni deck:

- gore signal + aktivni scope
- sredina za pokretanje i kontrolu baterije
- grafikon kao display, ne kao izolovana kartica bez konteksta
- istorija sabijena u preglednije, nize, citljivije elemente

### Compatibility

`Compatibility` treba da izgleda kao fit/analysis receiver:

- izvor modela i scope izbora jasno odvojeni
- context / VRAM / offload kontrole grupisane
- primena i rezultat u odvojenom sloju
- aktivna brojcana vrednost odmah vidljiva kad korisnik klikne `Primeni`

### Knowledge

`Knowledge` treba da deluje kao document/search transport, ne kao zbijen form ekran:

- spacing izmedju opisa, inputa i dugmadi mora biti izdasan
- `documents-only / documents+web / web-only` logika mora biti citljiva i dosledna
- mesanje srpskog/engleskog i losi unicode prikazi moraju ostati nulta tolerancija

### OpenCode advanced

`OpenCode` sekundarni alati moraju da prate isti deck jezik:

- preset i security kontrola u ravnim, logicnim modulima
- action trake u jednoj horizontali gde god je moguce
- nema rastegnutih dugmadi bez hijerarhije

### Tuning Lab

`Tuning Lab` mora da zadrzi dubinu, ali da izgleda kao prava mikseta/deck zona:

- slotovi moraju biti uskladjeni po visini i poravnanju
- numericke fine kontrole treba da zadrze hi-fi identitet
- preset, source, profile, context i output moraju imati jasniji poredak

## Test i validacija

Faza je uspesna kada:

- `Napredno` izgleda kao stvarni hi-fi sekundarni hub
- `Benchmark`, `Compatibility`, `Knowledge`, `OpenCode advanced` i kljucni `Tuning Lab` blokovi dele isti modularni jezik
- korisnik moze bez razmisljanja da vidi gde menja, gde primenjuje i gde gleda rezultat
- na uzem laptop prikazu nista kljucno ne bezi u besmislene uske kolone
- na telefonu glavni moduli ostaju citljivi i bez prelamanja koje ubija UX

## Rizici

- ako shared shell bude previse genericki, strane ce opet postati slicne admin panelu
- ako se pretera sa dekoracijom, izgubice se action clarity
- ako se mobile pass ostavi za kraj kao "sitna dorada", vratice se previsoki i zbijeni rasporedi

## Preporuceni ishod ove faze

Na kraju ove faze RuntimePilot treba da izgleda kao jedan isti proizvod i kada korisnik sidje ispod pocetne strane. Ne samo lepse, nego i jasnije: manji broj pogresnih klikova, manje lutanja i manje trenutaka u kojima korisnik mora da nagadja sta se promenilo.
