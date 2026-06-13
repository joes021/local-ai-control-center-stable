# Windows Installer/Runtime Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a truthful Windows installer/runtime completion milestone that supports all three starter-model prompt tiers, persists durable runtime/model configuration, exposes one planned sequential download queue, runs a real first-run `OpenCode` smoke, and promotes `product_installation_status` to `complete` only when the installer/runtime product really works.

**Architecture:** Split questionnaire/catalog truth, runtime configuration truth, download-queue truth, first-run smoke truth, and final gate truth into focused modules. Reuse the existing manifest-driven and injectable style so every phase stays testable, and keep the top-level pipeline thin by wiring explicit per-phase collaborators in `main.py`/`defaults.py`.

**Tech Stack:** Python 3.11, pytest, PowerShell launcher, packaged JSON manifests, subprocess-based runtime/OpenCode verification, streaming HTTP downloads via stdlib.

---

### Task 1: Shared Runtime Manifest Catalog And Prompt Truth

**Files:**
- Create: `src/local_ai_control_center_installer/runtime_manifest.py`
- Modify: `src/local_ai_control_center_installer/prompts.py`
- Modify: `src/local_ai_control_center_installer/runtime_bootstrap.py`
- Modify: `src/local_ai_control_center_installer/manifests/windows-stable-runtime.json`
- Test: `tests/test_runtime_manifest.py`
- Modify: `tests/test_prompts.py`
- Modify: `tests/test_runtime_bootstrap.py`

- [ ] **Step 1: Write failing runtime-manifest catalog tests**

```python
def test_load_runtime_manifest_exposes_three_prompt_visible_models():
    manifest = load_runtime_manifest()
    catalog = list_prompt_starter_models(manifest)
    assert [item.model_id for item in catalog] == [
        "recommended-6gb",
        "recommended-12gb",
        "recommended-24gb",
    ]
```

- [ ] **Step 2: Run the new manifest tests and confirm they fail**

Run: `python -m pytest tests/test_runtime_manifest.py -q`
Expected: FAIL because `runtime_manifest.py` does not exist and the packaged manifest still exposes only one starter model.

- [ ] **Step 3: Add `runtime_manifest.py` with shared catalog helpers**

```python
@dataclass(frozen=True)
class StarterModelOption:
    model_id: str
    prompt_label: str
    prompt_order: int
    recommended_default: bool
```

Include helpers for:
- loading the packaged runtime manifest
- validating starter-model prompt metadata
- listing prompt-visible starter models in order
- resolving execution-facing starter-model entries by `model_id`

- [ ] **Step 4: Expand the packaged Windows runtime manifest**

Add real entries for:
- `recommended-6gb`
- `recommended-12gb`
- `recommended-24gb`

Use pinned single-file Q4_K_M metadata from the approved spec:
- 7B revision `13fb94bfda8c8cf22497dc57b78f391a9acb426a`
- 14B revision `d0a692ef765eefbf2fabb130b3cb2e8917e3d225`
- 32B revision `9d3053fce650fe1cdbdb75998c2a87add9d178ef`

Each starter-model entry must also include:
- `prompt_order`
- `prompt_label`
- `recommended_default`
- `size_bytes`
- pinned digest / checksum field expected by the runtime manifest contract

- [ ] **Step 5: Make `prompts.py` render its starter-model menu from the shared manifest helpers**

```python
options = list_prompt_starter_models(load_runtime_manifest())
default_choice = determine_default_prompt_choice(options)
```

Remove the hard-coded `MODEL_CHOICES` source of truth.

- [ ] **Step 6: Add prompt-truth coverage for required `OpenCode` wording**

Write and satisfy a test that confirms the questionnaire clearly says `OpenCode` is required for a successful installation.

- [ ] **Step 7: Make `runtime_bootstrap.py` consume the shared manifest helpers**

Replace local starter-model validation/resolution with imports from `runtime_manifest.py`.

- [ ] **Step 8: Run focused prompt/runtime tests**

Run: `python -m pytest tests/test_runtime_manifest.py tests/test_prompts.py tests/test_runtime_bootstrap.py -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/local_ai_control_center_installer/runtime_manifest.py src/local_ai_control_center_installer/prompts.py src/local_ai_control_center_installer/runtime_bootstrap.py src/local_ai_control_center_installer/manifests/windows-stable-runtime.json tests/test_runtime_manifest.py tests/test_prompts.py tests/test_runtime_bootstrap.py
git commit -m "feat: add shared runtime model catalog"
```

### Task 2: Durable Runtime Configuration Persistence

**Files:**
- Modify: `src/local_ai_control_center_installer/session.py`
- Modify: `src/local_ai_control_center_installer/runtime_bootstrap.py`
- Modify: `src/local_ai_control_center_installer/reporting.py`
- Test: `tests/test_session.py`
- Modify: `tests/test_runtime_bootstrap.py`
- Modify: `tests/test_reporting.py`

- [ ] **Step 1: Write failing tests for persistent model-location and runtime-endpoint config**

```python
def test_apply_runtime_payload_writes_model_locations_and_runtime_endpoint_configs(tmp_path: Path):
    updated = apply_runtime_payload(...)
    assert updated.model_locations_config_status == "ready"
    assert updated.runtime_endpoint_config_status == "ready"
```

- [ ] **Step 2: Add failure-path tests for config persistence truth**

Cover:
- `model-locations.json` write failure
- `runtime-endpoint.json` write failure
- expected status downgrade
- expected `failing_step`

- [ ] **Step 3: Run the focused runtime/reporting tests and confirm they fail**

Run: `python -m pytest tests/test_runtime_bootstrap.py tests/test_session.py tests/test_reporting.py -q`
Expected: FAIL because the new statuses and config artifacts do not exist.

- [ ] **Step 4: Extend `InstallerSession` with durable config fields**

Add:
- `model_locations_config_status`
- `runtime_endpoint_config_status`
- `model_locations_config_path`
- `runtime_endpoint_config_path`
- `managed_runtime_port`

- [ ] **Step 5: Write runtime config helpers in `runtime_bootstrap.py`**

```python
def _write_model_locations_config(path: Path, *, default_model_root: Path, additional_paths: list[str]) -> Path:
    ...

def _write_runtime_endpoint_config(path: Path, *, port: int) -> Path:
    ...
```

Make `runtime_payload_status` stay non-ready until:
- active-model config is written
- model-locations config is written
- runtime-endpoint config is written

- [ ] **Step 6: Expose the new config fields in human log and JSON report**

Include both status fields and both persisted config paths.

- [ ] **Step 7: Run focused tests**

Run: `python -m pytest tests/test_runtime_bootstrap.py tests/test_session.py tests/test_reporting.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/local_ai_control_center_installer/session.py src/local_ai_control_center_installer/runtime_bootstrap.py src/local_ai_control_center_installer/reporting.py tests/test_session.py tests/test_runtime_bootstrap.py tests/test_reporting.py
git commit -m "feat: persist runtime configuration artifacts"
```

### Task 3: Global Download Plan And Streaming Progress

**Files:**
- Create: `src/local_ai_control_center_installer/download_plan.py`
- Modify: `src/local_ai_control_center_installer/downloads.py`
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `src/local_ai_control_center_installer/session.py`
- Modify: `src/local_ai_control_center_installer/runtime_bootstrap.py`
- Modify: `src/local_ai_control_center_installer/opencode_bootstrap.py`
- Test: `tests/test_download_plan.py`
- Modify: `tests/test_downloads.py`
- Modify: `tests/test_runtime_bootstrap.py`
- Modify: `tests/test_opencode_bootstrap.py`

- [ ] **Step 1: Write failing tests for a precomputed unified queue**

```python
def test_build_download_plan_lists_runtime_model_and_opencode_before_downloads():
    plan = build_download_plan(...)
    assert [item.label for item in plan.items] == [
        "llama.cpp runtime",
        "starter model recommended-12gb",
        "OpenCode",
    ]
```

- [ ] **Step 2: Run download-plan tests and confirm failure**

Run: `python -m pytest tests/test_download_plan.py tests/test_downloads.py -q`
Expected: FAIL because `download_plan.py` and streaming progress contracts do not exist.

- [ ] **Step 3: Add `download_plan.py` with a queue model**

```python
@dataclass(frozen=True)
class DownloadPlanItem:
    key: str
    label: str
    url: str
    destination_hint: str
    size_bytes: int | None
```

Build a full ordered queue before the first download starts.

- [ ] **Step 4: Make `defaults.py` own the single global queue truth and store it in `InstallerSession`**

Lock this design choice for the implementation:
- build the canonical `DownloadPlan` once in `defaults.py` before any installer-managed download starts
- persist that plan in `InstallerSession` as the only queue truth source
- make `main.py` and later phases consume that one canonical queue rather than recomputing local queue views

- [ ] **Step 5: Extend `downloads.py` with a streaming helper**

```python
def download_file(url: str, destination: Path, *, progress_callback=None, plan_item: DownloadPlanItem | None = None) -> Path:
    ...
```

Emit:
- current index
- total
- bytes downloaded
- total bytes
- ETA when enough data exists

- [ ] **Step 6: Thread the queue/progress contract through `defaults.py`, `main.py`, `session.py`, `runtime_bootstrap.py`, and `opencode_bootstrap.py`**

The default path should:
- build one global download plan
- create a terminal progress printer
- let runtime/OpenCode phases consume planned queue items truthfully

- [ ] **Step 7: Add regression tests for runtime/OpenCode queue labels and ordering**

Confirm queue truth still works when:
- `OpenCode` is skipped
- a starter model is already present
- a required artifact must be redownloaded

- [ ] **Step 8: Run focused tests**

Run: `python -m pytest tests/test_download_plan.py tests/test_downloads.py tests/test_runtime_bootstrap.py tests/test_opencode_bootstrap.py tests/test_main.py tests/test_session.py -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/local_ai_control_center_installer/download_plan.py src/local_ai_control_center_installer/downloads.py src/local_ai_control_center_installer/defaults.py src/local_ai_control_center_installer/main.py src/local_ai_control_center_installer/session.py src/local_ai_control_center_installer/runtime_bootstrap.py src/local_ai_control_center_installer/opencode_bootstrap.py tests/test_download_plan.py tests/test_downloads.py tests/test_runtime_bootstrap.py tests/test_opencode_bootstrap.py tests/test_main.py tests/test_session.py
git commit -m "feat: add unified download planning and progress"
```

### Task 4: Stable Managed Runtime Endpoint And Server Truth

**Files:**
- Modify: `src/local_ai_control_center_installer/server_verification.py`
- Modify: `src/local_ai_control_center_installer/runtime_bootstrap.py`
- Modify: `src/local_ai_control_center_installer/opencode_bootstrap.py`
- Modify: `src/local_ai_control_center_installer/session.py`
- Test: `tests/test_server_verification.py`
- Modify: `tests/test_runtime_bootstrap.py`
- Modify: `tests/test_opencode_bootstrap.py`

- [ ] **Step 1: Write failing tests for canonical managed port behavior**

```python
def test_server_verification_uses_persisted_managed_runtime_port(tmp_path: Path):
    updated = apply_server_verification(...)
    assert updated.verified_server_port == 39281
```

- [ ] **Step 2: Add a failing upgrade/rerun ownership test**

```python
def test_server_verification_fails_when_foreign_process_owns_managed_port():
    ...
```

- [ ] **Step 3: Add failing tests for same-owner managed port reuse/restart**

Cover both accepted behaviors from the spec:
- reuse same installer-managed runtime when safe
- clean stop/restart when installer chooses not to reuse

- [ ] **Step 4: Run focused server tests and confirm failure**

Run: `python -m pytest tests/test_server_verification.py tests/test_opencode_bootstrap.py -q`
Expected: FAIL because server verification still chooses a free ephemeral port and `OpenCode` config still bakes that URL.

- [ ] **Step 5: Replace free-port truth with managed-port truth**

Add helpers for:
- reading the persisted runtime-endpoint config
- determining whether the port is free
- determining whether the occupying process is the same installer-managed runtime from the same install root

- [ ] **Step 6: Make `opencode_bootstrap.py` generate managed config from the canonical runtime endpoint**

```python
base_url = load_runtime_endpoint_config(...).base_url
```

No managed `OpenCode` config should point at a one-off verification URL after this task.

- [ ] **Step 7: Run focused tests**

Run: `python -m pytest tests/test_server_verification.py tests/test_runtime_bootstrap.py tests/test_opencode_bootstrap.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/local_ai_control_center_installer/server_verification.py src/local_ai_control_center_installer/runtime_bootstrap.py src/local_ai_control_center_installer/opencode_bootstrap.py src/local_ai_control_center_installer/session.py tests/test_server_verification.py tests/test_runtime_bootstrap.py tests/test_opencode_bootstrap.py
git commit -m "feat: add canonical managed runtime endpoint"
```

### Task 5: First-Run OpenCode Smoke

**Files:**
- Create: `src/local_ai_control_center_installer/first_run_validation.py`
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `src/local_ai_control_center_installer/reporting.py`
- Modify: `src/local_ai_control_center_installer/session.py`
- Test: `tests/test_first_run_validation.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_reporting.py`

- [ ] **Step 1: Write failing tests for bounded first-run smoke**

```python
def test_apply_first_run_validation_marks_ready_after_real_opencode_response(tmp_path: Path):
    updated = apply_first_run_validation(...)
    assert updated.first_run_status == "ready"
```

- [ ] **Step 2: Add failure tests for prerequisites, foreign port ownership, process failure, empty assistant payload, and stop failure**

Also add same-owner managed-port rerun coverage for the first-run validator:
- reuse existing installer-managed runtime when safe
- controlled stop/restart when reuse is not chosen

Run: `python -m pytest tests/test_first_run_validation.py -q`
Expected: FAIL because `first_run_validation.py` does not exist.

- [ ] **Step 3: Implement a focused first-run validator**

```python
def apply_first_run_validation(session: InstallerSession, *, temp_root: Path, ...):
    ...
```

Use:
- persisted install-root `OpenCode` artifact
- persisted managed `OpenCode` config
- canonical managed runtime port
- bounded non-interactive `opencode --pure run --format json --model ...`

- [ ] **Step 4: Wire the new phase into defaults/main**

Keep `main.py` thin and injectable. Add the phase after `TurboQuant` and before the final product gate.

- [ ] **Step 5: Expose first-run fields in reporting**

Include:
- `first_run_status`
- `first_run_process_status`
- `first_run_connection_status`
- `first_run_log_path` if you introduce one

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_first_run_validation.py tests/test_main.py tests/test_reporting.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/local_ai_control_center_installer/first_run_validation.py src/local_ai_control_center_installer/defaults.py src/local_ai_control_center_installer/main.py src/local_ai_control_center_installer/reporting.py src/local_ai_control_center_installer/session.py tests/test_first_run_validation.py tests/test_main.py tests/test_reporting.py
git commit -m "feat: add first-run opencode validation"
```

### Task 6: TurboQuant Phase And Final Product Gate

**Files:**
- Create: `src/local_ai_control_center_installer/turboquant.py`
- Create: `src/local_ai_control_center_installer/product_gate.py`
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `src/local_ai_control_center_installer/reporting.py`
- Modify: `src/local_ai_control_center_installer/session.py`
- Test: `tests/test_turboquant.py`
- Test: `tests/test_product_gate.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_reporting.py`
- Modify: `tests/test_session.py`

- [ ] **Step 1: Write failing tests for non-blocking TurboQuant truth**

```python
def test_apply_turboquant_marks_failed_with_error_when_selected_but_no_windows_strategy_exists():
    updated = apply_turboquant(...)
    assert updated.turboquant_status == "failed"
    assert updated.turboquant_error is not None
```

- [ ] **Step 2: Write failing tests for final product gate**

```python
def test_apply_product_gate_marks_complete_only_when_all_required_statuses_are_ready():
    updated = apply_product_gate(...)
    assert updated.product_installation_status == "complete"
```

- [ ] **Step 3: Add failing negative gate tests from the spec**

Cover:
- `install_opencode = false` -> final failed
- missing `model_locations_config_status` -> final failed
- missing `runtime_endpoint_config_status` -> final failed
- `turboquant_status = failed` with all hard-fail statuses ready -> final complete
- `failing_step` remains `None` when `TurboQuant` is the only failure

- [ ] **Step 4: Run focused tests and confirm failure**

Run: `python -m pytest tests/test_turboquant.py tests/test_product_gate.py tests/test_main.py -q`
Expected: FAIL because the phase modules and gate do not exist.

- [ ] **Step 5: Implement `turboquant.py`**

Windows truth for this milestone:
- `skipped` when not selected
- `failed` with `turboquant_error` when selected and no packaged strategy exists
- never own `failing_step` by itself

- [ ] **Step 6: Implement `product_gate.py`**

```python
def apply_product_gate(session: InstallerSession) -> InstallerSession:
    ...
```

Promote `complete` only when:
- required component choices are accepted
- runtime/server/OpenCode/first-run statuses are ready
- required persisted config statuses are ready

- [ ] **Step 7: Change `main()` to return success only for final `complete`**

Do not key CLI success off intermediate milestone statuses anymore.

- [ ] **Step 8: Run focused tests**

Run: `python -m pytest tests/test_turboquant.py tests/test_product_gate.py tests/test_main.py tests/test_reporting.py tests/test_session.py -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/local_ai_control_center_installer/turboquant.py src/local_ai_control_center_installer/product_gate.py src/local_ai_control_center_installer/defaults.py src/local_ai_control_center_installer/main.py src/local_ai_control_center_installer/reporting.py src/local_ai_control_center_installer/session.py tests/test_turboquant.py tests/test_product_gate.py tests/test_main.py tests/test_reporting.py tests/test_session.py
git commit -m "feat: add final installer runtime completion gate"
```

### Task 7: Final Wiring, README Truth, And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `src/local_ai_control_center_installer/defaults.py`
- Modify: `src/local_ai_control_center_installer/main.py`
- Modify: `tests/test_package_smoke.py`

- [ ] **Step 1: Write failing README/package smoke expectations**

```python
def test_package_smoke_now_expects_complete_product_installation_status():
    ...
```

- [ ] **Step 2: Run final smoke tests and confirm failure**

Run: `python -m pytest tests/test_package_smoke.py -q`
Expected: FAIL until the package smoke reflects the new final gate.

- [ ] **Step 3: Update README truthfully**

State that this milestone now delivers:
- three starter-model tiers
- durable runtime/model configuration
- canonical managed runtime endpoint
- planned download queue and progress
- first-run `OpenCode` smoke
- completed installer/runtime gate

Keep non-goals explicit:
- portal/browser/update flows
- Linux parity
- real Windows TurboQuant installation if unsupported

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Inspect worktree state**

Run: `git status --short`
Expected: only known unrelated untracked artifacts plus the intended tracked changes before the final commit

- [ ] **Step 6: Commit**

```bash
git add README.md src/local_ai_control_center_installer/defaults.py src/local_ai_control_center_installer/main.py tests/test_package_smoke.py
git commit -m "docs: finalize installer runtime completion milestone"
```


