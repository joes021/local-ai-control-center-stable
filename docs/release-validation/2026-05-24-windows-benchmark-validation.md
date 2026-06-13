# Windows Benchmark Validation

Date: 2026-05-24
Branch: `codex/panel-integration`

## Scope

This validation closes the Benchmark restoration slice for the Windows control panel:

- installer-managed benchmark backend service
- `/api/benchmark` route family
- live `/slots` throughput signal
- benchmark batteries and run-state lifecycle
- restored `Benchmark` tab in the shipped frontend bundle

## Automated Evidence

### Targeted benchmark + frontend tests

Command:

```powershell
python -m pytest tests\test_control_center_benchmark.py tests\test_control_center_benchmark_routes.py tests\test_control_center_frontend_dist.py -q
```

Result:

- `27 passed`

### Full test suite

Command:

```powershell
python -m pytest -q
```

Result:

- `424 passed`

## Live Runtime Smoke

Using the current repo code against the live installer-managed runtime rooted at:

- `C:\Users\<user>\AppData\Local\Temp\lacc-rc-fresh-v0.4.5`

Observed:

- `load_benchmark_summary()` initially returned an idle payload while runtime was not actively serving tokens
- `start_selected_benchmark("short")` returned `accepted`
- run state moved through `queued -> running -> done`
- resulting metric history contained:
  - `promptTokensPerSecond`
  - `completionTokensPerSecond`
  - `totalTokensPerSecond`
- saved benchmark run history persisted the completed run entry

Representative live metric from the smoke:

- `promptTokensPerSecond = 16.35`
- `completionTokensPerSecond = 45.8`
- `totalTokensPerSecond = 37.7`

## Frontend Packaging Evidence

Frontend build completed successfully and produced:

- `frontend/dist/assets/index-D-B3OytC.js`
- `frontend/dist/assets/index-BaoNoy93.css`

These assets were copied into:

- `src/local_ai_control_center_installer/control_center_backend/frontend_dist/`

The packaged frontend now contains:

- `Benchmark` navigation entry
- `LIVE THROUGHPUT` section

## Release Readiness Conclusion

The Windows control panel now truthfully ships Benchmark as part of the public product:

- current throughput
- average throughput
- historical trend graph
- benchmark scenarios and batteries
- benchmark run history

Known honest limit:

- live throughput remains naturally idle when the runtime is not actively processing requests; the panel does not fake non-zero token rates.


