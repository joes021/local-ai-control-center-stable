# Settings + Compatibility + Benchmark Hybrid Shell Design

## Status

Ovaj dokument definiše sledeći UX/UI korak za tri strane:

- `Settings`
- `Compatibility`
- `Benchmark`

Dokument namerno ide dalje od ranijeg `home-shell` pravca. Cilj nije da te strane budu samo “slične početnoj”, nego da preuzmu isti spoljašnji hi-fi jezik, a da iznutra ostanu prilagođene sopstvenom poslu.

## Cilj

Napraviti tri strane koje:

- pripadaju istom RuntimePilot hi-fi sistemu kao početna strana
- nemaju mrtve kartice, duplirane komande ni placeholder module
- jasno odvajaju stanje, akcije i rezultat akcije
- koriste punu širinu ekrana bez zagušenja i bez uskih vertikalnih kolona
- ostaju čitljive i kada strana ima mnogo parametara, statusa i istorije

## Problem Koji Rešavamo

Trenutni sistem je funkcionalan, ali na ove tri strane i dalje postoji stari obrazac:

- previše malih kartica koje liče da nešto rade, a zapravo samo opisuju
- radne zone koje su previše uske u odnosu na širinu ekrana
- rezultat posle klika nije uvek dovoljno blizu mestu akcije
- pojedini moduli više liče na generički admin panel nego na RuntimePilot hi-fi control deck
- `Settings` je najgušći i lako sklizne u “zid opcija”
- `Benchmark` lako postaje previsoka lista run-ova umesto mernog deka
- `Compatibility` meša pregled, editor i primenu tako da korisnik ne vidi odmah šta je stvarno aktivno

## Dizajn Smer

Preporučeni smer je `hibridni shell`.

To znači:

- spolja isti jezik kao početna strana
- unutra raspored optimizovan za konkretan posao te strane

Ne radimo ni jednu od dve krajnosti:

1. ne kopiramo početnu stranu doslovno
2. ne prelazimo u potpuno generički “kompaktni admin” raspored

RuntimePilot mora da ostane prepoznatljiv, ali bez žrtvovanja jasnoće.

## Osnovna Pravila

### 1. Jedna jasna hijerarhija po strani

Na svakoj strani korisnik mora odmah da vidi:

1. gde se čita tok rada
2. gde se čita trenutno stanje
3. gde se klikće
4. gde se vidi posledica klika

Ako neki element ne spada ni u jednu od te četiri uloge, treba ga ukloniti ili spojiti sa drugim elementom.

### 2. Nema mrtvih kartica

Kartica sme da postoji samo ako:

- prikazuje živo stanje
- vodi na sledeći korak
- sadrži stvarnu akciju
- prikazuje rezultat ili poslednju promenu

Kartice koje samo “glume modul” nisu dozvoljene.

### 3. Akcije žive na jednom mestu

Svaka strana treba da ima jedan primarni `action deck` koji je glavno mesto za klikove.

Ne treba imati:

- jednu kolonu dugmadi
- pa ispod toga drugi niz istih ili sličnih dugmadi
- pa pored toga kartice koje deluju klikabilno, a nisu

Jedna akcija treba da postoji samo jednom u primarnom toku.

### 4. Rezultat mora da bude blizu akcije

Posle klika korisnik odmah mora da vidi šta se desilo.

To znači:

- `Poslednja akcija`
- `Aktivno sada`
- `Editor čeka proveru`
- `Run status`

moraju biti ili odmah ispod akcija ili u jasno obeleženoj susednoj zoni.

### 5. Širina ekrana mora da radi za nas

Desktop raspored ne sme da ostavlja ogroman prazan prostor desno dok je važan sadržaj sabijen u usku kolonu.

Široki ekran treba da donese:

- duže horizontalne radne module
- bolju preglednost
- manje vertikalnog skrolovanja

## Zajednički Shell Za Sve Tri Strane

Svaka od tri strane prati isti gornji obrazac:

1. `PageFlowCard`
2. `RuntimePilotStatusDeck`
3. `RuntimePilotActionDeck`
4. jedna ili dve velike radne zone pune širine
5. rezultat ili istorija ispod radne zone

### 1. PageFlowCard

`PageFlowCard` ostaje prvi modul na strani i objašnjava:

- šta se ovde radi
- kojim redosledom
- gde je sledeći korak

On ne sme biti dugačak. Njegova svrha je orijentacija, ne dokumentacija.

### 2. RuntimePilotStatusDeck

`RuntimePilotStatusDeck` postaje kratki “signal strip” konkretne strane.

Status kartice treba da budu:

- jednake visine
- vizuelno čitljive
- klikabilne samo ako zaista vode do sledeće radnje

Status deck ne služi da prikaže sve moguće podatke, nego samo nekoliko najvažnijih.

### 3. RuntimePilotActionDeck

`RuntimePilotActionDeck` je primarna komandna zona strane.

Na njemu su samo stvarne akcije koje korisnik može odmah da pokrene.

On ne sme biti podeljen na više paralelnih “mikro rail” sistema bez jasne potrebe.

### 4. Radne zone

Glavni sadržaj ispod gornjeg shell-a treba da bude organizovan kao veliki horizontalni hi-fi moduli:

- puni ili skoro puni širinom
- jasno odvojeni
- bez vizuelnog utiska da su to samo generičke forme u okvirima

## Strana: Settings

## Uloga Strane

`Settings` je komandni rack za profile, inference, kontekst, GPU ponašanje, OpenCode ponašanje i pretragu.

To nije strana za “čitanje puno kartica”, nego za:

- biranje
- menjanje
- snimanje
- primenu
- proveru šta je aktivno

## Gornji Shell

### PageFlowCard

Tok rada mora da kaže:

1. izaberi ili prilagodi vrednosti
2. snimi ili primeni
3. proveri aktivno stanje i rezultat

### Status deck

Preporučene kartice:

- aktivni profil
- context
- output
- GPU layers režim
- pretraga / provider

Ako kartica nema praktičnu vrednost za odluku korisnika, ne ulazi u status deck.

### Action deck

Primarne akcije:

- `Sačuvaj bez primene`
- `Primeni postojeće`
- `Sačuvaj i primeni`
- `Vrati podrazumevano`

Te četiri akcije treba da budu jedino centralno mesto za potvrdu promene.

## Glavni Raspored

`Settings` ispod shell-a treba da bude podeljen po temama, a ne po nizu sitnih kartica:

### Modul 1: Inference i sampling

Ovo je glavna radna zona za:

- `temperature`
- `top-k`
- `top-p`
- `min-p`
- `repeat penalty`
- `repeat last n`
- `presence`
- `frequency`
- `seed`

Ovaj modul treba da izgleda kao komandni deck, ne kao beskrajni zid mini kartica.

Pravilo:

- primarne kontrole mogu stajati u mreži
- ali objašnjenja moraju biti uredno poravnata i čitljiva
- saveti tipa “za kod / za chat / za benchmark” moraju biti deo istog horizontalnog jezika

### Modul 2: Context, output i GPU slojevi

Drugi veliki modul okuplja:

- context
- output tokens
- GPU layers
- VRAM fit pomoćni signal

Ovo mora biti jedna logička celina zato što korisnik te vrednosti doživljava kao jednu odluku: koliko dugo radi, koliko izlaza daje i da li staje u mašinu.

### Modul 3: OpenCode profil i bezbednost

Treći veliki modul okuplja:

- OpenCode profil
- thinking režim
- pristup / autonomiju
- bezbednosni režim
- preset ponašanja

Ovo mora izgledati kao jedna operativna zona, ne kao niz raštrkanih dropdown menija.

### Modul 4: Pretraga i provider

Poseban modul za:

- provider pretrage
- lokalni SearxNG tok
- status izvora
- helper poruke

Status poruke ovde moraju biti jasne, čiste i bez sirovih tehničkih fraza ili mojibake problema.

## Result Zone

Na `Settings` strani rezultat promene mora jasno razlikovati:

- šta je samo sačuvano
- šta je primenjeno
- šta je trenutno aktivno u runtime-u

Ako korisnik klikne `Primeni`, mora odmah da vidi novu aktivnu vrednost na istoj strani.

## Strana: Compatibility

## Uloga Strane

`Compatibility` je kalkulator odluke.

Korisnik ovde dolazi da vidi:

- da li model staje
- pod kojim uslovima staje
- šta može da primeni odmah
- šta je samo predlog u editoru

## Gornji Shell

### PageFlowCard

Tok rada mora da kaže:

1. izaberi izvor modela
2. proveri fit
3. primeni context i GPU odluku
4. proveri `Aktivno sada`

### Status deck

Preporučene kartice:

- aktivni model
- izvor provere
- fit status
- context predlog
- GPU slojevi predlog

### Action deck

Primarne akcije:

- `Proveri kompatibilnost`
- `Primeni context`
- `Primeni GPU slojeve`
- `Otvori Modele`
- `Otvori Browser katalog`

Ako postoji dodatni link ka izvornom modelu, on treba da živi u sekundarnom delu rezultata, a ne kao duplirana primarna akcija.

## Glavni Raspored

`Compatibility` treba da ima dve jasne radne zone:

### Leva zona: kalkulator

Ovde žive:

- izbor modela ili izvora
- kalkulacija VRAM fit-a
- procena context / GPU layers
- opis rezultata

To je glavni deo strane i mora biti širi od desne zone.

### Desna zona: stanje primene

Ovde žive:

- `Aktivno sada`
- `Editor čeka proveru`
- `Poslednja akcija`

To je “truth panel” i korisnik mora odmah da razume razliku između:

- predloga
- editora
- stvarno aktivnog runtime stanja

## Ključno Pravilo

`Compatibility` ne sme da meša “izračunato”, “upisano” i “aktivno”.

Ta tri stanja moraju biti fizički i tekstualno odvojena.

## Strana: Benchmark

## Uloga Strane

`Benchmark` je merni dek.

Korisnik ovde dolazi da:

- pokrene scenario
- prati tok rada
- vidi graf
- poredi throughput
- pregleda istoriju

## Gornji Shell

### PageFlowCard

Tok rada mora da kaže:

1. izaberi scenario ili bateriju
2. pokreni run
3. prati signal i graf
4. uporedi istoriju i odluči sledeći korak

### Status deck

Preporučene kartice:

- stanje run-a
- aktivni scenario
- throughput signal
- baterija / broj prolaza
- aktivni profil

### Action deck

Primarne akcije:

- `Pokreni izabrani test`
- `Pokreni celu bateriju`
- `Sačuvaj bateriju`
- `Vrati podrazumevano`
- `Izvezi rezultat`

Akcije za Tuning Lab, logove ili dodatne stranice treba da budu sekundarne i jasno odvojene od glavnog pokretanja benchmarka.

## Glavni Raspored

### Modul 1: Kontrole benchmarka

Scenario, baterija, repeat i ostale kontrole pokretanja treba da budu na jednom mestu i jasno poravnate.

### Modul 2: Grafikon benchmarka

Graf je centralni vizuelni modul.

Pravila:

- metrika i vremenski opseg moraju biti odmah uz graf
- korisnik mora moći da uključi jednu, dve ili sve tri linije
- pomoćni info strip ne sme vizuelno potisnuti sam graf

### Modul 3: Aktivnost i telemetrija

Živa aktivnost i telemetrija treba da ostanu kompaktne i da ne pretvaraju stranu u previsoku listu događaja.

### Modul 4: Istorija run-ova

Istorija ne sme biti jedna duga vertikalna kolona.

Za duge baterije prikaz mora biti sabijen, pregledan i pogodan za brzo skeniranje.

Na primer:

- kompaktan grid
- tabela
- kratke status kartice u gustoj mreži

Ali ne beskrajna lista velikih blokova.

## Vizuelna Pravila

Važe za sve tri strane:

- svi moduli u istom redu moraju imati konzistentnu visinu gde god je to moguće
- dropdown meniji moraju imati punu neprovidnu pozadinu i ispravan `z-index`
- tekst mora imati dovoljno jak kontrast na tamnoj hi-fi podlozi
- dugmad u istoj akcijskoj grupi moraju biti jednake visine
- radne zone moraju koristiti horizontalni prostor, a ne gurati sadržaj u uske stubove
- ako modul deluje klikabilno, mora zaista da bude klikabilan

## Komponentna Strategija

Treba maksimalno graditi na postojećim shell komponentama:

- `PageFlowCard`
- `RuntimePilotStatusDeck`
- `RuntimePilotActionDeck`
- `PageDataStateCard`
- `ActionResultPanel`

Posebne stranice ne treba da ponovo izmišljaju isti shell, nego da iznutra slože sopstveni radni sadržaj.

## Mobilni i Uži Desktop

Iako je primarni slučaj desktop, raspored mora da se lomi kontrolisano:

- status deck i action deck mogu preći u 2 reda
- veliki moduli mogu preći iz 2 kolone u 1
- ali bez preklapanja, bez odsecanja teksta i bez lebdećih kartica preko drugih modula

## Test Strategija

Za svaku od tri strane završni rad mora da ima:

1. source-level proveru u `tests/test_control_center_frontend_dist.py`
2. proveru packaged `frontend_dist` bundle-a
3. uspešan frontend build
4. osvežen packaged portal
5. živu proveru u lokalnom browseru

## Očekivani Ishod

Ako je dizajn uspešan, korisnik na svakoj od te tri strane dobija isti osećaj kao na početnoj:

- zna gde gleda stanje
- zna gde klikće
- zna gde vidi posledicu klika
- nema osećaj da ga UI tera da pogađa

Razlika je samo u poslu koji strana radi:

- `Settings` je komandni rack
- `Compatibility` je kalkulator + primena
- `Benchmark` je merni dek

To je cilj koji ovaj dokument zaključava.
