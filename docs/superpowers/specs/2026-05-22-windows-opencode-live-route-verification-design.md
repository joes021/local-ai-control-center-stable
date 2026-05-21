# Windows OpenCode Live-Route Verification Design

Date: 2026-05-22

## Goal

Define the next Windows follow-up slice for `Local AI Control Center` after the first `OpenCode` bootstrap and verification milestone:

- strengthen `OpenCode` verification so success proves a live route to the verified local runtime
- introduce an installer-owned, marker-based inference smoke during `OpenCode` verification
- preserve truthful failure mapping and cleanup semantics
- fix `opencode_log_path` truth so reports do not point at logs that never existed
- update public milestone wording so README and reports describe `live-route verification` rather than a weaker config/process handshake

This follow-up intentionally strengthens the proof semantics of the existing `OpenCode` slice. It does not yet claim a full end-user `OpenCode` first-run experience.

## Scope

This design covers only the next Windows `OpenCode` truth-hardening milestone:

- keep the current bootstrap and pipeline order intact
- keep `OpenCode` verification inside the existing `opencode_verification.py` module
- start a temporary verifier-owned `llama-server` only for the `OpenCode` live-route proof
- place an installer-owned relay in front of that temporary runtime
- require a small installer-owned inference smoke that carries a unique marker
- mark verification successful only when the relay sees the marker and the upstream runtime returns success
- keep `product_installation_status` at `incomplete`
- fix persisted log-path truth for early `OpenCode` failure cases
- update README and report wording so milestone claims stay accurate

This design does not yet cover:

- a normal end-user `OpenCode` interactive session
- a broader first-run product smoke beyond the installer verifier
- `TurboQuant`
- browser or portal UX
- update flows or repair flows
- final product-complete status

## Truth Contract

The current `OpenCode` verifier proves too little. This follow-up changes the meaning of `OpenCode` success.

After this slice:

- `opencode_verification_status = "ready"` means the installer proved a live `OpenCode` route to the local runtime
- `opencode_connection_status = "ready"` means:
  - `OpenCode` sent a real inference request
  - the installer-owned relay saw the expected installer-only marker in that request
  - the relay successfully forwarded the request to the temporary local runtime
  - the upstream runtime returned a successful response

It is no longer enough that:

- `OPENCODE_CONFIG_CONTENT` points at the expected base URL
- `stdout` contains a model token that looks correct

Public wording should become more precise:

- use `installer-managed OpenCode live-route verification`
- do not describe this milestone as a completed end-user inference smoke

## Recommended Verification Strategy

Use a bounded three-part verifier during the existing `OpenCode` verification phase:

1. a temporary verifier-owned `llama-server`
2. an installer-owned relay that sits in front of that server
3. a bounded `OpenCode` inference smoke aimed at the relay

### Why this approach

- it gives a real server-side proof instead of a config-only or stdout-only proxy signal
- it does not require changing the earlier `server_verification` slice into a long-lived service
- it keeps the proof bounded and installer-owned
- it preserves the existing main pipeline while making `OpenCode` success meaningfully stronger

### Rejected alternatives

#### Stronger CLI handshake without server-side proof

Not recommended. A better token match or stricter output parsing still does not prove that `OpenCode` actually contacted the local runtime.

#### Reusing the earlier server-verification process as a long-lived service

Not recommended for this follow-up. That would widen scope by changing the lifecycle contract of the already completed `server_verification` slice.

#### Silent semantic downgrade

Not recommended. If the current proof is too weak, the right fix is to strengthen the proof, not merely soften the wording while leaving the same weak behavior in place.

## Live-Route Flow

The `OpenCode` verification phase should run in this order:

1. verify existing prerequisites already required for `OpenCode`
2. start a temporary verifier-owned `llama-server` on a loopback port
3. start an installer-owned relay on a separate loopback port
4. generate a unique installer-only marker for the verification attempt
5. keep the persisted installer-managed `OpenCode` config pointed at the already-persisted verified runtime URL
6. inject a verification-only config override that points `OpenCode` at the relay base URL
7. launch a bounded `OpenCode` process for a small non-interactive inference smoke
8. capture combined `stdout` and `stderr` into the `OpenCode` verification log
9. confirm that:
   - the relay saw the expected marker
   - the relay successfully obtained an upstream runtime response
10. stop `OpenCode`, the relay, and the temporary verifier runtime cleanly

Verification succeeds only if all proof conditions pass inside the same bounded run.

The persisted install-root managed config must remain stable and must keep the already-persisted runtime URL from the current installer state:

- `providers.local-lacc.options.baseURL = <verified_server_url>/v1`

The relay URL is verification-only state. It must not be written into the persisted install-root config because the relay is destroyed during cleanup.

## Relay Contract

The relay is installer-owned and exists only for the bounded verification attempt.

Its responsibilities are:

- listen on loopback only
- accept the `OpenCode` verification request
- inspect the request body for the expected installer-only marker
- forward the request to the temporary verifier-owned `llama-server`
- record:
  - whether the marker was seen
  - whether upstream responded successfully
  - any relay-side transport failure relevant to truthful failure mapping

For this slice, the relay contract is intentionally narrow:

- accept only `POST` requests to `/v1/chat/completions`
- require JSON request bodies
- search for the marker inside the request `messages` payload rather than arbitrary top-level fields
- forward the request to the temporary verifier runtime at its own `/v1/chat/completions` endpoint
- treat upstream success as:
  - HTTP `200`
  - a JSON response body that can be decoded
  - a response body that contains at least one assistant message/content payload
- reject or fail any unexpected extra verification-time request shape outside this bounded contract

The relay is not a reusable product component. It is only a verifier helper for this slice.

## Inference Smoke Contract

The `OpenCode` verification smoke must become a real bounded inference request.

Requirements:

- use a unique marker generated for the current run
- keep the request short and deterministic
- avoid broad prompt semantics or user-facing content
- aim only to prove route usage, not model quality

The verifier should freeze the smoke command contract to the current documented non-interactive CLI shape:

- `opencode --pure run --format json --model local-lacc/<active-model-id> "<prompt>"`

The verification launch environment must keep the earlier bounded-startup protections:

- keep `OPENCODE_DISABLE_MODELS_FETCH=true`
- do not allow manifest or other env overrides to replace that value during live-route verification
- do not allow the verifier run to broaden itself into additional model-discovery traffic beyond the single bounded smoke request

The prompt should contain the marker in a deterministic, exact-match form such as:

- `LACC_VERIFY_MARKER:<uuid>`

The marker should be placed in the user message text passed to `opencode run`, so the relay can detect it in the JSON request body under `messages`.

The smoke is successful only when:

- `OpenCode` exits successfully
- the relay saw the expected marker
- the upstream verifier runtime returned success

The smoke remains internal installer proof. It is not yet the public "first-run user smoke" milestone.

## Failure Truth

Keep the existing high-level `OpenCode` session fields:

- `opencode_verification_status`
- `opencode_process_status`
- `opencode_connection_status`

But strengthen `failing_step` truth for the new failure modes:

- `opencode-runtime-server-start`
- `opencode-relay-start`
- `opencode-inference-smoke`
- `opencode-live-route-proof`
- `opencode-process-stop`

Failure mapping guidance:

- prerequisite problems still map to `opencode-verification-prerequisites`
- failure to start the temporary verifier runtime maps to `opencode-runtime-server-start`
- failure to start the relay maps to `opencode-relay-start`
- `OpenCode` process launch or bounded inference execution failure maps to `opencode-inference-smoke`
- missing marker proof or failed upstream proof maps to `opencode-live-route-proof`
- cleanup failure after an otherwise successful proof maps to `opencode-process-stop`

Earlier primary failures must remain authoritative when cleanup also fails.

Truth table for the new failure modes:

| failing_step | opencode_verification_status | opencode_process_status | opencode_connection_status | Meaning |
|---|---|---|---|---|
| `opencode-verification-prerequisites` | `failed` | `skipped` | `skipped` | verifier could not start because owned prerequisites were not valid |
| `opencode-runtime-server-start` | `failed` | `skipped` | `skipped` | temporary verifier runtime never became available |
| `opencode-relay-start` | `failed` | `skipped` | `skipped` | relay never became available, so no `OpenCode` proof run happened |
| `opencode-inference-smoke` | `failed` | `failed` | `skipped` | `OpenCode` process did not complete the bounded smoke attempt before any live-route proof was established |
| `opencode-inference-smoke` with preserved partial proof | `failed` | `failed` | `ready` | `OpenCode` process ultimately failed, but the relay had already seen the marker and upstream had already returned success |
| `opencode-live-route-proof` after mixed partial smoke | `failed` | `failed` | `failed` | the relay saw the marker, but upstream runtime returned failure or an invalid response, so live-route proof failed even though part of the smoke path was reached |
| `opencode-live-route-proof` | `failed` | `ready` | `failed` | `OpenCode` ran, but live-route proof was missing or upstream proof failed |
| `opencode-process-stop` | `failed` | `ready` | `ready` | proof succeeded and only cleanup failed afterward |

The `ready/failed/skipped` combinations above are normative for planning, testing, and reporting.

Partial-smoke truth rule:

- if the `OpenCode` process ultimately fails the smoke step, but the relay already saw the marker and upstream already returned success, preserve that partial proof:
  - `opencode_verification_status = failed`
  - `opencode_process_status = failed`
  - `opencode_connection_status = ready`
- if the `OpenCode` process ultimately fails and the relay saw the marker, but upstream runtime failed or returned an invalid response:
  - `failing_step = opencode-live-route-proof`
  - `opencode_verification_status = failed`
  - `opencode_process_status = failed`
  - `opencode_connection_status = failed`
- if the smoke step fails before relay proof is established, `opencode_connection_status = skipped`

This rule preserves the strongest truthful signal available without promoting the overall verification to success.

## Log Truth

`opencode_log_path` must become stricter:

- do not persist a path merely because a run path was computed
- store `session.opencode_log_path` only when the log file actually exists
- if failure happens before log creation, session/report JSON/human log must use `null` or the equivalent absent value rather than a dead temp path
- if the log exists, keep the current persistence behavior into install-root logs

This truth rule matters most in early failures, where diagnostics must not point users to files that were never created.

## Module Shape

The main work should remain centered in:

- `src/local_ai_control_center_installer/opencode_verification.py`

Add small verifier-focused helpers there for:

- starting and stopping the temporary verifier runtime
- starting and stopping the relay
- generating the installer-only marker
- building the bounded inference smoke request
- collecting proof state from the relay
- managing log-path truth

Likely reporting updates remain narrow:

- `src/local_ai_control_center_installer/reporting.py`
- `README.md`

The main installer pipeline in `main.py` should not need a new phase. The stronger proof stays inside the current `OpenCode` verification phase.

The verification-only relay override should be built from `OPENCODE_CONFIG_CONTENT` at process launch time, not by mutating the persisted install-root managed config on disk.

## Public Wording Changes

README and reporting should describe the milestone more precisely:

- replace weaker wording about generic `OpenCode verification` against the runtime route
- use wording equivalent to `installer-managed OpenCode live-route verification`

At the same time, keep these truths explicit:

- this is not yet the full end-user first-run smoke
- `product_installation_status` remains `incomplete`
- `TurboQuant` remains out of scope

## Testing Expectations

The follow-up should use TDD and add focused coverage for:

- successful live-route proof when marker is seen and upstream succeeds
- failure when `OpenCode` runs but the relay never sees the marker
- failure when the relay sees the marker but upstream runtime response fails
- temporary verifier runtime start failure mapping
- relay start failure mapping
- cleanup truth after a successful proof
- early failure before log creation leaves `opencode_log_path` unset
- persisted reports do not claim a nonexistent `OpenCode` log
- README/report wording reflects `live-route verification`

## Acceptance Criteria

This follow-up is successful only if all of the following are true:

- `OpenCode` success now requires a real live-route proof, not only a config or stdout proxy signal
- the installer can truthfully claim installer-managed `OpenCode` live-route verification
- early failure reports no longer point at nonexistent `OpenCode` logs
- the bounded verifier still cleans up its temporary runtime and relay processes truthfully
- the README continues to separate this stronger verifier milestone from full product completion
