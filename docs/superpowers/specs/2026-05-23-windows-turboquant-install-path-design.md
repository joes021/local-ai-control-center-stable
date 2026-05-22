## Purpose

This slice closes the current Windows `TurboQuant` placeholder and replaces it with a real installer-managed packaged install path.

The goal is not to make `TurboQuant` a hard-fail core dependency. The goal is to make the installer truthfully capable of:

- detecting when the packaged Windows `TurboQuant` path is supported on the current machine
- downloading a pinned upstream Windows artifact when needed
- verifying and persisting that artifact like the other installer-managed payloads
- reporting a truthful `ready` or `failed` outcome with concrete reasons

## Scope

This slice adds:

- a manifest-pinned Windows `TurboQuant` artifact based on the upstream packaged release
- a real optional download-plan item for `TurboQuant`
- a durable install path under the install root
- metadata persistence and rerun readiness checks
- a supported-hardware gate for the packaged Windows CUDA path
- human log and JSON report fields for the installed `TurboQuant` artifact

This slice does not add:

- Linux `TurboQuant`
- a source build pipeline for `TurboQuant`
- promotion of `TurboQuant` to a hard-fail product gate
- switching the main runtime from the stable CPU `llama.cpp` payload to the CUDA `TurboQuant` payload

## Truth Contract

`TurboQuant` remains optional and non-hard-fail.

If `attempt_turboquant = false`:

- `turboquant_status = skipped`

If `attempt_turboquant = true` and core installer/runtime prerequisites are not ready:

- `turboquant_status = skipped`

If `attempt_turboquant = true` and the packaged Windows path is unsupported on the current machine:

- `turboquant_status = failed`
- `turboquant_error` must explain that the packaged path currently targets Windows x64 with a usable NVIDIA driver path

If `attempt_turboquant = true` and the packaged path is supported:

- the installer must use a manifest-backed download/install path
- `turboquant_status = ready` only after the artifact is present, checksum-verified, metadata-persisted, and the bundled DLL set can be loaded on the current machine

`TurboQuant` failure must never overwrite a stronger core failure and must never block `product_installation_status = complete` when all hard-fail core checks pass.

## Packaged Windows Strategy

The first complete Windows strategy is the upstream prebuilt release:

- upstream repository: `TheTom/llama-cpp-turboquant`
- packaged asset: `turboquant-plus-tqp-v0.1.1-windows-x64-cuda12.4.zip`

The installer-managed payload should live under:

- `tools/turboquant/windows-x64-cuda12.4`

The installer must persist:

- artifact id
- artifact root
- artifact metadata path
- primary executable path

## Supported Hardware Gate

The packaged strategy is considered eligible only when:

- platform is Windows
- architecture is x64/AMD64
- `nvidia-smi` is available from PATH or the standard NVIDIA NVSMI location
- `nvidia-smi` returns at least one GPU row successfully

If that gate fails, the installer must fail the optional `TurboQuant` phase with a concrete support message instead of pretending no packaged path exists.

## Readiness Checks

The installer-managed `TurboQuant` artifact is ready only when:

- required files exist under the packaged install root
- required file checksums match the pinned manifest
- `turboquant-artifact.json` matches the pinned source artifact sha
- the bundled DLL set can be loaded via Windows loader on the current machine

The readiness check is intentionally about packaged artifact integrity plus machine compatibility, not about replacing or re-verifying the already-stable core runtime route.

## Download Plan

If `TurboQuant` was requested and the packaged Windows strategy is supported, the single installer download queue must include a `TurboQuant` item when the artifact is not already ready.

If `TurboQuant` is unsupported on the current machine, the download plan should not invent a dead queue item.

## Modules

- add manifest: `src/local_ai_control_center_installer/manifests/windows-stable-turboquant.json`
- extend `download_plan.py` with optional `TurboQuant` queue support
- extend `session.py` with persisted `TurboQuant` artifact fields
- extend `reporting.py` with those fields
- replace the stub in `turboquant.py` with a manifest-backed Windows install flow

## Verification

Minimum verification for this slice:

- targeted `pytest` coverage for the new strategy, readiness, install, and reporting behavior
- full local `pytest` pass after integration
