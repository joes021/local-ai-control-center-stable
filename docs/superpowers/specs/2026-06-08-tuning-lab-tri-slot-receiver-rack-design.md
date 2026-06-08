# Tuning Lab Tri Slot Receiver Rack Design

**Datum:** 2026-06-08  
**Status:** odobren dizajn, spreman za planiranje implementacije  
**Cilj:** preurediti sekciju `Tri slota` u `Tuning Lab` tako da zadrzi sve postojece funkcije i parametre, ali da vizuelno i UX-logicki radi kao jedan siroki hi-fi `receiver rack` umesto kao skup uskih kartica i dugačkih formi.

## Problem

Postojeci `Tri slota` prikaz u `Tuning Lab` funkcionalno pokriva vazne stvari:

- tri odvojena slota
- glavni inference parametri
- `context` i `output`
- `thinking mode`
- `OpenCode profile`
- finije sampling vrednosti

Ali UX i vizuelni raspored su postali slab deo sistema:

- previse podataka je sabijeno u uske vertikalne kartice
- informacije se lome i gube pri citanju
- korisnik mora da "trazi" sta je identitet slota, sta su glavne vrednosti, a sta fina stelovanja
- desni deo sa finim parametrima deluje kao nabacana lista, a ne kao ozbiljan kontrolni blok
- prethodni predlozi sa uskim kolonama gubili su previse informacija
- ovalni / pilasti elementi ne odgovaraju trazenom hi-fi jeziku

Korisnik je eksplicitno potvrdio da `Tri slota` ne treba da budu tri uska mikseta kanala, nego jedan siroki dek preko cele sirine, jer je to preglednije na desktopu.

## Produkt cilj

`Tri slota` treba da postane:

- pregledan za desktop upotrebu
- dovoljno jasan pocetniku
- dovoljno brz naprednom korisniku
- vizuelno uskladjen sa `RuntimePilot` hi-fi smerom
- spreman da kasnije dobije mobilnu adaptaciju bez promene osnovne logike

Korisnik mora odmah da razume:

1. koji slot gleda
2. za sta taj slot sluzi
3. koje su glavne radne vrednosti
4. gde se rade fina stelovanja
5. sta je izmenjeno i sta se menja

## Zakljucane odluke

Na osnovu odobrenog brainstorminga, zakljucane su sledece odluke:

- bazni smer je `Wide A`, ne uski kanalni prikaz
- `Tri slota` ostaju u jednom sirokom modulu preko cele sirine
- slotovi se redjaju odozgo nadole kao tri siroke radne trake
- vizuelni jezik mora biti `hi-fi receiver / studio rack`, ne obicne web kartice
- glavni komandni elementi treba da budu kockasti / plocasti, ne ovalni
- glavni brojevi (`Context`, `Output`) treba da dobiju jaci, "display" tretman
- svih `9` finih kontrola mora ostati prisutno i vidljivo
- fini parametri ne smeju izgledati kao nabacani dugmici
- fini parametri treba da budu grupisani u logicne blokove
- preporuceni smer za fini deo je `trim rack`
- ciljni vizuelni smer je `receiver rack v3`

## Van opsega ovog dizajna

Ovaj dizajn ne menja:

- backend logiku `Tuning Lab`-a
- broj slotova
- koji se parametri cuvaju i salju
- pravila izbora pobednika
- queue i istoriju run-ova
- raspored ostalih delova `Tuning Lab` strane van sekcije `Tri slota`

Ovaj dokument je fokusiran samo na:

- UI strukturu
- hijerarhiju informacija
- kontrolni jezik
- stanja i povratnu informaciju u okviru `Tri slota`

## Predlozena struktura modula

Sekcija `Tri slota` postaje jedan siroki `receiver rack` modul sa tri horizontalne trake.

### Spoljni modul

Spoljni modul sadrzi:

- naziv sekcije
- kratko objasnjenje ili status
- jedinstven vizuelni okvir koji deluje kao jedna kontrolna povrsina

Njegova uloga je da vizuelno objedini sva tri slota u jedan sistem, umesto da ostavi utisak tri nepovezane kartice.

### Jedna slot traka

Svaki slot se prikazuje kao jedna siroka horizontalna traka sa tri zone:

1. `Identitet i namena`
2. `Glavne vrednosti`
3. `Fine kontrole`

Ovaj raspored se mora ponoviti potpuno isto za sva tri slota, da korisnik ne mora ponovo da uci gde je sta.

## Zona 1: Identitet i namena

Leva zona svakog slota prikazuje:

- labelu slota
- naziv / ulogu slota
- jednu kratku pomocnu recenicu
- glavne kockaste komandne blokove:
  - `Profil`
  - `Thinking`
  - `Source`
- opciono 1-2 `LED` status indikatora

Ova zona odgovara na pitanje:

`Sta je ovo i kada ga koristim?`

Ne sme da se pretvori u dugi tekstualni opis. Fokus je na brzom prepoznavanju.

## Zona 2: Glavne vrednosti

Srednja zona prikazuje samo stvari koje korisnik najcesce proverava ili menja kao "glavne":

- `Context`
- `Output`
- 1-2 pomocne sekundarne vrednosti, zavisno od slota

Ove vrednosti dobijaju `digital display` tretman:

- monospaced ili display izgled
- jaci kontrast
- vizuelni utisak "prozorceta" ili mernog displeja

Ova zona odgovara na pitanje:

`Koliko je ovaj slot jak / dug / zahtevan?`

Srednja zona ne treba da pokusava da prikaze svih 9 finih parametara. To je posao desne zone.

## Zona 3: Fine kontrole

Desna zona je `precision rack`.

Sadrzi svih 9 finih kontrola:

- `temperature`
- `top-k`
- `top-p`
- `min-p`
- `repeat penalty`
- `repeat last N`
- `presence penalty`
- `frequency penalty`
- `seed`

Ali umesto nabacane liste, deli se u tri logicke grupe:

### 1. Sampling

- `temperature`
- `top-k`
- `top-p`

### 2. Stability

- `min-p`
- `repeat penalty`
- `repeat last N`

### 3. Bias

- `presence penalty`
- `frequency penalty`
- `seed`

Ovaj grupisani raspored je kljucna UX odluka. Korisnik ne dobija samo 9 nepovezanih brojki, nego tri smislene podgrupe.

## Vizuelni jezik kontrola

### Kockasti komandni blokovi

Za:

- `Profil`
- `Thinking`
- `Source`
- eventualne dodatne status / akcione blokove unutar slota

koristi se kockasti, plocasti tretman:

- mali radijus
- cvrsta ivica
- osecaj fizickog tastera ili selektora

Ne koriste se pilasti, meki `pill` oblici kao primarni jezik.

### Display vrednosti

Za `Context` i `Output` koristi se vizuelni jezik malih displeja:

- tamnija podloga
- zeleni ili svetliji digitalni tekst
- monospaced karakter

Poenta nije retro estetika radi estetike, nego da korisnik odmah izdvoji glavne radne limite od pomocnih tekstova.

### Fine kontrole kao trim rack

Fini parametri se prikazuju kao `trim rack`, ne kao obicna forma.

Najbezbednija implementaciona varijanta za pravi UI je:

- grupisane horizontalne `trim` sine sa jasnim labelama i vrednostima

Razlog:

- zauzimaju manje visine nego veliki vertikalni faderi
- lakse se citaju kada ih ima 9
- lakse se implementiraju responsivno
- i dalje nose osecaj preciznog studijskog stelovanja

Vertikalni faderi su dobar inspirativni smer, ali `receiver rack v3` je pokazao da grupisane horizontalne trim sine daju zreliji balans citljivosti i hi-fi identiteta.

## Interakcioni model

Svaki slot treba da zadrzi postojecu mogucnost izmene vrednosti, ali raspored mora da jasno razdvoji:

- identitet slota
- glavne radne limite
- fino stelovanje

Pri promeni vrednosti korisnik treba odmah da vidi:

- koja je kontrola promenjena
- gde da procita trenutnu brojcanu vrednost
- kom logickom bloku kontrola pripada

Drugim recima:

- korisnik ne "klikce po listi"
- korisnik "steluje kanal"

## Stanja i feedback

U okviru svakog slota treba da postoje jasna stanja:

- normalno
- izmenjeno u draftu
- primenjeno / trenutno aktivno
- preporuceno
- problem / nevalidna vrednost

Minimalna vizuelna pravila:

- `draft changed` naglasiti ivicom, svetlom, ili malim indikatorom u okviru te kontrole
- `aktivni / preporuceni` status moze dobiti LED ili oznaku
- nevalidna vrednost mora imati jasan kontrast i tekstualnu poruku blizu problema

Ovaj dizajn ne propisuje tacnu boju za svako stanje, ali propisuje da stanja moraju biti vidljiva bez otvaranja dodatnog panela.

## Raspored po redu citanja

Na desktopu korisnik treba da cita slot ovim redom:

1. slot labela i naziv
2. `Profil / Thinking / Source`
3. `Context / Output`
4. sekundarni pomocni brojevi
5. fine kontrole po grupama

To je namerno: prvo razumevanje, pa tek onda duboko stelovanje.

## Responsivni princip

Iako je desktop prvi prioritet, modul mora imati jasan responsivni plan:

- na sirokom desktopu slot ostaje u 3 zone
- na srednjim sirinama zone mogu da se spuste u 2 reda
- na mobilnom se slot slaze vertikalno po istoj hijerarhiji:
  - identitet
  - glavne vrednosti
  - precision rack

Bitno je da se hijerarhija ne menja. Menja se samo slaganje, ne mentalni model.

## Arhitektonske smernice za implementaciju

Implementacija treba da razdvoji tri nivoa:

### 1. Layout komponenta slota

Odgovorna za:

- 3-zonski raspored
- desktop / tablet / mobile varijantu
- osnovne status klase

### 2. Vizuelne podkomponente

Posebne male komponente ili jasno izdvojeni render blokovi za:

- `slot identity block`
- `display metric`
- `square control block`
- `precision group`
- `trim control`

Time se sprecava da sav UI ostane zakopan u jednoj ogromnoj JSX strukturi.

### 3. Mapiranje podataka

Postojeci podaci treba da se preslože u novu hijerarhiju bez menjanja semantike:

- podaci ostaju isti
- menja se samo njihovo grupisanje i prikaz

## Rizici i zastita od regresija

Glavni rizici:

- da hi-fi stil postane tezi za citanje nego prethodni jednostavniji prikaz
- da 9 finih kontrola opet deluje prenatrpano
- da responsivno lomljenje pokvari logiku grupa
- da ceo modul ostane "kartica u kartici", umesto jedne kontrolne povrsine

Zbog toga implementacija mora da proveri:

- da je svaki slot citljiv bez horizontalnog skrola
- da su sve 3 precision grupe jasno odvojene
- da `Context` i `Output` ostaju vizuelno dominantni u srednjoj zoni
- da identitet slota ne potone pod parametrima

## Testiranje

Plan implementacije mora da pokrije makar ove provere:

### Vizuelne / rasporedne provere

- desktop sirina: sva 3 slota citljiva i jasno odvojena
- srednja sirina: nema raspada ili preklapanja
- mobilna sirina: hijerarhija ostaje ista i razumljiva

### Interakcione provere

- menjanje svakog od 9 finih parametara ostaje moguce
- menjanje `Profil`, `Thinking`, `Source` ostaje moguce
- `Context` i `Output` i dalje jasno pokazuju vrednost
- `draft` i `applied` stanje ostaju vidljivi

### Regresione provere

- nijedan postojeci slot podatak nije izgubljen
- nijedna postojeca kontrola nije uklonjena
- prikaz i dalje radi za sva tri slota

## Konacna preporuka

Za implementaciju treba uzeti `receiver rack v3` kao bazni vizuelni i UX smer.

To znaci:

- siroki modul preko cele sirine
- tri horizontalne slot trake
- tri zone po slotu
- kockasti komandni blokovi
- digitalni prikaz glavnih vrednosti
- precision rack sa 3 grupe i svih 9 finih parametara

Ovo je trenutno najbolji balans izmedju:

- jasnog desktop rada
- hi-fi identiteta
- citljivosti
- potpune funkcionalnosti
- kasnije responsivne adaptacije
