# Local AI Control Center Stable

Clean restart repo for building a stable `Local AI Control Center`.

This repository now prioritizes:

- stable installer behavior
- transparent runtime setup
- reliable model bootstrap
- reliable OpenCode integration
- reliable local control panel behavior
- clear logs and diagnostics

Working principle:

- stable core first
- shell and polish second

## Repository Layout

- `docs/requirements/PRODUCT_REQUIREMENTS.md`
  - locked product requirements
- `docs/plans/2026-05-20-implementation-plan.md`
  - initial execution plan

## Current Scope

Priority order:

1. Windows
2. Ubuntu x86_64
3. Ubuntu arm64

The current goal is a trustworthy installer, runtime, and local control panel product.

## Development Setup

Use an editable install for local development:

```powershell
python -m pip install -e .[dev]
```

Run the test suite with:

```powershell
python -m pytest
```

## Manual Bootstrap From Checkout

For a manual installer run straight from a clean checkout, use the PowerShell launcher:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\install.ps1
```

The launcher is intentionally thin. It should:

- resolve the repo root from `bootstrap/`
- find `python` or fall back to `py`
- set a process-local `PYTHONPATH` that includes `src`
- hand off to the Python installer module without an import error

Smoke checklist:

- the launcher reaches the installer prompts from a repo checkout
- if Python is missing, the launcher asks whether to attempt Python installation and then exits cleanly because this slice cannot continue without Python bootstrap
- cancelling the questionnaire exits without a Python import traceback

## Windows Release Installer

For end users on Windows, the preferred artifact is a single executable installer:

- `LocalAIControlCenterSetup-v<version>.exe`

That executable is intended to be launched with a double-click and should run the full installer flow without requiring ZIP extraction or a manual PowerShell command.

The installer window should remain open at the end of the run so the user can read the final success or failure output and press Enter to close it.

For the packaged Windows installer, the core installation path is based on bundled Python plus prebuilt runtime artifacts. It should not block on developer-only tools such as `git`, `Node.js`, or local C/C++ build toolchains.

## Control Panel

The installed Windows product now includes a local web control panel:

- default URL: `http://127.0.0.1:3210/`
- persistent launcher: `control-center/Open-Control-Center.cmd` inside the install root
- persistent runtime host: `control-center/LocalAIControlCenterPanel.exe`

The installer is expected to:

- deploy the persistent control panel runtime into the install root
- auto-launch the control panel after a successful installation
- keep panel truth tied to installer-managed config, runtime, model, and OpenCode artifacts

The control panel currently focuses on the reliable core path:

- `Home`
- `Server`
- `OpenCode`
- `Models`
- `Settings`
- `Logs`
- `Repair`

The first stable panel version intentionally does not expose unfinished `Browser`, `Benchmark`, or `Updates` flows in the main navigation.

## Current Product Status

The current Windows installer/control-panel milestone is complete for this repository scope.

This repository now delivers:

- the numbered installer questionnaire contract
- truthful dependency bootstrap and blocking/failure classification
- three manifest-backed starter model tiers: `recommended-6gb`, `recommended-12gb`, and `recommended-24gb`
- pinned `llama.cpp` runtime payload preparation
- durable active-model, model-locations, and runtime-endpoint configuration in the install root
- one planned sequential download queue with installer-managed progress output
- canonical installer-managed runtime endpoint verification
- installer-managed `OpenCode` artifact preparation
- installer-managed `OpenCode` live-route verification against the active local runtime/model route
- bounded first-run end-user `OpenCode` smoke against the persisted managed configuration
- installer-managed packaged Windows `TurboQuant` installation for supported NVIDIA x64 systems, with truthful non-hard-fail status reporting
- integrated local control panel packaging, deployment, and auto-launch
- truthful runtime/model/OpenCode/TurboQuant status views in the local control panel
- reliable model activation, local/Hugging Face/Unsloth registration, and download progress in the control panel
- installer-truth-backed settings, OpenCode presets, and TurboQuant presets in the control panel
- final installer/runtime completion gating through `product_installation_status`
- human-readable logging and JSON reporting

The current `recommended-6gb` default is `gemma-4-E4B-it-Q4_K_M.gguf`, pinned from the public Hugging Face GGUF derivative at `StageMind/gemma-4-e4b` for the upstream `google/gemma-4-E4B-it` model family.

This repository still does not claim:

- Linux parity
