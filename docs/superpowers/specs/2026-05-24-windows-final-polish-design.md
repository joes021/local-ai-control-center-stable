# Windows Final Polish Design

Date: 2026-05-24

## Goal

Zatvoriti preostale Windows produktske ivice tako da `Local AI Control Center` bude stvarno miran za spoljasnje testiranje pre bilo kakvog Ubuntu nastavka.

## Scope

Ovaj slice namerno pokriva samo Windows aplikaciju i javni Windows release tok:

- `Models` i `Browser` lifecycle istinu
- runtime i `OpenCode` operativnu istinu
- clean-machine i upgrade validaciju
- novi Windows release tek kada te stavke prodju zajedno

Van scope-a za ovaj sprint:

- Ubuntu x86_64 i Ubuntu arm64 implementacija
- dodatni veliki UI redizajn van onoga sto direktno podize pouzdanost
- nove eksperimentalne runtime mogucnosti

## Product Truth Contract

Windows panel ne sme da ostavi nijednu od sledecih sivih zona:

- model ne sme delovati kao bezbedan aktivni izbor ako runtime ne moze stvarno da ga podigne
- download ne sme delovati aktivno ako worker vise nije ziv
- `OpenCode` ne sme delovati upotrebljivo ako runtime nije spreman ili ako konekcija nije stvarna
- `Browser` i `Models` ne smeju imati divergentne akcione rezultate za isti model lifecycle
- panel i installer moraju ostaviti istu istinu o:
  - aktivnom modelu
  - aktivnom runtime-u
  - runtime portu
  - runtime health statusu
  - update/download statusu

## Design

### 1. Canonical model lifecycle

`Browser` i `Models` treba da koriste isti lifecycle recnik i isti backend truth sloj. To znaci:

- jedan kanonski progress payload za model download
- jasan `idle | starting | downloading | completed | canceled | error` tok
- nema regresije napretka za isti aktivni download
- nema lazno zalepljenog `downloading` statusa kad worker nije aktivan
- aktivacija modela ili:
  - uspeva i ostavlja runtime spremnim
  - ili biva odbijena sa preciznim razlogom pre nego sto ostavi sistem u polu-stanju

`MTP` GGUF varijante ostaju eksplicitno nepodrzane kao aktivni runtime modeli dok ne postoji stvaran produkcioni path za njih. To mora biti jasno u:

- action result payload-u
- panel statusu
- Browser/Models copy-u

### 2. Runtime/OpenCode operational truth

Panel treba da razlikuje najmanje tri stanja:

- aplikacija/proces postoji
- runtime proces postoji ali jos nije health-ready
- runtime je stvarno spreman i `OpenCode` moze da ga koristi

`OpenCode` akcije treba da rade po strogoj semantici:

- `open` prvo osigurava runtime readiness
- ako readiness ne uspe, korisnik dobija jasan failure razlog i sledeci korak
- status ne sme da ostane na "aktivan" ako postoji samo UI/proces bez funkcionalne konekcije

### 3. Release-candidate validation

Windows release se smatra kandidatom za spoljasnje testiranje tek kada prodju zajedno:

- fresh install
- upgrade install
- starter model path
- Browser direct download path
- local model import path
- runtime switch path
- `OpenCode` launch path
- update path

Validation zapis mora ostati u `docs/release-validation/` i README/release notes moraju odgovarati stvarnom stanju, ne optimisticnom tumacenju.

## Implementation Shape

Glavne jedinice ostaju iste, ali se dodatno zatezu:

- `models_service.py`
  - kanonski download/action truth
  - aktivacija i rollback/recovery istina
- `browser_sources.py` / `browser_catalog_service.py`
  - remote katalog robustnost i quant/source edge cases
- `server_service.py` / `status_service.py` / `opencode_service.py`
  - runtime readiness i panel truth
- `BrowserPage.tsx` / `ModelsPage.tsx` / `HomePage.tsx` / `OpenCodePage.tsx` / `ServerPage.tsx`
  - jasniji UI status i manje dvosmislenosti

## Testing Strategy

Pre svake relevantne produkcione izmene:

- napisati ili prosiriti failing regression test
- potvrditi da pada iz pravog razloga
- tek onda uraditi minimalnu implementaciju

Na kraju sprinta obavezno:

- `python -m pytest -q`
- `python -m build`
- `powershell -ExecutionPolicy Bypass -File .\packaging\build_windows_installer.ps1`

## Success Criteria

Sprint je zavrsen tek kada:

- `Models` i `Browser` vise ne ostavljaju zaglavljene ili lazne statuse
- nepodrzan model ne moze tiho da srusi runtime
- `OpenCode` i runtime statusi nisu kontradiktorni
- Windows fresh install i update path prodju na ovoj masini kao finalni kandidat
- novi Windows installer i release note-ovi odgovaraju stvarnom stanju proizvoda


