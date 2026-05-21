# Windows Stable Runtime Payload Design

Date: 2026-05-21

## Goal

Define the next Windows delivery slice for `Local AI Control Center` after stable bootstrap:

- pinned runtime payload metadata in repo
- `llama.cpp` runtime artifact download or verification
- starter model download or verification
- active model configuration persistence
- truthful runtime status reporting

This slice is intentionally limited to runtime payload preparation. It does not yet claim that the server is runnable.

## Scope

This design covers only the next Windows runtime payload milestone:

- run runtime bootstrap only after dependency bootstrap is `ready`
- load a pinned runtime manifest from the installer package
- download or verify a single pinned `llama.cpp` runtime artifact
- download or verify the selected starter model
- write active model configuration only after runtime artifact and model are verified
- extend human log and JSON report with runtime payload statuses

This design does not yet cover:

- server start or health-check verification
- `OpenCode` installation or verification
- `TurboQuant`
- dynamic "latest" release lookup
- browser download UX
- multi-model lifecycle management

## Product Positioning

The repository goal remains:

- stable core first
- shell second

The runtime slice should therefore optimize for:

- pinned, deterministic artifact sources
- staging-before-promote safety
- truthful partial-progress reporting
- clean extension points for later `OpenCode` and server verification phases

## Recommended Source Strategy

Use a pinned runtime manifest stored inside the installer package.

### Why this approach

- installer behavior stays deterministic
- source URLs and checksums are versioned with the code
- tests can target stable metadata without network-dependent discovery logic
- later source updates become explicit repo changes instead of hidden behavior changes

### Rejected alternatives

#### Hardcoded Python constants

Faster for one pass, but harder to evolve once multiple artifacts or model variants appear.

#### Dynamic latest-release discovery

Too unstable for this installer phase. It introduces source drift, release-shape changes, and harder-to-explain failure behavior.

## Installer Flow

The runtime payload flow should follow this order.

### 1. Bootstrap gate

The runtime payload phase starts only if:

- `bootstrap_status == ready`

If bootstrap failed, runtime work is skipped entirely.

### 2. Manifest load

Load the pinned Windows runtime manifest from the package.

Recommended location:

- `src/local_ai_control_center_installer/manifests/windows-stable-runtime.json`

If the manifest is missing, invalid, or does not contain the required Windows runtime artifact entry or the requested starter model entry:

- stop the runtime phase
- set `runtime_payload_status = failed`
- set `runtime_artifact_status = failed` only when the runtime artifact definition itself is unavailable or invalid
- set `starter_model_status = failed` when the requested starter model entry is unavailable or invalid
- set downstream runtime fields that were not attempted to `skipped`
- report `failing_step = runtime-manifest`

### 3. Runtime artifact verification or download

Check whether the expected `llama.cpp` payload is already present at the final install location.

If present:

- verify required file layout
- verify the pinned runtime artifact id matches the installed runtime metadata marker

Checksum truth for `llama.cpp` must be explicit:

- manifest `sha256` applies to the staged downloaded archive
- already-promoted final runtime directories are not re-hashed as one directory blob in this slice
- final in-place verification uses required file layout plus a persisted runtime metadata marker written at successful promotion time

If not present or verification fails:

- download into a staging directory
- verify checksum
- verify required file layout
- promote into the final runtime location only after verification succeeds

### 4. Starter model verification or download

Check whether the selected starter model is already present at the final model location.

If present:

- verify filename and checksum

If not present or verification fails:

- download into staging
- verify checksum
- promote into the final model location only after verification succeeds

### 5. Active model configuration

Write active model configuration only after both of the following are true:

- runtime artifact is verified in place or verified and promoted
- starter model is verified in place or verified and promoted

Recommended location:

- `<install_root>\\config\\active-model.json`

### 6. Runtime payload reporting

Persist truthful runtime results in logs, JSON report, and installer session.

The runtime slice should clearly distinguish:

- runtime artifact readiness
- starter model readiness
- active model configuration readiness

## Install Layout

Recommended final layout:

- `<install_root>\\runtime\\llama.cpp\\`
- `<install_root>\\models\\<starter-model-id>\\`
- `<install_root>\\config\\active-model.json`

Temporary run artifacts remain under the installer temp run directory so failed runs still leave diagnostics.

## Manifest Shape

The runtime manifest should be plain JSON and versioned in-repo.

### Runtime artifact entry

The `llama.cpp` entry should define:

- `id`
- `url`
- `sha256`
- `archive_type`
- `required_files`
- `install_subdir`

### Starter model entry

Each starter model entry should define:

- `id`
- `url`
- `sha256`
- `target_filename`
- `install_subdir`

The installer should not guess download locations or filenames outside the manifest.

For this slice, Windows runtime artifact selection is not dynamic. The manifest provides one pinned Windows runtime artifact contract, and reporting should describe it as the pinned runtime artifact rather than a user-selected artifact.

## Module Layout

Extend the Python package with focused runtime modules.

### Existing modules to extend

- `src/local_ai_control_center_installer/session.py`
  - add runtime payload status fields and persisted paths
  - keep existing `starter_model` field as the requested starter model id chosen during the questionnaire

- `src/local_ai_control_center_installer/reporting.py`
  - include runtime payload results in human log and JSON report

- `src/local_ai_control_center_installer/main.py`
  - run runtime payload orchestration only after bootstrap succeeds

### New modules

- `src/local_ai_control_center_installer/runtime_bootstrap.py`
  - runtime payload orchestration
  - manifest-driven sequencing
  - runtime status transitions

- `src/local_ai_control_center_installer/downloads.py`
  - slice-specific download helpers for runtime payload work only
  - checksum verification
  - archive extraction where needed
  - staging/promote helpers
  - rollback behavior for partial final-location failures

## Data Model

The runtime slice should extend the session instead of replacing existing bootstrap truth.

### Additional session fields

- `runtime_payload_status`
  - `ready`
  - `failed`
  - `skipped`

- `runtime_artifact_status`
  - `ready`
  - `failed`
  - `skipped`

- `starter_model_status`
  - `ready`
  - `failed`
  - `skipped`

- `active_model_config_status`
  - `ready`
  - `failed`
  - `skipped`

- `runtime_artifact_id`
- `runtime_artifact_path`
- `starter_model_path`
- `active_model_config_path`
- `runtime_metadata_path`

### Requested vs resolved model fields

Keep the existing session field:

- `starter_model`

Meaning in this slice:

- requested starter model id selected during the questionnaire

Add:

- `starter_model_path`

Meaning in this slice:

- resolved final on-disk location of the requested starter model after verification or promotion

### Product installation truth

Keep:

- `product_installation_status = incomplete`

Add:

- `runtime_payload_status`

This keeps the installer honest. The slice prepares a runtime payload, but does not yet prove runnable-server behavior.

## Success Model

The runtime payload slice has two top-level truthful outcomes:

### Runtime phase skipped

If bootstrap was not ready, the runtime phase does not run.

In that case:

- `runtime_payload_status = skipped`
- `runtime_artifact_status = skipped`
- `starter_model_status = skipped`
- `active_model_config_status = skipped`

### Runtime phase executed

If bootstrap was ready, the runtime payload slice is successful only if all of the following are true:

- the pinned `llama.cpp` artifact is verified in place or verified and promoted
- the selected starter model is verified in place or verified and promoted
- active model configuration was written successfully

Only then:

- `runtime_payload_status = ready`

If any of those conditions fail:

- `runtime_payload_status = failed`

The slice must not upgrade `product_installation_status` beyond `incomplete`.

## Failure Rules

Runtime failure handling should be strict and truthful.

### Bootstrap failed

If bootstrap is not ready:

- do not start runtime download logic
- set all runtime statuses to `skipped`
- do not set `runtime_payload_status = failed` for this case

### Runtime artifact failure

If runtime manifest load for `llama.cpp` fails, or if `llama.cpp` download, checksum, extraction, metadata-marker verification, or layout verification fails:

- `runtime_artifact_status = failed`
- `starter_model_status = skipped`
- `active_model_config_status = skipped`
- `runtime_payload_status = failed`

### Starter model failure

If runtime artifact succeeds but model download or checksum fails:

- `runtime_artifact_status = ready`
- `starter_model_status = failed`
- `active_model_config_status = skipped`
- `runtime_payload_status = failed`

### Active model configuration failure

If runtime artifact and model are ready but writing `active-model.json` fails:

- `runtime_artifact_status = ready`
- `starter_model_status = ready`
- `active_model_config_status = failed`
- `runtime_payload_status = failed`

### Final-location safety

Failed runs may leave diagnostics in the temp run area, but the final install layout must not be left in a partially promoted state.

Use the same truth-preserving approach as the bootstrap slice:

- stage first
- verify first
- promote only when complete
- rollback final-location changes when promotion fails

## Logging and Reporting

Human log and JSON report should clearly expose:

- pinned runtime artifact id
- selected starter model id
- runtime artifact outcome
- starter model outcome
- active model configuration outcome
- failing step when runtime payload fails

JSON output should remain stable enough for later portal and update flows.

## Testing Strategy

Use TDD and keep runtime behavior decomposed into small, testable units.

### Test focus

#### Manifest loading

- manifest exists
- manifest parsing succeeds
- missing required fields fail clearly
- missing pinned runtime artifact entry fails clearly
- missing requested starter model entry fails clearly

#### Download and verification

- checksum success
- checksum failure
- required file layout success
- required file layout failure
- in-place runtime metadata-marker verification success
- in-place runtime metadata-marker verification failure

#### Staging and promotion

- staging download path
- promote success
- promote rollback on failure
- no partial final-location state on failure

#### Runtime orchestration

- bootstrap ready triggers runtime phase
- bootstrap failed skips runtime phase
- runtime artifact failure blocks later runtime steps
- model failure blocks active model config
- config write failure reports truthful partial success

#### Reporting

- human log includes runtime statuses
- JSON report includes runtime payload fields
- `product_installation_status` remains `incomplete`

## Non-Goals For This Slice

The implementation must not claim more than it actually verifies.

Do not claim completion of:

- runnable `llama.cpp` server verification
- HTTP health-check success
- `OpenCode` readiness
- `TurboQuant` readiness
- finished product installation

The correct outcome of this slice is:

- runtime payload prepared and truthfully reported

not:

- full application ready

## Transition To Next Slice

Once this runtime payload slice is complete, the next runtime plan should extend the same reporting and session structures to:

- `OpenCode` installation and verification
- optional `TurboQuant`
- first-run runtime validation
- server launch and health-check gate
