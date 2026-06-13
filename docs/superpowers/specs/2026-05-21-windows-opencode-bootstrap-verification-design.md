# Windows OpenCode Bootstrap And Verification Design

Date: 2026-05-21

## Goal

Define the next Windows delivery slice for `Local AI Control Center` after verified `llama.cpp` server readiness:

- install a pinned, installer-managed `OpenCode` artifact
- generate installer-managed `OpenCode` configuration that targets the verified local runtime
- verify `OpenCode` starts successfully under isolated installer-controlled configuration
- verify `OpenCode` resolves the expected local runtime and active model without relying on a user profile
- record truthful `OpenCode` bootstrap and verification state in logs and JSON reporting

This slice intentionally stops at `OpenCode` bootstrap plus config/process handshake. It does not yet claim full product completion.

## Scope

This design covers only the next Windows `OpenCode` milestone:

- run `OpenCode` work only after `llama.cpp` server verification is `ready`
- use a pinned installer-managed Windows `OpenCode` release artifact
- validate the installed `OpenCode` payload using manifest-defined required files and pinned checksums
- write installer-managed `OpenCode` config under install root
- launch `OpenCode` in an isolated verification context
- verify the process starts and remains alive long enough to complete handshake checks
- verify `OpenCode` resolves the expected local runtime endpoint and active model routing
- stop the verification process cleanly
- extend human log and JSON report with truthful `OpenCode` bootstrap and verification outcomes

This design does not yet cover:

- first real inference prompt smoke through `OpenCode`
- `TurboQuant`
- browser or portal UX flows
- update or self-repair flows for `OpenCode`
- desktop `OpenCode` app packaging
- final product-complete status

## Product Positioning

The repository goal remains:

- stable core first
- shell second

The `OpenCode` slice should therefore optimize for:

- pinned installer-managed ownership
- truthful proof that `OpenCode` is wired to the verified local runtime
- isolation from pre-existing user `OpenCode` configuration
- deterministic Windows behavior that can be planned and tested
- clean extension points for later first-run inference validation and full product completion

## Recommended Bootstrap And Verification Strategy

Use a pinned release-artifact strategy plus an isolated config/process handshake:

- install a pinned Windows `OpenCode` artifact from an installer manifest
- generate a narrow installer-managed `OpenCode` config bridge
- launch `OpenCode` under isolated config control
- prove that `OpenCode` resolves the expected local provider and active model
- stop the process cleanly after verification

### Why this approach

- it keeps `OpenCode` under installer ownership instead of depending on user-managed global installs
- it aligns with the existing runtime artifact pattern already used for `llama.cpp`
- it avoids false positives from user-global `OpenCode` config, project config, or plugins
- it gives a meaningful proof of integration without prematurely expanding into prompt-smoke behavior
- it keeps the next slice focused on one major missing product dependency

### Rejected alternatives

#### External dependency discovery

Not recommended. Discovering a user-managed `OpenCode` install would make the product harder to support, harder to reproduce, and easier to mis-report as successful because of environment drift.

#### Full prompt smoke in the same slice

Stronger proof, but too broad for the immediate next step. Prompt formatting, model warmup, output validation, and end-user behavior should be isolated into the next first-run validation slice.

#### Config-file-only verification

Too weak. The existence of a generated config file does not prove that `OpenCode` can start or that it actually resolves the expected local runtime and active model.

## Windows Artifact Strategy

`OpenCode` should use its own installer manifest rather than being merged into the existing runtime manifest.

Recommended new packaged manifest:

- `src/local_ai_control_center_installer/manifests/windows-stable-opencode.json`

Reason:

- runtime and `OpenCode` will evolve independently
- checksum and required-file truth should remain narrow and reviewable
- later `OpenCode` updates should not force changes to the runtime manifest structure

The artifact source should be a pinned Windows release asset that the installer downloads directly and validates by checksum. It must not depend on:

- `latest` redirect semantics
- a machine-global package manager state
- user-global `npm install -g`
- an already-installed `OpenCode`

The implementation may use the upstream Windows release asset format that is current at implementation time, but the installer contract must remain:

- pinned version
- pinned archive checksum
- pinned required-file checksums for the installed executable payload

This design intentionally targets native Windows execution even though upstream docs currently recommend WSL for the best experience. Native Windows support exists and is the supported target for this product slice.

## OpenCode Manifest Contract

The new `OpenCode` manifest should follow the same truth model as runtime payload manifests.

### Required top-level sections

- `opencode_artifact`

### Required `opencode_artifact` fields

- `id`
- `url`
- `sha256`
- `archive_type`
- `required_files`
- `required_file_sha256`
- `install_subdir`
- `launch`

### Required `launch` fields

- `executable_relative_path`
- `verification_args`
- `extra_env`

Field intent:

- `executable_relative_path`
  - relative path from artifact root to the Windows executable or launcher used by the installer
- `verification_args`
  - fixed static leading arguments for the single bounded installer verification command
- `extra_env`
  - static environment additions required by the pinned artifact for deterministic startup

The launch contract must be fully installer-owned and explicit. The verifier must not infer executable paths or launch flags by scanning the filesystem heuristically.

For this slice, `verification_args` is the single source of truth for static verification arguments and must resolve to the equivalent of:

- `["--pure", "models"]`

The verifier then appends exactly one runtime-computed trailing argument:

- `local-lacc`

This means the effective verification command shape for this slice is:

- `opencode --pure models local-lacc`

The manifest may not change the verification subcommand semantics for this slice. It only carries the fixed static args and executable path required to build that one bounded verification command.

The config environment variable names are normative slice constants, not manifest-controlled values:

- `OPENCODE_CONFIG`
- `OPENCODE_CONFIG_CONTENT`

### Required JSON shapes

To keep manifest validation identical in spirit to the runtime slice:

- `required_files`
  - JSON array of relative file paths as strings
- `required_file_sha256`
  - JSON object mapping relative file path string to lowercase hex SHA-256 digest string

Rules:

- every key in `required_file_sha256` must also appear in `required_files`
- `required_files` may contain paths that are presence-only checks
- checksum validation is mandatory for every path listed in `required_file_sha256`

## Installer-Owned Disk Contract

The installer should control the following `OpenCode` paths under install root:

- `tools/opencode/`
  - unpacked `OpenCode` artifact root
- `tools/opencode/opencode-artifact.json`
  - installer metadata describing the installed artifact source checksum and artifact id
- `config/opencode/managed-config.json`
  - installer-generated narrow `OpenCode` configuration bridge
- `logs/opencode-verification.log`
  - stdout and stderr capture for the `OpenCode` verification process

The session and reporting layer should surface all of these paths where relevant.

## Managed Config Contract

The installer-managed config must be intentionally narrow. It is not a general user settings export.

It should capture only the minimum state required for truthful local-runtime routing:

- installer-managed marker
- fixed installer-managed provider id: `local-lacc`
- expected local provider/runtime type
- verified local runtime base URL
- active model identity from installer-managed model config
- top-level selected model string: `local-lacc/<active-model-id>`
- `enabled_providers: ["local-lacc"]`
- any `OpenCode` provider/model settings required to route toward the local runtime
- `autoupdate: false` or equivalent installer-managed update suppression if supported

The generated config should derive its truth from already installer-owned sources:

- `verified_server_url`
- `active-model.json`
- installer manifest launch contract

The verifier must treat a missing or malformed installer-managed config as a real failure, not a soft warning.

## Launch Isolation Strategy

Plain use of a config file path is not enough because current upstream `OpenCode` docs describe configuration as merge-based across multiple layers.

Verification must therefore isolate itself from:

- user-global `OpenCode` config
- project-local `opencode.json`
- `.opencode` directories
- unrelated environment-provided config content
- plugin loading side effects that are not required for this slice

Recommended verification isolation:

- launch from a temporary empty working directory
- pass the installer-managed config path through `OPENCODE_CONFIG`
- use `OPENCODE_CONFIG_CONTENT` for critical runtime/model overrides
- set `OPENCODE_DISABLE_MODELS_FETCH=true` during verification so the handshake does not depend on remote model directory refresh
- include `--pure` in the verification launch path to suppress non-essential external extension layers

The override content used for verification should at minimum force:

- expected local provider/runtime selection
- expected local base URL
- expected active model identifier
- any provider enablement needed for that route

This ensures the verification result proves installer wiring rather than ambient user configuration.

## Verification Flow

The `OpenCode` phase should follow this order.

### 1. Server gate

The phase starts only if:

- `bootstrap_status == ready`
- `runtime_payload_status == ready`
- `server_verification_status == ready`

If server verification is not ready, all `OpenCode` work is skipped.

### 2. User-choice gate

If `install_opencode == false`:

- do not install or verify `OpenCode`
- set all `OpenCode` statuses to `skipped`
- keep `product_installation_status = incomplete`
- keep CLI success unavailable because the selected milestone was not completed

### 3. Manifest load

Load and validate the packaged `OpenCode` manifest before touching disk or process launch.

If the manifest is invalid:

- stop the `OpenCode` phase
- set truthful `OpenCode` status fields
- report `failing_step = opencode-manifest`

### 4. Artifact readiness check

Before downloading anything, verify whether the pinned `OpenCode` artifact is already ready:

- required files exist under the manifest install subdir
- required file checksums match manifest-pinned values
- `opencode-artifact.json` confirms the expected artifact id and source checksum

If the artifact is not ready:

- download the pinned archive
- verify archive checksum
- extract to a staging location
- verify required files
- verify required file checksums
- write installer metadata
- promote the staged payload into install root

### 5. Verification prerequisites

Before generating config or starting a process, verify that all required inputs exist and are readable:

- installed `OpenCode` executable from manifest launch contract
- `verified_server_url`
- `active-model.json`
- active model id and model path resolved from that file
- active model file present on disk

If any prerequisite is missing or unreadable:

- stop the phase
- set truthful `OpenCode` statuses
- report `failing_step = opencode-verification-prerequisites`

The active model file remains a prerequisite even though this slice does not run inference, because the installer-managed `OpenCode` route must not be considered valid if the selected local model target is already missing on disk.

### 6. Managed config generation

Generate `config/opencode/managed-config.json` from installer-owned truth.

If config generation fails:

- stop the phase
- set `opencode_verification_status = failed`
- report `failing_step = opencode-config`

### 7. Isolated process start

Create a temporary empty verification working directory and start `OpenCode` using:

- the manifest-defined executable
- the manifest-defined verification arguments
- the verifier-appended trailing provider argument `local-lacc`
- `OPENCODE_CONFIG`
- `OPENCODE_CONFIG_CONTENT`
- any manifest-defined extra environment values
- stdout and stderr redirected to `logs/opencode-verification.log`

The subprocess `cwd` for verification is always the temporary empty verification directory, never the current repository and never an inferred user project directory.

This is a single bounded verification subprocess. There is no separate long-lived `OpenCode` daemon process in this slice and no second handshake subprocess. The same command both starts and performs the routing handshake.

Process start is not considered successful only because `Popen(...)` returned. The verifier must still confirm the process stays alive long enough to produce the handshake result and exits cleanly within the allowed timeout.

### 8. Startup liveness check

During a bounded startup window:

- poll whether the process is still alive
- fail early if it exits before handshake checks can complete successfully
- fail if it hangs beyond the bounded verification timeout and cannot be stopped cleanly

If it dies early:

- `opencode_process_status = failed`
- `opencode_connection_status = skipped`
- `opencode_verification_status = failed`
- `failing_step = opencode-process-start`

### 9. Connection and routing handshake

This slice does not yet perform prompt inference. Instead, it proves routing truth.

The handshake contract must be explicit and fixed enough for implementation planning.

The installer-managed config should create exactly one allowed local provider entry:

- provider id: `local-lacc`
- provider implementation package: `@ai-sdk/openai-compatible`
- `options.baseURL = <verified_server_url>/v1`
- `models` containing exactly the active installer-managed model id
- top-level `model = local-lacc/<active-model-id>`

The preferred verification command is:

- `opencode --pure models local-lacc`

Run it under the isolated installer-managed environment with:

- `OPENCODE_CONFIG` pointing at `managed-config.json`
- `OPENCODE_CONFIG_CONTENT` carrying any required runtime override content
- `OPENCODE_DISABLE_MODELS_FETCH=true`
- installer-managed disable-autoupdate behavior

Accepted handshake proof for `opencode_connection_status = ready`:

- the same bounded verification subprocess from Step 7 exits with code `0`
- stdout contains the exact token `local-lacc/<active-model-id>`
- the verifier has already validated that the generated managed config contains `options.baseURL = <verified_server_url>/v1`

This proof comes from the isolated installer-managed launch context, not from a global shell environment or user profile.

If routing cannot be proven:

- `opencode_process_status = ready`
- `opencode_connection_status = failed`
- `opencode_verification_status = failed`
- `failing_step = opencode-connection`

### 10. Verified ready state

`OpenCode` verification is successful only if all of the following are true:

- the pinned artifact is present and valid
- prerequisites were present
- the process started and remained alive
- the installer-managed config was accepted
- the isolated handshake proved the expected local provider and active model routing

Only then:

- `opencode_artifact_status = ready`
- `opencode_process_status = ready`
- `opencode_connection_status = ready`
- `opencode_verification_status = ready`

### 11. Clean stop

The preferred verification command is bounded and should normally exit on its own after printing the handshake result.

After either success or failure, attempt cleanup only if the verification process is still running.

For this slice:

- first wait for bounded natural exit
- if still running, attempt a normal terminate path
- wait a bounded amount of time
- if needed, force kill once to avoid leaving an orphaned verifier process

Cleanup truth:

- if cleanup is the first failure after all prior verification gates passed, `failing_step = opencode-process-stop`
- if an earlier verification step already failed, preserve that earlier `failing_step`
- still record cleanup failure details in diagnostics and human log output

If the process cannot be stopped cleanly after an otherwise successful handshake:

- `opencode_verification_status = failed`
- `failing_step = opencode-process-stop`

The installer must not leave a successful verification process running in the background and still claim ready.

## Status Model

Extend the installer session with `OpenCode` bootstrap and verification truth instead of replacing server-verification truth.

### Additional session fields

- `opencode_artifact_status`
  - `ready`
  - `failed`
  - `skipped`

- `opencode_verification_status`
  - `ready`
  - `failed`
  - `skipped`

- `opencode_process_status`
  - `ready`
  - `failed`
  - `skipped`

- `opencode_connection_status`
  - `ready`
  - `failed`
  - `skipped`

- `opencode_artifact_id`
- `opencode_artifact_path`
- `opencode_metadata_path`
- `opencode_config_path`
- `verified_opencode_command`
- `opencode_log_path`

### Product installation truth

Keep:

- `product_installation_status = incomplete`

Reason:

- this slice proves installer-managed `OpenCode` bootstrap and routing handshake only
- it does not yet prove a first real inference pass
- the product requirements still expect a first-run test before final completion can be claimed

## Failure Rules

Failure handling should remain strict and truthful.

### Server verification not ready

If server verification was not ready:

- do not start `OpenCode` work
- set:
  - `opencode_artifact_status = skipped`
  - `opencode_verification_status = skipped`
  - `opencode_process_status = skipped`
  - `opencode_connection_status = skipped`

### User did not select OpenCode

If `install_opencode == false`:

- do not install or verify `OpenCode`
- set all `OpenCode` statuses to `skipped`
- leave `product_installation_status = incomplete`

### Manifest failure

If the packaged `OpenCode` manifest is invalid:

- `opencode_artifact_status = failed`
- `opencode_verification_status = failed`
- `opencode_process_status = skipped`
- `opencode_connection_status = skipped`
- `failing_step = opencode-manifest`

### Artifact failure

If download, checksum, extraction, metadata write, or required-file validation fails:

- `opencode_artifact_status = failed`
- `opencode_verification_status = failed`
- `opencode_process_status = skipped`
- `opencode_connection_status = skipped`
- `failing_step = opencode-artifact`

### Config failure

If installer-managed config cannot be generated from verified local state:

- `opencode_artifact_status = ready`
- `opencode_verification_status = failed`
- `opencode_process_status = skipped`
- `opencode_connection_status = skipped`
- `failing_step = opencode-config`

### Verification prerequisite failure

If the executable, verified server URL, active model config, active model path, or model file is missing or unreadable:

- `opencode_artifact_status = ready`
- `opencode_verification_status = failed`
- `opencode_process_status = skipped`
- `opencode_connection_status = skipped`
- `failing_step = opencode-verification-prerequisites`

### Process start failure

If subprocess start raises or the process exits before handshake checks complete:

- `opencode_artifact_status = ready`
- `opencode_process_status = failed`
- `opencode_connection_status = skipped`
- `opencode_verification_status = failed`
- `failing_step = opencode-process-start`

### Connection failure

If the process is alive but installer-managed routing truth cannot be proven:

- `opencode_artifact_status = ready`
- `opencode_process_status = ready`
- `opencode_connection_status = failed`
- `opencode_verification_status = failed`
- `failing_step = opencode-connection`

### Stop failure

If handshake succeeded but cleanup stop fails:

- `opencode_artifact_status = ready`
- `opencode_process_status = ready`
- `opencode_connection_status = ready`
- `opencode_verification_status = failed`
- `failing_step = opencode-process-stop`

If verification already failed earlier and cleanup also fails:

- keep the earlier verification `failing_step`
- preserve cleanup failure details in diagnostics without changing the primary failure step

## Module Layout

Keep the extension focused and aligned with the existing installer architecture.

### Existing modules to extend

- `src/local_ai_control_center_installer/session.py`
  - add `OpenCode` session and reporting fields

- `src/local_ai_control_center_installer/reporting.py`
  - include `OpenCode` artifact and verification outcomes in human log and JSON report

- `src/local_ai_control_center_installer/defaults.py`
  - provide the real filesystem, subprocess, and environment-backed default adapters

- `src/local_ai_control_center_installer/main.py`
  - run `OpenCode` bootstrap and verification after server verification and before reporting
  - include `OpenCode` verification in the CLI exit gate

### New modules

- `src/local_ai_control_center_installer/opencode_bootstrap.py`
  - manifest load
  - artifact readiness
  - download, extract, stage, promote
  - metadata write and validation
  - managed config generation

- `src/local_ai_control_center_installer/opencode_verification.py`
  - prerequisite resolution
  - isolated launch construction
  - process liveness checks
  - routing handshake
  - clean shutdown
  - status transitions

This split keeps artifact bootstrap and live verification separate, which matches the existing runtime/server division and reduces test coupling.

## Reporting

Human log and JSON report should clearly expose:

- `OpenCode` artifact status
- `OpenCode` verification status
- `OpenCode` process status
- `OpenCode` connection status
- pinned `OpenCode` artifact id
- `OpenCode` artifact path
- `OpenCode` metadata path
- managed config path
- resolved verification command
- `OpenCode` verification log path
- failing step when `OpenCode` work fails

The reporting layer should remain truthful even when:

- artifact validation fails before launch
- config generation fails
- startup fails immediately
- routing proof fails while the process stays alive
- cleanup stop fails after a good handshake

## CLI Exit Truth

The top-level CLI should return success only when all of the following are true:

- `bootstrap_status == ready`
- `runtime_payload_status == ready`
- `server_verification_status == ready`
- `opencode_verification_status == ready`

This means:

- the current implementation milestone is complete
- the installer can truthfully claim verified local `OpenCode` integration against the active runtime

This does not yet mean:

- `product_installation_status == complete`
- full product ready

The report and README must continue to distinguish milestone success from final product completion.

### Timeout ownership

This spec requires bounded verification and bounded cleanup, but the exact timeout values remain implementation constants to be chosen during planning and codified in tests. The required behavior is:

- verification may not wait indefinitely
- cleanup may not wait indefinitely
- timeout expiry must map to the documented failure rules

## Testing Strategy

Use TDD and keep the `OpenCode` logic decomposed into small, injectable units.

### Test focus

#### Artifact and manifest

- fail when packaged `OpenCode` manifest is invalid
- reuse a ready artifact when metadata, required files, and pinned file checksums match
- redownload when the artifact metadata is missing or mismatched
- fail when required files or file checksums do not match the manifest

#### Prerequisites

- skip when server verification is not ready
- skip when `install_opencode == false`
- fail when `active-model.json` is missing
- fail when `verified_server_url` is missing
- fail when the `OpenCode` executable from the launch contract is missing

#### Config generation and isolation

- fail when installer-managed config cannot be written
- verification launch injects installer-managed config env correctly
- verification launch uses an isolated working directory rather than the current project
- verification launch includes the isolation arguments required by the manifest contract
- verification launch uses `OPENCODE_CONFIG` and `OPENCODE_CONFIG_CONTENT` as the fixed env names for this slice
- verification launch disables remote models fetch during the handshake
- generated config contains `local-lacc` as the only enabled provider and `<verified_server_url>/v1` as the configured base URL

#### Process behavior

- fail when subprocess start raises
- fail when the process exits before handshake completes
- the only accepted handshake command shape for this slice is `opencode --pure models local-lacc`
- fail when `opencode models local-lacc` output does not contain `local-lacc/<active-model-id>`
- fail when the verification process hangs and cannot be cleaned up

#### Success path

- success when the artifact is ready, config is generated, process starts, routing proof passes, and cleanup succeeds
- verification command and config path are recorded

#### Cleanup truth

- if stop fails after successful routing proof, final status becomes failed with `opencode-process-stop`
- if connection proof failed first and cleanup also fails, the earlier `failing_step` remains primary

#### Reporting and orchestration

- human log includes `OpenCode` fields
- JSON report includes `OpenCode` fields
- `main()` exit code now depends on `opencode_verification_status`

## Non-Goals For This Slice

The implementation must not claim more than it actually verifies.

Do not claim completion of:

- full end-user `OpenCode` usage
- first inference request correctness
- `TurboQuant`
- browser-integrated product flows
- final product installation completion

The correct outcome of this slice is:

- installer-managed `OpenCode` payload installed and validated
- installer-managed `OpenCode` process verified against the local runtime/model route

not:

- first-run user workflow fully validated
- full product ready

## Transition To Next Slice

Once this slice is complete, the next plan should extend the same session and reporting structures to:

- run a first real inference smoke through the verified `OpenCode` path
- promote `product_installation_status` from `incomplete` to complete only when that smoke succeeds
- optionally add `TurboQuant` as a separately reported non-core component
- close the final product-complete gate


