# Local AI Control Center Stable

Clean restart repo for building a stable `Local AI Control Center`.

This repository exists to prioritize:

- stable installer behavior
- transparent runtime setup
- reliable model bootstrap
- reliable OpenCode integration
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

The current goal is not feature expansion. The goal is a trustworthy installer and runtime product.

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

## Current Slice Status

The current Windows installer/runtime milestone is complete for this repository scope.

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
- final installer/runtime completion gating through `product_installation_status`
- human-readable logging and JSON reporting

The current `recommended-6gb` default is `gemma-4-E4B-it-Q4_K_M.gguf`, pinned from the public Hugging Face GGUF derivative at `StageMind/gemma-4-e4b` for the upstream `google/gemma-4-E4B-it` model family.

This repository still does not claim:

- portal or browser UI flows
- update UX or catalog UX
- Linux parity
