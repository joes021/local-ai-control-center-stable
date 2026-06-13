# RuntimePilot v0.4.92 Release Checklist

Date: 2026-06-13
Version target: `v0.4.92`
Installer target: `dist/RuntimePilotSetup-v0.4.92.exe`

## 1. Repo hardening

- [x] Public repo history sanitized and force-pushed.
- [x] README screenshots refreshed to current RuntimePilot UI.
- [x] Stale root release notes and old checksum clutter removed from the public root.
- [x] Public release preflight remains wired into the installer build flow.

## 2. Build verification

- [x] `python -m local_ai_control_center_installer.release_preflight --repo-root . --scope installer --scope public`
- [x] `python -m pytest tests/test_release_preflight.py tests/test_control_center_fleet.py tests/test_control_center_frontend_dist.py tests/test_control_center_status.py tests/test_windows_packaging.py -k "release_preflight or reserved_example_url_placeholder or fleet or status_route_prefers_running_source_version or windows_packaging" -q`
- [x] `python -m build`
- [x] `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`

## 3. Before GitHub release

- [ ] Push release commit and tag to GitHub.
- [ ] Review `git diff --stat` and final asset names before publish.
- [ ] Generate `dist/release-notes-v0.4.92.md`.
- [ ] Confirm `dist/SHA256SUMS-v0.4.92.txt` contains installer, latest alias, wheel, and sdist hashes.

## 4. Windows trust and antivirus reality

- [ ] Keep release notes honest that the `.exe` is unsigned and may trigger SmartScreen or antivirus warnings.
- [ ] Keep Avast guidance limited to installer-folder exception advice, not blanket antivirus disablement.

## 5. Final smoke test

- [ ] Launch `RuntimePilotSetup-v0.4.92.exe`.
- [ ] Confirm startup launcher opens portal automatically.
- [ ] Confirm portal `/api/status` reports `0.4.92`.
- [ ] Confirm Home, Models, and OpenCode entry flow still work.
- [ ] Confirm no personal paths appear in packaged release notes, checksums, or public README.
