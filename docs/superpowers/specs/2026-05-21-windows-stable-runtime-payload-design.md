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
- download or verify `llama.cpp` runtime artifacts
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

### 3. Runtime artifact verification or download

Check whether the expected `llama.cpp` payload is already present at the final install location.

If present:

- verify required file layout
- verify checksums where applicable

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

- runtime artifact is verified and promoted
- starter model is verified and promoted

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

## Module Layout

Extend the Python package with focused runtime modules.

### Existing modules to extend

- `src/local_ai_control_center_installer/session.py`
  - add runtime payload status fields and persisted paths

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
  - download helpers
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
- `starter_model_id`
- `starter_model_path`
- `active_model_config_path`

### Product installation truth

Keep:

- `product_installation_status = incomplete`

Add:

- `runtime_payload_status`

This keeps the installer honest. The slice prepares a runtime payload, but does not yet prove runnable-server behavior.

## Success Model

The runtime payload slice is successful only if all of the following are true:

- bootstrap was already `ready`
- the expected `llama.cpp` artifact is verified and promoted
- the selected starter model is verified and promoted
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
- set runtime statuses to `skipped`

### Runtime artifact failure

If `llama.cpp` download, checksum, extraction, or layout verification fails:

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

- selected runtime artifact id
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

#### Download and verification

- checksum success
- checksum failure
- required file layout success
- required file layout failure

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
