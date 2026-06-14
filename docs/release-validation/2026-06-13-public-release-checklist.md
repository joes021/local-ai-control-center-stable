# RuntimePilot Public Release Checklist

Date: 2026-06-13
Version target: `v0.4.93`
Installer target: `dist/RuntimePilotSetup-v0.4.93.exe`

## 1. Repo hardening

- [x] Release preflight added to the installer build flow.
- [x] Public documentation scrubbed of personal user paths and private machine references.
- [x] Fleet placeholder switched to reserved example address space (`192.0.2.0/24`).
- [x] Temporary screenshots, panel logs, and workspace artifacts ignored via `.gitignore`.

## 2. Build verification

- [x] `python -m local_ai_control_center_installer.release_preflight --repo-root . --scope installer --scope public`
- [x] `python -m pytest tests/test_release_preflight.py tests/test_control_center_fleet.py tests/test_control_center_frontend_dist.py -k "release_preflight or reserved_example_url_placeholder or fleet" -q`
- [x] `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`

## 3. Before public GitHub release

- [ ] Push branch and tag to GitHub.
- [ ] Confirm GitHub secret scanning and push protection are enabled on the repository.
- [ ] Review `git diff --stat` and installer asset names before publishing release notes.
- [ ] Upload `dist/RuntimePilotSetup-v0.4.93.exe` and `dist/RuntimePilotSetup-latest.exe` only after final smoke test.

## 4. Windows trust and antivirus reality

- [ ] Prefer Authenticode signing for the public `.exe`.
- [ ] If signing is not available yet, mention clearly in release notes that SmartScreen or antivirus may require manual confirmation.
- [ ] Avoid claiming the unsigned installer is "verified safe" by Microsoft; keep the wording honest.

## 5. Final smoke test on a clean machine

- [ ] Fresh install into default path.
- [ ] Launcher opens RuntimePilot portal automatically.
- [ ] Main portal loads, runtime can start, models page works, OpenCode launch path works.
- [ ] Installer/uninstaller shortcuts appear correctly.
- [ ] No personal paths appear in UI, logs, or packaged help text.
