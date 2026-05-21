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

## Bootstrap Slice Status

This slice already delivers:

- the numbered installer questionnaire contract
- dependency bootstrap and blocking/failure classification
- human-readable logging and JSON reporting

This slice does not yet deliver:

- `llama.cpp`
- model download
- `OpenCode` verification
- a runnable server
