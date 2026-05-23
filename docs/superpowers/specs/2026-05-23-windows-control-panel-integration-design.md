# Windows Control Panel Integration Design

## Goal

Turn the stable Windows installer/runtime product into a finished local-first product that:

- installs all required runtime pieces and dependencies
- launches a reliable Local AI Control Center web panel after installation
- gives truthful live status for `llama.cpp` and `TurboQuant`
- makes model management and model download reliable
- makes runtime, model, OpenCode, and TurboQuant configuration reliable enough to support real local-AI presets

This design does not invent a new UI. It ports and stabilizes the existing `Local AI Control Center` panel against the installer-managed truth already implemented in this repository.

## Source of Truth

The control panel must not be allowed to drift from installer reality. The canonical truth for the integrated product is:

1. persisted installer-managed artifacts in the install root
2. persisted installer-managed configuration files
3. bounded live probes against the active runtime and the local host

The panel may display richer derived status, but it must never fabricate state that contradicts those sources.

### Canonical persisted artifacts

The integrated panel must read and respect the current installer-managed state already produced by this repo:

- `config/active-model.json`
- `config/runtime-endpoint.json`
- `config/opencode/managed-config.json`
- runtime artifact metadata
- TurboQuant artifact metadata
- installer logs and install reports

### Canonical live probes

Live status must be derived from bounded checks such as:

- active runtime process ownership
- loopback port binding
- `/health` response of the managed runtime
- local UI binding status
- Tailscale presence and Tailscale IP detection

The UI must clearly separate:

- configured identity
- live operational status
- action results

## Product Direction

The existing `joes021/local-ai-control-center` repository contains the target panel UX and page structure.
The existing `joes021/llm-service-monitor` repository contains useful service/monitoring primitives.

The best product path is:

- preserve the existing control panel UX direction
- transplant only the needed frontend and backend source
- re-anchor the backend on installer-managed truth from this repository
- selectively reuse service-monitor logic only where it strengthens runtime/network/status reliability

This avoids both extremes:

- not a blind copy of old bugs
- not a needless rewrite from zero

## Scope

The integrated Windows product must include all of the following:

### Installer outcome

After a successful install:

- the control panel backend is installed
- the control panel frontend is installed
- the control panel can be launched locally
- the installer can optionally auto-launch the panel
- the installed product has one coherent install root and one coherent configuration story

### Panel sections required for product completion

The initial integrated product should keep the current panel shape:

- `Home`
- `Server`
- `OpenCode`
- `Models`
- `Settings`
- `Logs`
- `Repair`
- `Updates`

`Browser` and `Benchmark` may stay present only if they can be carried over without weakening the core product. They are not higher priority than reliability of `Server`, `Models`, and `Settings`.

### Operational control requirements

The panel must provide:

- runtime status for `llama.cpp`
- runtime status for `TurboQuant`
- active runtime identity
- active model identity
- local runtime port and URL
- local UI URL
- Tailscale availability
- Tailscale IP when available
- truthful UI exposure status
- `Start`, `Stop`, and `Restart` for the active server path

### Model-management requirements

The panel must provide a reliable model table and reliable model actions:

- list installed and known models truthfully
- show active model truthfully
- show whether a model is already present on disk
- show whether a model download is in progress
- show bounded progress, speed, and ETA during download
- support local model add
- support selected curated/downloadable models
- ensure successful downloads become visible in the active local model registry
- ensure chosen/active models are correctly propagated to OpenCode-managed configuration

The `Models` flow is a critical-risk area and must be hardened first among panel-specific features.

### Configuration requirements

The panel must provide reliable configuration for:

- runtime selection visibility
- `llama.cpp` parameters
- TurboQuant parameters
- OpenCode profile/step settings
- working directory
- context size
- output token limits
- model-specific overrides where supported
- reusable presets suitable for local AI operation

The panel must support practical presets rather than raw parameter dumping only.

## Out of Scope for this Windows milestone

These are explicitly not blockers for product completion in this repo:

- Ubuntu x64 port
- Ubuntu arm64 port
- remote orchestration across multiple hosts
- generalized cluster management
- arbitrary Tailscale exposure management toggles
- fully new UI redesign

## Architecture

## Frontend

The frontend should be transplanted from `joes021/local-ai-control-center/frontend` into this repo with minimal visual churn.

The target structure should remain close to the original:

- `frontend/src/App.tsx`
- `frontend/src/pages/*`
- `frontend/src/components/*`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`

The initial objective is behavioral reliability, not UI reinvention.

## Backend

The backend should be implemented inside this repo as the installer-managed control center backend, using the old backend only as a donor.

The backend should:

- keep the clean API/page decomposition from `local-ai-control-center/backend/app`
- replace old state derivation with installer-managed truth from this repo
- selectively reuse monitor logic from `llm-service-monitor` for:
  - runtime detection
  - host/network detection
  - Tailscale detection
  - bounded update/download monitoring

Recommended target package layout:

- `src/local_ai_control_center_installer/control_center_backend/`
  - `main.py`
  - `config.py`
  - `state.py`
  - `routes/`
  - `services/`
  - `workers/`

Static built frontend assets should be packaged alongside the backend in the Python package.

## State model

The integrated backend must stop using any legacy state as the primary authority when installer-managed equivalents exist.

The unified state model should separate:

- installer truth
- control-panel derived state
- transient action state

### Installer truth

Derived from install-root files written by this repo.

### Derived live state

Computed on demand from probes:

- runtime status
- health status
- PID
- port owner
- Tailscale detection

### Transient action state

Used for:

- model download progress
- update progress
- panel action result banners

Transient state may be stored in dedicated panel state files, but it must not overwrite installer truth.

## Reliability requirements by area

## 1. Server/runtime reliability

The panel must distinguish:

- configured active runtime
- runtime artifact readiness
- live runtime status
- health readiness

Displayed statuses must map cleanly to:

- `stopped`
- `warming`
- `started`
- `failed`
- `unknown`

The backend must never claim `started` without both:

- process/path ownership confidence
- positive health confirmation

## 2. Model-table reliability

The model table must be rebuilt on top of canonical installer-managed model state.

The final model list must merge:

- curated installer-aware models
- locally installed models
- optional additional model registrations

Every row must have stable identity fields:

- model id
- label
- source
- filename
- on-disk path when present
- installed flag
- active flag

The old panel’s model logic must be audited for:

- duplicate rows
- stale installed state
- desynchronization after download
- activate/download action mismatch
- incorrect OpenCode propagation

## 3. Download reliability

Model downloads must use the same reliability bar as the installer:

- streaming download
- bounded request timeouts
- atomic completion semantics
- checksum verification when available
- truthful retry behavior
- persisted progress state for UI polling

The panel must show:

- current phase
- downloaded size
- total size when known
- speed
- ETA
- final success or failure outcome

## 4. Settings reliability

Settings must stop behaving like a loose form serializer.

The backend must implement an explicit settings contract covering:

- global defaults
- active-model overrides
- runtime preference
- TurboQuant parameter schema
- OpenCode step schema
- working directory

On save, the backend must:

- validate the payload
- normalize the payload
- persist the payload to the correct canonical location
- update derived runtime/OpenCode config outputs as needed
- return a truthful action result

The panel must not show a setting as “saved” unless persistence and required side effects both succeeded.

## 5. Preset reliability

Presets are a product requirement, not a cosmetic bonus.

The system must support reliable presets for:

- TurboQuant operating modes
- OpenCode step profiles
- practical local-AI working defaults

Preset application must be deterministic and inspectable:

- load preset into editor
- review resulting values
- save explicitly
- confirm persisted result

## 6. Tailscale truth

The panel must detect and display:

- whether Tailscale is installed or callable
- the Tailscale IP if available
- whether the UI is actually exposed through the current binding model

It must not imply remote exposure just because Tailscale exists.

## Installer integration requirements

The installer must grow from “install runtime product” to “install and launch control center product”.

After a successful installation:

- the panel backend runtime is available
- the frontend static assets are available
- the panel launch contract is written
- the installer can launch the panel automatically
- the final success message points to the panel URL

The Windows installer should keep a predictable local panel port. The existing panel’s `3210` is the best default because the current UX already assumes it.

## Migration strategy

The safest migration strategy is staged transplantation:

1. import the panel frontend and minimal backend shell
2. replace status/runtime routes with installer-managed truth
3. harden `Models`
4. harden `Settings`, `TurboQuant`, and `OpenCode`
5. wire installer auto-launch and completion UX
6. stabilize `Logs`, `Repair`, and `Updates`

This keeps the product usable throughout the transition and attacks the highest-risk areas first.

## Testing strategy

This integration must be test-first and layered.

### Unit tests

Required for:

- runtime status derivation
- model-table normalization
- download progress state
- settings normalization/validation
- preset persistence
- Tailscale detection mapping

### Route tests

Required for:

- `/api/status`
- `/api/server/*`
- `/api/models/*`
- `/api/settings/*`
- `/api/opencode/*`
- `/api/updates/*`

### Integration tests

Required for:

- installer-managed config consumed by panel backend
- model download becomes visible in model table
- model activation updates OpenCode-facing config
- runtime start/stop/restart affects live status truthfully

### Packaging verification

Required for:

- frontend assets bundled into the installed product
- backend launch works after installer completion
- installer auto-launch opens the panel successfully

## Success criteria

The Windows product is complete for this milestone only when all of the following are true:

- installer succeeds end-to-end
- installer launches the control panel
- panel shows truthful runtime/server/network status
- `Models` can reliably add/download/activate models
- active model is correctly propagated to OpenCode-managed config
- `Settings` and preset flows persist correctly and predictably
- TurboQuant configuration is available and reliable
- the panel remains stable under repeated refreshes and action polling
- test coverage exists for the highest-risk flows

## Recommended execution order

1. create a GitHub checkpoint and isolate work on a panel integration branch
2. transplant frontend and backend shell from `local-ai-control-center`
3. re-anchor backend truth on this repo’s installer artifacts/config
4. harden `Server` and `Home`
5. harden `Models`
6. harden `Settings`, `TurboQuant`, and `OpenCode`
7. integrate installer auto-launch and final product messaging
8. verify packaging and run full regression
