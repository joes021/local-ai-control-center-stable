# Windows Server Verification Design

Date: 2026-05-21

## Goal

Define the next Windows delivery slice for `Local AI Control Center` after runtime payload preparation:

- start `llama.cpp` server against the active model
- verify the server stays alive long enough to bind and answer health
- record truthful server verification status
- stop the verification process cleanly after the check completes

This slice is intentionally limited to `llama.cpp` runnable-server verification. It does not yet claim that the full product is complete.

## Scope

This design covers only the next Windows server-verification milestone:

- run server verification only after runtime payload is `ready`
- load the active model from installer-managed configuration
- locate `llama-server.exe` from the verified runtime payload
- start `llama-server` on a local verification port
- confirm the process remains alive during startup
- poll a local health endpoint until it responds or times out
- stop the verification process cleanly
- extend human log and JSON report with server verification truth

This design does not yet cover:

- `OpenCode` installation or verification
- `TurboQuant`
- portal UI controls
- repeated lifecycle actions such as restart or reopen
- inference smoke prompts
- final product-complete status

## Product Positioning

The repository goal remains:

- stable core first
- shell second

The server-verification slice should therefore optimize for:

- truthful runnable-server evidence
- clear prerequisite boundaries
- deterministic local verification behavior
- clean extension points for later `OpenCode` and full first-run validation

## Recommended Verification Strategy

Use a narrow subprocess-based verification pass:

- start `llama-server`
- confirm process liveness
- confirm local HTTP health
- stop the process

### Why this approach

- it proves more than on-disk payload readiness
- it isolates server failures from later `OpenCode` integration problems
- it gives the first honest `works / does not work` signal for the local runtime core
- it keeps failure mapping narrow and supportable

### Rejected alternatives

#### Health plus inference request

Stronger proof, but too broad for the next slice. It adds prompt formatting, warmup variance, and model-response timing concerns that are better handled after basic server readiness is proven.

#### Full lifecycle controller

Start/stop/reopen/PID-tracking infrastructure is useful later for the portal, but too large for this milestone. The immediate need is truthful server verification, not a full runtime manager.

## Verification Flow

The server-verification phase should follow this order.

### 1. Runtime gate

The phase starts only if:

- `bootstrap_status == ready`
- `runtime_payload_status == ready`

If runtime payload is not ready, server verification is skipped entirely.

### 2. Verification prerequisites

Before starting a process, verify all required inputs exist:

- `active-model.json`
- resolved active model path from that file
- model file present on disk
- `llama-server.exe` present in the verified runtime location

If any prerequisite is missing or unreadable:

- stop the server-verification phase
- set server verification statuses truthfully
- report `failing_step = server-verification-prerequisites`

### 3. Port selection

Choose a local verification port for this run.

The design should prefer:

- a deterministic installer-owned local port selection helper
- loopback-only behavior
- explicit reporting of the chosen port and resulting base URL

Recommended verified URL shape:

- `http://127.0.0.1:<port>`

### 4. Process start

Start `llama-server` as a subprocess with:

- the resolved model path
- the chosen port
- stdout/stderr redirected to a server verification log file

Process start is not considered successful merely because `subprocess.Popen(...)` returned. The verifier must still confirm the process remains alive through the startup window.

### 5. Startup liveness check

For a bounded startup window:

- poll whether the process is still alive
- fail early if the process exits before health becomes ready

If the process fails to stay alive long enough to complete startup:

- `server_process_status = failed`
- `server_health_status = skipped`
- `server_verification_status = failed`
- `failing_step = server-process-start`

### 6. Health polling

While the process is alive, poll a local health endpoint until:

- it responds successfully, or
- a timeout is reached

If health never responds but the process remained alive:

- `server_process_status = ready`
- `server_health_status = failed`
- `server_verification_status = failed`
- `failing_step = server-health`

If the process dies during health polling:

- treat this as startup/process failure rather than success
- keep failure truth tied to the earliest failed verification step

### 7. Verified ready state

Server verification is successful only if all of the following are true:

- prerequisites were present
- the process started and remained alive
- the local verification port was usable
- health responded successfully

Only then:

- `server_process_status = ready`
- `server_health_status = ready`
- `server_verification_status = ready`

### 8. Clean stop

After either success or failure, attempt a clean stop of the verification process if it was started.

If verification itself succeeded but the process could not be stopped cleanly:

- `server_verification_status = failed`
- report `failing_step = server-process-stop`

The installer must not leave a successful verification process orphaned in the background and still claim ready.

## Status Model

Extend the installer session with server-verification state instead of replacing existing bootstrap or runtime truth.

### Additional session fields

- `server_verification_status`
  - `ready`
  - `failed`
  - `skipped`

- `server_process_status`
  - `ready`
  - `failed`
  - `skipped`

- `server_health_status`
  - `ready`
  - `failed`
  - `skipped`

- `verified_server_port`
- `verified_server_url`
- `server_log_path`

### Product installation truth

Keep:

- `product_installation_status = incomplete`

Reason:

- this slice proves `llama.cpp` server readiness only
- it does not yet prove `OpenCode`
- it does not yet prove full first-run product behavior

## Failure Rules

Failure handling should remain strict and truthful.

### Runtime payload not ready

If runtime payload was not ready:

- do not start server verification
- set:
  - `server_verification_status = skipped`
  - `server_process_status = skipped`
  - `server_health_status = skipped`

### Prerequisite failure

If active model config, model path, model file, or `llama-server.exe` is missing or unreadable:

- `server_process_status = skipped`
- `server_health_status = skipped`
- `server_verification_status = failed`
- `failing_step = server-verification-prerequisites`

### Port failure

If a verification port cannot be selected or used:

- `server_process_status = failed`
- `server_health_status = skipped`
- `server_verification_status = failed`
- `failing_step = server-port-bind`

### Process start failure

If subprocess start fails or exits before healthy startup:

- `server_process_status = failed`
- `server_health_status = skipped`
- `server_verification_status = failed`
- `failing_step = server-process-start`

### Health failure

If the process is alive but health does not respond in time:

- `server_process_status = ready`
- `server_health_status = failed`
- `server_verification_status = failed`
- `failing_step = server-health`

### Stop failure

If verification succeeded but cleanup stop fails:

- `server_process_status = ready`
- `server_health_status = ready`
- `server_verification_status = failed`
- `failing_step = server-process-stop`

## Module Layout

Keep the extension focused and aligned with the existing installer architecture.

### Existing modules to extend

- `src/local_ai_control_center_installer/session.py`
  - add server-verification fields

- `src/local_ai_control_center_installer/reporting.py`
  - include server-verification outcomes in human log and JSON report

- `src/local_ai_control_center_installer/defaults.py`
  - provide the real subprocess and HTTP-backed default adapter

- `src/local_ai_control_center_installer/main.py`
  - run server verification after runtime payload and before reporting
  - include server verification in the CLI exit gate

### New module

- `src/local_ai_control_center_installer/server_verification.py`
  - prerequisite resolution
  - port selection
  - subprocess startup
  - health polling
  - clean shutdown
  - status transitions

## Reporting

Human log and JSON report should clearly expose:

- server verification status
- server process status
- server health status
- verified local port
- verified local URL
- server verification log path
- failing step when server verification fails

The existing report model should remain truthful even when:

- subprocess startup fails
- the server dies before health responds
- health times out
- stop/cleanup fails

## CLI Exit Truth

The top-level CLI should return success only when all of the following are true:

- `bootstrap_status == ready`
- `runtime_payload_status == ready`
- `server_verification_status == ready`

This is the first slice where the installer can honestly claim runnable `llama.cpp` verification.

## Testing Strategy

Use TDD and keep the verification logic decomposed into small, injectable units.

### Test focus

#### Prerequisites

- skip when runtime payload is not ready
- fail when `active-model.json` is missing
- fail when the active model path is missing
- fail when `llama-server.exe` is missing

#### Process behavior

- fail when subprocess start raises
- fail when process exits before health becomes ready
- fail when health times out
- fail when chosen port cannot be used

#### Success path

- success when process starts, health responds, and stop succeeds
- verified URL and port are recorded

#### Cleanup truth

- if stop fails after successful health, final status becomes failed with `server-process-stop`

#### Reporting and orchestration

- human log includes server-verification fields
- JSON report includes server-verification fields
- `main()` exit code now depends on `server_verification_status`

## Non-Goals For This Slice

The implementation must not claim more than it actually verifies.

Do not claim completion of:

- `OpenCode` readiness
- `TurboQuant`
- full application installation
- full portal lifecycle controls
- inference correctness beyond health readiness

The correct outcome of this slice is:

- verified `llama.cpp` server start, health, and clean stop

not:

- full product ready

## Transition To Next Slice

Once this slice is complete, the next plan should extend the same session and reporting structures to:

- `OpenCode` installation and verification
- optional `TurboQuant`
- first-run inference smoke validation
- full product-complete gate
