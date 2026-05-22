# Windows Installer/Runtime Completion Design

Date: 2026-05-22

## Goal

Define the next Windows milestone that closes the remaining installer/runtime gaps inside this repository so the installer can truthfully report a completed installer/runtime installation when the core local workflow really works.

This milestone upgrades the current Windows installer from "stable core with strong internal verification" to "truthful installer/runtime-complete flow" by adding:

- a real three-tier starter-model contract that matches the prompt surface
- truthful required-component handling for `OpenCode`
- persisted model-location configuration
- a stable installer-managed runtime endpoint contract
- a single planned sequential download queue with user-visible progress
- a bounded first-run end-user `OpenCode` smoke
- optional `TurboQuant` status reporting that is explicit but non-hard-fail
- a final installer/runtime gate that can promote `product_installation_status` to `complete`

## Repo Finish Line

The locked product requirements include broader portal and shell expectations that are not implemented in this repository today.

This spec therefore uses a narrower and honest finish line:

- complete the Windows installer/runtime product that this repository already owns
- do not pretend this milestone also creates a missing portal/browser/update subsystem

For this repo, `product_installation_status = complete` should mean:

- the installer-owned runtime payload is ready
- the installer-owned `OpenCode` payload is ready
- the active model is ready
- the installed local runtime and installed `OpenCode` work together in a bounded first-run path
- the install-root runtime and model configuration is coherent and durable for the current repository scope

It does not newly claim:

- portal UI availability
- portal-driven runtime controls
- portal-driven OpenCode launch orchestration

That repo-scope boundary must be reflected in README wording when this milestone lands.

## Scope

This design covers the remaining Windows installer/runtime work that is both:

- required by the current repository's installer/runtime scope
- implementable inside the current Python/PowerShell installer repository

The milestone includes:

- replacing the static prompt-only starter-model menu with a manifest-driven three-model catalog
- pinning real Windows starter-model entries for:
  - `recommended-6gb`
  - `recommended-12gb`
  - `recommended-24gb`
- keeping those starter-model entries single-file so the installer can stay sequential without inventing multipart model assembly
- making additional model read locations persist into install-root configuration rather than only the installer session snapshot
- introducing a stable installer-managed runtime endpoint shared by server verification, managed `OpenCode` config, and first-run smoke
- introducing a global download planning step so the installer knows the whole queue before the first download starts
- introducing a shared sequential download progress contract used by runtime, starter-model, and `OpenCode` downloads
- adding an explicit `TurboQuant` phase with truthful Windows behavior
- adding a bounded first-run `OpenCode` smoke that uses persisted installed artifacts and the persisted managed config exactly as written
- promoting the installer from conservative `incomplete` product status to a truthful final `complete` or `failed`
- updating README, reports, and CLI exit gating to match the new finish line

This design does not cover:

- portal UI, browser catalog, or update UI flows
- Linux parity
- automatic discovery/consumption logic for additional model paths inside a future portal
- a real Windows `TurboQuant` build pipeline if no supported Windows install path exists
- broader app-shell concerns outside this installer/runtime repository

## Why This Is The Right Next Milestone

The current repo already proves a lot:

- runtime payload can be prepared
- `llama.cpp` can be verified
- `OpenCode` can be live-route verified

But it still has four important installer/runtime truth gaps:

1. the installer prompt offers three starter-model tiers while the runtime manifest only guarantees one
2. the persisted `OpenCode` config points at an ephemeral verification URL rather than a durable installer-managed runtime endpoint
3. `TurboQuant` selection is collected but not truthfully resolved
4. `product_installation_status` never reaches a terminal truthful final state

Closing those gaps is a more honest path to a finished Windows installer/runtime product than adding more isolated verifier depth.

## Recommended Approach

Use one cohesive completion milestone that keeps the current pipeline structure but adds four new layers:

1. truthful installer contract completion
2. stable runtime endpoint truth
3. truthful final-use smoke
4. truthful final installer/runtime gate

### Why this approach

- it reuses the existing manifest-driven and injectable architecture
- it fixes existing misleading prompt/repo mismatches rather than layering new behavior on top
- it lets the installer finally state `complete` only after a real bounded user-path proof
- it keeps optional `TurboQuant` reporting separate from the hard-fail core path
- it turns the currently fragmented download logic into one precomputed queue contract

### Rejected alternatives

#### Only add a first-run smoke

Not recommended. That would still leave a misleading starter-model menu, a dead persisted `OpenCode` config target, and an unimplemented `TurboQuant` selection.

#### Keep the current random verification port and rewrite config only during smoke

Not recommended. That preserves a dead persisted managed config outside the smoke run and keeps the installer from producing a durable runtime endpoint contract.

#### Jump to portal/browser work now

Not recommended inside this repo. The current codebase is an installer/runtime product, and it still has unfinished core-contract work of its own.

## Starter Model Contract

The starter-model prompt and runtime manifest must be derived from the same truth source.

After this milestone:

- the prompt must no longer use a hard-coded `MODEL_CHOICES` constant that can drift away from the packaged manifest
- the packaged runtime manifest must contain all prompt-visible starter-model entries
- the prompt must present exactly the starter-model entries that the manifest marks as installer-recommended

The Windows packaged runtime manifest should contain three pinned single-file `Qwen2.5-Coder` GGUF entries:

### `recommended-6gb`

- model id: `recommended-6gb`
- display label: `recommended-6gb`
- upstream repo: `Qwen/Qwen2.5-Coder-7B-Instruct-GGUF`
- pinned revision: `13fb94bfda8c8cf22497dc57b78f391a9acb426a`
- filename: `qwen2.5-coder-7b-instruct-q4_k_m.gguf`
- install path: `models/recommended-6gb/recommended-6gb.gguf`
- size bytes: `4683073536`
- pinned digest: `fa9e1815472201e7dea978475c1f3ca7bc7df773eaeb3b3a383258c25b052f6f`

### `recommended-12gb`

- model id: `recommended-12gb`
- display label: `recommended-12gb`
- upstream repo: `Qwen/Qwen2.5-Coder-14B-Instruct-GGUF`
- pinned revision: `d0a692ef765eefbf2fabb130b3cb2e8917e3d225`
- filename: `qwen2.5-coder-14b-instruct-q4_k_m.gguf`
- install path: `models/recommended-12gb/recommended-12gb.gguf`
- size bytes: `8988110272`
- pinned digest: `f87bfd654aed5318df1819cc17b5204270b69d05d905c0fa6960d84e4843ba18`

### `recommended-24gb`

- model id: `recommended-24gb`
- display label: `recommended-24gb`
- upstream repo: `Qwen/Qwen2.5-Coder-32B-Instruct-GGUF`
- pinned revision: `9d3053fce650fe1cdbdb75998c2a87add9d178ef`
- filename: `qwen2.5-coder-32b-instruct-q4_k_m.gguf`
- install path: `models/recommended-24gb/recommended-24gb.gguf`
- size bytes: `19851335872`
- pinned digest: `2687a00b84e7e35c652ea0024cb8747070b090e9f311ab9b6461b8a71c2bc50f`

The manifest should also carry prompt metadata per starter model, for example:

- `prompt_order`
- `prompt_label`
- `recommended_default`

The prompt should load that packaged manifest and render the numbered menu from it.

This removes the current drift risk where the prompt advertises choices that the packaged manifest cannot satisfy.

## Required Component Truth

The current repository scope still treats `OpenCode` as a core component of a successful completed installer/runtime installation.

Therefore:

- declining `OpenCode` may still be allowed as a user choice
- but the installer must treat that choice as incompatible with a successful completed installer/runtime outcome

Truth rules:

- if `install_opencode = false`, the run may still proceed through the installer pipeline
- but the final gate must set:
  - `product_installation_status = failed`
  - `failing_step = product-gate`
  - `error_message` that explains a required component was declined

The prompt surface should also become clearer:

- the `OpenCode` question must explain that this is a required component for a successful installation

This keeps user control without pretending the installation can still be complete.

## Model Location Persistence

Additional model read locations must become real install-root configuration.

After this milestone:

- the installer must persist a dedicated install-root config file for model locations
- that config must include:
  - the default writable model root
  - zero or more additional read-only model paths from the questionnaire

Recommended config file:

- `config/model-locations.json`

Recommended payload:

```json
{
  "default_model_root": "C:\\Users\\<user>\\LocalAIControlCenter\\models",
  "additional_read_only_model_paths": [
    "D:\\models",
    "E:\\shared-models"
  ]
}
```

This config should be written during the runtime payload phase because that phase already owns install-root model structure and active-model configuration.

## Stable Installer-Managed Runtime Endpoint

The current persisted `OpenCode` config truth is insufficient because it captures `verified_server_url` from a temporary server-verification run that is torn down afterward.

This milestone must replace that ephemeral endpoint contract with a stable installer-managed runtime endpoint contract.

Recommended Windows contract:

- reserve one default loopback runtime port for the installed local runtime, for example a packaged installer-managed port such as `39281`
- persist that endpoint into install-root config as the canonical runtime URL
- make server verification, managed `OpenCode` config generation, and first-run smoke all use that same canonical endpoint contract

Truth rules:

- if the managed port is unavailable because another process already owns it, server verification must fail truthfully
- `OpenCode` managed config must always point to the canonical installer-managed runtime endpoint, never to a one-off verification port
- first-run smoke must start the temporary runtime on that canonical managed port, so the persisted installed config is exercised exactly as written

Upgrade/rerun ownership rule:

- if the canonical managed port is held by a process that the installer can positively identify as the same installer-managed `llama.cpp` runtime from the same install root, the installer may either:
  - reuse that running managed process for verification/smoke, or
  - stop it cleanly and restart it under installer control
- if the canonical managed port is held by any other process, the installer must fail with a clear port-ownership error rather than silently switching to a different port

The installer must never "fix" a busy managed port by quietly picking a random replacement port, because that would break the persisted endpoint contract.

Recommended persisted config addition:

- `config/runtime-endpoint.json`

Recommended payload:

```json
{
  "base_url": "http://127.0.0.1:39281",
  "port": 39281,
  "installer_managed": true
}
```

The exact default port can be chosen during planning, but the contract must be stable and shared.

Ownership and write timing:

- `runtime-endpoint.json` must be written before `OpenCode` bootstrap runs
- the same phase that establishes install-root runtime configuration must own this file, so `runtime_bootstrap.py` is the recommended writer

## Sequential Download Planning And Progress Contract

The installer needs a truthful sequential progress surface for installer-managed downloads and a single precomputed queue contract.

This design keeps that contract bounded:

- downloads remain one by one
- the installer prints progress updates to the terminal
- queue truth is computed before the first actual download starts

Required queue information during the final download/install run:

- current file label
- file index
- total file count
- remaining file count
- bytes downloaded for the current file
- total bytes for the current file when known
- estimated ETA for the current file when enough data exists

This does not require turning the whole installer into a streaming TUI. A line-oriented callback contract is sufficient.

Recommended download abstractions:

- a global `download_plan` step before any actual payload download begins
- a small `DownloadPlanItem`
- a progress callback signature that receives immutable progress events
- default terminal output that renders:
  - file label
  - `current/total`
  - percent
  - speed
  - ETA

The same shared download helper and queue plan should back:

- runtime archive download
- starter-model download
- `OpenCode` archive download
- any future installer-managed `TurboQuant` artifact download

The important architectural rule is:

- the installer must know the whole queued file list before the first download starts

That means the pipeline needs an explicit planning phase that resolves manifests and selected optional components into one ordered queue. The queue executor may still be called from narrower phase helpers, but queue truth must come from one global plan.

## TurboQuant Contract

`TurboQuant` remains non-hard-fail, but it can no longer be a silent questionnaire-only field.

This milestone adds an explicit `TurboQuant` phase with truthful reporting.

For Windows in this repository, the recommended contract is conservative:

- if `attempt_turboquant = false`
  - `turboquant_status = skipped`
- if `attempt_turboquant = true`
  - the installer must attempt the Windows `TurboQuant` strategy known to the packaged manifest, if one exists
  - otherwise it must set:
    - `turboquant_status = failed`
    - a dedicated `turboquant_error` that clearly explains that no supported Windows `TurboQuant` install path is currently packaged

`TurboQuant` failure must never hide or overwrite a stronger core installer/runtime failure.

`TurboQuant` failure must also never block `product_installation_status = complete` when all hard-fail installer/runtime requirements pass.

That preserves the product requirement that `TurboQuant` status be clear, but not core-blocking.

## First-Run End-User OpenCode Smoke

The current live-route verifier is strong internal proof, but it is not yet the public first-run milestone.

This milestone adds a distinct bounded first-run smoke with these differences:

- it must use the persisted install-root `OpenCode` artifact
- it must use the persisted install-root managed config exactly as written
- it must not depend on the temporary verification relay
- it must look like a real first-use CLI run rather than an installer-owned route proof harness

Recommended first-run flow:

1. verify final prerequisites:
   - `bootstrap_status == ready`
   - `runtime_payload_status == ready`
   - `server_verification_status == ready`
   - `opencode_artifact_status == ready`
   - `opencode_verification_status == ready`
   - persisted managed config exists
   - persisted active-model config exists
   - persisted runtime-endpoint config exists
2. start a bounded temporary `llama-server` against the persisted active model on the canonical installer-managed runtime endpoint
3. keep the persisted `OpenCode` managed config path active
4. launch the installed `opencode.exe` from install-root with a bounded non-interactive command:
   - `opencode --pure run --format json --model local-lacc/<active-model-id> "<prompt>"`
5. use a deterministic user-facing smoke prompt such as:
   - `Reply with the single word READY.`
6. parse JSON output and require:
   - process exit `0`
   - at least one assistant message/content payload
   - non-empty assistant text
7. stop the temporary server cleanly

This smoke should prove:

- installed `OpenCode` can actually run in its persisted configuration
- installed `OpenCode` can actually obtain a real assistant response from the active local runtime/model

It should not reuse the live-route relay marker because that was verifier-specific internal proof, not the public first-run contract.

## Installer/Runtime Completion Truth Contract

This milestone introduces the first truthful terminal installer/runtime outcome for this repository.

After the full installer pipeline runs:

- `product_installation_status = complete` only when:
  - bootstrap is ready
  - runtime payload is ready
  - server verification is ready
  - `OpenCode` is both installed and live-route verified
  - the first-run end-user smoke passes
  - all required component choices were accepted
- `product_installation_status = failed` when any hard-fail installer/runtime requirement in this repository scope is not satisfied
- `product_installation_status = incomplete` remains acceptable only for pre-final states inside the pipeline or cancellation scenarios before the gate runs

Recommended new final-gate statuses:

- `first_run_status`
- `first_run_process_status`
- `first_run_connection_status`
- `model_locations_config_status`
- `runtime_endpoint_config_status`
- `turboquant_status`
- `turboquant_error`

Recommended `failing_step` additions:

- `model-catalog`
- `model-locations-config`
- `first-run-prerequisites`
- `first-run-runtime-server-start`
- `first-run-opencode-smoke`
- `first-run-process-stop`
- `product-gate`

Truth rules:

- if first-run smoke fails, `product_installation_status = failed`
- if `OpenCode` was declined, `product_installation_status = failed`
- if `model-locations.json` was not persisted successfully, `product_installation_status = failed`
- if `runtime-endpoint.json` was not persisted successfully, `product_installation_status = failed`
- if `TurboQuant` fails but all hard-fail installer/runtime gates pass, `product_installation_status` may still be `complete`
- if `TurboQuant` is the only failure, `failing_step` must remain `None` and the failure lives in `turboquant_status` plus `turboquant_error`

## Pipeline Shape

Keep the existing overall sequence, but extend it:

1. collect answers
2. scan dependencies
3. plan global download queue and canonical runtime endpoint
4. apply bootstrap phase
5. apply runtime payload
6. apply server verification
7. apply `OpenCode` bootstrap
8. apply `OpenCode` live-route verification
9. apply `TurboQuant` phase
10. apply first-run smoke
11. apply final product gate
12. persist reports

The final product gate should live in a small dedicated module rather than inside the first-run smoke module.

Recommended module:

- `product_gate.py`

## Module Shape

Recommended additions and extensions:

- add `runtime_manifest.py`
  - shared runtime manifest and starter-model catalog loading
  - questionnaire-facing starter-model metadata helpers
  - execution-facing starter-model resolution helpers
- extend `runtime_bootstrap.py`
  - model-locations config write
  - runtime-endpoint config write
  - shared starter-model metadata handling
- extend `prompts.py`
  - manifest-driven starter-model menu
  - clearer required `OpenCode` wording
- add `download_plan.py`
  - global queue planning based on selected components and manifests
- extend `downloads.py`
  - sequential streaming download helper
  - progress-event callback contract
- add `turboquant.py`
  - explicit optional `TurboQuant` phase with Windows truth mapping
- add `first_run_validation.py`
  - bounded first-run `OpenCode` smoke
- add `product_gate.py`
  - terminal installer/runtime truth policy
- extend `session.py`
  - new first-run and `TurboQuant` status fields
- extend `reporting.py`
  - include model-location config, first-run, and `TurboQuant` truth
- extend `defaults.py`
  - default adapters for new phases and progress printer
- extend `main.py`
  - wire new phases
  - base exit code on final installer/runtime completion rather than intermediate milestone success

## Reporting Contract

Human log and JSON report must include:

- the chosen starter-model tier
- the persisted model-locations config path
- the persisted runtime-endpoint config path
- first-run statuses
- `TurboQuant` status
- final `product_installation_status`
- the final `failing_step`

README must update its "Current Slice Status" wording so the Windows installer no longer claims only an intermediate milestone once this work is complete.

## Testing Strategy

Use TDD and keep each new behavior injectable.

### Manifest and prompt truth

- prompt renders exactly the models from the packaged manifest
- prompt default matches the manifest-marked recommended default
- prompt no longer advertises unsupported starter-model choices
- runtime manifest contains all three packaged starter-model entries

### Runtime payload and config persistence

- selected `recommended-12gb` and `recommended-24gb` paths resolve and write active-model config correctly
- model-locations config is written with default and additional read-only paths
- runtime-endpoint config is written with the canonical managed port and URL
- runtime payload may not report `ready` until active-model, model-locations, and runtime-endpoint config artifacts are all persisted successfully
- config-write failure maps truthfully

### Download planning and progress

- global download plan contains the whole file queue before downloads start
- queue ordering is truthful for runtime archive, chosen starter model, `OpenCode`, and selected `TurboQuant`
- sequential download helper emits index/total progress events in order
- progress callback sees percent and ETA when total size is known
- runtime and `OpenCode` phases pass the expected file labels into the shared download helper

### TurboQuant

- skipped when not selected
- clear failed status when selected but no packaged Windows strategy exists
- failure does not overwrite a stronger hard-fail product error

### First-run smoke

- skip/fail when prerequisites are missing
- fail when canonical managed port is occupied by a foreign process
- reuse or controlled-stop/restart is explicitly handled when the port is already owned by the same installer-managed runtime
- fail when temporary runtime cannot start
- fail when `OpenCode` process fails
- fail when no assistant content is returned
- succeed when installed artifacts and persisted config produce a bounded response
- cleanup failures map truthfully without hiding stronger earlier failures

### Product gate

- `product_installation_status = complete` only when all hard-fail installer/runtime conditions pass
- `product_installation_status = failed` when `OpenCode` was declined
- `product_installation_status = failed` when required persisted config artifacts are missing or failed
- `product_installation_status = complete` may coexist with `turboquant_status = failed`
- `main()` returns `0` only for `product_installation_status = complete`

## Non-Goals For This Milestone

Do not claim completion of:

- Linux support
- portal/browser/update flows
- real Windows `TurboQuant` installation if no supported packaged path exists

The correct outcome of this milestone is:

- a truthful Windows installer/runtime product that can declare itself complete after a real bounded first-run user-path smoke and a coherent global download/install contract

not:

- a full cross-platform shell product

## Assumptions

This design assumes:

- the current repository finish line is the Windows installer/runtime product that this codebase already owns
- user review gates are pre-approved for this session because the user explicitly requested autonomous progress without waiting for answers
