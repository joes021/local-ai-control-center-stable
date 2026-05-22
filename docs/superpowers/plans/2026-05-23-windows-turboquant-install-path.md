## Goal

Implement a real Windows `TurboQuant` install path that stays optional but can finish `ready` on supported NVIDIA Windows machines.

## Task 1: Add failing tests

Touch:

- `tests/test_turboquant.py`
- `tests/test_download_plan.py`
- `tests/test_reporting.py`
- `tests/test_session.py`
- `tests/test_main.py` if session serialization expectations need to expand

Add coverage for:

- supported packaged Windows strategy resolution
- unsupported machine failure truth
- download-plan inclusion when requested and supported
- successful install with metadata persistence
- reporting/session serialization of `TurboQuant` artifact fields

Run:

```powershell
python -m pytest tests/test_turboquant.py tests/test_download_plan.py tests/test_reporting.py tests/test_session.py tests/test_main.py -q
```

## Task 2: Add packaged manifest

Create:

- `src/local_ai_control_center_installer/manifests/windows-stable-turboquant.json`

Include:

- pinned upstream release URL
- archive sha256
- required files
- required file sha256 map
- install subdir
- launch executable

## Task 3: Implement TurboQuant installer flow

Touch:

- `src/local_ai_control_center_installer/turboquant.py`

Add:

- manifest loader and validation
- supported Windows strategy detection
- packaged artifact readiness checks
- staged download/extract/promote flow
- metadata persistence
- bounded DLL-load smoke

## Task 4: Wire queue, session, and reports

Touch:

- `src/local_ai_control_center_installer/download_plan.py`
- `src/local_ai_control_center_installer/session.py`
- `src/local_ai_control_center_installer/reporting.py`
- `README.md`

Add:

- optional `TurboQuant` download plan item
- persisted `TurboQuant` artifact fields
- truthful human log and JSON report fields
- updated README claim that Windows now has a packaged `TurboQuant` path

## Task 5: Verify

Run targeted tests, then full suite:

```powershell
python -m pytest tests/test_turboquant.py tests/test_download_plan.py tests/test_reporting.py tests/test_session.py tests/test_main.py -q
python -m pytest -q
```
