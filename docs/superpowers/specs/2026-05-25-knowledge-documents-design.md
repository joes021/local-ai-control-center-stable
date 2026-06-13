# Knowledge / Documents Design

Datum: 2026-05-25

## Cilj

Dodati prvi pravi `Knowledge / Documents` workspace u `Local AI Control Center` tako da korisnik moze da:

- prijavi lokalne fajlove i foldere kao knowledge izvore
- indeksira ih bez rucne instalacije dodatnog alata
- pretrazuje dokumente lokalno
- trazi odgovor od aktivnog lokalnog modela nad dokumentima
- opciono spoji `documents + web` u istom answer toku

Ovaj slice ne menja runtime truth model. I dalje postoji jedan installer-managed runtime i jedan kanonski aktivni model.

## Product truth

Prva verzija mora da bude poštena i uska:

- knowledge indeks je lokalni i installer-managed
- korisnik ne instalira nista rucno
- dokumenti ostaju na korisnickom disku; u indeks se cuva samo izracunat tekst i metadata potrebna za pretragu
- cloud `opencode` provider se ovde ne dira
- `Knowledge` odgovor ide kroz isti lokalni runtime kao i `Search answer`

## Arhitektura

Dodaje se poseban knowledge sloj:

- `knowledge_service.py`
- `knowledge` API rute
- `KnowledgePage.tsx`

Sloj ima tri odgovornosti:

1. upravljanje izvorima
2. indeksiranje i lokalna FTS pretraga
3. answer orchestration nad pronadjenim dokumentima, sa opcijom da se doda i web context

## Skladiste i truth fajlovi

Novi installer-managed artefakti:

- `config/control-center/knowledge-sources.json`
  - lista fajlova/foldera koje je korisnik prijavio
- `config/control-center/knowledge-history.json`
  - kratka istorija knowledge query i answer zahteva
- `config/control-center/knowledge-index.sqlite3`
  - SQLite baza sa dokument metadata i FTS tabelom

## Podrzani formati

Prvi produkcioni slice podrzava:

- `txt`
- `md`
- `markdown`
- `json`
- `csv`
- `html`
- `htm`
- `py`
- `js`
- `ts`
- `tsx`
- `jsx`
- `css`
- `log`
- `docx`
- `pdf`

Za `docx` koristimo parser baziran na ZIP/XML standardnoj biblioteci.
Za `pdf` koristimo `pypdf`, spakovan kroz installer zavisnosti.

Ako fajl ne moze da se procita:

- ne obara ceo run
- ostaje u source summary-ju kao skipped/error stavka

## Indeks model

SQLite cuva:

- jedan red po dokumentu
- source path
- display name
- file size
- modified time
- file type
- status
- extracted text
- extracted char count

FTS se koristi za:

- brzu lokalnu full-text pretragu
- ranking po jednostavnom relevance signalu

Nije cilj da odmah uvodimo embeddings ni vektorsku bazu.

## Sources UX

Prva verzija koristi eksplicitan lokalni path unos:

- `Add folder path`
- `Add file path`
- `Reindex`
- `Remove`

Za svaki source prikazujemo:

- path
- type
- status
- broj indeksiranih dokumenata
- broj gresaka/skipped stavki
- poslednji index timestamp

## Query i answer modovi

Knowledge workspace podrzava tri answer mod-a:

- `documents-only`
- `documents+web`
- `web-only`

Semantika:

- `documents-only`
  - radi samo lokalnu FTS pretragu
- `documents+web`
  - radi dokument query, zatim poziva postojeci shared web search sloj
  - oba konteksta ulaze u prompt
- `web-only`
  - practical handoff na postojeci Search answer tok, ali kroz isti workspace

## Prompt augmentation

Knowledge answer koristi sistemski blok sa:

- kratkim pravilima da model ne izmislja
- listom dokumenata
- snippet-ima i putanjama

Ako je ukljucen i web:

- web context ostaje odvojen od doc context-a
- model dobija jasno obelezene sekcije:
  - `Local documents`
  - `Web results`

## Boundaries

Ovaj slice namerno ne pokriva:

- live watch/sync fajlova u realnom vremenu
- OCR za skenirane PDF-ove/slike
- embeddings / semantic search
- OpenCode cloud provider knowledge tool
- remote file share browse UX

## Validation gate

Feature nije gotov dok ne prodje:

- source add/remove
- reindex
- text extraction za plain text, docx i pdf
- local query
- local answer nad dokumentima
- `documents+web` answer tok
- frontend build
- full pytest
- Windows installer build
- lokalni upgrade na ovoj masini

## Nesto sto mora ostati istinito

Kada knowledge nije indeksiran ili nema pogodaka:

- UI ne sme da glumi da ima context
- answer tok mora da vrati kratku i jasnu poruku

Kada je runtime nedostupan:

- knowledge answer ne sme da glumi da radi
- query kroz dokumente i dalje sme da radi, jer ne zavisi od runtime-a


