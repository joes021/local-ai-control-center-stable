# Tuning Lab - Game Batch 01

Datum: 2026-05-29
Namena: prvi konkretan batch test za poređenje podešavanja `llama.cpp + lokalni model + OpenCode`

## Zašto baš ova 3 prompta

Izabrao sam 3 prompta koji dobro pokrivaju tri različita nivoa težine:

1. `Jumping Ball Runner`
   - mali do srednji scope
   - jedan HTML fajl
   - dobar za brza poređenja i stabilan token flow
2. `Balloon Blaster`
   - srednji scope
   - više gameplay sistema i više stanja u igri
   - dobar za proveru da li model ume da održi koherenciju kroz više feature-a
3. `Octopus Invaders`
   - veliki scope
   - višefajlni projekat
   - dobar za pravi agentic coding stres test

Važno: prompti ispod su **normalizovani za benchmark**. Nisu slepo kopirani sa interneta, nego su preuređeni da budu:

- determinističniji
- lakši za success check
- bolji za poređenje između modela i različitih inference podešavanja

## Izvori inspiracije

- OpenAI GPT-5 primer `Jumping Ball Runner`:
  - <https://openai.com/index/introducing-gpt-5/>
- Balloon Blaster prompt iz DEV članka:
  - <https://dev.to/blinknbuild/i-vibe-coded-a-balloon-popping-game-using-claude-ai-2l42>
- `Octopus Invaders` standardizovani benchmark prompt:
  - <https://gist.github.com/sudoingX/d2df91b5efa8f21c315501133fe22d33>
- OpenGame kao potvrda da su game-generation prompti legitiman benchmark pravac:
  - <https://github.com/leigest519/OpenGame>

## Batch struktura

- `easy`: Jumping Ball Runner
- `medium`: Balloon Blaster
- `hard`: Octopus Invaders

Svaki run treba da radi u svom izolovanom podfolderu ili worktree-u.

---

## 1. Jumping Ball Runner

### Zašto je dobar

- brz za izvršavanje
- lako se proverava
- odličan za first-pass tuning
- daje lep throughput signal jer model ne luta previše

### Prompt

Napravite kompletnu browser igru `Jumping Ball Runner` kao **jedan jedini `index.html` fajl** sa ugrađenim CSS i JavaScript kodom.

Zahtevi:

- igra mora da radi lokalno samo otvaranjem `index.html`
- igrač kontroliše jednu lopticu ili lik koji skače preko prepreka
- cilj je da preživi što duže
- brzina igre mora postepeno da raste
- mora da postoji:
  - prikaz trenutnog skora
  - high score
  - retry / restart dugme
  - zvučni efekti generisani u browseru ili bez eksternih audio fajlova
- vizuelni stil treba da bude šaren, jasan i prijatan, sa parallax pozadinom
- kontrole moraju da rade tastaturom
- igra mora da ima:
  - start stanje
  - aktivan gameplay
  - game over stanje
- kod treba da bude dovoljno čist da se lako razume i menja

Na kraju:

- ostavite kratak komentar pri vrhu fajla šta je urađeno
- nemojte koristiti build alat, framework ni spoljne zavisnosti osim ako su apsolutno neophodne

### Predlog success check-a

- `index.html` postoji
- u HTML-u postoje stringovi:
  - `Jumping Ball Runner`
  - `Score`
  - `High Score`
- browser otvara stranicu bez fatalne JS greške

---

## 2. Balloon Blaster

### Zašto je dobar

- uvodi više gameplay sistema od običnog endless runner-a
- dobar je za proveru da li model drži fokus kroz više feature-a
- i dalje je dovoljno kompaktan da batch ne traje predugo

### Prompt

Napravite kompletnu browser igru `Balloon Blaster` kao **jedan jedini `index.html` fajl** sa ugrađenim CSS i JavaScript kodom.

Zahtevi:

- igra mora da radi lokalno samo otvaranjem `index.html`
- shooter se nalazi pri dnu ekrana, a baloni dolaze odozgo
- igrač puca i skuplja poene razbijanjem balona
- moraju da postoje najmanje:
  - tri veličine balona sa različitim vrednostima poena
  - combo sistem
  - najmanje tri power-up mehanike
  - particle efekti pri pucanju balona
  - high score čuvan lokalno
  - najmanje dva nivoa težine
- kontrole moraju da rade tastaturom, a bonus je ako rade i mišem ili touch-om
- igra mora da ima:
  - start ekran
  - aktivan gameplay
  - pauzu ili jasan game over / restart tok
- nema React-a, nema build alata, nema framework-a
- ako ubacujete zvuk, neka bude browser-native ili bez spoljnog audio foldera
- UI mora da bude dovoljno jasan da korisnik odmah shvati:
  - rezultat
  - combo
  - aktivne efekte

Na kraju:

- na vrh fajla dodajte kratak komentar sa opisom igre i kontrola

### Predlog success check-a

- `index.html` postoji
- HTML/JS sadrži stringove:
  - `Balloon Blaster`
  - `Combo`
  - `High Score`
- browser otvara stranicu bez fatalne JS greške

---

## 3. Octopus Invaders

### Zašto je dobar

- najbliži je pravom agentic coding stres testu
- tera model da održava arhitekturu kroz više fajlova
- dobar je za razlikovanje “brzo piše” od “stvarno drži projekat na nogama”

### Prompt

Napravite browser igru `Octopus Invaders` kao **višefajlni vanilla JavaScript projekat** bez framework-a i bez biblioteka.

Obavezna struktura projekta:

- `index.html`
- `README.md`
- `css/styles.css`
- `js/config.js`
- `js/game.js`
- `js/player.js`
- `js/enemies.js`
- `js/particles.js`
- `js/background.js`
- `js/ui.js`
- `js/audio.js`

Zahtevi:

- igra je vertical space shooter
- koristi `canvas`
- igra mora da radi lokalno kada se projekat servira preko jednostavnog static server-a
- mora da postoji:
  - start ekran
  - gameplay loop
  - pause
  - game over ekran
- igrač upravlja brodom
- postoje različiti tipovi neprijatelja
- mora da postoji score sistem, health, combo i makar jedan boss ili završni veći susret
- pozadina treba da ima više slojeva i osećaj dubine
- efekti pogodaka i eksplozija moraju da postoje
- audio treba da bude proceduralan ili browser-native, bez oslanjanja na spoljne binarne assete
- kod mora da bude razdvojen po odgovornostima tako da fajlovi zaista imaju smisla
- `README.md` mora da objasni:
  - šta je igra
  - kako da se pokrene
  - kontrole
  - strukturu projekta

Na kraju:

- proverite da su importi i redosled učitavanja ispravni
- cilj je da igra radi iz prve bez ručnog dorađivanja

### Predlog success check-a

- svi navedeni fajlovi postoje
- `README.md` postoji i sadrži `controls` ili `kontrole`
- `index.html` referencira CSS i JS strukturu projekta
- browser otvara igru bez fatalne JS greške

---

## Preporučeni redosled za prvi batch

1. `Jumping Ball Runner`
2. `Balloon Blaster`
3. `Octopus Invaders`

To daje lep odnos:

- kratko
- srednje
- dugo

i omogućava da vidiš:

- koji set podešavanja je najstabilniji
- koji je najbrži
- gde model počinje da se raspada kad scope poraste

## Važna napomena za benchmark poštenje

Za batch test nemoj koristiti potpuno otvorene promptove tipa:

- “napravi neku lepu igru”
- “izaberi sam temu”
- “napravi nešto zabavno”

To je dobro za demo, ali loše za poređenje. Za tuning nam trebaju promptovi koji su dovoljno konkretni da:

- različiti run-ovi rade sličan zadatak
- success check ima smisla
- rezultat može da se poredi kroz vreme

## Moj jasan predlog

Ovo je dobar prvi `Game Batch 01`.

Ako budemo pravili `Game Batch 02`, tada bih išao na:

- jednu puzzle/logic igru
- jednu tower defense ili RTS-lite igru
- jednu igru sa jačim UI i persistence slojem


