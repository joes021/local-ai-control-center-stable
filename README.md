# Local AI Control Center Stable

Installer-managed local control panel for running `llama.cpp`, `TurboQuant`, GGUF models, and `OpenCode`, with a finished Windows path and an Ubuntu x86_64 port in progress.

[![Latest release](https://img.shields.io/github/v/release/joes021/local-ai-control-center-stable?display_name=tag&label=latest%20release)](https://github.com/joes021/local-ai-control-center-stable/releases/latest)
[![Windows](https://img.shields.io/badge/platform-Windows-2ea043)](https://github.com/joes021/local-ai-control-center-stable/releases/latest)
[![Ubuntu x86_64](https://img.shields.io/badge/platform-Ubuntu%20x86__64%20(in%20progress)-d29922)](https://github.com/joes021/local-ai-control-center-stable)
[![Repository scope](https://img.shields.io/badge/scope-installer%20%2B%20control%20panel-c58a1f)](https://github.com/joes021/local-ai-control-center-stable)

## Download

Primary end-user artifact:

- [Download the latest Windows installer](https://github.com/joes021/local-ai-control-center-stable/releases/latest)

Current release:

- [LocalAIControlCenterSetup-v0.4.30.exe](https://github.com/joes021/local-ai-control-center-stable/releases/download/v0.4.30/LocalAIControlCenterSetup-v0.4.30.exe)

The Windows product is intended to be launched with a double-click. No ZIP extraction and no manual PowerShell command are required for the packaged installer path.

## What You Get

- a single Windows `.exe` installer
- bundled runtime preparation for `llama.cpp`
- packaged Windows `TurboQuant` path for supported NVIDIA x64 systems
- installer-managed `OpenCode` bootstrap and launch
- a local control panel at `http://127.0.0.1:3210/`
- local model catalog plus an internet-backed GGUF browser
- live benchmark throughput, averages, and history inside the control panel
- a shared `SearxNG` search workspace for local web results and local-model answers
- a local `Knowledge` workspace for installer-managed document indexing, query, and answer flows
- truthful logs, reports, and runtime status

## Product Screens

### Home

![Home overview](.github/assets/home-overview.png)

### Browser

![Browser catalog](.github/assets/browser-catalog.png)

### Settings

![Settings and profiles](.github/assets/settings-profiles.png)

## What This Repository Delivers

This repository focuses on one product path:

1. install the Windows product reliably
2. prepare runtime artifacts and starter models truthfully
3. open a usable local control panel
4. manage models and launch `OpenCode` against the installer-managed runtime

The current Windows milestone includes:

- numbered installer prompts with clear final outcome reporting
- starter model tiers for `recommended-6gb`, `recommended-12gb`, and `recommended-24gb`
- pinned runtime payload setup and verification
- durable runtime endpoint, active-model, and model-locations config
- installer-managed `OpenCode` bootstrap and live-route verification
- packaged Windows `TurboQuant` install path with required OpenSSL sidecar DLLs
- Start Menu, Desktop, and uninstall shell integration
- truthful runtime, model, `OpenCode`, and `TurboQuant` status in the panel
- Browser table for `Hugging Face` and `Unsloth` GGUF discovery
- installer-managed model download worker with progress tracking and error reporting
- settings, presets, and runtime preferences persisted through the control panel
- Benchmark tab with live throughput, averages, historical trend, and benchmark batteries
- shared `SearxNG` search layer for the `Search` tab and `OpenCode` `local-lacc` provider path
- installer-managed `Knowledge` workspace with local document indexing and `documents-only` / `documents+web` answer modes
- visible `Compatibility` workspace instead of a hidden calculator modal

The current default `recommended-6gb` starter model is `gemma-4-E4B-it-Q4_K_M.gguf`.

## Installed Product Layout

After a successful Windows install, the product provides:

- control panel URL: `http://127.0.0.1:3210/`
- runtime endpoint: installer-managed local endpoint
- panel launcher: `control-center/Open-Control-Center.cmd`
- panel host: `control-center/LocalAIControlCenterPanel.exe`
- `OpenCode` launcher: `control-center/Open-OpenCode.cmd`
- Start Menu folder: `Local AI Control Center`

The control panel currently exposes:

- `Home`
- `Server`
- `OpenCode`
- `Models`
- `Browser`
- `Knowledge`
- `Search`
- `Compatibility`
- `Benchmark`
- `Settings`
- `Logs`
- `Repair`

## Models vs Browser

The product keeps these flows separate on purpose:

- `Models`
  - local catalog, active model switching, local GGUF import, and direct registry management
- `Browser`
  - internet-backed GGUF discovery from `Hugging Face` and `Unsloth`, compatibility checks, and installer-managed download actions

## Search

The control panel now includes a dedicated `Search` workspace:

- backed by a shared `SearxNG` service layer
- able to return raw web results
- able to ask the active local model to answer using those web results as extra context
- shared with the installer-managed `OpenCode` `local-lacc` provider path

Important boundary:

- cloud `opencode` providers do not currently pass through the local `SearxNG` proxy layer

## Knowledge

The control panel now also includes a dedicated `Knowledge` workspace:

- add local file or folder paths as installer-managed knowledge sources
- index supported documents locally through a packaged SQLite FTS path
- query local documents directly
- ask the active local model to answer with:
  - `documents-only`
  - `documents+web`
  - `web-only`

Current scope:

- first release supports plain text-ish files, `docx`, and `pdf`
- document indexing stays local to the install root state
- cloud `opencode` providers are not yet wired into this local knowledge layer

## Build From Source

Editable development install:

```powershell
python -m pip install -e .[dev]
```

Run tests:

```powershell
python -m pytest
```

Build the packaged Windows installer:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows_installer.ps1
```

Manual bootstrap from a clean checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\install.ps1
```

Ubuntu x86_64 source bootstrap from a clean checkout:

```bash
chmod +x ./bootstrap/install.sh
./bootstrap/install.sh
```

Ubuntu x86_64 shell launcher truth currently provided by the source-bootstrap path:

- panel launcher: `control-center/Open-Control-Center.sh`
- panel host wrapper: `control-center/local-ai-control-center-panel`
- `OpenCode` launcher: `control-center/Open-OpenCode.sh`

## Repository Layout

- `bootstrap/`
  - thin PowerShell launcher for source checkout bootstrap
- `frontend/`
  - control panel frontend
- `src/local_ai_control_center_installer/`
  - installer, runtime orchestration, packaged backend, manifests, and release logic
- `tests/`
  - installer, runtime, control-panel, and packaging regression coverage
- `docs/requirements/PRODUCT_REQUIREMENTS.md`
  - locked product requirements

## Current Scope

Priority order:

1. Windows
2. Ubuntu x86_64
3. Ubuntu arm64

## Windows Test Checklist

Za sledeci ozbiljan real-world test koristi:

- [Windows real-world test checklist](docs/release-validation/2026-05-25-windows-real-world-test-checklist.md)

This repository currently claims a complete Windows installer + runtime + control-panel milestone for its own scope.

The Ubuntu x86_64 path currently includes:

- runtime and `OpenCode` manifest resolution
- shell bootstrap via `bootstrap/install.sh`
- Linux control-panel shell launchers and Linux picker integration

The Ubuntu x86_64 path does not yet claim a finished release artifact or a completed release-validation checklist.

This repository does not yet claim:

- Linux parity
- a finished Ubuntu product path
- every possible GGUF runtime variant as production-safe by default
- `MTP` GGUF variants as supported active runtime models in this Windows product

## Working Principle

- stable core first
- shell and polish second
