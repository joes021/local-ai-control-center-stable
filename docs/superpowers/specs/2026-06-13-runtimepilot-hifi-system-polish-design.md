# RuntimePilot Hi-Fi System Polish Design

**Datum:** 2026-06-13  
**Status:** odobren dizajn, spreman za planiranje implementacije  
**Cilj:** zakljucati jedinstven hi-fi vizuelni i UX jezik za RuntimePilot tako da glavni tokovi `Runtime -> Modeli -> OpenCode -> Napredno` postanu referentni sistem, a zatim da se isti jezik planski prelije na sve preostale stranice koje jos deluju kao mesavina starog i novog UI-a.

## Problem

RuntimePilot je tokom vise iteracija dobio mnogo dobrih hi-fi delova, ali proizvod jos nije vizuelno i UX-logicki potpuno ujednacen.

Trenutno stanje:

- neke strane vec imaju jasan `deck / rack / faceplate` identitet
- druge strane jos koriste obicne web kartice, genericke forme ili prenatrpane vertikalne blokove
- isti tip akcije nema uvek isti vizuelni tretman
- nije svuda jednako jasno gde se gleda rezultat posle klika
- sekundarne strane jos ponekad deluju kao zasebni alati, a ne kao delovi jednog istog uredjaja

To pravi tri problema:

1. korisnik ne stice osecaj da je sve deo jednog sistema  
2. napredni delovi i dalje umeju da zbune ili vizuelno "iskoce" iz proizvoda  
3. svaki novi polish lako postaje parcijalan umesto sistemski

## Zakljucana strategija

Na osnovu korisnicke potvrde zakljucan je smer:

- prvo se zakljucava hi-fi jezik na glavnim tokovima
- zatim se isti jezik preliva na preostale strane

Ovaj smer se ovde vodi kao:

- `C -> A`

Znacenje:

- `C`: prvo zatezemo glavne tokove `Runtime -> Modeli -> OpenCode -> Napredno`
- `A`: posle toga radimo siroko vizuelno ujednacavanje svih ostalih strana

Odbacena su dva manje pogodna puta:

- samo siroko sminkanje svega bez zakljucanog sistema
- preveliki redizajn svih sekundarnih strana odjednom, bez jasno zakljucanih osnovnih modula

## Produkt cilj

RuntimePilot treba da deluje kao jedan hi-fi komandni uredjaj, ne kao zbir tabova sa razlicitim stilovima.

Korisnik treba da stekne tri jasna utiska:

1. proizvod ima jedan dosledan vizuelni jezik  
2. svaka glavna akcija izgleda i ponasa se predvidivo  
3. i pocetnik i napredni korisnik mogu brzo da procitaju sta je glavni signal, sta je akcija, a gde je dublja dijagnostika

## Referentne strane

Ove cetiri strane postaju osnova za ceo sistem:

- `Pocetna`
- `Runtime`
- `Modeli`
- `OpenCode`

`Napredno` se tretira kao sekundarni hub, ali ulazi u isti referentni set jer treba da postane glavni nosac za sve dubinske alate.

## Zakljucane UX odluke

### 1. Glavni tok ostaje primaran

Prvi korisnicki put i dalje mora da bude:

1. proveri runtime  
2. potvrdi lokalni model  
3. otvori OpenCode rad  

Napredni alati ne nestaju, ali vise ne smeju da guse prvi klik.

### 2. Posle svakog klika mora da bude jasno gde se gleda rezultat

Ovo pravilo vazi svuda:

- akcija mora da bude vizuelno jasna
- ishod mora da bude prostorno blizu ili eksplicitno oznacen
- sledeci korak mora da bude ocigledan

### 3. Dublji alati ulaze u `advanced rack`, ne u glavni display

Kad postoji osnovni tok i dubinski tok, oni se vise ne mesaju.

Osnovni tok:

- glavni display
- kratki signal
- komandni rail

Dublji tok:

- advanced disclosure
- dijagnosticki rack
- servisni modul
- CLI / preview / browser / tuning / presets / istorija

### 4. Fine brojcane kontrole dobijaju `mixer deck` jezik

Svuda gde postoje brojcane vrednosti i finija stelovanja:

- Tuning Lab
- Compatibility
- Settings
- Benchmark kontrole
- delovi OpenCode naprednog ponasanja

koristi se isti princip:

- glavne vrednosti kao display
- finije kontrole kao mixer / trim / fader logika
- transport i monitoring odvojeni od samog unosa

## Standardni hi-fi moduli

Ovo postaje zajednicki alfabet za ceo sistem.

### 1. `Display panel`

Svrha:

- glavna informacija
- zasto je bitna
- sta se menja ili potvrdjuje

Koristi se za:

- aktivni runtime
- aktivni model
- OpenCode sesiju
- benchmark rezultat
- compatibility sazetak
- settings sazetak

Pravila:

- jedan glavni naslov ili stanje
- jedna kratka pomocna recenica
- bez pretrpavanja malim helper tekstovima u vrhu

### 2. `Command rail`

Svrha:

- 2 do 4 glavne akcije istog nivoa

Pravila:

- isti vertikalni ritam
- ista visina komandi
- isti signalni tretman
- jasan primarni i sekundarni prioritet
- ne koristiti genericka razvlacena dugmad preko cele sirine ako to ne pomaze citanju

Vizuelni cilj:

- komande moraju delovati kao deo istog transport / deck jezika

### 3. `Signal strip`

Svrha:

- kratki, gusti statusni pregled
- male metrike
- led / signal / state karakter

Pravila:

- kratko i citljivo
- bez dugih objasnjenja
- sluzi za orijentaciju, ne za dubinsko objasnjavanje

### 4. `Mixer deck`

Svrha:

- brojcane i fine kontrole
- grupisana stelovanja

Pravila:

- glavne vrednosti se izdvajaju kao display
- finije vrednosti idu u logicke grupe
- ne koristiti gomilu nepovezanih input polja
- transport / apply / save ide odvojeno od samih kontrola

### 5. `Status footer`

Svrha:

- objasnjava sta se vidi posle klika
- prikazuje pristup / aktivni profil / trenutno stanje
- pokazuje sledeci logican korak

Pravila:

- koristi se kao smireni zavrsetak modula
- ne preuzima vizuelnu tezinu glavnog display-a
- uvek vraca korisnika na pitanje "sta sada dalje?"

## Kako izgledaju referentne strane

### Pocetna

Pocetna ostaje:

- vodjeni ulaz gore
- tri velika modula ispod
- sekundarni alati u donjem summary rack-u

Njena uloga:

- pokazuje osnovni proizvodni tok
- sluzi kao UX referenca za `display panel + command rail + status footer`

### Runtime

Runtime ostaje referenca za:

- `PrimaryFlowCard`
- support module
- `advanced rack`
- command preview i dijagnostiku

Ova strana zakljucava kako izgleda razdvajanje:

- osnovni cockpit sloj
- support sloj
- dubinska dijagnostika
- CLI servisni sloj

### Modeli

Modeli postaju referenca za:

- brzi izbor
- aktivaciju i fit
- advanced katalog
- dodavanje lokalnog modela

Ova strana zakljucava:

- kako izgleda prelaz iz brzog rada u dublji katalog
- kako izgledaju akcije `aktiviraj / proveri / dodaj / preuzmi`
- kako se rezultat posle klika cita kroz aktivni model, progress i poslednju akciju

### OpenCode

OpenCode postaje referenca za:

- transport deck
- sesijski signal
- managed config
- launcher / command preview
- preset i agent behavior rack

Ova strana zakljucava:

- kako izgleda kad jedna strana ima vise servisnih podsistema, ali i dalje deluje kao jedinstven uredjaj

### Napredno

Napredno vise ne sme da bude samo "mesto gde su ostale stvari".

Njegova uloga je da postane:

- sekundarni hub
- katalog dubinskih tokova
- organizovana ulazna tacka za benchmark, tuning, compatibility, help, project memory i srodne alate

To znaci da i `Napredno` mora da dobije isti hi-fi identitet kao i glavne strane, samo sa sekundarnim prioritetom.

## Faza 1: Zakljucavanje glavnog sistema

U ovoj fazi se ne radi sve odjednom svuda, nego se finalizuje zajednicki jezik.

Radni opseg:

- `HomePage`
- `ServerPage`
- `ModelsPage`
- `OpenCodePage`
- `AdvancedPage`
- zajednicke komponente koje grade ta iskustva

Sta se ovde finalizuje:

- hijerarhija naslova
- izgled komandnih rail-ova
- tretman helper teksta
- spacing izmedju display / support / advanced slojeva
- signalni marker sistem
- pravilo `gde gledam rezultat posle klika`

Rezultat ove faze treba da bude:

- vizuelni jezik koji vise nije eksperiment
- sistem spreman da se preslika na ostalo

## Faza 2: Prelivanje sistema na sekundarne strane

Kada je Faza 1 zakljucana, radi se sweep kroz preostale strane.

### Grupa A: Knowledge, Search, Browser

Cilj:

- isti header / deck ritam
- vise vazduha izmedju teksta, polja i dugmadi
- rezultat i detalj kao instrument panel, ne kao gomila kartica

### Grupa B: Benchmark, Tuning Lab, Compatibility

Cilj:

- mixer deck princip svuda gde postoje fine kontrole
- grafici, istorija i aktivnost kompaktniji i pregledniji
- `apply / save / result` uvek kroz isti UX tok

### Grupa C: Help, Jobs, Fleet, Updates, Repair, Logs, Workflows, Project Memory

Cilj:

- i lakse strane dobijaju isti faceplate tretman
- manje plain listi i "default web" blokova
- isti osecaj da je sve deo jednog proizvoda

## Komponentni uticaj

Implementacija ovog dizajna verovatno zahteva prosirenje ili stabilizaciju sledecih zajednickih komponenti:

- `PrimaryFlowCard`
- `PageFlowCard`
- `PageDataStateCard`
- `ActionResultPanel`
- `HomeHiFiModule`
- `TelemetryPanel`
- reusable `runtimepilot-faceplate-module` stilovi
- reusable `deck-control-button` stilovi
- reusable `advanced-disclosure` i `module-shell` stilovi

Poenta nije da svaka strana dobije unikatan CSS, nego da sto vise koristi isti sistemski skup modula.

## Error handling i UX fallback

Kada neka strana nema dovoljno podataka:

- i dalje mora da izgleda kao deo hi-fi sistema
- loading i error stanja moraju koristiti iste shell / faceplate principe
- ne sme da deluje kao da je dizajn "nestao" cim nema podataka

To je posebno vazno za:

- Browser katalog
- Knowledge
- Search rezultate
- OpenCode sesijski signal
- Benchmark istoriju i grafike

## Testiranje

Ovaj dizajn treba da bude pokriven na tri nivoa.

### 1. Source-level proverama

Potvrditi da glavne i sekundarne strane koriste:

- standardne hi-fi module
- zajednicke shell klase
- pravilno grupisane advanced sekcije

### 2. Bundle proverama

Potvrditi da je osvezen i paketovani `frontend_dist`, ne samo source.

### 3. Vizuelnom proverom

Rucno proveriti:

- da li stranice deluju kao isti proizvod
- da li spacing vise nije zbijen
- da li genericka dugmad i forme vise ne vire iz hi-fi smera
- da li je odmah jasno gde se vidi rezultat posle klika

## Rizici

Glavni rizici ovog posla su:

- da polish postane samo kozmeticki
- da se previse razlicitih layout ideja zadrzi istovremeno
- da sekundarne strane dobiju hi-fi boje, ali ne i hi-fi hijerarhiju
- da se izgubi preglednost na manjim sirinama

Zato je kljucno da:

- prvo bude zakljucan sistem modula
- tek onda krenu masovnije izmene po stranicama

## Kriterijumi uspeha

Ovaj dizajn je uspesan ako na kraju:

- `Runtime`, `Modeli`, `OpenCode` i `Napredno` deluju kao jedna ista porodica
- sekundarne strane vise ne deluju kao stari UI koji je samo prebojen
- korisnik moze brzo da procita glavni signal, komandu i rezultat
- fine kontrole svuda imaju smislen `mixer deck` jezik
- proizvod ostavlja utisak jednog komandnog uredjaja, a ne zbirke tabova

## Sledeci korak

Posle ovog dokumenta ide:

- implementacioni plan po fazama
- pa tek onda stvarni polish sweep kroz kod


