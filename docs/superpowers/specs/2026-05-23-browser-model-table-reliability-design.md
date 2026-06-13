# Browser Model Table Reliability Design

Date: 2026-05-23
Scope: Windows control panel model browser/table plus reliable internet-backed download flow

## Goal

The integrated Windows control panel must expose a real internet-backed model table so a user can:

- browse GGUF models from the internet
- see source, size, quantization, fit/compatibility hints, and source links
- add or directly download a model with one clear click path
- watch truthful progress and errors
- end with the model present in the installer-managed local catalog and available to OpenCode

This slice restores and hardens the `Browser` tab from the older panel instead of stretching the current `Models` page beyond its purpose.

## Product Truth

Two model surfaces now have distinct responsibilities:

- `Models`
  - installer-managed local catalog
  - curated starter models
  - locally registered custom Hugging Face / Unsloth entries
  - activation, local download status, delete, and local GGUF import

- `Browser`
  - internet-discovered GGUF catalog
  - source-first browsing across `Hugging Face` and `Unsloth`
  - compatibility entrypoint
  - add-to-local and direct download entrypoint

The browser table must never become a second independent model store. It is only an internet discovery layer that feeds the existing installer-managed local catalog.

## Source Contract

The first stable browser table uses these sources:

- `Hugging Face`
  - live catalog fetch from the Hugging Face models API
  - GGUF-only filtering
  - repo page links and direct file links

- `Unsloth`
  - live catalog fetch through the Hugging Face models API filtered to the `unsloth` author
  - GGUF-only filtering
  - repo page links and direct file links

Unsloth documentation remains a product reference for recommendations and interpretation, but the actual downloadable files still come from Hugging Face-hosted repos. The browser table should therefore expose:

- source label
- repo link
- direct file download URL
- family / quantization / size metadata

## Architecture

The existing `frontend/src/pages/BrowserPage.tsx` is restored to the main navigation instead of building a new table from scratch.

New backend pieces are added inside the current installer-managed control-center backend:

- `routes/browser.py`
  - `/api/browser/catalog`
  - `/api/browser/catalog/refresh`
  - `/api/browser/catalog/add`
  - `/api/browser/catalog/download`

- `routes/compatibility.py`
  - `/api/compatibility/check`
  - `/api/compatibility/apply`

- `services/browser_catalog_service.py`
  - browser cache load/store
  - merged refresh metadata
  - last-known fit persistence

- `services/browser_sources.py`
  - Hugging Face source fetch
  - Unsloth source fetch
  - GGUF normalization

- `services/compatibility_service.py`
  - compatibility calculation against current system/runtime/settings truth

The browser cache lives under installer-managed config:

- `config/control-center/browser-catalog-cache.json`

This keeps the browser table durable across app restarts without creating a second product state root.

## Download Reliability Contract

This is the highest-risk part of the slice and the main hardening target.

### Single canonical download path

Browser downloads must use the same existing installer-managed download engine as local catalog downloads:

- register or upsert the model into the local custom registry
- resolve a deterministic `localModelId`
- call the existing `download_model(localModelId)` path
- observe progress only through the canonical `/api/models/download-progress` payload

There must not be a second browser-specific file-transfer implementation.

### Deterministic local model identity

Remote model registration must return a stable `localModelId` directly, instead of relying on fuzzy post-hoc matching whenever possible.

That means:

- `add_hf_model(...)` returns `localModelId`
- `add_unsloth_model(...)` returns `localModelId`
- `/api/browser/catalog/add` and `/api/browser/catalog/download` both expose that ID in the action result

Fallback matching by filename may remain only as a defensive recovery path.

### Truthful progress and failure behavior

Clicking `Download` from the browser table must produce one of these truthful outcomes:

- `accepted`
  - local model registered or refreshed
  - download worker started
  - progress becomes active

- `completed`
  - file exists on disk
  - local catalog reflects `installed = true`

- `error`
  - download worker reports a concrete actionable message
  - browser table does not claim success
  - local catalog entry may remain registered, but not installed

The UI must never silently succeed or silently fail.

## Compatibility Contract

The browser table should expose a compatibility entrypoint for an internet model without requiring it to be already downloaded.

Compatibility is calculated on demand from:

- current installer-managed settings
- current system/runtime/TurboQuant truth
- model metadata normalized from the source record

The result is cached back into the browser catalog as the model’s last known fit state so the table can display:

- `Radi`
- `Granicno`
- `Ne radi`
- `Nije provereno`

This slice does not attempt a perfect or universal optimizer for every possible model. It aims for truthful, bounded guidance integrated with the current settings/runtime contract.

## UI Behavior

The main nav regains:

- `Browser`

The browser page remains a table-first internet model workflow with:

- source filter
- sort options
- table rows for internet models
- detail panel
- compatibility entrypoint
- `Add to local`
- direct `Download`
- shared progress card

`Models` remains available as the local catalog after a browser download completes.

## Non-Goals

This slice does not include:

- a giant crawler across arbitrary model websites
- full dynamic parsing of every possible model card field
- automatic optimal-parameter synthesis for every model family
- replacing the existing `Models` page

## Verification

Success requires all of the following:

- browser routes are live in the integrated backend
- `Browser` appears in the integrated control-panel navigation
- Hugging Face and Unsloth catalog data can be loaded or refreshed
- clicking browser `Download` truthfully registers the local model and starts the canonical download path
- completed browser downloads appear installed in the local catalog
- failures report actionable errors and do not silently disappear
- the integrated Windows installer still builds and packages the updated panel


