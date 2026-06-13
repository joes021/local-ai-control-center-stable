# Ubuntu x86_64 Installer Design

Date: 2026-05-24

## Goal

Preneti postojeći installer-managed proizvod na `Ubuntu x86_64` bez menjanja njegovog truth modela:

- jedan installer-managed install root
- jedan installer-managed lokalni runtime endpoint
- jedan kontrolni panel na fiksnom lokalnom UI portu
- isti model lifecycle i `OpenCode` ugovor kao na Windows-u

Ovaj slice nije “novi Linux proizvod”, nego Ubuntu x64 port istog proizvoda koji je već zatvoren kao Windows release candidate.

## Product truth that must remain identical

Ubuntu x64 put mora da zadrži ista tvrđenja kao Windows:

- instalacija je uspešna samo ako su spremni:
  - `Control Center`
  - `llama.cpp`
  - `OpenCode`
  - najmanje jedan upotrebljiv model
- aktivni model mora da se propagira ka `OpenCode`
- panel mora istinito da prikazuje:
  - runtime status
  - health
  - aktivni runtime
  - port
  - aktivni model
- `Browser`, `Models`, `Updates` i `Settings` ostaju isti proizvodni slojevi, ne novi Linux-only tokovi

## Install layout

Podrazumevani Ubuntu x64 install root:

- `~/local-ai-control-center`

Glavne putanje:

- install root: `~/local-ai-control-center`
- models: `~/local-ai-control-center/models`
- config: `~/local-ai-control-center/config`
- logs: `~/local-ai-control-center/logs`
- control center launcher: `~/local-ai-control-center/control-center/Open-Control-Center.sh`
- control center host: `~/local-ai-control-center/control-center/local-ai-control-center-panel`

UI ostaje na:

- `http://127.0.0.1:3210/`

Runtime endpoint ostaje installer-managed lokalni loopback URL na dinamički izabranom portu.

## Installer shape

Ubuntu x64 installer treba da ostane tekstualni i numbered, kao Windows installer, ali prilagođen shell okruženju:

- tanki shell launcher
- Python core installer
- isti numbered prompt contract
- isti jasan finalni outcome
- isti log + JSON report

Ne pravimo poseban GUI installer za ovaj slice.

## Platform assumptions to isolate

Windows-specifične pretpostavke moraju biti eksplicitno odvojene:

- `.exe` launcher i PyInstaller shell integration
- Start Menu / Desktop shortcut logika
- Windows uninstall registry entry
- Windows process creation flags
- `CREATE_NEW_CONSOLE` / `CREATE_NO_WINDOW`
- Windows runtime DLL sidecar provere

Ubuntu x64 mora da uvede Linux pandan samo gde je potreban:

- `.sh` launcheri umesto `.cmd`
- opcioni `.desktop` fajlovi umesto Start Menu registra
- `subprocess` bez Windows-specific flags
- Linux path, permissions i executable-bit pravila

## Runtime strategy

`llama.cpp` ostaje primarni runtime.

Ubuntu x64 port treba da podrži:

- installer-managed runtime payload
- server health verification
- server start/stop/restart kroz panel
- isti active-model i runtime-endpoint config format gde je razumno

Ako Linux zahteva poseban runtime manifest, treba ga uvesti kao novi manifest, a ne granati Windows manifest heuristikom.

## OpenCode strategy

`OpenCode` na Ubuntu x64 mora da ostane installer-managed komponenta.

Minimum za ovaj slice:

- installer-managed payload deploy
- managed config generation
- `OpenCode` launch iz panela
- connected/app-only truth u statusu
- first-run smoke kao na Windows-u

Ako Linux format pakovanja bude drugačiji od Windows-a, to mora biti izolovano u manifest i launcher sloju, ne u panel contract-u.

## TurboQuant strategy

Za `Ubuntu x86_64` ne uvoditi lažnu podršku.

Prihvatljiva stanja za prvi x64 slice su samo:

1. stvarno podržan i proverljiv Ubuntu x64 install path
2. eksplicitno nepodržan sa jasnim statusom i razlogom

Ne uvoditi “placeholder success”.

## Updates strategy

Updates moraju ostati GitHub-release-backed i installer-managed.

Za Ubuntu x64 to znači:

- panel mora da prepozna latest Linux x64 artifact
- `Check updates` i `Install update` moraju da koriste Linux artifact, ne Windows `.exe`
- worker truth, progress, speed, ETA i installer-launch/handoff semantika ostaju iste

Ako prvi Ubuntu x64 slice još nema packaged updater artifact, to mora biti jasno označeno kao boundary, a ne prećutano.

## Validation gate

Ubuntu x64 ne sme biti proglašen spremnim dok ne prođe:

- fresh install
- upgrade
- starter model path
- Browser direct download path
- local model import path
- runtime switch path
- `OpenCode` launch path
- update path

Drugim rečima, isti validation checklist kao Windows RC, samo na Ubuntu x64.

## Explicit non-goals for this slice

- Ubuntu arm64 implementacija
- novi UI redizajn
- eksperimentalni MTP runtime support
- feature widening van postojećeg Windows scope-a


