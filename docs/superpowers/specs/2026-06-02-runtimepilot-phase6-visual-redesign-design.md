# RuntimePilot Phase 6 Visual Redesign

## Cilj

Portal treba da izgleda kao novi proizvod i kada se izuzme header. Vizuelni identitet mora da se vidi kroz navigaciju, zajedničke sekcije, telemetry blokove i početni ekran, tako da korisnik dobije utisak komandnog mosta umesto običnog admin panela.

## Problem

Trenutni rebrand je uglavnom ostao na:

- novom RuntimePilot headeru
- novim ikonama prečica
- jačem shell okviru

Unutrašnje kartice i tokovi još koriste stari vizuelni jezik, pa korisnik ne vidi dovoljno grafičke razlike.

## Rešenje

Phase 6 uvodi vidljive RuntimePilot elemente u zajedničke UI slojeve:

1. Navigacija dobija ikone i mali dvoredni cockpit raspored, tako da svaka sekcija izgleda kao deo jedinstvenog runtime panela.
2. Shell markeri i page shell dobijaju jače grafičke akcente, uključujući ikonice, signal linije i diskretnu instrument-panel dekoraciju.
3. Zajedničke sekcije kao što su `PageFlowCard`, `TelemetryPanel` i početne status kartice dobijaju RuntimePilot badge/glyph elemente umesto generičnog teksta.
4. Početna strana dobija jasniji `mission control` sloj sa vizuelno izdvojenim overview karticama.

## Granice

Ovaj krug ne menja:

- backend ponašanje
- informacione tokove i API ugovore
- dublji interni rename paketa i foldera

## Validacija

Uspeh ovog kruga znači:

- da se grafičke izmene vide odmah na početnoj i kroz glavnu navigaciju
- da testovi potvrde prisustvo novih RuntimePilot vizuelnih klasa i teksta u `frontend_dist`
- da localhost pregled jasno pokaže više od samog header rebrand-a
