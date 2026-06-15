# Tuning Lab B-Light Shell Design

**Datum:** 2026-06-15  
**Status:** odobreno za implementaciju  
**Cilj:** presložiti `Tuning Lab` tako da vizuelno i UX-logički prati novu Početnu stranu: jasan vrh sa signalom i sledećim korakom, glavni tri-slot deck u centru, a batch, eksperiment, progres i istorija kao sekundarni moduli bez placeholder osećaja.

## Problem

`Tuning Lab` trenutno ima sve bitne funkcije, ali ih prikazuje kao previše ravnopravne blokove:

- korisnik ne vidi odmah gde počinje glavni tok
- cockpit, batch, eksperiment, tri slota i istorija deluju kao odvojeni svetovi
- isti tip objašnjenja se ponavlja na više mesta
- deo kartica više objašnjava ekran nego što vodi na sledeću akciju
- ekran je funkcionalan, ali nije dovoljno čitljiv kao Početna strana

## Dizajn smer

Usvaja se `B-light` pristup:

- zadržavamo postojeće funkcije i backend tokove
- ne lomimo postojeći tri-slot receiver rack
- uvodimo jaču hijerarhiju sekcija po uzoru na Početnu
- uklanjamo osećaj da svaki blok “traži jednaku pažnju”
- svaki veliki modul mora da ima jednu jasnu ulogu

## Ciljni raspored

`Tuning Lab` strana treba da se čita ovim redom:

1. `Tuning Lab signal i spremnost`
2. `Aktivni run cockpit`
3. `Tri slota`
4. `Batch tok`
5. `Eksperiment`
6. `Progres i red čekanja`
7. `Istorija`

## Uloge sekcija

### 1. Signal i spremnost

Gornji modul treba odmah da odgovori:

- da li je runtime spreman
- da li je OpenCode spreman
- koji model i workspace su aktivni
- da li postoje blockeri za queue

Ovaj modul ne sme da bude dugačak i ne sme da duplira batch ili istoriju.

### 2. Aktivni run cockpit

Cockpit ostaje zaseban i važan, ali treba da bude predstavljen kao “live deck”, ne kao duga enciklopedija.

Zadržavamo:

- živi signal
- GPU offload dijagnostiku
- workspace / log / komande
- workspace preview
- OpenCode sesiju uživo

Smanjujemo:

- ponavljanje objašnjenja
- pomoćne kartice koje ne vode ka sledećem čitanju

### 3. Tri slota

Tri-slot receiver rack ostaje centralni glavni modul i ne sme biti potisnut ispod sekundarnih tokova. On ostaje “glavni radni dek”.

### 4. Batch tok

Batch deo ostaje jasan operativni tok:

- učitaj task
- pokreni task
- otvori rezultat

Treba da deluje kao kontrolni deo, ne kao tekstualni opis sistema.

### 5. Eksperiment

Eksperiment ostaje mesto za napredna podešavanja i ručno menjanje task-a, workdir-a i success check lanca. To je “edit deck”, a ne početni ekran.

### 6. Progres i red čekanja

Ovaj deo treba da bude sažet i praktičan:

- aktivni run
- queue status
- jasan sledeći korak

Ne treba da glumi drugi cockpit.

### 7. Istorija

Istorija ostaje puna po funkciji, ali treba da bude najniže jer je retrospektiva, ne prvi tok rada.

## Pravila za polish

- svaka velika sekcija mora da ima samo jednu glavnu poruku
- pomoćni tekst ide tek posle akcije, ne ispred nje
- hi-fi jezik ostaje: faceplate, deck, signal, rack
- bez mrtvih placeholder kartica
- bez duplih “objašnjavajućih” zona koje ne menjaju ponašanje korisnika
- zadržati sve postojeće akcije

## Van opsega

Ova iteracija ne menja:

- backend queue logiku
- winner logiku
- sadržaj istorije
- tri-slot parametre
- Tuning Lab API ugovore

Menja samo:

- raspored
- hijerarhiju
- tekstualni signal
- vizuelni odnos modula
