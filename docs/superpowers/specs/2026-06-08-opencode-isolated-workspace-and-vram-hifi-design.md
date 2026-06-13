# OpenCode Isolated Workspace and VRAM Hi-Fi Control Design

**Datum:** 2026-06-08  
**Status:** odobren dizajn, spreman za implementaciju  
**Cilj:** uvesti dva jasna režima ručnog OpenCode rada i prelomiti `VRAM fit / Opšta podešavanja` u odobreni hi-fi `mixer -> primena -> monitoring` raspored.

## Problem

RuntimePilot sada uspešno otvara desktop OpenCode aplikaciju, ali korisnik nema jasan izbor između:

- rada nad stvarnim projektom
- rada nad bezbednim izolovanim workspace-om

To zbunjuje naročito kada korisnik želi da eksperimentiše bez rizika po glavni projekat.

Paralelno sa tim, `Settings -> Opšta podešavanja / VRAM fit tuning` i dalje vizuelno nose previše klasičnih web kartica i kolona. Funkcionalnost postoji, ali UX ne prati odobreni `hi-fi mixer` smer.

## Zaključane odluke

Na osnovu korisnički odobrenog pravca, sledeće odluke su zaključane:

- `OpenCode` dobija **dva jasna ručna režima**:
  - `Otvori OpenCode`
  - `Otvori u izolovanom workspace-u`
- običan režim koristi trenutni `workingDirectory`
- izolovani režim koristi poseban pripremljen workspace, po istom bezbednosnom principu kao `Tuning Lab`
- gde god je moguće, oba režima treba da zadrže **desktop OpenCode GUI**, ne povratak na stari prazni terminalski tok

Za `VRAM fit` i povezani deo `Opštih podešavanja` zaključan je sledeći vizuelni i radni jezik:

- `B` kao glavni hi-fi vizuelni smer
- raspored:
  1. `menjanje`
  2. `primena i snimanje`
  3. `monitoring`
- `REC + PLAY` logika za `Sačuvaj i primeni`

## OpenCode ručni režimi

### 1. Direktan rad

Ovaj režim ostaje podrazumevani i najbrži tok:

- koristi aktivni `workingDirectory`
- koristi `managed-config.json`
- koristi trenutni RuntimePilot runtime/model kontekst
- namenjen je svakodnevnom radu nad stvarnim projektom

UI copy mora jasno da kaže da ovaj režim menja pravi projekat, ne sandbox.

### 2. Izolovani workspace

Ovaj režim uvodi bezbedniji tok za eksperimentisanje:

- pravi izolovani workspace pre otvaranja OpenCode-a
- ako je repo čist, koristi `git worktree`
- ako nije, koristi kopiju radnog direktorijuma
- zatim otvara OpenCode baš nad tim izolovanim workspace-om

UI copy mora jasno da kaže da je ovo bezbedan probni režim i da ne dira glavni projekat direktno.

### Status i rezultat

Posle klika korisnik mora odmah da vidi:

- da li je otvoren direktan ili izolovan režim
- nad kojom putanjom je OpenCode pokrenut
- da li se koristi desktop GUI ili CLI fallback

Ako je otvoren izolovani režim, rezultat treba da pokaže i:

- način pripreme (`git worktree` ili `copy`)
- putanju workspace-a

## OpenCode UI promene

### OpenCode strana

Na vrhu `OpenCode` strane ostaju tri velika horizontalna modula, ali glavni modul menja akcioni sloj:

- glavno dugme: `Otvori OpenCode`
- sekundarno dugme: `Otvori u izolovanom workspace-u`
- bootstrap/install popravka ostaje dostupna, ali se spušta u pomoćni kontrolni sloj i ne glumi više sekundarnu radnu akciju

Copy mora prestati da govori da je sve CLI po defaultu. Sada postoje:

- desktop GUI tok
- CLI fallback

### Početna strana

Na početnoj, `OpenCode` zona takođe dobija isti par akcija:

- `Otvori OpenCode`
- `Izolovani workspace`

Tuning Lab više nije sekundarna akcija te kartice; on ostaje sekundarni alat niže u hijerarhiji.

## VRAM fit / Opšta podešavanja hi-fi raspored

Odobreni raspored se implementira kao tri široka deck modula jedan ispod drugog.

### Red 1: Menjanje

Prvi red je `mixer`:

- glavne parametre treba vizuelno tretirati kao kanale / kontrole
- ne kao gomilu običnih kartica

Minimalni fokus u tom redu:

- GPU layers override
- context za VRAM fit
- glavni inference signal koji objašnjava šta trenutno menjaš

Ako TurboQuant utiče na isti VRAM fit scenario, njegova relevantna pomoć ostaje prisutna, ali ne sme da zatrpa prvi red.

### Red 2: Primena i snimanje

Drugi red je `transport deck` i sadrži tri kontrole:

- `▣ Sačuvaj bez primene`
- `▶ Primeni postojeće`
- `▣ + ▶ Sačuvaj i primeni`

Vizuelna semantika:

- `Sačuvaj bez primene` = snimanje u config
- `Primeni postojeće` = restart/pokretanje po poslednjem sačuvanom stanju
- `Sačuvaj i primeni` = kombinovana `REC + PLAY` logika

Ovo je ključna UX tačka jer korisnik mora da razlikuje:

- izmenu u editoru
- upis u config
- stvarnu primenu na živi runtime

### Red 3: Monitoring

Treći red služi za posmatranje i potvrdu:

- sačuvano vs editor stanje
- primenjeno vs neprimenjeno
- VRAM fit procene
- runtime signal

Tu idu:

- monitoring trake
- compare kartice
- status chipovi
- helper copy koji tumači rezultat

Treći red ne sme da glumi editor i ne sme da sadrži glavna akcijska dugmad.

## Dizajn jezik

Vizuelni jezik ostaje:

- hi-fi `B` smer
- pločastiji horizontalni moduli
- manje klasičnih web kartica
- jasniji `faceplate / deck / transport` karakter

Za `Sačuvaj i primeni` ne koristi se `reload` logika, nego isključivo `REC + PLAY` logika bez muljavih duplih senki.

## Uspeh

Ova iteracija je uspešna kada:

- korisnik u `OpenCode` zoni jasno vidi razliku između rada nad pravim projektom i rada u sandbox-u
- izolovani režim otvara stvarni odvojeni workspace
- `Tuning Lab` nastavlja da radi bez regresije
- `VRAM fit` više ne deluje kao dugačak zid kartica, nego kao jasan hi-fi tok:
  - menjanje
  - primena
  - monitoring


