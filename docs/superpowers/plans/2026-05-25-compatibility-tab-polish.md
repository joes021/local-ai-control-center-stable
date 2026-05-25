# Compatibility Tab Polish Plan

## Scope

Napraviti vidljiv i isporucen Compatibility tab, ispolirati ga u dva prolaza i zavrsiti pun Windows release tok:

1. dedicated tab i stranica
2. UX polish pass 1
3. UX polish pass 2
4. testovi i frontend build
5. installer build
6. lokalni upgrade ove masine
7. live smoke u instaliranoj aplikaciji
8. commit + push + GitHub release

## Koraci

### Task 1 - Compatibility kao first-class page
- dodati `Compatibility` u glavnu navigaciju
- napraviti `CompatibilityPage.tsx`
- refaktorisati calculator body da ga koriste i modal i stranica

### Task 2 - Source pickeri i sistemski snapshot
- aktivni model quick entry
- local catalog picker
- remote catalog picker sa search/source filterom
- ugradjeni system snapshot pregled

### Task 3 - Polish pass 1
- empty states
- helper copy
- recommendation tok
- bolji raspored akcija

### Task 4 - Polish pass 2
- vizuelna hijerarhija
- kompaktnost
- povezanost sa `Models` i `Browser`

### Task 5 - Validation
- ciljane testove pustiti prvo
- onda pun `python -m pytest -q`
- `npm --prefix frontend run build`
- `python -m build`
- `packaging/build_windows_installer.ps1 -PythonExe python`
- lokalni installer upgrade
- live smoke na `127.0.0.1:3210`

### Task 6 - Release
- bump verzije
- commit
- push
- GitHub release sa novim `.exe`
