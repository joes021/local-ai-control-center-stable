# Windows Real-World Test Checklist - 2026-05-25

## Scope

Ova checklist-a je namenjena za stvarno korisnicko testiranje Windows proizvoda iz grane `codex/panel-integration`, nakon release-a `v0.4.31`.

Cilj nije samo da se proveri da li "nesto radi", nego da se potvrdi da je ceo installer-managed proizvod pouzdan u realnom toku:

- instalacija
- update
- runtime
- modeli
- OpenCode
- Browser
- Search
- Knowledge
- Compatibility
- Benchmark

## Test discipline

Za svaku stavku zabelezi:

- `PASS`
- `PARTIAL`
- `FAIL`

Ako je `PARTIAL` ili `FAIL`, zabelezi:

- tacan korak
- sta si ocekivao
- sta se stvarno desilo
- screenshot ili poruku iz UI-ja

## Test environment

Pre pocetka zabelezi:

- masina
- CPU
- GPU
- VRAM
- RAM
- da li je `TurboQuant` predvidjen da radi na toj masini
- da li postoji `WSL`
- da li postoji internet konekcija
- da li postoji `SearxNG` manual URL ili ces koristiti managed `Windows + WSL` setup

## Pre-flight checks

1. Preuzmi aktuelni installer:
   - `LocalAIControlCenterSetup-v0.4.31.exe`
2. Potvrdi da stari panel nije ostao zalepljen u cudnom stanju.
3. Ako testiras update put:
   - zabelezi verziju sa koje kreces
4. Ako testiras fresh install:
   - koristi novi ili ocisceni install root

## Fresh install

1. Pokreni installer dvoklikom.
   - Ocekivanje:
     - vidi se installer prozor
     - koraci i poruke su citljivi
2. Prodji kroz install root izbor.
   - Ocekivanje:
     - default root je jasan
     - custom root radi
3. Prodji kroz model bootstrap izbor.
   - Ocekivanje:
     - preporuceni model je jasno oznacen
     - izbor je razumljiv
4. Zavrsni install tok.
   - Ocekivanje:
     - vidi se progress
     - na kraju installer prijavljuje uspeh ili iskren razlog neuspeha
5. Posle install-a pokreni panel.
   - Ocekivanje:
     - `http://127.0.0.1:3210/` radi
     - Home se otvara bez greske

## Upgrade path

1. Pokreni novi installer preko postojece instalacije.
   - Ocekivanje:
     - nudi ili prepoznaje `Upgrade`
2. Zavrsetak update-a.
   - Ocekivanje:
     - nema nevidljivog install toka
     - panel posle update-a vraca novu verziju
3. Proveri:
   - Start Menu precicu
   - Desktop precicu
   - uninstall entry

## Home and status truth

1. Otvori `Home`.
   - Ocekivanje:
     - status kartice nisu prazne
     - aktivni model je jasan
     - runtime status nije lazno `started`
2. Ako server ne radi:
   - Ocekivanje:
     - UI to iskreno kaze
3. Ako server radi:
   - Ocekivanje:
     - health je `ok`
     - port je prikazan

## Server tab

1. Klikni `Start server`.
   - Ocekivanje:
     - runtime stvarno predje u `warming -> started`
2. Klikni `Stop server`.
   - Ocekivanje:
     - runtime predje u `stopped`
3. Klikni `Restart`.
   - Ocekivanje:
     - stop/start ciklus prodje bez zaglavljivanja
4. Ako je aktivan `TurboQuant`:
   - Ocekivanje:
     - ako moze da radi na toj masini, server se stvarno podigne
5. Ako je aktivan neprimeren model:
   - Ocekivanje:
     - dobijes iskren razlog, ne lazni `warming` bez kraja

## Runtime switch

1. Prebaci na `llama.cpp`.
   - Ocekivanje:
     - izbor se sacuva
     - runtime zaista postane `llama.cpp`
2. Prebaci na `TurboQuant`.
   - Ocekivanje:
     - ako hardver podrzava, runtime zaista postane `TurboQuant`
     - ako ne podrzava, dobijes jasan razlog

## Models tab

1. Proveri lokalni katalog.
   - Ocekivanje:
     - aktivni model je jasno oznacen
     - skinuti modeli su jasno oznaceni
2. Aktiviraj mali/upotrebljiv model.
   - Ocekivanje:
     - aktivacija uspe
3. Aktiviraj tezi/rizican model.
   - Ocekivanje:
     - dobijes upozorenje:
       - `Ovaj model verovatno nece moci da radi ili ce raditi lose na ovoj masini.`
     - aktivacija ne krece odmah
     - tek posle eksplicitne potvrde ide forsirani pokusaj
4. Probaj model koji stvarno ne bi trebalo da stane.
   - Ocekivanje:
     - aktivni model ostaje prethodni
     - poruka je jasna
5. `Delete` tok.
   - Ocekivanje:
     - uklanjanje iz liste i/ili sa diska radi smisleno

## Browser tab

1. Pretraga po family/model nazivu.
   - Ocekivanje:
     - rezultati imaju smisla
2. Filter po quant-u.
   - Ocekivanje:
     - npr. `IQ2_XXS` ne nestaje bez razloga
3. Sort po:
   - `quant`
   - `size`
   - `last update`
   - Ocekivanje:
     - radi dosledno
4. `Add` model iz Browser-a.
   - Ocekivanje:
     - model ulazi u lokalni katalog
5. `Download`.
   - Ocekivanje:
     - progress se menja
     - nema laznog zalepljenog `downloading`
     - po zavrsetku status je istinit

## Compatibility tab

1. Otvori `Compatibility`.
   - Ocekivanje:
     - tab je odmah vidljiv i upotrebljiv
2. Proveri `Active model`.
   - Ocekivanje:
     - prikazuje:
       - fit status
       - headroom
       - preporuceni runtime
3. Proveri jedan remote model.
   - Ocekivanje:
     - procena ima smisla za taj hardver
4. Ako model ne fituje:
   - Ocekivanje:
     - to je jasno istaknuto i poklapa se sa Models aktivacijom

## OpenCode

1. Klikni `Open OpenCode`.
   - Ocekivanje:
     - otvara se vidljiv prozor
2. Ako runtime nije spreman:
   - Ocekivanje:
     - backend se pripremi ili se jasno prijavi razlog
3. Posalji jednostavan prompt.
   - Ocekivanje:
     - dobija se odgovor
4. Promeni aktivni model pa otvori novi OpenCode session.
   - Ocekivanje:
     - novi session preuzima novi model

## Search

1. Otvori `Search`.
2. Proveri da li pise da li je provider podesen.
   - Ocekivanje:
     - nema lazne pretpostavke `127.0.0.1:8080`
3. Ako koristis managed provider:
   - pokreni `Setup managed SearxNG (Windows + WSL)`
   - Ocekivanje:
     - posle setup-a provider predje u zdravo stanje
4. `Find web sources`.
   - Ocekivanje:
     - rezultati su smisleni i klikabilni
5. `Search + answer locally`.
   - Ocekivanje:
     - dobijes finalni odgovor, ne samo listu izvora

## Knowledge

1. Dodaj folder ili dokument source.
   - Ocekivanje:
     - source se registruje
2. Pokreni indeksiranje.
   - Ocekivanje:
     - dokumenti postanu queryable
3. Testiraj:
   - `documents-only`
   - `documents+web`
   - `web-only`
   - Ocekivanje:
     - razlika medju rezimima je jasna

## Benchmark

1. Otvori `Benchmark`.
   - Ocekivanje:
     - tab postoji u instaliranoj aplikaciji
2. Pokreni `short` run.
   - Ocekivanje:
     - run prodje `queued -> running -> done`
3. Pokreni `medium` run.
   - Ocekivanje:
     - rezultat se sacuva
4. `Compare selected runs`.
   - Ocekivanje:
     - compare prikaz ima smisla
5. `Export JSON` i `Export CSV`.
   - Ocekivanje:
     - fajlovi se izvezu bez greske

## Settings

1. Proveri profile.
   - Ocekivanje:
     - built-in i user profiles rade
2. Sacuvaj custom profil.
   - Ocekivanje:
     - novi profil ostaje dostupan posle refresh-a
3. Proveri `Context` i `Output tokens`.
   - Ocekivanje:
     - dropdown i `custom` tok rade smisleno
4. Proveri Search/SearxNG deo.
   - Ocekivanje:
     - `Managed local SearxNG (Windows + WSL)` je jasno odvojen od manual URL-a

## Repair and Logs

1. Otvori `Logs`.
   - Ocekivanje:
     - ne puca
2. Otvori `Repair`.
   - Ocekivanje:
     - osnovne akcije i statusi su razumljivi

## Updates

1. `Check updates`.
   - Ocekivanje:
     - jasna poruka da li postoji novija verzija
2. `Install update` kada postoji noviji release.
   - Ocekivanje:
     - vidi se progress
     - installer prozor je vidljiv

## Exit criteria

Windows liniju smatramo dovoljno mirnom za prelazak na Ubuntu x64 ako:

- fresh install prodje
- upgrade prodje
- `llama.cpp` radi
- `TurboQuant` radi na masini koja ga podrzava
- `OpenCode` radi
- `Browser` add/download radi
- `Search` radi
- `Knowledge` radi
- `Compatibility` daje smislen signal
- `Benchmark` radi
- nema laznih statusa tipa `downloading`, `warming`, `started`

## Known intentional boundaries

- `MTP` modeli nisu univerzalno podrzani na svakom hardveru
- cloud `opencode` provider ne prolazi kroz lokalni search proxy
- managed `SearxNG` lokalni setup koristi `Windows + WSL`
