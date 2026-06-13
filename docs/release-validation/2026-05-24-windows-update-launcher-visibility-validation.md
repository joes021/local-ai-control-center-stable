# Windows Update Launcher Visibility Validation

Date: 2026-05-24
Branch: `codex/panel-integration`

## Scope

Validate the Windows patch that makes the auto-update installer window visible and interactive
after the panel finishes downloading a new release.

## Root cause

The update worker already downloaded the new installer and launched it, but `_launch_installer()`
started the frozen console installer with:

- `creationflags = CREATE_NEW_CONSOLE`
- `stdin = DEVNULL`
- `stdout = DEVNULL`
- `stderr = DEVNULL`

That combination let the installer run in the background while hiding the user-visible console
contract that the product depends on:

- progress output
- final success/failure message
- `Press Enter to close the installer window...`

On the affected machine this showed up exactly as:

- the panel said the installer launcher was started
- no visible installer window appeared to the user
- local installer logs still proved the installer had actually run

## Code change

Changed `_launch_installer()` in:

- `src/local_ai_control_center_installer/control_center_backend/services/updates_service.py`

so the installer still launches in a new console window, but no longer redirects its standard
streams to `DEVNULL`.

## Regression test

Added:

- `tests/test_control_center_updates.py`
  - `test_launch_installer_opens_visible_console_window`

The test locks the intended Windows behavior:

- installer is launched from its update folder
- install root prefill environment variables are still injected
- launcher does **not** pass `stdin`, `stdout`, or `stderr` overrides

## Verification

### Targeted update tests

Command:

```powershell
python -m pytest tests/test_control_center_updates.py -q
```

Result:

- `8 passed`

### Full test suite

Command:

```powershell
python -m pytest -q
```

Result:

- `414 passed`

### Packaging

Commands:

```powershell
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Result:

- `dist/LocalAIControlCenterSetup-v0.4.13.exe`
- `dist/local_ai_control_center_installer-0.4.13-py3-none-any.whl`
- `dist/local_ai_control_center_installer-0.4.13.tar.gz`

## Release readiness

Ready for a Windows patch release that fixes the invisible auto-update installer window by letting
the launched installer own its visible console session again.


