# Settings + Compatibility + Benchmark home-shell spec

## Cilj

Tri ekrana treba da prate isti UX jezik kao početna strana:

- bez bočnog rail-a koji vizuelno cepa sadržaj
- bez mrtvih ili dupliranih kartica
- sa jasnim horizontalnim signalom odmah ispod header-a
- sa glavnim radnim modulima preko pune širine ekrana

## Zajednički obrazac

Svaka strana dobija isti raspored:

1. `PageFlowCard` kao kratko objašnjenje toka rada.
2. Horizontalni status deck sa 4-5 kartica koje predstavljaju stvarno stanje te strane.
3. Horizontalni action strip sa stvarnim klikovima.
4. Glavni moduli složeni vertikalno, preko pune širine.

## Settings

- Dodati status deck za:
  - aktivni profil
  - context
  - search provider
  - temu
  - TurboQuant stanje
- Dodati action strip za skok na:
  - opšta podešavanja
  - VRAM fit
  - pretragu
  - TurboQuant
- Zadržati postojeće deck module, ali ih vezati za novi vrh strane.

## Compatibility

- Ukloniti `SecondaryActionRail`.
- Na vrhu prikazati status deck za:
  - aktivni model
  - lokalni katalog
  - udaljeni katalog
  - snimak sistema
  - trenutni fit
- Dodati action strip za:
  - aktivni model
  - otvaranje Modela
  - otvaranje Browser kataloga
  - otvaranje izvornog linka
- Kalkulator i izbor izvora ostaju glavni sadržaj preko cele širine.

## Benchmark

- Ukloniti `SecondaryActionRail`.
- Na vrhu prikazati status deck za:
  - stanje run-a
  - scenario
  - throughput
  - bateriju
  - profil
- Dodati action strip za:
  - pokretanje izabranog testa
  - pokretanje cele baterije
  - otvaranje Tuning Lab-a
  - otvaranje logova
  - izvoz
- Zadržati grafikon, istoriju i telemetriju, ali da svi žive u punoj širini bez desnog bočnog bloka.

## Dizajn pravila

- Sve akcije moraju da budu stvarne, bez placeholder kartica.
- Horizontalne kartice u istom redu moraju da imaju jednaku visinu.
- Tekst mora da ostane čitljiv na tamnoj hi-fi podlozi.
- Raspored mora da preživi desktop širinu bez preklapanja i bez nepotrebnog praznog prostora.
