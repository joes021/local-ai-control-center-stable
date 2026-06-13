# RuntimePilot Project Memory Design

**Datum:** 2026-06-04  
**Status:** predlog za implementaciju  
**Cilj:** dodati ugrađeni `Project Memory` sistem koji pomaže agentu da zadrži cilj, odluke i sledeće korake čak i kada task traje dugo ili kontekst naraste.

## Problem

`OpenCode` i srodni tokovi danas mogu da odrade mnogo toga, ali imaju jedan praktičan problem:

- korisnik zada dobar cilj
- agent krene dobro
- posle više koraka ili dužeg konteksta fokus oslabi
- agent počne da menja sporedne stvari
- korisnik mora ručno da podseća sistem šta je zapravo bitno

To posebno boli početnike i korisnike koji:

- nisu vešti sa promptovima
- ne razumeju kako da održavaju session state
- ne znaju kada treba “resetovati” ili “re-fokusirati” agenta

Ako želimo da RuntimePilot bude upotrebljiv široj publici, sistem mora da obezbedi **spoljnu radnu memoriju** koju agent koristi automatski, a korisnik može da vidi i ispravi.

## Šta ne treba raditi kao osnovu

Ovaj problem ne treba rešavati tako što:

- samo povećamo broj tokena
- uvedemo Obsidian kao obavezni deo proizvoda
- tražimo od korisnika da sam vodi dugačke projektne beleške

To ne rešava glavni UX problem. Početnicima treba **ugrađena struktura**, ne još jedan alat i još jedan mentalni model.

## Zaključane odluke

Na osnovu korisničkog cilja i dosadašnjeg proizvoda, `Project Memory` treba da radi ovako:

- mora biti ugrađen direktno u `RuntimePilot`
- ne sme tražiti od korisnika poznavanje Obsidian-a, vault-ova ili AI terminologije
- mora biti primarno dizajniran za početnike
- agent mora da ga koristi automatski
- korisnik mora da može da ga vidi i po potrebi ručno ispravi
- memorija mora biti vezana za konkretan projekat / task tok
- glavni cilj i važna pravila moraju moći da se “zaključaju”
- sistem mora da zna razliku između:
  - cilja
  - odluka
  - napretka
  - sledećeg koraka
- `OpenCode` i `Tuning Lab` su prva mesta integracije
- Obsidian može kasnije postati opcioni napredni dodatak, ali ne i osnova v1

## UX cilj

Korisnik ne sme da mora da razmišlja:

- “Gde mi je zapisan glavni cilj?”
- “Da li agent i dalje zna šta radi?”
- “Šta smo već odlučili?”
- “Šta je sledeće?”

RuntimePilot treba da odgovori na to umesto korisnika.

## Mentalni model proizvoda

Naziv u UI-ju treba da bude:

- `Project Memory`
ili na lokalizovanim mestima:
- `Radna memorija projekta`

Ne treba koristiti tehničke ili marketinške nazive poput:

- semantic memory
- context graph
- agent vault
- persistent cognition

Za običnog korisnika to pravi više zabune nego vrednosti.

## Struktura memorije

Svaki projektni memory zapis u v1 treba da ima 5 glavnih blokova:

### 1. Glavni cilj

Jedna kratka i jasna rečenica.

Primer:

- `Napraviti playable HTML igru Jumping Ball Runner koja ispunjava sve zahteve iz taska.`

### 2. Važna pravila

Stvari koje agent ne sme da zaboravi ili prekrši.

Primeri:

- `Igra mora biti u jednom HTML fajlu.`
- `Mora postojati score.`
- `Mora postojati restart.`
- `Bez eksternih biblioteka.`

### 3. Već odlučeno

Bitne odluke da agent ne menja pristup bez razloga.

Primeri:

- `Koristimo canvas.`
- `Output je index.html.`
- `Ne uvodimo build korake.`

### 4. Napredak

Sažetak već urađenog rada.

Primeri:

- `Postavljena osnovna game loop logika.`
- `Dodat score counter.`
- `Postavljen restart flow.`

### 5. Sledeće

Jedan jasan naredni korak ili mali skup prioriteta.

Primeri:

- `Proveriti collision i game over tok.`
- `Dovršiti input handling.`

## Ključni UX princip

Korisnik ne treba sve da piše ručno.

Početni tok treba da bude:

1. korisnik zada zadatak
2. sistem predloži početnu `Project Memory`
3. korisnik vidi i po potrebi ispravi
4. agent dalje automatski održava memoriju
5. korisnik samo po potrebi klikne:
   - `Ispravi`
   - `Dodaj pravilo`
   - `Zaključaj cilj`

To znači da je memorija:

- automatski korisna
- ali ne i “crna kutija”

## Gde se prikazuje u UI-ju

### A. Stalni sažeti strip

Treba dodati jedan mali, stalni `Project Memory` strip u glavnom shell-u ili odmah uz `OpenCode` / `Tuning Lab` zone.

Taj strip prikazuje:

- `Cilj`
- `Sledeće`
- indikator napretka
- dugme `Otvori Project Memory`

To mora biti:

- kratko
- čitljivo
- ne previše visoko

### B. Puni Memory panel

Klik na `Otvori Project Memory` otvara:

- stranu
ili
- veliki side panel / drawer

Pun prikaz treba da sadrži:

- `Glavni cilj`
- `Važna pravila`
- `Već odlučeno`
- `Napredak`
- `Sledeće`
- `Poslednje ažuriranje`
- `Izvor izmene: agent / korisnik`

### C. Brze akcije

Treba dodati brze kontrole:

- `Zaključaj cilj`
- `Dodaj pravilo`
- `Označi kao završeno`
- `Osveži iz poslednjeg run-a`
- `Vrati fokus na cilj`

## Kako agent koristi memoriju

Pre svakog ozbiljnijeg koraka agent dobija:

- originalni task
- + sažetak `Project Memory`

Minimalni format koji ide agentu treba da bude:

- `Glavni cilj`
- `Važna pravila`
- `Već odlučeno`
- `Napredak`
- `Sledeće`

To je važnije od sirovog dugog transcript-a, jer agent time dobija **strukturu prioriteta**, ne samo više teksta.

## Drift zaštita

Da agent ne odluta, v1/v2 dizajn treba da uvede 3 mehanizma.

### 1. Goal lock

`Glavni cilj` može da bude zaključan.

Zaključan cilj:

- agent ne menja sam
- menja se samo na eksplicitnu korisničku potvrdu

### 2. Rule lock

Pojedina pravila mogu da budu zaključana.

Primer:

- `Jedan HTML fajl`
- `Bez biblioteka`

To sprečava “tiho” menjanje važnih ograničenja tokom dužeg rada.

### 3. Drift warning

Ako agent počne da radi nešto što ne liči na:

- `Glavni cilj`
- `Važna pravila`
- `Sledeće`

sistem treba da prikaže drift signal.

Primer upozorenja:

- `Agent trenutno doteruje styling, a prioritet je collision logika.`

To ne mora odmah blokirati rad, ali mora biti vidljivo.

## Integracija po površinama

### OpenCode

Prva i najvažnija integracija.

Potrebno je:

- da `OpenCode` run koristi `Project Memory` kao uvodni kontekst
- da se po završetku koraka memory osveži
- da korisnik može da vidi šta je agent “zapamtio”

### Tuning Lab

Svaki task / batch run treba da ima svoju memory strukturu.

To omogućava:

- bolje poređenje slotova
- manje lutanja tokom task izvršavanja
- jasniji razlog zašto je neki slot uspeo ili odlutao

### Workflows

Kasnije workflow preset može da sadrži i memory policy, npr:

- agresivno sažimanje
- striktan goal lock
- coding-first memory
- research-first memory

To nije uslov za v1.

## Arhitektura v1

### Backend domen

Dodati novi domen, na primer:

- `project_memory_service.py`
- `routes/project_memory.py`

Servis vodi:

- aktivnu memoriju po projektu / run-u
- zaključane stavke
- sažeti prikaz
- istoriju izmena

### Osnovni model podataka

Minimalno:

- `memoryId`
- `scopeType` (`opencode`, `tuning-lab`, `general-project`)
- `scopeId`
- `goal`
- `rules[]`
- `decisions[]`
- `progress[]`
- `nextSteps[]`
- `lockedFields`
- `updatedAt`
- `updatedBy`

### Izvori ažuriranja

Memory se ažurira iz:

- početnog task-a
- agent output-a
- korisničkih ručnih izmena
- success/failure signala iz run-a

### Pravilo pisanja

Agent nikad ne treba da:

- briše glavni cilj bez potvrde
- menja zaključana pravila
- masovno prepisuje memoriju bez jasnog razloga

## Šta v1 ne radi

Da bismo ostali fokusirani, v1 ne treba da uključuje:

- embedding sistem
- RAG nad celim projektom
- automatski knowledge graph
- Obsidian sync
- komplikovanu hijerarhiju beleški
- “samostalno razmišljanje” nad memory zapisima

V1 treba da bude:

- jednostavan
- stabilan
- razumljiv korisniku

## Predlog rollout-a

### Phase 1

Dodati:

- `Project Memory` panel
- 5 osnovnih sekcija
- ručni prikaz + osnovno automatsko punjenje iz task-a
- stalni sažeti strip

### Phase 2

Dodati:

- automatsko osvežavanje iz `OpenCode` i `Tuning Lab` run-ova
- `Goal lock`
- `Rule lock`
- osnovni `drift warning`

### Phase 3

Dodati:

- export / import
- opcioni napredni sync sa Obsidian-om
- memory policy po workflow-u

## Zašto je ovo bolji smer od Obsidian-first pristupa

Obsidian kao primarna osnova bi:

- otežao setup
- uveo dodatni alat koji početnici ne razumeju
- pomerio “izvor istine” van RuntimePilot-a
- povećao support trošak

Ugrađeni `Project Memory` sistem:

- radi odmah
- razumljiv je prosečnom korisniku
- agent ga koristi automatski
- i dalje može kasnije da dobije opcioni Obsidian sloj za napredne korisnike

## Zaključak

Najpametniji sledeći proizvodni korak nije `Obsidian unutar OpenCode-a`, nego:

- **ugrađeni `Project Memory` unutar RuntimePilot-a**

To direktno rešava problem:

- dugog konteksta
- zaboravljanja glavnog cilja
- početničke nesigurnosti
- agent lutanja

Na taj način RuntimePilot postaje ne samo launcher i kontrolni centar, nego i **sistem koji čuva fokus rada**.


